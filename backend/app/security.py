"""MVP security helpers: admin key check + in-memory rate limiting."""
import secrets
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

from .config import get_settings


def require_admin(x_admin_key: str | None = Header(default=None)) -> None:
    """Protects CRM/admin endpoints when ADMIN_API_KEY is set. (Open in local dev when unset.)"""
    expected = get_settings().admin_api_key
    if not expected:
        return
    if not x_admin_key or not secrets.compare_digest(x_admin_key, expected):
        raise HTTPException(status_code=401, detail="Admin key required (header X-Admin-Key)")


_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request) -> None:
    """Simple per-IP sliding window for the public chat endpoints. Production: Redis-based limiter."""
    limit = get_settings().rate_limit_per_minute
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests, slow down")
    q.append(now)


def reset_rate_limits() -> None:
    _hits.clear()
