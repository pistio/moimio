"""Private bootstrap issuance; no HTTP/CLI issuer, environment switch or startup mint.

Provisioning is trusted to establish buyer/payment truth separately. This record
binds that assertion; it is not proof that Paddle or independent custody did so.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit
from uuid import UUID

from email_validator import validate_email
from fastapi import HTTPException, Request
from sqlalchemy import select, func, text, update

from app.core.config import get_settings
from app.models import AuthSession, BootstrapGrant, User


def now():
    return datetime.now(timezone.utc)


def token_digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def buyer_commitment(email):
    address = validate_email(email, check_deliverability=False).normalized.lower()
    return hmac.new(
        get_settings().secret_key.encode(),
        b"hosted-bootstrap-buyer/v1:" + address.encode(),
        hashlib.sha256,
    ).hexdigest()


def configured_hosted():
    s = get_settings()
    return bool(
        s.moimio_tenant_id
        or s.feature_account_portal
        or s.moimio_webhook_url
        or s.moimio_webhook_secret
        or s.account_url
    )


def origin_value(value):
    u = urlsplit(value)
    if (
        u.scheme != "https"
        or not u.hostname
        or u.username
        or u.password
        or u.path
        or u.query
        or u.fragment
    ):
        raise ValueError("HOSTED_HTTPS_ORIGIN_REQUIRED")
    return u.geturl()


def refuse():
    raise HTTPException(403, detail={"key": "errors.setup.already_completed"})


async def profile(db, request: Request | None = None, *, cookie_action=False):
    s = get_settings()
    grant = await db.scalar(select(BootstrapGrant))
    hosted = configured_hosted() or grant is not None
    if not hosted:
        if request and request.headers.get("origin"):
            allowed = {
                *s.cors_origin_list,
                s.public_origin.rstrip("/"),
                str(request.base_url).rstrip("/"),
            }
            if request.headers["origin"] not in allowed:
                refuse()
        return None
    try:
        origin = origin_value(s.public_origin)
        if str(UUID(s.moimio_tenant_id)) != s.moimio_tenant_id:
            raise ValueError("invalid tenant")
        if grant and (
            grant.tenant_id != s.moimio_tenant_id or grant.public_origin != origin
        ):
            raise ValueError("binding mismatch")
    except ValueError:
        raise HTTPException(503, detail={"key": "errors.auth.token_invalid_or_expired"})
    if request:
        if request.headers.get("host") != urlsplit(origin).netloc:
            refuse()
        supplied = request.headers.get("origin")
        if (cookie_action and supplied != origin) or (supplied and supplied != origin):
            refuse()
    return origin


async def issue_bootstrap(
    db, *, tenant_id, buyer_email, checkout_id, transaction_commitment, public_origin
):
    """Private provisioning call ONLY. Must be inside the paid tenant's owned DB.

    Returns a bearer secret once. No endpoint or normal startup calls this. Lost
    response requires review, never token reissue or a public-first-user fallback.
    """
    if str(UUID(tenant_id)) != tenant_id or str(UUID(checkout_id)) != checkout_id:
        raise ValueError("BOOTSTRAP_IDENTITY_INVALID")
    if len(transaction_commitment) != 64 or any(
        c not in "0123456789abcdef" for c in transaction_commitment
    ):
        raise ValueError("BOOTSTRAP_TRANSACTION_INVALID")
    origin_value(public_origin)
    if (
        not configured_hosted()
        or get_settings().moimio_tenant_id != tenant_id
        or get_settings().public_origin != public_origin
    ):
        raise ValueError("BOOTSTRAP_CONFIGURATION_MISMATCH")
    await bootstrap_exclusion(db)
    if await db.scalar(select(func.count()).select_from(User)) or await db.scalar(
        select(func.count()).select_from(BootstrapGrant)
    ):
        raise ValueError("BOOTSTRAP_ALREADY_ESTABLISHED")
    token = secrets.token_urlsafe(32)
    db.add(
        BootstrapGrant(
            tenant_id=tenant_id,
            request_id=checkout_id,
            public_origin=public_origin,
            buyer_commitment=buyer_commitment(buyer_email),
            transaction_commitment=transaction_commitment,
            token_digest=token_digest(token),
            expires_at=now() + timedelta(minutes=30),
        )
    )
    await db.flush()
    return token


async def valid_session(db, payload):
    sid = payload.get("sid")
    if not sid:
        # Existing CE access tokens retain only their original bounded lifetime;
        # Hosted tokens without a persisted session require a fresh login.
        return (
            not configured_hosted()
            and not await db.scalar(select(BootstrapGrant.tenant_id))
            and payload.get("type") == "access"
        )
    try:
        row = await db.get(AuthSession, UUID(sid))
    except (ValueError, TypeError):
        return False
    try:
        uid = UUID(payload["sub"])
    except (ValueError, TypeError, KeyError):
        return False
    return bool(
        row and row.user_id == uid and row.revoked_at is None and row.expires_at > now()
    )


async def revoke_user_sessions(db, user_id):
    await db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now())
    )


async def cookie_secure(db, request):
    return bool(await profile(db)) or (
        get_settings().public_origin or str(request.base_url)
    ).startswith("https://")


async def bootstrap_exclusion(db):
    if db.in_nested_transaction():
        raise ValueError("BOOTSTRAP_ROOT_TRANSACTION_REQUIRED")
    if await db.scalar(text("SHOW transaction_isolation")) != "read committed":
        raise ValueError("BOOTSTRAP_READ_COMMITTED_REQUIRED")
    await db.execute(text("SELECT pg_advisory_xact_lock(716450201)"))
