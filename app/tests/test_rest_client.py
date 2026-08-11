import io
import json
import urllib.error

import pytest

from src.rest_client import RestClient, RestNotFoundError


class FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def http_error(code, headers=None, body=b'{"message": "error"}'):
    return urllib.error.HTTPError(
        url="https://api.github.com/repos/owner/repo",
        code=code,
        msg="error",
        hdrs=headers if headers is not None else {},
        fp=io.BytesIO(body),
    )


def test_get_raises_not_found_without_retrying(monkeypatch):
    attempts = {"count": 0}

    def fake_urlopen(request, timeout):
        attempts["count"] += 1
        raise http_error(404)

    monkeypatch.setattr("src.rest_client.urllib.request.urlopen", fake_urlopen)

    client = RestClient("fake-token")

    with pytest.raises(RestNotFoundError):
        client.get("https://api.github.com/repos/owner/repo")

    assert attempts["count"] == 1


def test_get_retries_on_server_error_then_succeeds(monkeypatch):
    attempts = {"count": 0}

    def fake_urlopen(request, timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise http_error(503)
        return FakeResponse({"ok": True})

    monkeypatch.setattr("src.rest_client.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("src.http_retry.time.sleep", lambda seconds: None)

    client = RestClient("fake-token")
    result = client.get("https://api.github.com/repos/owner/repo")

    assert result == {"ok": True}
    assert attempts["count"] == 2


def test_get_respects_retry_after_header(monkeypatch):
    attempts = {"count": 0}

    def fake_urlopen(request, timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise http_error(403, headers={"Retry-After": "7"})
        return FakeResponse({"ok": True})

    monkeypatch.setattr("src.rest_client.urllib.request.urlopen", fake_urlopen)
    sleep_calls = []
    monkeypatch.setattr(
        "src.http_retry.time.sleep", lambda seconds: sleep_calls.append(seconds)
    )

    client = RestClient("fake-token")
    client.get("https://api.github.com/repos/owner/repo")

    assert sleep_calls == [7.0]


def test_get_gives_up_after_max_attempts(monkeypatch):
    attempts = {"count": 0}

    def fake_urlopen(request, timeout):
        attempts["count"] += 1
        raise http_error(503)

    monkeypatch.setattr("src.rest_client.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("src.http_retry.time.sleep", lambda seconds: None)

    client = RestClient("fake-token", max_attempts=3)

    with pytest.raises(RuntimeError):
        client.get("https://api.github.com/repos/owner/repo")

    assert attempts["count"] == 3


def test_get_does_not_retry_on_permission_denied_403_without_retry_after(monkeypatch):
    def fake_urlopen(request, timeout):
        raise http_error(403)

    monkeypatch.setattr("src.rest_client.urllib.request.urlopen", fake_urlopen)

    client = RestClient("fake-token", max_attempts=3)

    with pytest.raises(RuntimeError):
        client.get("https://api.github.com/repos/owner/repo")


def test_get_all_pages_concatenates_full_pages_until_short_page(monkeypatch):
    pages = [
        [{"n": i} for i in range(100)],
        [{"n": i} for i in range(3)],
    ]

    def fake_urlopen(request, timeout):
        return FakeResponse(pages.pop(0))

    monkeypatch.setattr("src.rest_client.urllib.request.urlopen", fake_urlopen)

    client = RestClient("fake-token")
    items = client.get_all_pages("https://api.github.com/repos/owner/repo/pulls?state=closed")

    assert len(items) == 103


def test_get_all_pages_stops_on_empty_first_page(monkeypatch):
    monkeypatch.setattr(
        "src.rest_client.urllib.request.urlopen",
        lambda request, timeout: FakeResponse([]),
    )

    client = RestClient("fake-token")
    items = client.get_all_pages("https://api.github.com/repos/owner/repo/pulls?state=closed")

    assert items == []
