import json
import time
import urllib.error
import urllib.request

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_BASE_SECONDS = 2.0
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30
RETRYABLE_SERVER_ERROR_CODES = {500, 502, 503, 504}
RETRYABLE_THROTTLING_CODES = {403, 429}


class RestNotFoundError(RuntimeError):
    pass


class _RetryableTransportError(RuntimeError):
    def __init__(self, message, retry_after_seconds=None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class RestClient:
    def __init__(self, token, max_attempts=DEFAULT_MAX_ATTEMPTS):
        self._token = token
        self._max_attempts = max_attempts

    def get(self, url):
        return self._with_exponential_backoff(lambda: self._request_once(url))

    def get_all_pages(self, url):
        all_items = []
        page = 1
        while True:
            separator = "&" if "?" in url else "?"
            page_url = f"{url}{separator}per_page=100&page={page}"
            page_data = self._with_exponential_backoff(lambda: self._request_once(page_url))
            if not page_data:
                break
            all_items.extend(page_data)
            if len(page_data) < 100:
                break
            page += 1
        return all_items

    def _with_exponential_backoff(self, fn):
        last_error = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                return fn()
            except _RetryableTransportError as error:
                last_error = error
                if attempt == self._max_attempts:
                    break
                delay = error.retry_after_seconds or self._backoff_seconds(attempt)
                time.sleep(delay)
        raise RuntimeError(str(last_error)) from last_error

    def _request_once(self, url):
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "lab01-rest-client",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=DEFAULT_REQUEST_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            self._raise_for_http_error(error, url)

    def _raise_for_http_error(self, error, url):
        body = error.read().decode("utf-8")
        message = f"HTTP {error.code} em {url}: {body}"

        if error.code == 404:
            raise RestNotFoundError(message) from error

        retry_after = self._parse_retry_after(error.headers)
        if self._is_retryable(error.code, retry_after):
            raise _RetryableTransportError(message, retry_after_seconds=retry_after) from error

        raise RuntimeError(message) from error

    @staticmethod
    def _is_retryable(code, retry_after):
        is_server_error = code in RETRYABLE_SERVER_ERROR_CODES
        is_throttled = code in RETRYABLE_THROTTLING_CODES and (code == 429 or retry_after is not None)
        return is_server_error or is_throttled

    @staticmethod
    def _backoff_seconds(attempt):
        return DEFAULT_RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))

    @staticmethod
    def _parse_retry_after(headers):
        if not headers:
            return None
        value = headers.get("Retry-After")
        if value is None:
            return None
        try:
            return max(float(value), 1.0)
        except (TypeError, ValueError):
            return None
