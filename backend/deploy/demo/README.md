# Moimio demo kit

Everything needed to run the public Moimio demo workspace (Moimio v1.0.7).
Start with **RUNBOOK.md**. All data is invented; every address is `@example.org`.

| File | What it is |
|---|---|
| `RUNBOOK.md` | How to set up, load, publish and reset the demo. |
| `dataset/moimio-demo-workspace.zip` | The demo data as a whole-workspace export (`python -m app.cli.export_all`). Loaded by `reset_demo.sh` via `python -m app.cli.import_all`. |
| `dataset/moimio-backup-youth-retreat-2027.zip` | Main event alone, a normal event backup for **Backup ▸ From backup**. 51 people, rooms, small groups, marks, check-in. |
| `dataset/moimio-backup-jugendfreizeit-2027-de.zip` | German registration form, no people. |
| `dataset/moimio-backup-youth-retreat-2027-ko.zip` | Korean registration form, no people. |
| `compose/demo.override.yml` | Second compose file for the tenant: v1.0.7 images and a Mailpit mail catcher. |
| `compose/demo.env.example` | Tenant `.env` for the demo (demo notice, SMTP to Mailpit, webhooks off, rate limit). |
| `reset.conf.example` | Settings for `reset_demo.sh`. |
| `scripts/reset_demo.sh` | Wipes the tenant database and restores the demo (`check` = only if the demo login is broken). For cron. |
| `scripts/post_restore.py` | After a restore: event dates, open registration, demo login as Event Admin. Also `ensure-admin` and `check`. |
| `scripts/seed_demo.py` | Builds the demo data from nothing through the API (deterministic). |
| `scripts/regenerate_dataset.sh` | Rebuilds `dataset/` for a new Moimio version in a throw-away stack. |
| `scripts/split_archive.py` | Splits the workspace export into per-event backup ZIPs. |
| `scripts/moimio_api.py` | Small API client used by the Python scripts (`MOIMIO_URL`, `MOIMIO_ADMIN_EMAIL`, `MOIMIO_ADMIN_PASSWORD`). |

The Python scripts need only `httpx`, which the Moimio backend image already
has; the shell scripts run them inside the backend container.
