#!/usr/bin/env bash
# Reset the public Moimio demo workspace to the demo dataset.
#
#   reset_demo.sh          full reset (wipe database, restore, re-open)
#   reset_demo.sh check    reset only if the demo login no longer works
#
# Runs on the host that runs the demo tenant's docker compose stack
# (backend/deploy/production.yml + compose/demo.override.yml). Needs only
# docker and openssl on the host; every Moimio step runs inside the backend
# container with the app's own commands:
#   alembic (on container start)   -> empty schema
#   post_restore.py ensure-admin   -> throw-away Super Admin (first-run setup)
#   python -m app.cli.import_all   -> the demo events, original names
#   post_restore.py finish         -> dates, open registration, demo login
#
# Settings: environment variables, or a file named by DEMO_KIT_CONF
# (default: <kit>/reset.conf) with KEY=value lines.
#   DEMO_COMPOSE_FILE   path to production.yml                  (required)
#   DEMO_ENV_FILE       path to the tenant's demo.env           (required)
#   DEMO_USER_PASSWORD  password of the published demo login    (required)
#   DEMO_USER_EMAIL     published demo login                    [demo@example.org]
#   DEMO_PROJECT        compose project name                    [moimio-demo]
#   DEMO_OVERRIDE_FILE  [<kit>/compose/demo.override.yml]
#   DEMO_DATASET        [<kit>/dataset/moimio-demo-workspace.zip]
#   DEMO_DATES          live | registration | keep              [live]
set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONF="${DEMO_KIT_CONF:-$KIT/reset.conf}"
# shellcheck disable=SC1090
[ -f "$CONF" ] && { set -a; . "$CONF"; set +a; }

: "${DEMO_COMPOSE_FILE:?set DEMO_COMPOSE_FILE (path to production.yml)}"
: "${DEMO_ENV_FILE:?set DEMO_ENV_FILE (path to the tenant .env)}"
: "${DEMO_USER_PASSWORD:?set DEMO_USER_PASSWORD}"
DEMO_USER_EMAIL="${DEMO_USER_EMAIL:-demo@example.org}"
DEMO_PROJECT="${DEMO_PROJECT:-moimio-demo}"
DEMO_OVERRIDE_FILE="${DEMO_OVERRIDE_FILE:-$KIT/compose/demo.override.yml}"
DEMO_DATASET="${DEMO_DATASET:-$KIT/dataset/moimio-demo-workspace.zip}"
DEMO_DATES="${DEMO_DATES:-live}"

dc() { docker compose -p "$DEMO_PROJECT" -f "$DEMO_COMPOSE_FILE" -f "$DEMO_OVERRIDE_FILE" --env-file "$DEMO_ENV_FILE" "$@"; }
log() { echo "[$(date -u +%FT%TZ)] $*"; }

# Run one of the kit's Python scripts inside the backend container.
kit_py() {
  dc exec -T \
    -e MOIMIO_URL=http://localhost:8000 \
    -e MOIMIO_ADMIN_EMAIL="${ADMIN_EMAIL:-}" -e MOIMIO_ADMIN_PASSWORD="${ADMIN_PASSWORD:-}" \
    -e MOIMIO_ADMIN_NAME="Demo Operator" \
    -e DEMO_USER_EMAIL="$DEMO_USER_EMAIL" -e DEMO_USER_PASSWORD="$DEMO_USER_PASSWORD" \
    -e DEMO_DATES="$DEMO_DATES" \
    backend python "/tmp/demo-kit/$1" "${@:2}"
}

copy_kit() {
  dc exec -T backend mkdir -p /tmp/demo-kit
  for f in "$KIT"/scripts/*.py "$DEMO_DATASET"; do dc cp "$f" "backend:/tmp/demo-kit/"; done
}

wait_backend() {
  for _ in $(seq 1 60); do
    if dc exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  log "backend did not become healthy"; dc logs --tail 50 backend; exit 1
}

if [ "${1:-reset}" = "check" ]; then
  copy_kit
  if kit_py post_restore.py check; then dc exec -T backend rm -rf /tmp/demo-kit; exit 0; fi
  log "demo is broken, resetting"
fi

log "closing the demo to visitors"
dc stop frontend backend

log "wiping the database"
dc up -d db mailpit
for _ in $(seq 1 30); do dc exec -T db sh -c 'pg_isready -U "$POSTGRES_USER"' >/dev/null 2>&1 && break; sleep 1; done
dc exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS \"$POSTGRES_DB\" WITH (FORCE);" \
  -c "CREATE DATABASE \"$POSTGRES_DB\" OWNER \"$POSTGRES_USER\";"'

log "starting the backend (applies migrations)"
dc up -d backend
wait_backend
copy_kit

# A fresh Super Admin every night; nobody needs to know its password. Its
# address is unguessable, so nobody can request a password reset for it
# through the public Mailpit inbox.
ADMIN_EMAIL="ops-$(openssl rand -hex 8)@example.org"
ADMIN_PASSWORD="$(openssl rand -hex 24)"

log "restoring the demo dataset"
kit_py post_restore.py ensure-admin
dc exec -T backend python -m app.cli.import_all --in "/tmp/demo-kit/$(basename "$DEMO_DATASET")" --as "$ADMIN_EMAIL"
kit_py post_restore.py finish

if [ "$DEMO_DATES" = "live" ]; then
  log "moving check-in times to the first afternoon of the event"
  dc exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
WITH o AS (
  SELECT p.id, e.start_date, e.timezone,
         row_number() OVER (PARTITION BY p.event_id ORDER BY p.participant_number) AS rn
  FROM participants p JOIN events e ON e.id = p.event_id
  WHERE p.checked_in AND e.start_date IS NOT NULL)
UPDATE participants p
   SET checked_in_at = ((o.start_date + time '14:05') AT TIME ZONE o.timezone) + o.rn * interval '4 min 17 sec'
  FROM o WHERE o.id = p.id;
SQL
fi

log "emptying the Mailpit inbox"
dc exec -T backend python -c "
import urllib.request
urllib.request.urlopen(urllib.request.Request('http://mailpit:8025/mail/api/v1/messages', method='DELETE'))" \
  || log "could not empty Mailpit (not fatal)"

dc exec -T backend rm -rf /tmp/demo-kit
log "opening the demo to visitors"
dc up -d frontend
log "done"
