from datetime import datetime, timedelta, timezone
from src.errors import RateLimitReached


def test_rate_limit_reached_message_contains_remaining_and_reset():
    err = RateLimitReached(reset_at="2099-01-01T00:00:00Z", remaining=5)
    assert "5" in str(err)
    assert "2099" in str(err)


def test_seconds_until_reset_returns_positive_for_future():
    future = (datetime.now(timezone.utc) + timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    err = RateLimitReached(reset_at=future, remaining=0)
    assert err.seconds_until_reset() > 0


def test_seconds_until_reset_returns_zero_for_past():
    err = RateLimitReached(reset_at="2000-01-01T00:00:00Z", remaining=0)
    assert err.seconds_until_reset() == 0
