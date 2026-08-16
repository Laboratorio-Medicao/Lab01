import json
import logging
import urllib.error
import urllib.request

from src.errors import RateLimitReached
from src.http_retry import (
    RetryableTransportError,
    call_with_retry,
    is_retryable_http_status,
    parse_retry_after_header,
)

GITHUB_GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RATE_LIMIT_THRESHOLD = 100
GRAPHQL_RETRYABLE_ERROR_TYPES = {"RATE_LIMITED", "SERVICE_UNAVAILABLE"}

logger = logging.getLogger(__name__)


class GraphQLRequestError(RuntimeError):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


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
        def _log_retry(attempt, max_attempts, error, delay_seconds):
            logger.warning(
                "tentativa %s/%s falhou (%s); nova tentativa em %.1fs",
                attempt,
                max_attempts,
                error,
                delay_seconds,
            )

        try:
            return call_with_retry(
                lambda: self._execute_once(query, variables or {}),
                self._max_attempts,
                on_retry=_log_retry,
            )
        except RetryableTransportError as error:
            raise GraphQLRequestError(str(error), retryable=True) from error

    def _execute_once(self, query, variables):
        request = self._build_request(query, variables)

        try:
            with urllib.request.urlopen(request, timeout=self._request_timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            self._raise_for_http_error(error)
        except urllib.error.URLError as error:
            raise RetryableTransportError(f"falha de rede na requisição GraphQL: {error.reason}")

        body = self._parse_response_body(raw_body)

        if body.get("errors"):
            errors = body["errors"]
            self._raise_for_graphql_errors(errors)

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
        retry_after_seconds = parse_retry_after_header(error.headers)
        message = f"HTTP {error.code} na requisição GraphQL: {raw_body}"

        if is_retryable_http_status(error.code, retry_after_seconds):
            raise RetryableTransportError(message, retry_after_seconds=retry_after_seconds)
        raise GraphQLRequestError(message)

    @staticmethod
    def _raise_for_graphql_errors(errors):
        is_transient = any(
            isinstance(error, dict) and error.get("type") in GRAPHQL_RETRYABLE_ERROR_TYPES
            for error in errors
        )
        message = f"erros retornados pela API GraphQL: {errors}"
        if is_transient:
            raise RetryableTransportError(message)
        raise GraphQLRequestError(message)

    @staticmethod
    def _parse_response_body(raw_body):
        try:
            return json.loads(raw_body)
        except json.JSONDecodeError as error:
            raise GraphQLRequestError(f"resposta inválida da API GraphQL: {error}") from error

    def _log_and_await_rate_limit(self, rate_limit):
        if not rate_limit:
            return

        remaining = rate_limit["remaining"]
        cost = rate_limit["cost"]
        reset_at = rate_limit["resetAt"]
        logger.info("rate limit: remaining=%s cost=%s resetAt=%s", remaining, cost, reset_at)

        if remaining > self._rate_limit_threshold:
            return

        logger.warning(
            "rate limit baixo (remaining=%s <= threshold=%s); resetAt=%s",
            remaining,
            self._rate_limit_threshold,
            reset_at,
        )
        raise RateLimitReached(reset_at=reset_at, remaining=remaining)
