import time

DEFAULT_RETRY_BACKOFF_BASE_SECONDS = 2.0
RETRYABLE_SERVER_ERROR_CODES = {500, 502, 503, 504}
RETRYABLE_THROTTLING_CODES = {403, 429}


class RetryableTransportError(RuntimeError):
    def __init__(self, message, retry_after_seconds=None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


def is_retryable_http_status(code, retry_after_seconds):
    is_server_error = code in RETRYABLE_SERVER_ERROR_CODES
    is_throttled = code in RETRYABLE_THROTTLING_CODES and (
        code == 429 or retry_after_seconds is not None
    )
    return is_server_error or is_throttled


def parse_retry_after_header(headers):
    if not headers:
        return None
    value = headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(float(value), 1.0)
    except (TypeError, ValueError):
        return None


def exponential_backoff_seconds(attempt, base_seconds=DEFAULT_RETRY_BACKOFF_BASE_SECONDS):
    return base_seconds * (2 ** (attempt - 1))


def call_with_retry(fn, max_attempts, on_retry=None):
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except RetryableTransportError as error:
            last_error = error
            if attempt == max_attempts:
                break
            delay_seconds = error.retry_after_seconds
            if delay_seconds is None:
                delay_seconds = exponential_backoff_seconds(attempt)
            if on_retry is not None:
                on_retry(attempt, max_attempts, error, delay_seconds)
            time.sleep(delay_seconds)
    raise last_error
