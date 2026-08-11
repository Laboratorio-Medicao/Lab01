import io
import json
import urllib.error
from datetime import datetime, timedelta, timezone

import pytest

from src.client import GitHubGraphQLClient, GraphQLRequestError


class FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def rate_limit_payload(remaining=4999, cost=1, reset_at="2099-01-01T00:00:00Z"):
    return {"remaining": remaining, "cost": cost, "resetAt": reset_at}


def http_error(code, headers=None, body=b'{"message": "error"}'):
    return urllib.error.HTTPError(
        url="https://api.github.com/graphql",
        code=code,
        msg="error",
        hdrs=headers if headers is not None else {},
        fp=io.BytesIO(body),
    )


def test_execute_returns_data_on_success(monkeypatch):
    payload = {"data": {"rateLimit": rate_limit_payload(), "search": {"nodes": []}}}
    monkeypatch.setattr(
        "src.client.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(payload),
    )

    client = GitHubGraphQLClient(token="fake-token")

    data = client.execute("query { search { nodes } }")

    assert data["search"] == {"nodes": []}


def test_execute_raises_on_graphql_errors(monkeypatch):
    payload = {"errors": [{"message": "boom"}]}
    monkeypatch.setattr(
        "src.client.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(payload),
    )

    client = GitHubGraphQLClient(token="fake-token")

    with pytest.raises(GraphQLRequestError):
        client.execute("query { }")


