"""Auth service — user creation, authentication, token management."""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.models.user import User, UserRole
from app.schemas.auth import UserCreate


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(func.lower(User.email) == email.strip().lower()))
    matches = list(result.scalars())
    return matches[0] if len(matches) == 1 else None


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    user = User(
        email=str(data.email).strip().lower(),
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=UserRole(data.role),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    result = await db.execute(select(User).where(func.lower(User.email) == email.strip().lower()).with_for_update())
    matches = list(result.scalars())
    user = matches[0] if len(matches) == 1 else None
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def generate_tokens(user: User, session_id: str | None = None) -> dict:
    """Generate access + refresh token pair for a user."""
    access_token = create_access_token(
        subject=str(user.id),
        role=user.role.value, session_id=session_id,
    )
    refresh_token = create_refresh_token(subject=str(user.id), session_id=session_id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
    }
