"""Security utilities — password hashing, JWT creation and verification."""

from datetime import datetime, timedelta, timezone

import uuid
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# ─── Password hashing ───
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ─── JWT ───
def create_access_token(subject: str, role: str, session_id: str | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": subject,
        "role": role,
        "exp": expire,
        "type": "access",
    }
    if session_id:
        payload["sid"] = session_id
    payload["jti"] = str(uuid.uuid4())
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(subject: str, session_id: str | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload = {
        "sub": subject,
        "exp": expire,
        "type": "refresh",
    }
    if session_id:
        payload["sid"] = session_id
    payload["jti"] = str(uuid.uuid4())
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT. Returns payload dict or None if invalid."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        return payload
    except JWTError:
        return None
