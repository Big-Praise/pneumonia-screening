"""Sessions for the API: a signed JWT in an httpOnly cookie.

Decisions:
- httpOnly cookie, not localStorage: page JavaScript can never read the token,
  so an XSS bug can't steal sessions.
- SameSite=Lax + same-origin deployment (the Vercel frontend proxies /api/* to
  this backend) means browsers won't attach the cookie to cross-site POSTs,
  which covers CSRF for this app.
- The token carries only the user id; the user row is re-read on every request,
  so a deleted user is logged out immediately.
- Login throttling is per username (a proxy chain makes client IPs unreliable).
"""
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Cookie, HTTPException, Response, status

import auth
import config
from db import User, get_session

COOKIE = "session"
ALGO = "HS256"

# Dev fallback: a random secret per process (restarts log everyone out). See config TODO.
_SECRET = config.JWT_SECRET or secrets.token_urlsafe(48)
USING_EPHEMERAL_SECRET = not config.JWT_SECRET


def issue(response: Response, user: auth.AuthUser) -> None:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": str(user.id), "iat": now, "exp": now + timedelta(hours=config.SESSION_HOURS)},
        _SECRET, algorithm=ALGO,
    )
    response.set_cookie(
        COOKIE, token, max_age=config.SESSION_HOURS * 3600, httponly=True,
        secure=config.COOKIE_SECURE, samesite="lax", path="/",
    )


def clear(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/", httponly=True, secure=config.COOKIE_SECURE,
                           samesite="lax")


def current_user(session: str | None = Cookie(default=None, alias=COOKIE)) -> auth.AuthUser:
    """FastAPI dependency: the logged-in user, or 401."""
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in.")
    if not session:
        raise unauthorized
    try:
        payload = jwt.decode(session, _SECRET, algorithms=[ALGO])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized from None
    with get_session() as s:
        user = s.get(User, user_id)
        if user is None:
            raise unauthorized
        return auth.AuthUser(user.id, user.username, user.full_name)


class LoginThrottle:
    """After MAX_FAILS failures within WINDOW seconds, a username is locked for LOCK seconds."""
    MAX_FAILS, WINDOW, LOCK = 5, 15 * 60, 5 * 60

    def __init__(self):
        self._fails: dict[str, list[float]] = {}
        self._locked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def check(self, username: str) -> None:
        with self._lock:
            until = self._locked_until.get(username, 0)
        if until > time.monotonic():
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                "Too many failed attempts. Try again in a few minutes.")

    def failed(self, username: str) -> None:
        now = time.monotonic()
        with self._lock:
            recent = [t for t in self._fails.get(username, []) if now - t < self.WINDOW] + [now]
            self._fails[username] = recent
            if len(recent) >= self.MAX_FAILS:
                self._locked_until[username] = now + self.LOCK
                self._fails[username] = []

    def succeeded(self, username: str) -> None:
        with self._lock:
            self._fails.pop(username, None)
            self._locked_until.pop(username, None)


throttle = LoginThrottle()
