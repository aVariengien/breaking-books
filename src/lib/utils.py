"""Small shared utilities."""

import hashlib


def hash_string(s: str) -> str:
    """Return a stable SHA256 hex digest of a string (used as cache key)."""
    return hashlib.sha256(s.encode()).hexdigest()


def slug(text: str) -> str:
    """Convert text to a filesystem-safe slug (e.g. 'My Card' → 'my-card')."""
    raise NotImplementedError()
