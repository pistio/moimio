# Hosted account verification — Cloud only

Frozen executable/test source: `c5c3dc6a8215e5f00172607e10fa653f1d41ac9c`; complete frozen tree `193c948df5b00adf7d84d7ef63a175881fe08b10`. Based on verified main585af2c3a6cdf89b8d4b2516a858bdef490a9351. Subsequent delivery changes are documentation/evidence only. No upstream history rewritten.

## Executed final checks

- `/workspace/moimio-core-acceptance-venv/bin/python scripts/cloud-owned-tests.py`: **600 passed,3 skipped,183 warnings,54.45s**, exit0. Own PostgreSQL only; application TCP refused. Skips are existing missing development stress fixtures: `/tmp/people2.json`, `/tmp/people.json`, and the historical generated stress CSV. No account/security/migration case skipped. Warnings include inherited synchronous tests marked asyncio and existing dependency deprecations.
- Frontend `npm test -- --maxWorkers=2 --minWorkers=1`: **132 passed,16 files**,10.66s; `npm run build`: passed including existing language/build checks. No new translation keys; six-language Core support retained.
- Actual PostgreSQL107a→108a migration preserves existing user, creates no fabricated grant/session, refuses unsafe downgrade. Separate physical concurrent bootstrap requests produce201/403; concurrent use of one refresh produces200/401 and exactly one surviving digest.
- Independent frozen reviewer:13 focused PostgreSQL/API+migration passed; separately executed stale-cookie logout attack1 passed. Original developmental counterexample independently reproduced first: attacker rotation left newer access/refresh alive after logout with old cookie. Fix revokes signed session family; both now401. Wrong/expired/replayed grant, foreign buyer/origin/Host, weak/malformed Hosted configuration and stripped config after a latched grant remain refused.
- **4/4 new targeted mutations** detected at intended assertions with passing baselines, isolated source copies. Buyer binding, bootstrap secret, Secure cookie and revoked-session rejection. Sanitised evidence is adjacent; no JWT/cookie contents retained in report.

## Composed acceptance

The paired SaaS laboratory executes compiled Website/edge → exact fictional checkout → signed payment → actual private Core issuer and migrated owned PostgreSQL → compiled private setup → real login → actual process restart → explicit event creation → local signed event/credit consumption. Primary and independent reviewer both executed the journey successfully. Paddle, mail delivery, provisioning host, proxy forwarding and TLS certificate are fictional; normal lifespans/schedulers never run. No actual outbound transport. The exact final SaaS revision and counts are recorded in its companion report; do not treat earlier developmental executions as final runs.

## Compatibility and remaining admission

Migration108a and paired frontend/backend, isolated stable secret and canonical HTTPS PUBLIC_ORIGIN are mandatory for Hosted. Existing Hosted users re-login; CE legacy access tokens retain original bounded expiry. PUBLIC_ORIGIN is now explicitly passed through the bundled production compose template; existing environment files need separate reviewed compatibility handling. No old binary is assumed to enforce this. Grant issuance failure/lost notice remains review-required, never public setup fallback or automatic re-provisioning.

No real Docker/Caddy/SMTP/Paddle/host/network admission was tested. Provider trust, actual HTTPS/proxy boundary, account delivery, encrypted backups, old-worker exclusion, refund/erasure policy and operational approval remain blockers. The SaaS compatibility matrix covers coordinated maintenance/cutover. Core main/tag/manual workflow builds/publishes GHCR; no such trigger was dispatched. Feature draft only. Recovery NO_GO; G1/G9/G12 CLOSED. No NiPogi, real data/keys, production migration, paid Actions, merge, deployment or activation.
