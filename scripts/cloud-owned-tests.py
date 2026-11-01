"""Disposable Core test launcher; never accepts an existing database URL."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import secrets
import pgserver

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="moimio-core-owned-tests-") as folder:
    server = pgserver.get_server(Path(folder) / "pg", cleanup_mode="delete")
    try:
        uri = server.get_uri().replace("postgresql://", "postgresql+asyncpg://", 1)
        env = {
            k: v
            for k, v in os.environ.items()
            if k in ("PATH", "LANG", "TZ", "SYSTEMROOT")
        }
        env.update(
            {
                "HOME": folder,
                "DATABASE_URL": uri,
                "TEST_DATABASE_URL": uri,
                "PYTHONPATH": str(root / "backend"),
                "SECRET_KEY": secrets.token_urlsafe(40),
                "FEATURE_OUTBOUND_WEBHOOKS": "true",
                "SMTP_HOST": "",
            }
        )
        # Refuse dotenv files, never inspect their values.
        if (root / "backend/.env").exists():
            raise RuntimeError("OWNED_TEST_DOTENV_REFUSED")
        result = subprocess.run(
            [sys.executable, "-c", """import socket,sys
original=socket.socket.connect
original_ex=socket.socket.connect_ex
def connect(s,a):
    if s.family != socket.AF_UNIX: raise AssertionError('CORE_TEST_EXTERNAL_TCP_REFUSED')
    return original(s,a)
def connect_ex(s,a):
    if s.family != socket.AF_UNIX: raise AssertionError('CORE_TEST_EXTERNAL_TCP_REFUSED')
    return original_ex(s,a)
socket.socket.connect=connect
socket.socket.connect_ex=connect_ex
import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
""", "-q", "--tb=short", *sys.argv[1:]],
            cwd=root / "backend",
            env=env,
        )
        raise SystemExit(result.returncode)
    finally:
        server.cleanup()
