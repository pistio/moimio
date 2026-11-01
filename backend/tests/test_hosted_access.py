"""Actual owned PostgreSQL/API bootstrap and session authority, no providers."""

from datetime import timedelta
from uuid import uuid4
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, func
from app.core.config import get_settings
from app.models import AuthSession, BootstrapGrant, User
from app.services import hosted_access as access
from app.core.database import get_db
from app.main import app

pytestmark = pytest.mark.asyncio
ORIGIN = "https://buyer.fictional.example"
EMAIL = "owner@buyer.fictional.example"
PASSWORD = "fictional-private-password"


@pytest.fixture
def hosted(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "moimio_tenant_id", str(uuid4()))
    monkeypatch.setattr(s, "public_origin", ORIGIN)
    return s


async def issuer(db, hosted):
    token = await access.issue_bootstrap(
        db,
        tenant_id=hosted.moimio_tenant_id,
        buyer_email=EMAIL,
        checkout_id=str(uuid4()),
        transaction_commitment="1" * 64,
        public_origin=ORIGIN,
    )
    await db.commit()
    return token


async def api(db):
    async def use_db():
        yield db
        await db.commit()

    app.dependency_overrides[get_db] = use_db
    return AsyncClient(
        transport=ASGITransport(app=app), base_url=ORIGIN, headers={"Origin": ORIGIN}
    )


async def test_foreign_first_admin_cannot_claim_hosted(db, hosted):
    token = await issuer(db, hosted)
    client = await api(db)
    try:
        async with client:
            status = (await client.get("/api/setup/status")).json()
            assert status == {"needs_setup": False, "bootstrap_required": True}
            body = {
                "email": EMAIL,
                "full_name": "Fictional buyer",
                "password": PASSWORD,
            }
            for changed in (
                {},
                {"bootstrap_token": "x" * 43},
                {"bootstrap_token": token, "email": "foreign@buyer.fictional.example"},
            ):
                assert (
                    await client.post("/api/setup/init", json=body | changed)
                ).status_code == 403
                await db.rollback()
                assert await db.scalar(select(func.count()).select_from(User)) == 0
            assert (
                await client.post(
                    "/api/setup/init", json=body | {"bootstrap_token": token}
                )
            ).status_code == 201
            assert (
                await client.post(
                    "/api/setup/init", json=body | {"bootstrap_token": token}
                )
            ).status_code == 403
            await db.rollback()
            grant = await db.scalar(select(BootstrapGrant))
            assert grant.consumed_at is not None
            assert token not in grant.token_digest
            assert await db.scalar(select(func.count()).select_from(User)) == 1
    finally:
        app.dependency_overrides.clear()


async def test_login_refresh_replay_logout_and_access_revocation(db, hosted):
    token = await issuer(db, hosted)
    client = await api(db)
    try:
        async with client:
            assert (
                await client.post(
                    "/api/setup/init",
                    json={
                        "email": EMAIL,
                        "full_name": "Fictional buyer",
                        "password": PASSWORD,
                        "bootstrap_token": token,
                    },
                )
            ).status_code == 201
            login = await client.post(
                "/api/auth/login", json={"email": EMAIL.upper(), "password": PASSWORD}
            )
            assert login.status_code == 200
            cookie = login.headers["set-cookie"]
            for field in (
                "HttpOnly",
                "Secure",
                "SameSite=strict",
                "Path=/api/auth",
                "Max-Age=",
            ):
                assert field in cookie
            old_cookie = client.cookies.get("refresh_token")
            first_access = login.json()["access_token"]
            assert (
                await client.get(
                    "/api/auth/me", headers={"Authorization": "Bearer " + first_access}
                )
            ).status_code == 200
            refreshed = await client.post("/api/auth/refresh")
            assert refreshed.status_code == 200
            assert (
                "Secure" in refreshed.headers["set-cookie"]
                and "HttpOnly" in refreshed.headers["set-cookie"]
            )
            new_cookie = client.cookies.get("refresh_token")
            assert old_cookie != new_cookie
            client.cookies.clear()
            client.cookies.set(
                "refresh_token",
                old_cookie,
                domain="buyer.fictional.example",
                path="/api/auth",
            )
            assert (await client.post("/api/auth/refresh")).status_code == 401
            await db.rollback()
            client.cookies.clear()
            client.cookies.set(
                "refresh_token",
                new_cookie,
                domain="buyer.fictional.example",
                path="/api/auth",
            )
            assert (await client.post("/api/auth/logout")).status_code == 200
            assert (
                await client.get(
                    "/api/auth/me", headers={"Authorization": "Bearer " + first_access}
                )
            ).status_code == 401
            await db.rollback()
            assert (await db.scalar(select(AuthSession))).revoked_at is not None
    finally:
        app.dependency_overrides.clear()


