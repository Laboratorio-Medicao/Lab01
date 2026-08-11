import json
import urllib.error
import urllib.request

from src.http_retry import (
    RetryableTransportError,
    call_with_retry,
    is_retryable_http_status,
    parse_retry_after_header,
)

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30


class RestNotFoundError(RuntimeError):
    pass


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
        try:
            return call_with_retry(fn, self._max_attempts)
        except RetryableTransportError as error:
            raise RuntimeError(str(error)) from error

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

        retry_after = parse_retry_after_header(error.headers)
        if is_retryable_http_status(error.code, retry_after):
            raise RetryableTransportError(message, retry_after_seconds=retry_after) from error

        raise RuntimeError(message) from error
