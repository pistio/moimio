# External acceptance correction — Core draft7

Frozen tested source `df5d2cfef5c636eff2a16adeb6f21ee7e95ec317`, complete tree `7df1ae94ec99e8e6bcd5443d9513d5825ce8ac37`, based on prior reviewed df50397502518e98edddc29542ff7c464e746335. Only this evidence document follows freeze. No main merge, release tag or remote image publication.

The reset issuer now sends canonical `/reset-password#reset=...`, never a newly issued query credential. The actual React page captures the bounded fragment in memory, strips location/history under StrictMode, refuses absent/short/old-query authority and submits the credential only to the existing same-origin POST body. Invalid links do not change the password. Existing one-use,30-minute expiry, password hashing/session revocation and private bootstrap controls remain. Old query links require fresh issuance after a paired frontend/backend cutover; this does not erase old logs or establish real mailbox/link-tracking safety. A forwarded valid email remains a bearer capability; no phishing-resistance claim.

Final primary verification on exactdf5d2cf:

- Owned PostgreSQL full backend: **600 passed,3 skipped,183 warnings,47.93s**, exit0. Skips are existing missing generated stress inputs, not account/migration checks.
- Frontend: **136 passed/17 files**,14.09s; complete build, language-key and PWA checks passed. Four new reset-fragment, StrictMode/history and old-query-refusal tests; six languages retained, no new keys.
- Actual local image backend `sha256:44abbe2131ee755ce2ef5dad56c25bc3398d13282917ed3d829bacda518f26a5`, frontend `sha256:8713d9e9ccc1fee75de2b6d66828643d6e0c0a2371a2eceffa114a8fcc8bcdf8`. Official Dockerfiles with transient public CA build mounts only; source/recipe digests recorded in SaaS evidence. No registry push/promotion.
- Primary and independent final local-image rehearsal passed: normal CMD/migration/lifespan, real Caddy TLS chain/hostname and source-generated credit route, actual compiled private setup/login/refresh/restart/event/reset, Secure/HttpOnly/Strict cookies, hostile Origin refusal, wrong tenant/missing key startup refusal. Credit was explicitly seeded as a fixture; not a payment claim. Reset UI digest was privately seeded; actual request-reset issuer separately tested against owned PG. No real SMTP/Paddle/provider.
- Separate full compiled checkout→event lab passed using actual local apps/edge/PG and fictional signed provider responses: one account, one credit granted and consumed, one event, restart; not live tax/mail/hosting evidence.
- Fresh independent reviewer executed **12 PG hosted-access tests**, **4 new frontend tests**, and final actual image rehearsal, with no source edits or concrete P0/P1 in reviewed paths.
- Two directly relevant reset mutations (query issuance and missing history stripping) were assertion-detected with passing baselines as part of4/4 selected cross-repo mutations. No functional/setup failure credited; no all-history recovery mutation claim.

One primary frozen image attempt timed out; unchanged rerun and independent final run passed. No root-cause/stability fix claimed. Developmental routing/certificate-client issues and sanitised logs are recorded in the companion report, not concealed as passes. All owned runtime containers/networks/temp data cleaned; local non-running build cache retained only.

**Real first-payment release NOT ADMITTED.** Approved Paddle catalog/customer/billing-location/tax response, private real-provider/sender integration, owner-controlled mailbox delivery, bearer forwarding/cancellation handling, actual host/TLS/secret/image/old-worker exclusion, encrypted backup custody/restore, legacy checkout cutover and refund data-disposition approval remain unresolved. No operational changes or credentials inspected on NiPogi. No mail, actual checkout, paid Actions, GHCR, merge, deployment or activation. Recovery NO_GO; G1/G9/G12 CLOSED.

Companion package: SaaS updated draft4, `docs/external-acceptance/EXECUTION_REVIEW_20261101.md`, plus exact Paddle/mail scope documents and release checklist. Website draft2 remains unchanged; no redesign. No new recovery subsystem.
