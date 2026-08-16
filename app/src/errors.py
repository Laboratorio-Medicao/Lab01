from datetime import datetime, timezone


class RateLimitReached(Exception):
    def __init__(self, reset_at: str, remaining: int):
        super().__init__(f"rate limit atingido (remaining={remaining}, reset_at={reset_at})")
        self.reset_at = reset_at
        self.remaining = remaining

    def seconds_until_reset(self) -> float:
        reset_dt = datetime.fromisoformat(self.reset_at.replace("Z", "+00:00"))
        delta = (reset_dt - datetime.now(timezone.utc)).total_seconds()
        return max(delta + 5, 0.0)
