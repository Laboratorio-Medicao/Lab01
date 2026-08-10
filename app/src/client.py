import json
import logging
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

GITHUB_GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RATE_LIMIT_THRESHOLD = 100
DEFAULT_RETRY_BACKOFF_BASE_SECONDS = 2.0
RETRYABLE_SERVER_ERROR_CODES = {500, 502, 503, 504}
RETRYABLE_THROTTLING_CODES = {403, 429}

logger = logging.getLogger(__name__)


class GraphQLRequestError(RuntimeError):
    pass


class _RetryableTransportError(RuntimeError):
    def __init__(self, message, retry_after_seconds=None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class GitHubGraphQLClient:
    def __init__(
        self,
        token,
        rate_limit_threshold=DEFAULT_RATE_LIMIT_THRESHOLD,
        max_attempts=DEFAULT_MAX_ATTEMPTS,
        request_timeout_seconds=DEFAULT_REQUEST_TIMEOUT_SECONDS,
    ):
        if not token:
            raise ValueError("GITHUB_TOKEN não configurado")
        self._token = token
        self._rate_limit_threshold = rate_limit_threshold
        self._max_attempts = max_attempts
        self._request_timeout_seconds = request_timeout_seconds

    def execute(self, query, variables=None):
        last_error = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                return self._execute_once(query, variables or {})
            except _RetryableTransportError as error:
                last_error = error
                if attempt == self._max_attempts:
                    break
                delay_seconds = error.retry_after_seconds
                if delay_seconds is None:
                    delay_seconds = self._exponential_backoff_seconds(attempt)
                logger.warning(
                    "tentativa %s/%s falhou (%s); nova tentativa em %.1fs",
                    attempt,
                    self._max_attempts,
                    error,
                    delay_seconds,
                )
                time.sleep(delay_seconds)
        raise GraphQLRequestError(str(last_error)) from last_error

    def _execute_once(self, query, variables):
        request = self._build_request(query, variables)

        try:
            with urllib.request.urlopen(request, timeout=self._request_timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            self._raise_for_http_error(error)
        except urllib.error.URLError as error:
            raise _RetryableTransportError(f"falha de rede na requisição GraphQL: {error.reason}")

        body = self._parse_response_body(raw_body)

        if body.get("errors"):
            raise GraphQLRequestError(f"erros retornados pela API GraphQL: {body['errors']}")

        data = body.get("data")
        if data is None:
            raise GraphQLRequestError(f"resposta da API GraphQL sem campo 'data': {body}")

        self._log_and_await_rate_limit(data.get("rateLimit"))
        return data

    def _build_request(self, query, variables):
        payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        return urllib.request.Request(
            GITHUB_GRAPHQL_ENDPOINT,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "Accept": "application/vnd.github+json",
                "User-Agent": "lab01-graphql-client",
            },
        )

    def _raise_for_http_error(self, error):
        raw_body = error.read().decode("utf-8")
        retry_after_seconds = self._parse_retry_after_header(error.headers)
        message = f"HTTP {error.code} na requisição GraphQL: {raw_body}"

        is_server_error = error.code in RETRYABLE_SERVER_ERROR_CODES
        is_throttled = error.code in RETRYABLE_THROTTLING_CODES and (
            error.code == 429 or retry_after_seconds is not None
        )
        if is_server_error or is_throttled:
            raise _RetryableTransportError(message, retry_after_seconds=retry_after_seconds)
        raise GraphQLRequestError(message)

    @staticmethod
    def _parse_retry_after_header(headers):
        if not headers:
            return None
        value = headers.get("Retry-After")
        if value is None:
            return None
        try:
            return max(float(value), 1.0)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_response_body(raw_body):
        try:
            return json.loads(raw_body)
        except json.JSONDecodeError as error:
            raise GraphQLRequestError(f"resposta inválida da API GraphQL: {error}") from error

    @staticmethod
    def _exponential_backoff_seconds(attempt):
        return DEFAULT_RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))

    def _log_and_await_rate_limit(self, rate_limit):
        if not rate_limit:
            return

        remaining = rate_limit["remaining"]
        cost = rate_limit["cost"]
        reset_at = rate_limit["resetAt"]
        logger.info("rate limit: remaining=%s cost=%s resetAt=%s", remaining, cost, reset_at)

        if remaining > self._rate_limit_threshold:
            return

        reset_at_datetime = datetime.fromisoformat(reset_at.replace("Z", "+00:00"))
        sleep_seconds = (reset_at_datetime - datetime.now(timezone.utc)).total_seconds()
        if sleep_seconds <= 0:
            return

        logger.warning(
            "rate limit baixo (remaining=%s <= threshold=%s); dormindo %.0fs até %s",
            remaining,
            self._rate_limit_threshold,
            sleep_seconds,
            reset_at,
        )
        time.sleep(sleep_seconds + 5)
