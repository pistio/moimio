"""Tiny Moimio API client shared by the demo-kit scripts.

Configuration (environment variables):
  MOIMIO_URL             Backend base URL. Default http://127.0.0.1:8000
                         (inside the backend container: http://localhost:8000).
  MOIMIO_ADMIN_EMAIL     Super Admin email.     Default admin@example.org
  MOIMIO_ADMIN_PASSWORD  Super Admin password.  Required (no default).
  MOIMIO_ADMIN_NAME      Name used if the Super Admin has to be created
                         through first-run setup. Default "Hannah Becker".

Only needs `httpx` (already installed in the Moimio backend image).
"""
import os
import sys
import time

import httpx

BASE_URL = os.environ.get("MOIMIO_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_EMAIL = os.environ.get("MOIMIO_ADMIN_EMAIL", "admin@example.org")
ADMIN_NAME = os.environ.get("MOIMIO_ADMIN_NAME", "Hannah Becker")


def admin_password() -> str:
    pw = os.environ.get("MOIMIO_ADMIN_PASSWORD")
    if not pw:
        sys.exit("MOIMIO_ADMIN_PASSWORD is not set.")
    return pw


client = httpx.Client(base_url=BASE_URL, timeout=120)


def req(method: str, path: str, **kw):
    """Call the API; retry on 429 (registration rate limit); raise on error."""
    for _ in range(10):
        r = client.request(method, path, **kw)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", "60"))
            print(f"  rate limited on {path}, waiting {wait}s ...", flush=True)
            time.sleep(wait)
            continue
        if r.status_code >= 400:
            print("ERROR", method, path, r.status_code, r.text[:500], file=sys.stderr)
            r.raise_for_status()
        return r.json() if r.content else None
    raise RuntimeError(f"still rate limited: {method} {path}")


def ensure_admin() -> None:
    """Create the first Super Admin via first-run setup if the instance is empty."""
    if req("GET", "/api/setup/status").get("needs_setup"):
        req("POST", "/api/setup/init", json={
            "email": ADMIN_EMAIL, "full_name": ADMIN_NAME, "password": admin_password()})
        print(f"created Super Admin {ADMIN_EMAIL}")


def login(email: str | None = None, password: str | None = None) -> None:
    r = client.post("/api/auth/login", json={
        "email": email or ADMIN_EMAIL, "password": password or admin_password()})
    r.raise_for_status()
    client.headers["Authorization"] = "Bearer " + r.json()["access_token"]
