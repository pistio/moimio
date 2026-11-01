"""Public URLs: Hosted pins public_origin; CE supports direct self-hosting.

Forwarded headers never supply authority. HTTPS reverse proxies must configure
public_origin explicitly; no environment label relaxes Hosted requirements.
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
