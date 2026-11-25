"""Make a freshly restored demo workspace ready for visitors.

A restore (Backup page or `python -m app.cli.import_all`) deliberately brings
every event back as a DRAFT with its Setup cards unticked, so visitors would
land in the Setup hub and the public registration form would be closed.
This script, run right after the restore:

  1. moves the event dates (see DEMO_DATES below),
  2. re-ticks the two Setup cards and opens registration again,
  3. creates the public demo login (a Staff account with no extra
     capabilities) and makes it Event Admin of every demo event.

It is idempotent: running it twice changes nothing the second time except
the dates.

Subcommands:
    python post_restore.py ensure-admin   # create the Super Admin on an empty
                                          # instance (first-run setup), needed
                                          # before `import_all --as ...`
    python post_restore.py finish         # steps 1-3
    python post_restore.py check          # exit 1 unless the demo login works
                                          # and sees an open event

Environment:
  MOIMIO_URL, MOIMIO_ADMIN_EMAIL, MOIMIO_ADMIN_PASSWORD, MOIMIO_ADMIN_NAME
                         see moimio_api.py (the Super Admin; keep it private)
  DEMO_USER_EMAIL        public demo login.     Default demo@example.org
  DEMO_USER_PASSWORD     its password.          Required for `finish`.
  DEMO_USER_NAME         its display name.      Default "Demo Organiser"
  DEMO_DATES             live (default) | registration | keep
      live          start = yesterday, end = today + 3. The app shows the
                    Event phase, sub-state Live: Organise board as home,
                    "Enter check-in mode" button, "Registration is still
                    open" banner, and the public form still accepts sign-ups.
      registration  start = today + 60, end = today + 64. The app shows the
                    Registration phase: registration dashboard as home,
                    Organise and People available, but no check-in button
                    (check-in only via /admin/events/<id>/checkin).
      keep          leave the dates in the backup (23-27 July 2027).
  DEMO_SYNC_YEAR         1 (default) replaces "2027" in the event names with
                         the year of the new start date; 0 leaves names alone.
"""
import datetime as dt
import os
import sys

from moimio_api import client, ensure_admin, login, req

DEMO_EMAIL = os.environ.get("DEMO_USER_EMAIL", "demo@example.org")
DEMO_NAME = os.environ.get("DEMO_USER_NAME", "Demo Organiser")
MODE = os.environ.get("DEMO_DATES", "live")
SYNC_YEAR = os.environ.get("DEMO_SYNC_YEAR", "1") == "1"
SEED_YEAR = "2027"


def new_dates(today: dt.date):
    if MODE == "live":
        return today - dt.timedelta(days=1), today + dt.timedelta(days=3)
    if MODE == "registration":
        return today + dt.timedelta(days=60), today + dt.timedelta(days=64)
    if MODE == "keep":
        return None
    sys.exit(f"DEMO_DATES must be live, registration or keep (got {MODE!r})")


def ensure_demo_user() -> str:
    pw = os.environ.get("DEMO_USER_PASSWORD")
    if not pw:
        sys.exit("DEMO_USER_PASSWORD is not set.")
    for u in req("GET", "/api/users/"):
        if u["email"].lower() == DEMO_EMAIL.lower():
            return u["id"]
    u = req("POST", "/api/users/", json={
        "email": DEMO_EMAIL, "full_name": DEMO_NAME, "password": pw, "role": "staff",
        "can_manage_users": False, "can_create_events": False})
    print(f"created demo login {DEMO_EMAIL}")
    return u["id"]


def finish():
    login()
    user_id = ensure_demo_user()
    dates = new_dates(dt.date.today())
    for ev in req("GET", "/api/events/"):
        eid = ev["id"]
        if ev.get("is_archived"):
            continue
        if dates:
            patch = {"start_date": dates[0].isoformat(), "end_date": dates[1].isoformat()}
            if SYNC_YEAR and SEED_YEAR in ev["name"]:
                patch["name"] = ev["name"].replace(SEED_YEAR, str(dates[0].year))
            ev = req("PATCH", f"/api/events/{eid}", json=patch)
        if ev["status"] != "open":
            req("POST", f"/api/events/{eid}/setup/confirm/details")
            req("POST", f"/api/events/{eid}/setup/confirm/registration")
            ev = req("POST", f"/api/events/{eid}/registration/open")
        team = req("GET", f"/api/events/{eid}/assignments/")
        if not any(str(a.get("user_id")) == str(user_id) for a in team):
            req("POST", f"/api/events/{eid}/assignments/", json={"user_id": user_id, "role": "event_admin"})
        print(f"ready: {ev['name']}  {ev['start_date']} - {ev['end_date']}  status={ev['status']}")


def check():
    """Can a visitor still use the demo? (password changed via the public
    inbox, team membership removed, registration closed ... -> reset)"""
    pw = os.environ.get("DEMO_USER_PASSWORD")
    if not pw:
        sys.exit("DEMO_USER_PASSWORD is not set.")
    try:
        login(DEMO_EMAIL, pw)
        events = req("GET", "/api/events/")
    except Exception as exc:  # noqa: BLE001 - any failure means "broken"
        print(f"demo login broken: {exc}")
        sys.exit(1)
    if not any(e["status"] == "open" and not e.get("is_archived") for e in events):
        print("demo login works but sees no open event")
        sys.exit(1)
    print(f"demo login OK, {len(events)} event(s)")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "ensure-admin":
        ensure_admin()
    elif cmd == "finish":
        finish()
    elif cmd == "check":
        check()
    else:
        sys.exit(__doc__)
    client.close()


if __name__ == "__main__":
    main()
