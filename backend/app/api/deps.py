"""FastAPI dependencies for authentication and role-based access control."""

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User, UserRole
from app.services.auth_service import get_user_by_id
from app.services.hosted_access import valid_session, profile

bearer_scheme = HTTPBearer()


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate JWT, return the authenticated user."""
    await profile(db, request)
    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"key": "errors.auth.token_invalid_or_expired"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_id(db, payload["sub"])
    if user is None or not user.is_active or not await valid_session(db, payload):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"key": "errors.auth.user_not_found_or_inactive"},
        )
    return user


async def get_current_user_query_token(
    request: Request,
    token: str = Query(..., description="JWT access token"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Variant of get_current_user that reads the token from a `?token=`
    query parameter. v1.0-pre #8/#9: needed for SSE endpoints because
    the EventSource browser API does not support custom request headers,
    so the JWT can't ride in the Authorization header. Same JWT format
    and validation as the header form.
    """
    await profile(db, request)
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"key": "errors.auth.token_invalid_or_expired"},
        )
    user = await get_user_by_id(db, payload["sub"])
    if user is None or not user.is_active or not await valid_session(db, payload):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"key": "errors.auth.user_not_found_or_inactive"},
        )
    return user


def require_role(*allowed_roles: UserRole):
    """Dependency factory — restricts endpoint to specific roles."""

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        # Super admin always passes role checks
        if current_user.role == UserRole.SUPER_ADMIN:
            return current_user
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"key": "errors.users.insufficient_permissions"},
            )
        return current_user

    return role_checker


# ─── v0.50i: archive read-only enforcement ──────────────────────────────────
#
# Archived events are read-only for everyone except Super Admin. Every
# write endpoint that mutates event-scoped data must gate on this. We
# provide two shapes:
#
#   1. `ensure_event_writable(db, event_id, user)` — call inline from a
#      route handler. Use this when event_id has to be resolved from
#      another entity (participant → event, category → event, etc.).
#
#   2. `require_writable_event` — FastAPI dependency for routes that
#      have `event_id` directly as a path param. Plugs into Depends().
#
# Both return nothing on success, raise 403 on any archived event (no
# Super Admin bypass since v0.50i-1).

async def ensure_event_writable(
    db: AsyncSession,
    event_id,
    user: User,
) -> None:
    """Raise 403 if the event is archived. Applies to everyone — Super Admin too.

    v0.50i-1: Super Admin bypass removed. Archive means the event is
    frozen; if someone needs to edit, they must unarchive first. The
    archive/unarchive endpoints themselves are gated on Super Admin
    role at the route level, not through this helper.

    Import locally to avoid a circular import with app.services.event_service.
    Callers pass the same db session and authenticated user they already have.
    The `user` argument is kept for signature stability and future use
    (e.g., logging the attempt).
    """
    from app.services.event_service import get_event_by_id
    event = await get_event_by_id(db, event_id)
    if event is None:
        # Let the actual route return 404 — don't preempt here.
        return
    if event.is_archived:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"key": "errors.event.archived_readonly"},
        )


def require_writable_event():
    """FastAPI dependency — use on routes whose path has `{event_id}`.

    Reads `event_id` from the matched path via the standard FastAPI
    mechanism (declare `event_id: uuid.UUID` in your route handler and
    this dep sees the same one).
    """
    import uuid as _uuid

    async def _check(
        event_id: _uuid.UUID,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> None:
        await ensure_event_writable(db, event_id, current_user)

    return _check


# ─── v0.50j: per-event admin check ──────────────────────────────────────────
#
# Replaces `require_role(UserRole.EVENT_ADMIN)` on event-scoped routes.
# Super Admin bypasses unconditionally. Other users must have an
# EventUserAssignment on this event with role='event_admin' (the per-event
# admin grant, separate from the system role).

async def ensure_event_admin(
    db: AsyncSession,
    event_id,
    user: User,
) -> None:
    """Raise 403 unless user is Super Admin or per-event admin on this event.

    Call inline from a route handler. For routes where event_id must be
    resolved from another entity (participant, category), resolve first
    then call this helper.
    """
    if user.role == UserRole.SUPER_ADMIN:
        return
    from app.models.event_assignment import EventUserAssignment
    from sqlalchemy import select as _select
    result = await db.execute(
        _select(EventUserAssignment).where(
            EventUserAssignment.event_id == event_id,
            EventUserAssignment.user_id == user.id,
        )
    )
    assignment = result.scalar_one_or_none()
    if assignment is None or assignment.role != "event_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"key": "errors.event.admin_required"},
        )


def require_event_admin_dep():
    """FastAPI dependency — use on routes whose path has `{event_id}`.

    Combines role/assignment check. For routes where event_id lives
    somewhere else (participant_id → event_id), call ensure_event_admin
    inline instead.
    """
    import uuid as _uuid

    async def _check(
        event_id: _uuid.UUID,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> User:
        await ensure_event_admin(db, event_id, current_user)
        return current_user

    return _check


def require_can_create_events():
    """Dependency — user must have can_create_events flag OR be Super Admin."""

    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role == UserRole.SUPER_ADMIN:
            return current_user
        if not current_user.can_create_events:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"key": "errors.event.create_permission_required"},
            )
        return current_user

    return _check


def require_can_manage_users():
    """Dependency — user must have can_manage_users flag OR be Super Admin."""

    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role == UserRole.SUPER_ADMIN:
            return current_user
        if not current_user.can_manage_users:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"key": "errors.users.manage_permission_required"},
            )
        return current_user

    return _check