def test_execute_retries_on_graphql_rate_limited_error_then_succeeds(monkeypatch):
    success_payload = {"data": {"rateLimit": rate_limit_payload(), "search": {}}}
    rate_limited_payload = {"errors": [{"type": "RATE_LIMITED", "message": "boom"}]}
    attempts = {"count": 0}

    def fake_urlopen(request, timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return FakeResponse(rate_limited_payload)
        return FakeResponse(success_payload)

    monkeypatch.setattr("src.client.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("src.http_retry.time.sleep", lambda seconds: None)

    client = GitHubGraphQLClient(token="fake-token", max_attempts=3)
    data = client.execute("query { }")

    assert attempts["count"] == 2
    assert data["search"] == {}


def test_execute_gives_up_after_max_attempts_on_graphql_rate_limited_error(monkeypatch):
    payload = {"errors": [{"type": "RATE_LIMITED", "message": "boom"}]}
    monkeypatch.setattr(
        "src.client.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(payload),
    )
    monkeypatch.setattr("src.http_retry.time.sleep", lambda seconds: None)

    client = GitHubGraphQLClient(token="fake-token", max_attempts=3)

    with pytest.raises(GraphQLRequestError) as excinfo:
        client.execute("query { }")

    assert excinfo.value.retryable is True


def test_execute_raises_on_missing_data_field(monkeypatch):
    monkeypatch.setattr(
        "src.client.urllib.request.urlopen",
        lambda request, timeout: FakeResponse({}),
    )

    client = GitHubGraphQLClient(token="fake-token")

    with pytest.raises(GraphQLRequestError):
        client.execute("query { }")


def test_execute_sleeps_until_reset_when_rate_limit_low(monkeypatch):
    reset_at = (datetime.now(timezone.utc) + timedelta(seconds=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    payload = {
        "data": {"rateLimit": rate_limit_payload(remaining=1, reset_at=reset_at), "search": {}}
    }
    monkeypatch.setattr(
        "src.client.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(payload),
    )
    sleep_calls = []
    monkeypatch.setattr("src.client.time.sleep", lambda seconds: sleep_calls.append(seconds))

    client = GitHubGraphQLClient(token="fake-token", rate_limit_threshold=100)
    client.execute("query { }")

    assert len(sleep_calls) == 1
    assert sleep_calls[0] > 0


def test_execute_does_not_sleep_when_rate_limit_healthy(monkeypatch):
    payload = {"data": {"rateLimit": rate_limit_payload(remaining=4999), "search": {}}}
    monkeypatch.setattr(
        "src.client.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(payload),
    )
    sleep_calls = []
    monkeypatch.setattr("src.client.time.sleep", lambda seconds: sleep_calls.append(seconds))

    client = GitHubGraphQLClient(token="fake-token", rate_limit_threshold=100)
    client.execute("query { }")

    assert sleep_calls == []


def test_execute_retries_on_server_error_then_succeeds(monkeypatch):
    payload = {"data": {"rateLimit": rate_limit_payload(), "search": {}}}
    attempts = {"count": 0}

    def fake_urlopen(request, timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise http_error(503)
        return FakeResponse(payload)

    monkeypatch.setattr("src.client.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("src.http_retry.time.sleep", lambda seconds: None)

    client = GitHubGraphQLClient(token="fake-token", max_attempts=3)
    data = client.execute("query { }")

    assert attempts["count"] == 2
    assert data["search"] == {}


def test_execute_retries_using_retry_after_header(monkeypatch):
    payload = {"data": {"rateLimit": rate_limit_payload(), "search": {}}}
    attempts = {"count": 0}

    def fake_urlopen(request, timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise http_error(403, headers={"Retry-After": "12"})
        return FakeResponse(payload)

    monkeypatch.setattr("src.client.urllib.request.urlopen", fake_urlopen)
    sleep_calls = []
    monkeypatch.setattr("src.http_retry.time.sleep", lambda seconds: sleep_calls.append(seconds))

    client = GitHubGraphQLClient(token="fake-token", max_attempts=3)
    client.execute("query { }")

    assert sleep_calls[0] == 12.0


def test_execute_does_not_retry_on_permission_denied_403(monkeypatch):
    def fake_urlopen(request, timeout):
        raise http_error(403)

    monkeypatch.setattr("src.client.urllib.request.urlopen", fake_urlopen)

    client = GitHubGraphQLClient(token="fake-token", max_attempts=3)

    with pytest.raises(GraphQLRequestError):
        client.execute("query { }")


def test_execute_does_not_retry_on_unauthorized(monkeypatch):
    attempts = {"count": 0}

    def fake_urlopen(request, timeout):
        attempts["count"] += 1
        raise http_error(401)

    monkeypatch.setattr("src.client.urllib.request.urlopen", fake_urlopen)

    client = GitHubGraphQLClient(token="fake-token", max_attempts=3)

    with pytest.raises(GraphQLRequestError):
        client.execute("query { }")

    assert attempts["count"] == 1


def test_execute_gives_up_after_max_attempts(monkeypatch):
    attempts = {"count": 0}

    def fake_urlopen(request, timeout):
        attempts["count"] += 1
        raise http_error(503)

    monkeypatch.setattr("src.client.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("src.http_retry.time.sleep", lambda seconds: None)

    client = GitHubGraphQLClient(token="fake-token", max_attempts=3)

    with pytest.raises(GraphQLRequestError) as excinfo:
        client.execute("query { }")

    assert attempts["count"] == 3
    assert excinfo.value.retryable is True


def test_execute_raises_non_retryable_error_on_graphql_errors(monkeypatch):
    payload = {"errors": [{"message": "boom"}]}
    monkeypatch.setattr(
        "src.client.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(payload),
    )

    client = GitHubGraphQLClient(token="fake-token")

    with pytest.raises(GraphQLRequestError) as excinfo:
        client.execute("query { }")

    assert excinfo.value.retryable is False


def test_execute_raises_non_retryable_error_on_permission_denied_403(monkeypatch):
    def fake_urlopen(request, timeout):
        raise http_error(403)

    monkeypatch.setattr("src.client.urllib.request.urlopen", fake_urlopen)

    client = GitHubGraphQLClient(token="fake-token", max_attempts=3)

    with pytest.raises(GraphQLRequestError) as excinfo:
        client.execute("query { }")

    assert excinfo.value.retryable is False


def test_constructor_requires_token():
    with pytest.raises(ValueError):
        GitHubGraphQLClient(token="")
