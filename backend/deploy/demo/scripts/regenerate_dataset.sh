#!/usr/bin/env bash
# Rebuild the demo dataset from scratch, e.g. for a new Moimio version.
#
#   regenerate_dataset.sh /path/to/production.yml [OUT_DIR]
#
# Starts a throw-away Moimio stack (project "moimio-demo-build", its own
# database volume, no published ports), seeds it with seed_demo.py, exports
# it with the app's own `python -m app.cli.export_all`, splits the archive
# into per-event backups, and deletes the stack again (`down -v`).
#
# Image versions come from compose/demo.override.yml: bump them there first.
# Output (default <kit>/dataset):
#   moimio-demo-workspace.zip        whole-workspace archive (for reset_demo.sh)
#   moimio-backup-<event>.zip        one backup per event (for the Backup page)
#
# Optional: DEMO_START_DATE / DEMO_END_DATE (see seed_demo.py).
# Needs docker and openssl on the host.
set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROD="${1:?usage: regenerate_dataset.sh /path/to/production.yml [OUT_DIR]}"
OUT="${2:-$KIT/dataset}"
WORK="$(mktemp -d)"
trap 'dc down -v >/dev/null 2>&1 || true; rm -rf "$WORK"' EXIT

cat > "$WORK/build.env" <<EOF
SUBDOMAIN=demo-build
POSTGRES_USER=moimio
POSTGRES_PASSWORD=$(openssl rand -hex 16)
POSTGRES_DB=moimio
SECRET_KEY=$(openssl rand -hex 32)
CORS_ORIGINS=http://localhost
RATE_LIMIT_REGISTRATION=0
SMTP_HOST=mailpit
SMTP_PORT=1025
SMTP_USER=build
SMTP_PASSWORD=build
SMTP_FROM_EMAIL=noreply@example.org
SMTP_TLS=false
FEATURE_ALLOCATION=true
FEATURE_OUTBOUND_WEBHOOKS=false
MOIMIO_TENANT_ID=demo-build
MOIMIO_WEBHOOK_URL=https://control-plane.invalid/unused
MOIMIO_WEBHOOK_SECRET=unused
EOF

dc() { docker compose -p moimio-demo-build -f "$PROD" -f "$KIT/compose/demo.override.yml" --env-file "$WORK/build.env" "$@"; }

docker network inspect moimio-public >/dev/null 2>&1 || docker network create moimio-public >/dev/null
dc up -d db
# --no-deps: no Mailpit for the build (registration mails simply fail to
# send, which is harmless), and nothing joins the shared public network.
dc up -d --no-deps backend
for _ in $(seq 1 60); do
  dc exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" >/dev/null 2>&1 && break
  sleep 2
done

dc exec -T backend mkdir -p /tmp/demo-kit
for f in "$KIT"/scripts/*.py; do dc cp "$f" backend:/tmp/demo-kit/; done
dc exec -T -e MOIMIO_URL=http://localhost:8000 -e MOIMIO_ADMIN_PASSWORD="$(openssl rand -hex 16)" \
  -e DEMO_START_DATE="${DEMO_START_DATE:-2027-07-23}" -e DEMO_END_DATE="${DEMO_END_DATE:-2027-07-27}" \
  backend python /tmp/demo-kit/seed_demo.py
dc exec -T backend python -m app.cli.export_all --out /tmp/demo-kit/moimio-demo-workspace.zip

mkdir -p "$OUT"
dc cp backend:/tmp/demo-kit/moimio-demo-workspace.zip "$OUT/moimio-demo-workspace.zip"
dc exec -T backend python /tmp/demo-kit/split_archive.py /tmp/demo-kit/moimio-demo-workspace.zip /tmp/demo-kit/split
for f in $(dc exec -T backend sh -c 'ls /tmp/demo-kit/split'); do
  dc cp "backend:/tmp/demo-kit/split/$f" "$OUT/$f"
done
echo "dataset written to $OUT"
