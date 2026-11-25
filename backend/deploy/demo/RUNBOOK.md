# Moimio public demo — runbook

For whoever runs the public demo workspace. Tested with Moimio **v1.0.7**
(images `ghcr.io/pistio/moimio-*:v1.0.7`) on 25 Nov 2026.

The demo is an ordinary Moimio tenant (`backend/deploy/production.yml`) with
three additions: a few settings, a Mailpit container that catches all mail,
and a nightly job that puts the demo data back.

---

## 1. What the demo tenant needs

### Settings (the tenant `.env`)

A complete example is in `compose/demo.env.example`. The lines that matter:

| Setting | Demo value | Why |
|---|---|---|
| `FEATURE_DEMO_NOTICE` | `true` | Shows the "This is a demonstration workspace … do not enter real personal data" notice on admin pages and above the public registration form. It only shows the notice; it does not change what the app does. |
| `MOIMIO_DEMO_MAIL_URL` | `https://<demo host>/mail/` | Makes "/mail/" in the notice a link to the Mailpit inbox. |
| `SMTP_HOST` / `SMTP_PORT` | `mailpit` / `1025` | **This is what keeps mail inside.** All mail the app sends goes to this one SMTP server; there is no other mail path. |
| `SMTP_USER` / `SMTP_PASSWORD` | any value, e.g. `demo` | Moimio only sends mail when `SMTP_USER` is set, and always logs in. Mailpit accepts any login. |
| `SMTP_TLS` / `SMTP_SSL` | `false` / `false` | Plain connection inside the tenant network. |
| `RATE_LIMIT_REGISTRATION` | `10` | Public sign-ups per minute per visitor address (enforced from v1.0.7). |
| `FEATURE_OUTBOUND_WEBHOOKS` | `false` | No Webhooks page, and the app sends no signals (`event.created`, `event.allocated`, …) to the control plane while visitors play. |
| `FEATURE_ACCOUNT_PORTAL`, `ACCOUNT_URL` | `false`, empty | No "Manage account" link. |
| `FEATURE_CREATE_EVENT_CONFIRMATION` | `false` | No billing dialog. |
| `MOIMIO_PARTICIPANT_CAP` | empty | No plan cap. |
| `LOG_LEVEL` | `INFO` | `DEBUG` would log participant data. |
| `MOIMIO_WEBHOOK_URL`, `MOIMIO_WEBHOOK_SECRET`, `MOIMIO_TENANT_ID` | placeholders | `production.yml` refuses to start without them; with webhooks off they are never used. |

### Mailpit and the image version (`compose/demo.override.yml`)

`production.yml` has no mail catcher, and in the v1.0.7 release it still
names the **v1.0.5** images. The override file fixes both:

* pins `moimio-backend` / `moimio-frontend` to **v1.0.7** (the demo data uses
  "show only if" fields, and the sign-up rate limit only works from v1.0.7);
* adds a `mailpit` container (no relay configured, so it cannot forward mail),
  with its web inbox under `/mail/`.

Start the tenant with both files:

```sh
docker compose -p moimio-demo -f production.yml -f demo.override.yml --env-file demo.env up -d
```

If the control plane starts the tenant, it must include the override file
(or the same changes), and must not re-render the tenant without it.

### The public `/mail/` address

Route `https://<demo host>/mail/*` to Mailpit in the outer Caddy, in front of
the existing route to the frontend. Mailpit is on the shared `moimio-public`
network as `moimio-demo-mailpit`:

```caddy
demo.example.org {
    handle /mail/* {
        reverse_proxy moimio-demo-mailpit:8025
    }
    # ... the existing route to this tenant's frontend stays below
}
```

---

## 2. Load the demo data

Everything is done by one script, which uses the app's own commands
(database migrations, first-run setup, `python -m app.cli.import_all`):

```sh
cp reset.conf.example reset.conf      # fill in paths + demo password, chmod 600
scripts/reset_demo.sh
```

What it does, in about 30 seconds:

1. stops the frontend (visitors get an error page for a moment) and the backend;
2. drops and recreates the tenant database;
3. starts the backend, which creates the empty tables;
4. creates a throw-away Super Admin with a random address and password
   (nobody needs it; a new one is made at every reset);
5. restores `dataset/moimio-demo-workspace.zip` with `app.cli.import_all`
   (events keep their own names);
6. runs `scripts/post_restore.py finish`: moves the event dates, ticks the two
   Setup cards and opens registration (a restore always brings events back as
   drafts), creates the demo login and makes it Event Admin of each event;
7. moves the check-in times to the first afternoon of the event;
8. empties the Mailpit inbox and starts the frontend again.

**By hand instead** (one event, e.g. on a test server): sign in as a Super
Admin, open **Backup ▸ From backup**, upload
`dataset/moimio-backup-youth-retreat-2027.zip`. It arrives as
"Youth Retreat 2027 (Restored)", as a draft: rename it, tick **Details** and
**Registration** in the Setup hub, then **Open registration**.

### What is in the data

All people are invented; every address ends in `@example.org`.

* **Youth Retreat 2027** (English): 51 people, including the Park and Schmidt
  families and friend groups linked by group code; marks "Leader" and
  "Worship team"; **Rooms** (5 men's, 6 women's, 2 family rooms) and
  **Small groups** (6), both filled by the allocation engine; 3 late sign-ups
  still unassigned; 28 people checked in, with "Paid" and "Welcome pack"
  columns.
* **Jugendfreizeit 2027** (German form) and **청년부 여름 수련회 2027**
  (Korean form): registration forms only, no people, to show the form in
  other languages.

### Event dates (`DEMO_DATES` in `reset.conf`)

