"""Public-facing URL derivation.

Email links (registration confirmation, password reset, etc.) are built
from the base URL the user actually hit, not from a pinned environment
variable. Reasons:

  - Self-hosters deploy onto whatever domain they own. The scaffold
    shouldn't require them to hand-configure a URL env var for basic
    functionality to work.
  - Container-per-tenant SaaS deployments (each tenant on their own
    backend at <tenant>.moimio.app) still benefit from this: a single
    image build serves any subdomain the operator points at it without
    a per-tenant URL config step.
  - Operator ergonomics: one fewer piece of configuration to get right.

Derivation order:
  1. X-Forwarded-Proto + X-Forwarded-Host — set by Caddy's reverse_proxy
     on every backend request in our standard deployment, and the
     convention any sane reverse proxy uses. Covers the Cloudflare
     tunnel case, LAN-IP deploys, any reverse-proxied topology.
  2. request.url.scheme + the raw Host header — direct uvicorn access
     during local dev without Caddy in front.
  3. request.base_url — last-resort synthesised by Starlette; kept so
     the function always returns *something* rather than raising.

Security note: this pattern trusts the Host header that reaches the
backend. In our deployment the backend port is not exposed outside the
Docker network, so only Caddy (which we control) ever sets these
headers. If a future deployment exposes the backend directly, a
trusted-host allowlist would be a sensible hardening step — but we'll
cross that when we get there.
"""

from fastapi import Request


def get_app_base_url(request: Request) -> str:
    """Return the public-facing base URL for this request (no trailing slash)."""
    from app.core.config import get_settings
    from app.services.hosted_access import configured_hosted, origin_value
    settings = get_settings()
    if settings.public_origin:
        return origin_value(settings.public_origin) if configured_hosted() else settings.public_origin.rstrip('/')
    if configured_hosted():
        raise ValueError('HOSTED_PUBLIC_ORIGIN_REQUIRED')
    # Self-hosted direct HTTP stays supported. Forwarded headers are not a
    # trusted URL authority; reverse proxies must configure public_origin.
    return str(request.base_url).rstrip('/')
