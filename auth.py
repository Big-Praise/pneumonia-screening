"""Authentication: registration, login, bcrypt password hashing.

Decisions:
- `bcrypt` is used directly (passlib is unmaintained and breaks on bcrypt>=4.1).
  bcrypt generates and embeds a per-password salt, so there is no salt/pepper
  for anyone to configure or leak.
- Functions return a small immutable `AuthUser`, not an ORM object, so it can
  live in st.session_state safely and never carries the password hash.
- Login state itself is Streamlit's per-browser-session state (server-side), so
  no cookie-signing secret is needed. If persistent "remember me" cookies are
  added later, that will need a secret — see TODO in config.py.
"""
import hmac
import re
from dataclasses import dataclass

import bcrypt
from sqlalchemy import select

import config
from db import User, get_session

USERNAME_RE = re.compile(r"^[a-z0-9_.-]{3,32}$")
MIN_PASSWORD_LEN = 8
MAX_PASSWORD_BYTES = 72  # bcrypt only uses the first 72 bytes; reject rather than truncate

# Compared against when a username doesn't exist, so a failed login takes the
# same time either way (prevents discovering valid usernames by timing).
_DUMMY_HASH = bcrypt.hashpw(b"timing-equaliser", bcrypt.gensalt())


class AuthError(ValueError):
    """User-facing validation/auth problem; message is safe to display."""


@dataclass(frozen=True)
class AuthUser:
    id: int
    username: str
    full_name: str | None

    @property
    def display_name(self) -> str:
        return self.full_name or self.username


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:  # malformed hash or over-long password
        return False


def normalise_username(username: str) -> str:
    return (username or "").strip().lower()


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LEN:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LEN} characters.")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise AuthError("Password is too long (maximum 72 bytes).")


def registration_requires_code() -> bool:
    return bool(config.REGISTRATION_CODE)


def register_user(username: str, password: str, full_name: str = "",
                  registration_code: str = "") -> AuthUser:
    """Create a clinician account. Raises AuthError with a displayable message."""
    if registration_requires_code() and not hmac.compare_digest(
        registration_code.encode("utf-8"), config.REGISTRATION_CODE.encode("utf-8")
    ):
        raise AuthError("Invalid registration code.")

    username = normalise_username(username)
    if not USERNAME_RE.match(username):
        raise AuthError("Username must be 3–32 characters: letters, numbers, . _ -")
    validate_password(password)

    with get_session() as s:
        if s.scalar(select(User.id).where(User.username == username)) is not None:
            raise AuthError("That username is already taken.")
        user = User(
            username=username,
            password_hash=hash_password(password),
            full_name=(full_name or "").strip() or None,
        )
        s.add(user)
        s.flush()  # assigns user.id
        return AuthUser(user.id, user.username, user.full_name)


def authenticate(username: str, password: str) -> AuthUser | None:
    """Return the user on correct credentials, else None (no detail on which part failed)."""
    username = normalise_username(username)
    with get_session() as s:
        user = s.scalar(select(User).where(User.username == username))
        if user is None:
            verify_password(password, _DUMMY_HASH.decode("ascii"))
            return None
        if not verify_password(password, user.password_hash):
            return None
        return AuthUser(user.id, user.username, user.full_name)