async def test_expired_grant_and_wrong_origin_remain_closed(db, hosted):
    token = await issuer(db, hosted)
    grant = await db.scalar(select(BootstrapGrant))
    grant.expires_at = access.now() - timedelta(seconds=1)
    await db.commit()
    client = await api(db)
    try:
        async with client:
            body = {
                "email": EMAIL,
                "full_name": "Fictional buyer",
                "password": PASSWORD,
                "bootstrap_token": token,
            }
            assert (await client.post("/api/setup/init", json=body)).status_code == 403
            await db.rollback()
            assert (
                await client.post(
                    "/api/auth/login",
                    headers={"Origin": "https://foreign.invalid"},
                    json={"email": EMAIL, "password": PASSWORD},
                )
            ).status_code == 403
            assert (
                await client.get(
                    "/api/setup/status", headers={"Host": "foreign.invalid"}
                )
            ).status_code == 403
            assert await db.scalar(select(func.count()).select_from(User)) == 0
    finally:
        app.dependency_overrides.clear()


async def test_latched_hosted_state_never_falls_back_to_public_ce_setup(
    db, hosted, monkeypatch
):
    await issuer(db, hosted)
    monkeypatch.setattr(hosted, "moimio_tenant_id", "")
    monkeypatch.setattr(hosted, "public_origin", "")
    client = await api(db)
    try:
        async with client:
            assert (await client.get("/api/setup/status")).status_code == 503
            assert (
                await client.post(
                    "/api/setup/init",
                    json={
                        "email": EMAIL,
                        "full_name": "Fictional buyer",
                        "password": PASSWORD,
                    },
                )
            ).status_code == 503
            assert await db.scalar(select(func.count()).select_from(User)) == 0
    finally:
        app.dependency_overrides.clear()


async def test_private_issuer_does_not_reissue_on_lost_notification(db, hosted):
    await issuer(db, hosted)
    with pytest.raises(ValueError, match="ALREADY_ESTABLISHED"):
        await issuer(db, hosted)
    await db.rollback()
    assert await db.scalar(select(func.count()).select_from(BootstrapGrant)) == 1
    assert await db.scalar(select(func.count()).select_from(User)) == 0


async def test_ce_setup_and_http_login_still_work(db):
    client = await api(db)
    try:
        async with client:
            assert (await client.get("/api/setup/status")).json()["needs_setup"] is True
            assert (
                await client.post(
                    "/api/setup/init",
                    json={
                        "email": EMAIL,
                        "full_name": "Fictional CE owner",
                        "password": PASSWORD,
                    },
                )
            ).status_code == 201
            assert (
                await client.post(
                    "/api/auth/login", json={"email": EMAIL, "password": PASSWORD}
                )
            ).status_code == 200
    finally:
        app.dependency_overrides.clear()


async def test_pinned_reset_url_refuses_forwarded_host_substitution(
    db, hosted, monkeypatch
):
    from app.api import auth

    token = await issuer(db, hosted)
    deliveries = []
    monkeypatch.setattr(
        auth, "send_password_reset_email", lambda *args: deliveries.append(args)
    )
    client = await api(db)
    try:
        async with client:
            await client.post(
                "/api/setup/init",
                json={
                    "email": EMAIL,
                    "full_name": "Fictional buyer",
                    "password": PASSWORD,
                    "bootstrap_token": token,
                },
            )
            assert (
                await client.post(
                    "/api/auth/request-reset",
                    json={"email": EMAIL},
                    headers={
                        "X-Forwarded-Host": "foreign.invalid",
                        "X-Forwarded-Proto": "http",
                    },
                )
            ).status_code == 200
            assert len(deliveries) == 1 and deliveries[0][2].startswith(
                ORIGIN + "/reset-password?token="
            )
            assert "foreign.invalid" not in deliveries[0][2]
            raw = deliveries[0][2].split("token=")[1]
            assert (
                await db.scalar(select(User))
            ).password_reset_token == access.token_digest(raw)
            assert (
                await client.post(
                    "/api/auth/reset-password",
                    json={"token": raw, "new_password": PASSWORD + "-changed"},
                )
            ).status_code == 200
            assert (
                await client.post(
                    "/api/auth/reset-password",
                    json={"token": raw, "new_password": PASSWORD},
                )
            ).status_code == 400
    finally:
        app.dependency_overrides.clear()
