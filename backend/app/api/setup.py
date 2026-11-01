"""Setup routes — first-run wizard."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
import hmac
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models import BootstrapGrant
from app.services import hosted_access as access

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.get("/status")
async def setup_status(request: Request, db: AsyncSession = Depends(get_db)):
    """Returns whether first-run setup is needed (no users exist)."""
    result = await db.execute(select(func.count()).select_from(User))
    count = result.scalar()
    hosted = await access.profile(db, request)
    return {"needs_setup": count == 0 and not hosted, "bootstrap_required": count == 0 and bool(hosted)}


class SetupInit(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    bootstrap_token: str | None = None


@router.post("/init", status_code=201)
async def setup_init(data: SetupInit, request: Request, db: AsyncSession = Depends(get_db)):
    """Create the first super admin. Only works when no users exist."""
    await access.bootstrap_exclusion(db)
    hosted = await access.profile(db, request, cookie_action=True)
    grant = await db.scalar(select(BootstrapGrant).with_for_update()) if hosted else None
    if hosted:
        token = data.bootstrap_token
        if (not grant or grant.consumed_at or grant.expires_at <= access.now()
                or not isinstance(token, str) or not 32 <= len(token) <= 128
                or not hmac.compare_digest(grant.token_digest, access.token_digest(token))
                or grant.buyer_commitment != access.buyer_commitment(str(data.email))):
            access.refuse()
    result = await db.execute(select(func.count()).select_from(User))
    if result.scalar() > 0:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"key": "errors.setup.already_completed"})

    if len(data.password) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"key": "errors.auth.password_too_short"})

    user = User(
        email=str(data.email).strip().lower(),
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=UserRole.SUPER_ADMIN,
        can_manage_users=True,
        can_create_events=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    if grant:
        grant.consumed_at = access.now()
        await db.flush()
    return {"id": str(user.id), "email": user.email, "full_name": user.full_name, "role": user.role.value}
