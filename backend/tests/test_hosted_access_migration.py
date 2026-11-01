"""Actual upgrade preserving existing users, no grant/session backfill."""
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
import pgserver
import psycopg


def test_actual_107_to_108_preserves_users_and_refuses_downgrade(tmp_path):
    root = Path(__file__).resolve().parents[1]
    server=pgserver.get_server(tmp_path/'migration-pg',cleanup_mode='delete')
    try:
        uri=server.get_uri()
        env={**os.environ,'DATABASE_URL':uri.replace('postgresql://','postgresql+asyncpg://',1)}
        def alembic(*args):
            return subprocess.run([sys.executable,'-m','alembic',*args],cwd=root,env=env,capture_output=True,text=True,timeout=60)
        result=alembic('upgrade','107a00000')
        assert result.returncode == 0, result.stderr[-1800:]
        uid=str(uuid4())
        with psycopg.connect(uri) as c:
            c.execute("INSERT INTO users(id,email,hashed_password,full_name,role,is_active,can_manage_users,can_create_events) VALUES (%s,%s,%s,%s,'super_admin',true,true,true)",
                      (uid,'owner@migration.fictional.example','fictional-not-a-password-hash','Fictional existing owner'))
        assert alembic('upgrade','head').returncode == 0
        with psycopg.connect(uri) as c:
            assert c.execute('SELECT count(*) FROM users WHERE id=%s',(uid,)).fetchone() == (1,)
            assert c.execute('SELECT count(*) FROM auth_sessions').fetchone() == (0,)
            assert c.execute('SELECT count(*) FROM hosted_bootstrap_grants').fetchone() == (0,)
            assert c.execute('SELECT version_num FROM alembic_version').fetchone() == ('108a00000',)
        refused=alembic('downgrade','107a00000')
        assert refused.returncode != 0 and 'HOSTED_ACCESS_UNSAFE_DOWNGRADE_REVIEW_REQUIRED' in refused.stderr
        with psycopg.connect(uri) as c:
            assert c.execute('SELECT version_num FROM alembic_version').fetchone() == ('108a00000',)
    finally:
        server.cleanup()
