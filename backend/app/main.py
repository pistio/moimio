"""Moimio — FastAPI application factory."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.exceptions import MoimioAppError
from fastapi.exceptions import RequestValidationError
from app.core.logging import setup_logging, get_logger
from app.core.middleware import CorrelationIDMiddleware
from app.core.database import engine, async_session_factory
from app.core.scheduler import start_scheduler, stop_scheduler
from app.services import webhook_service
from app.api.health import router as health_router
from app.api.capabilities import router as capabilities_router
from app.api.auth import router as auth_router
from app.api.events import router as events_router
from app.api.participants import router as participants_router
from app.api.allocations import router as allocations_router
from app.api.custom_fields import router as custom_fields_router
from app.api.export import router as export_router, restore_router
from app.api.user_preferences import router as preferences_router
from app.api.notes import router as notes_router
from app.api.checkin import router as checkin_router
from app.api.marks import router as marks_router
from app.api.stats import router as stats_router
from app.api.setup import router as setup_router
from app.api.users import router as users_router
from app.api.event_assignments import router as assignments_router
from app.api.preferences import router as pref_router
from app.api.streams import router as streams_router
from app.api.outbound_webhooks import router as outbound_webhooks_router
from app.api.billing_info import router as billing_info_router
from app.api.danger_zone import router as danger_zone_router
from app.api.workspace_settings import router as workspace_settings_router
from app.version import __version__

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown events."""
    setup_logging()
    logger.info(
        "moimio_starting",
        version=__version__,
        log_level=settings.log_level,
        feature_allocation=settings.feature_allocation,
        feature_outbound_webhooks=settings.feature_outbound_webhooks,
    )

    from app.services.hosted_access import profile
    async with async_session_factory() as db:
        await profile(db)  # fail before schedulers/provider registration

    # v1.0.0g: register the SaaS-managed webhook endpoint if env vars
    # are set. No-op for self-hosters who haven't configured these.
    if (
        settings.feature_outbound_webhooks
        and settings.moimio_webhook_url
        and settings.moimio_webhook_secret
    ):
        try:
            async with async_session_factory() as db:
                await webhook_service.ensure_saas_endpoint(
                    db,
                    url=settings.moimio_webhook_url,
                    secret=settings.moimio_webhook_secret,
                )
        except Exception:
            logger.exception("moimio_starting.saas_endpoint_register_failed")

    # v1.0.0g: background scheduler for outbound webhook retry + prune.
    # No-op when FEATURE_OUTBOUND_WEBHOOKS is off (no jobs registered).
    start_scheduler()

    yield

    await stop_scheduler()
    await engine.dispose()
    logger.info("moimio_stopped")


app = FastAPI(
    title="Moimio",
    description="Participant allocation platform — register, organise, allocate.",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── Middleware (order matters: last added = first executed) ───
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CorrelationIDMiddleware)

# ─── Exception handlers ───
# v0.70d-3c-2: services raise MoimioAppError (carries i18n key + params + status_code).
# A global handler converts to JSONResponse with the dict-detail shape that
# matches v0.70d-3b's auth/participants/events convention. Per-site try/except
# is no longer required at the api layer — the handler runs once, centrally.
@app.exception_handler(MoimioAppError)
async def moimio_app_error_handler(request: Request, exc: MoimioAppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.to_detail()},
    )

# v1.0.4ze (FORM-1): FastAPI answers its own validation failures with a LIST
# of {loc, msg, type} dicts, in English, naming internal field paths. The
# public registration form was rendering that list under a correctly
# translated heading, so a registrant who mistyped an email address was shown
# the inside of the server.
#
# This turns it into the shape the rest of the app already uses — the same
# {key, params} detail MoimioAppError produces — plus a per-field map so the
# form can mark the box that is wrong rather than printing a paragraph.
#
# The mapping is deliberately small. Five keys cover everything the public
# form can produce; anything else falls to `errors.field.invalid`, which is
# vague on purpose because its cause is unknown by definition.
_FIELD_ERROR_KEYS = {
    "missing": "errors.field.required",
    "string_too_short": "errors.field.too_short",
    "string_too_long": "errors.field.too_long",
    "value_error": "errors.field.invalid",
}


def _field_error_key(err: dict) -> str:
    """One error's i18n key. Email is special-cased because it is the
    commonest rejection by a wide margin and deserves to say so."""
    loc = err.get("loc") or ()
    field = str(loc[-1]) if loc else ""
    etype = str(err.get("type") or "")
    if "email" in field.lower():
        return "errors.field.email"
    return _FIELD_ERROR_KEYS.get(etype, "errors.field.invalid")


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    fields: dict[str, str] = {}
    for err in exc.errors():
        loc = [str(p) for p in (err.get("loc") or ()) if p != "body"]
        if not loc:
            continue
        # First error per field wins: the form marks one message per box.
        fields.setdefault(".".join(loc), _field_error_key(err))
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "key": "errors.validation.summary",
                "params": {},
                # Not part of the {key, params} contract, so an older client
                # that only reads `key` still gets a translated sentence.
                "fields": fields,
            }
        },
    )


# ─── Routers ───
# Always-on routers
app.include_router(health_router)
app.include_router(capabilities_router)
app.include_router(billing_info_router)
app.include_router(auth_router)
app.include_router(events_router)
app.include_router(participants_router)
app.include_router(custom_fields_router)
app.include_router(export_router)
app.include_router(restore_router)
app.include_router(preferences_router)
app.include_router(notes_router)
app.include_router(checkin_router)
app.include_router(marks_router)
app.include_router(stats_router)
app.include_router(setup_router)
app.include_router(users_router)
app.include_router(assignments_router)
app.include_router(pref_router)
app.include_router(streams_router)
app.include_router(danger_zone_router)
app.include_router(workspace_settings_router)

# Capability-gated routers (v1.0.0g)
#
# FEATURE_ALLOCATION (default ON): the allocation engine and its router.
# When off, /api/allocations* endpoints simply don't exist — receivers
# get a clean 404 rather than a runtime error from a half-included
# router. The frontend reads /api/capabilities to hide the corresponding
# nav entries.
if settings.feature_allocation:
    app.include_router(allocations_router)

# FEATURE_OUTBOUND_WEBHOOKS (default ON): admin CRUD for outbound webhooks.
# When off, the admin "Webhooks" section is hidden in the UI and the
# router itself is not registered. The scheduled retry/prune jobs are
# also skipped (see scheduler.start_scheduler).
if settings.feature_outbound_webhooks:
    app.include_router(outbound_webhooks_router)
