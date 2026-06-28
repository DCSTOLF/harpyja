"""Entry point wiring auth + retry (legacy fixture)."""

from auth import authenticate
from net.retry import compute_backoff


def run(token, attempt):
    if not authenticate(token):
        return None
    return compute_backoff(attempt)
