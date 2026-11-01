"""Application configuration via environment variables."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Canonical public origin for Hosted auth/reset links; never trust forwarded hosts.
    public_origin: str = ""

    # ─── Database ───
    database_url: str = "postgresql+asyncpg://moimio:moimio_dev@db:5432/moimio"

    # ─── Auth ───
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 1440  # 24 hours
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"

    # ─── App ───
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:6120"
    rate_limit_registration: int = 60  # sign-ups per minute per address; 0 = off

    # ─── Capability flags (v1.0.0g) ───
    #
    # Capability-not-commercial naming. CE does not know which capabilities
    # are "premium" — these are framed as generic toggles that any
    # self-hoster might legitimately want. SaaS sets per-tenant values via
    # the standard env-var surface; CE never gains tier awareness.
    #
    # FEATURE_ALLOCATION: when false, the allocation engine and its router
    # are excluded entirely. Bucket 4 §2: enables a registration-only
    # deployment for SaaS Registration tier and for self-hosters who don't
    # need group/room assignment.
    #
    # FEATURE_OUTBOUND_WEBHOOKS: when false, the outbound webhook
    # subsystem (admin UI, router, scheduler jobs) is hidden. Default ON
    # so self-hosters get the integration capability; SaaS can opt out
    # per tenant if a tier shouldn't expose it.
    feature_allocation: bool = True
    feature_outbound_webhooks: bool = True
    # v1.0.4a: WEBHOOK_ALLOW_PRIVATE_TARGETS. Outbound webhooks refuse
    # targets on private, loopback, link-local and similar addresses (see
    # app/services/webhook_url_policy.py). A self-hoster delivering to an
    # internal tool on their own network may switch this on. The hosted
    # edition never sets it. Default OFF: fail closed.
    webhook_allow_private_targets: bool = False
    # v1.0.1e-6: FEATURE_ACCOUNT_PORTAL — is this instance managed by the
    # Moimio SaaS control-plane (so the external account/billing portal link
    # is meaningful)? Defaults FALSE: the self-hosted CE is the source of
    # truth, and a self-hoster has no SaaS portal even if they set an
    # account_url for their own reasons. The SaaS sets this true per tenant.
    # This replaces the old, wrong criterion of "account_url is non-empty".
    feature_account_portal: bool = False

    # ─── Create-event confirmation (v1.0.0h) ───
    #
    # When true, the event-create flow surfaces a confirmation dialog
    # before completing the POST. The dialog renders the three billing-
    # info values below (amount + currency + card last-4) so the admin
    # sees what will be charged before committing.
    #
    # CE default: false. Self-hosters never see a dialog. SaaS sets
    # this to true at provisioning for tenants on the per-event plan.
    #
    # Capability-not-commercial naming: this flag describes the UI
    # capability (a confirmation step), not why a commercial provider
    # would want it (billing).
    feature_create_event_confirmation: bool = False

    # v1.0.0w (prepaid-credit model): where CE's "buy a credit" button in
    # the out-of-credits notice points. Read at runtime via GET
    # /api/billing-info so the SaaS can change it without a CE rebuild.
    # Empty = no self-serve link, and CE omits the button. Self-hosters
    # never set it.
    buy_credit_url: str = ""

    # v1.0.0aa: where CE's "Manage account" sidebar link points. The SaaS
    # injects its account-portal URL here; CE reads it via GET
    # /api/capabilities and shows the link only when it's non-empty. Empty
    # = no link, and CE omits it (self-hosters never set it). Like
    # buy_credit_url this is a SaaS-managed *value*, not a mode flag — CE
    # stays mode-agnostic and simply renders a link if it's given one.
    account_url: str = ""

    # ─── Demo notice (v1.0.4c) ───
    #
    # When true, the frontend shows a non-dismissable notice on every admin
    # page and above the public registration form saying this is a
    # demonstration workspace, mail is captured locally, and no real
    # personal data should be entered. The SaaS sets this per demo tenant;
    # self-hosters never do. Capability, not a mode: CE just renders it.
    feature_demo_notice: bool = False
    # Where the captured mail can be read (the demo's Mailpit inbox). When
    # non-empty the "/mail/" in the notice text becomes a link to it.
    moimio_demo_mail_url: str = ""

    # DEPRECATED (pre-v1.0.0w charge-on-creation model, superseded by the
    # prepaid-credit model in product policy v1). No longer read by the
    # billing-info endpoint. Retained as recognised settings so existing
    # tenant .env files still carrying EVENT_CHARGE_AMOUNT /
    # EVENT_CHARGE_CURRENCY / BILLING_CARD_LAST4 keep parsing on upgrade
    # rather than erroring. Safe to remove once no live .env references them.
    event_charge_amount: str = ""
    event_charge_currency: str = ""
    billing_card_last4: str = ""

    # ─── Tenant identity (v1.0.0h) ───
    #
    # Optional. When set, the value is stamped onto every outbound
    # webhook envelope as a top-level `tenant_id` field. When empty,
    # the field is omitted entirely — self-hosters never see it in
    # their payloads. SaaS provisioning sets this per-tenant at install
    # time so its receiver can route incoming webhooks to the right
    # customer record. CE doesn't interpret the value; it's an opaque
    # string chosen by whoever is provisioning the install.
    moimio_tenant_id: str = ""

    # ─── Participant cap (v1.0.0y) ───
    #
    # Optional. When set (an integer, e.g. 300), CE watches each event's
    # active roster (confirmed + pending, excluding removed) and — the
    # first time it crosses this number — emits ONE `event.over_cap`
    # webhook carrying an APPROXIMATE band (never the exact count) plus
    # this cap value. It never blocks registration; it only signals. When
    # unset (None) CE does no cap check at all, so self-hosters see no
    # change. SaaS provisioning sets this per-tenant from the plan size.
    moimio_participant_cap: int | None = None

    @field_validator("moimio_participant_cap", mode="before")
    @classmethod
    def _blank_participant_cap_is_none(cls, v: object) -> object:
        # An unset env var arrives as None; a present-but-empty one — e.g.
        # Compose's `${MOIMIO_PARTICIPANT_CAP:-}` when nothing is injected —
        # arrives as "". Treat blank/whitespace as "no cap" so a tenant
        # without a cap doesn't fail to start on integer parsing.
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    # ─── SaaS-managed webhook auto-registration (v1.0.0g) ───
    #
    # When both env vars are set at first boot AND no outbound webhook
    # endpoints exist yet, CE auto-creates a SaaS-managed endpoint
    # subscribing to all event types. The endpoint is flagged
    # `managed_by="saas"` and is hidden from the admin UI; self-hosters
    # never see it because they never set these env vars.
    #
    # Bucket 4 §1 reinforcement: CE doesn't know SaaS exists. These env
    # vars are framed as "automatic webhook configuration via environment"
    # — a feature self-hosters with deployment automation might also use.
    moimio_webhook_url: str = ""
    moimio_webhook_secret: str = ""

    # ─── Outbound webhook delivery log retention (v1.0.0g) ───
    #
    # The `outbound_webhook_deliveries` table grows with every webhook
    # attempt. 30 days is enough for any practical debugging conversation
    # and keeps the table small. Pruned daily by a scheduled job.
    webhook_delivery_retention_days: int = 30

    # NOTE: v0.61b-2 removed the `app_url` setting. Public URLs for email
    # links (registration confirmation, password reset) are now derived
    # from the incoming request via app.core.urls.get_app_base_url, so
    # self-hosters on different domains and future multi-domain SaaS
    # deployments don't need to pin a canonical URL in .env. Any lingering
    # APP_URL=... line in an existing .env file is silently ignored by
    # pydantic-settings and can be removed.

    # ─── Email (SMTP) ───
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Moimio"
    smtp_tls: bool = True       # STARTTLS on port 587
    smtp_ssl: bool = False      # Implicit SSL on port 465

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_user)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
