"""Auth routes — login, token refresh, user creation, current user, password change."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Cookie, status
from pydantic import BaseModel
import secrets
import uuid
from sqlalchemy import update
from app.models import AuthSession
from app.services import hosted_access as access
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import decode_token, verify_password, hash_password
from app.core.email import send_password_reset_email
from app.core.logging import get_logger
from app.core.urls import get_app_base_url
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserResponse
from app.schemas.user import PasswordChange
from app.services.auth_service import (
    authenticate_user,
    create_user,
    generate_tokens,
    get_user_by_email,
    get_user_by_id,
)
from app.api.deps import get_current_user, require_can_manage_users

settings = get_settings()
logger = get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate and return access token. Sets refresh token as httpOnly cookie."""
    await access.profile(db, request, cookie_action=True)
    user = await authenticate_user(db, data.email.strip().lower(), data.password)
    if not user:
        logger.warning("login_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"key": "errors.auth.invalid_credentials"},
        )

    sid = uuid.uuid4()
    tokens = generate_tokens(user, str(sid))
    db.add(AuthSession(id=sid, user_id=user.id, refresh_digest=access.token_digest(tokens['refresh_token']),
                       expires_at=access.now() + timedelta(days=settings.refresh_token_expire_days)))
    await db.flush()
    logger.info("login_success", user_id=str(user.id), role=user.role.value)

    # Clear the former narrower-path cookie so it cannot shadow the new one.
    response.delete_cookie('refresh_token', path='/api/auth/refresh',
                           secure=await access.cookie_secure(db, request), httponly=True, samesite='strict')
    # Set refresh token as httpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=await access.cookie_secure(db, request),
        samesite="strict",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/auth",
    )

    return TokenResponse(access_token=tokens["access_token"])


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    request: Request,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Exchange a valid refresh token for new access + refresh tokens (rotation)."""
    await access.profile(db, request, cookie_action=True)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"key": "errors.auth.refresh_missing"},
        )

    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh" or not await access.valid_session(db, payload):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"key": "errors.auth.refresh_invalid"},
        )

    user = await get_user_by_id(db, payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"key": "errors.auth.user_not_found"},
        )

    # Token rotation — issue entirely new pair
    tokens = generate_tokens(user, payload['sid'])
    changed = await db.execute(update(AuthSession).where(AuthSession.id == uuid.UUID(payload['sid']),
        AuthSession.refresh_digest == access.token_digest(refresh_token), AuthSession.revoked_at.is_(None),
        AuthSession.expires_at > access.now()).values(refresh_digest=access.token_digest(tokens['refresh_token'])))
    if changed.rowcount != 1:
        raise HTTPException(401, detail={'key': 'errors.auth.refresh_invalid'})
    logger.info("token_refreshed", user_id=str(user.id))

    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=await access.cookie_secure(db, request),
        samesite="strict",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/auth",
    )

    return TokenResponse(access_token=tokens["access_token"])


@router.post("/logout")
async def logout(response: Response, request: Request,
                 refresh_token: str | None = Cookie(default=None), db: AsyncSession = Depends(get_db)):
    await access.profile(db, request, cookie_action=True)
    payload = decode_token(refresh_token) if refresh_token else None
    if payload and payload.get('sid') and payload.get('type') == 'refresh':
        try:
            sid = uuid.UUID(payload['sid'])
        except (ValueError, TypeError):
            sid = None
        if sid:
            await db.execute(update(AuthSession).where(AuthSession.id == sid,
                AuthSession.user_id == uuid.UUID(payload['sub'])).values(revoked_at=access.now()))
    for path in ('/api/auth', '/api/auth/refresh'):
        response.delete_cookie('refresh_token', path=path, secure=await access.cookie_secure(db, request),
                               httponly=True, samesite='strict')
    return {"detail": "Logged out"}


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_can_manage_users()),
):
    """Create a new organising team member. Super Admin or Staff with can_manage_users flag."""
    existing = await get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"key": "errors.auth.email_taken"},
        )

    user = await create_user(db, data)
    logger.info(
        "user_created",
        new_user_id=str(user.id),
        role=user.role.value,
        created_by=str(current_user.id),
    )
    return user


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return current_user


@router.patch("/me/password")
async def change_password(
    data: PasswordChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change the current user's password."""
    if len(data.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"key": "errors.auth.password_too_short"},
        )

    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"key": "errors.auth.current_password_wrong"},
        )

    await access.revoke_user_sessions(db, current_user.id)
    current_user.hashed_password = hash_password(data.new_password)
    db.add(current_user)
    await db.flush()

    logger.info("password_changed", user_id=str(current_user.id))
    return {"detail": "Password changed successfully"}


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


@router.post("/request-reset")
async def request_password_reset(
    request: Request,
    data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset email. Always returns 200 to avoid user enumeration."""
    await access.profile(db, request, cookie_action=True)
    user = await get_user_by_email(db, data.email.strip().lower())
    if user and user.is_active:
        token = secrets.token_urlsafe(48)
        user.password_reset_token = access.token_digest(token)
        user.password_reset_expires = datetime.now(timezone.utc) + timedelta(minutes=30)
        db.add(user)
        await db.flush()
        # Canonical Hosted origin; credential stays in the browser fragment,
        # never in the HTTP request target or reverse-proxy query logs.
        base = get_app_base_url(request)
        reset_url = f"{base}/reset-password#reset={token}"
        send_password_reset_email(user.email, user.full_name, reset_url)
        logger.info("password_reset_requested", user_id=str(user.id))
    return {"detail": "If that email address is registered, you will receive a reset link shortly."}


@router.post("/reset-password")
async def reset_password(
    data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using a valid reset token. Expires after 30 minutes."""
    from sqlalchemy import select as _sel
    result = await db.execute(_sel(User).where(User.password_reset_token == access.token_digest(data.token)).with_for_update())
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"key": "errors.auth.reset_invalid"})

    if user.password_reset_expires is None or datetime.now(timezone.utc) > user.password_reset_expires:
        user.password_reset_token = None
        user.password_reset_expires = None
        db.add(user)
        await db.flush()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"key": "errors.auth.reset_expired"})

    if len(data.new_password) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"key": "errors.auth.password_too_short"})

    await access.revoke_user_sessions(db, user.id)
    user.hashed_password = hash_password(data.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    db.add(user)
    await db.flush()

    logger.info("password_reset_complete", user_id=str(user.id))
    return {"detail": "Password reset successfully. You can now sign in."}
