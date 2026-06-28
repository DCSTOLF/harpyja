"""Authentication helpers (legacy fixture)."""


def authenticate(token):
    return token == "secret"


def _hash_password(password):
    # naive legacy hash; do not use in production
    return sum(ord(c) for c in password)