Moimio decides what to show from the event's status and dates (the
visitor's own calendar day is compared):

* **Setup** — event is a draft.
* **Registration** — registration is open and the start date is in the future.
  Home is the registration dashboard; Organise and People are available;
  there is **no check-in button**.
* **Event** — registration closed, or the start date has arrived. Home is the
  Organise board with the **Enter check-in mode** button. Sub-state **Live**
  from start to end date, **Done** after the end date.

The public form accepts sign-ups whenever registration is open, whatever the
dates.

| `DEMO_DATES` | Dates set at each reset | What visitors see |
|---|---|---|
| `live` (**recommended**) | start = yesterday, end = today + 3 | Event phase, **Live**: Organise board, check-in mode, People, Reports, "Registration is still open" banner, and the public form still works. Registration, allocation and check-in are all one click away. |
| `registration` | start = today + 60, end = today + 64 | Registration phase: registration dashboard, Organise, People. Check-in only by typing `/admin/events/<id>/checkin`. Already checked-in people look odd before the event. |
| `keep` | 23–27 July 2027, as stored | Registration phase until 22 July 2027, Live 23–27 July, then **Done** for good. Not suitable for a long-running demo. |

With `live`/`registration` the year in the event names follows the new start
date ("Youth Retreat 2026" in November 2026). Because the dates are relative
to the reset day, **the reset must keep running**: after four days without a
reset a `live` event turns into "Done".

---

## 3. The demo login to publish

Publish **one** login, e.g. `demo@example.org` / a password you choose
(`DEMO_USER_PASSWORD`). The reset creates it as:

* a **Staff** account, with **"Allow this admin to manage users" off** and
  **"Can create new events" off**;
* **Event Admin** on each demo event.

Event Admin is the lowest role that can show the whole product: running the
allocation engine and committing it, and editing the form and group types,
are Event-Admin-only (a Staff role with permissions cannot). Checked against
the code (v1.0.7), this login **cannot**:

* delete, archive or unarchive an event, or create a new one;
* restore backups, or see the Backup, Workspace and Webhooks pages;
* see, create, edit or delete user accounts;
* request workspace deletion.

Never publish a Super Admin login.

What visitors **can** do (all undone by the next reset):

* change or delete anything inside the demo events: rename the event, edit
  the form, close registration, delete group types, rooms and marks, clear or
  redo allocations, remove (soft-delete) participants, import a CSV of people;
* download the participant spreadsheet, backups and PDFs — **including
  anything other visitors typed into the public form**;
* change the shared demo password (Preferences), or remove themselves from
  the event team through the API — either locks everyone else out;
* **take over the demo login through the public inbox**: "Forgot password"
  for `demo@example.org` sends the reset link to Mailpit, which anyone can
  read (tested: it works);
* fill the event or inbox with junk or offensive names that later visitors see.

Everyone shares one login, so visitors see each other's changes live.

---

## 4. Automatic reset

Run the full reset every night, and a cheap check every 15 minutes that
resets early if the demo login stops working or sees no open event (e.g.
after a password takeover). Example `/etc/cron.d/moimio-demo` (kit installed
in `/opt/moimio-demo-kit`):

```cron
SHELL=/bin/bash
# nightly reset, 03:17 server time
17 3 * * *    root  flock -n /run/moimio-demo-reset.lock /opt/moimio-demo-kit/scripts/reset_demo.sh       >> /var/log/moimio-demo-reset.log 2>&1
# every 15 min: reset only if the demo login is broken
*/15 * * * *  root  flock -n /run/moimio-demo-reset.lock /opt/moimio-demo-kit/scripts/reset_demo.sh check >> /var/log/moimio-demo-reset.log 2>&1
```

The job needs `docker` (compose v2) and `openssl` on the host and permission
to use Docker. Reset by hand at any time with `scripts/reset_demo.sh`.

---

## 5. Risks and what the operator must handle outside the app

* **Mail.** The demo notice does not stop mail. Only `SMTP_HOST=mailpit`
  does: the app has a single SMTP sender, configured from the environment,
  with no per-event server. If `SMTP_HOST` pointed at a real mail service,
  visitors could make the demo send confirmation mail to any address they
  type in. Check `SMTP_HOST` after every re-provisioning. Mailpit must not
  get relay options (`MP_SMTP_RELAY_*`).
* **The inbox is public.** Every message, including password-reset links,
  can be read by anyone. That is why the Super Admin is random and recreated
  each night, and why the 15-minute check exists.
* **Real personal data.** The notice asks visitors not to enter real data,
  but nothing prevents it, and anything entered is visible to every other
  visitor (People, exports, Mailpit) until the next reset. The notice is not
  shown on the login page or in full-screen check-in. Consider a privacy
  notice URL for the demo (Super Admin ▸ Workspace) and keep the reset daily.
* **Form spam.** `RATE_LIMIT_REGISTRATION` limits sign-ups per visitor address
  only; there is no CAPTCHA. Many addresses can still flood the event.
  The nightly reset clears it; Mailpit keeps at most 500 messages.
* **Abuse of the shared login** (see §3): only the reset repairs it.
* **Images.** Keep the override's image tags equal to the version on the
  website. For a new version, rebuild the dataset (below).

---

## 6. New Moimio version: rebuild the dataset

1. Set the new image tags in `compose/demo.override.yml`.
2. Run `scripts/regenerate_dataset.sh /path/to/production.yml` — it starts a
   throw-away stack, seeds it with `scripts/seed_demo.py`, exports it with
   `python -m app.cli.export_all`, writes the files into `dataset/`, and
   removes the stack.
3. Run `scripts/reset_demo.sh` on the demo tenant and look at it.
