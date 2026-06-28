"""Retry/backoff policy (legacy fixture)."""


def compute_backoff(attempt):
    return min(2 ** attempt, 60)


class RetryPolicy:
    def __init__(self, max_attempts):
        self.max_attempts = max_attempts

    def should_retry(self, attempt):
        return attempt < self.max_attempts
