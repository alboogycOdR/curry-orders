# Decision log

Seeded from `SPEC_v1.1.md` Appendix A (frozen at v1.1) and maintained here
going forward. New decisions get the next `D-NN` and a row below; the spec
itself is not edited to add them unless it materially changes behaviour
described there. Where an entry below narrows or supersedes the spec text,
the spec's own precedence rule still applies to everything it doesn't
mention: this document wins on choices made *after* v1.1, the spec wins
otherwise.

| ID | Decision | Rationale |
|---|---|---|
| D-01 | No `new_request` status; checkout writes the first real status inside the reservation transaction | A transient state would need recovery logic for no benefit; a failed transaction leaves nothing behind |
| D-02 | One `cancelled` status with `cancellation_reason` enum (`customer_request, staff, cash_rejected, payment_rejected, no_show, day_closed, duplicate, owner_exception, other`) | Simpler matrix; reason carries the semantics; reports group by reason |
| D-03 | `orders.dish_units_consumed`, set on `start_kitchen`, never cleared; dish-unit ceiling counts occupying set ∪ consumed | Resolves the §8.1/§19 contradiction without a parallel ledger |
| D-04 | Order sequence from `trading_days.next_order_seq` under the existing `FOR UPDATE` lock | Zero extra locking; per-collection-date numbering as v1.0 intended |
| D-05 | Horizon = today (if open and before cut-off) + next 7 days (up to 8 dates) | Matches the literal v1.0 wording "today through +7" |
| D-06 | Cash same-day only, therefore public cash checkout only 00:00–10:00 SAST; flagged to owner | Preserves the v1.0 confirmed model; the alternative is a settings toggle, not code |
| D-07 | No email anywhere in v1; token URL + Copy/Share + lookup; SMS optional adapter | Avoids an email provider, deliverability work and extra POPIA data |
| D-08 | Hold extension is mandatory: once, +15 min, staff-only, audited | Wrong-reference proofs are common; without extension staff would cancel paying customers |
| D-09 | `payment_review` never auto-expires; hold-lapsed and SLA-breached flags instead | A submitted proof is evidence of intent; silent drops create disputes |
| D-10 | Reinstate keeps the same order number and re-runs all ceilings | Customer already has the reference; capacity must still be honest |
| D-11 | `assisted_after_cutoff_enabled` owner setting; when on, any staff with mandatory reason | Clear ownership of the risk; default deny preserved |
| D-12 | Staff password reset via owner-set temporary password + forced change | No email provider; three users; owner is always reachable |
| D-13 | Django 5 + Postgres 16 + HTMX/Alpine/Tailwind, in-process APScheduler, single deployable | One deployable, developer's primary language, no broker/Redis. *(Hosting clause superseded by D-28.)* |
| D-14 | `customers.mobile_e164` unique; upsert; order-level snapshots | Enables reorder history later without a login |
| D-15 | Slot change allowed up to `in_kitchen`; never from `ready`; same day only | Kitchen batches by day; a date change is a new capacity event |
| D-16 | Close out day = explicit staff action after grace, with a nightly safety job | Home kitchen closes the door at a known time; no order may remain `ready` forever |
| D-17 | Kitchen lock = `trading_days.kitchen_locked_at`; later confirmations flagged, not blocked | Cooking in batches must not stop the payment queue |
| D-18 | Verify from `awaiting_eft` without proof allowed with reason | Staff see funds in the bank app before customers upload screenshots |
| D-19 | `vat_registered` default false; receipt says "Not a tax invoice" | Home business is below the VAT threshold until proven otherwise |
| D-20 | Bounded corrections: `revert_ready`, `uncollect` (≤10 min), both audited | Mis-taps on a phone at the gate are certain; unbounded undo would corrupt reports |
| D-21 | Rate limits: checkout 5/min/IP, proof 5/h/token, lookup 10/h/IP and 10/h/order number, login 5 failures → 15 min lock | Cheap abuse resistance without CAPTCHA |
| D-22 | Idempotency keys stored 24 h with request hash | Double-taps on slow mobile networks are the norm |
| D-23 | Address never in metadata, sitemaps, OG tags, or on any page before confirmation; no map; no exterior photo | Private residence |
| D-24 | Settings is a single typed row with an events table | Type safety and diff-able audit beat a key-value bag for ~40 keys |
| D-25 | Dishes are archived, never hard-deleted | Permalinks are marketing assets; snapshots reference them |
| D-26 | Staff app served from the same origin as the public site under `/manage` | Removes CORS entirely |
| D-27 | Postgres-backed throttling, no Redis | Three staff and 100 orders/day do not justify another service |
| D-28 | Host on the existing **Clawsrv VPS** instead of a new AWS VM; object storage is self-hosted MinIO in the same compose stack instead of S3 `af-south-1` | Uses infrastructure already paid for and administered; removes the AWS account, IAM and egress entirely; `django-storages` speaks the same S3 API so only `S3_ENDPOINT` changes in code. Trade-offs accepted: no managed-DB failover, no provider-side object snapshots, host patching is the owner's job, and Cape Town latency depends on where Clawsrv actually sits — hence the mandatory off-host backup regime (§15), the isolation rules and the re-measured LCP budget (§17.5) |
| D-29 | `order_lines.option_key` is an ordinary application-set column, not a Postgres generated column, despite §7.10's wording | `schema_v1_1.sql` declares it `text NOT NULL DEFAULT ''`, not `GENERATED ALWAYS AS (...) STORED`. Per the spec's own precedence rule the SQL wins on structure. `core/ordering.py` (§17.2) must compute and set it explicitly — sorted `"Option=Value|..."` — on every insert and on `amend_items`; nothing enforces it at the DB layer, so a unit test on the derivation (§20.5) is load-bearing |

## Clawsrv survey (2026-08-28)

Captured here because it is infrastructure fact, not a design choice — see
`SPEC_v1.1.md` §17.5/§17.6 for the full write-up and D-28 above for the
decision it fed. Re-run the survey (`ssh clawusr@100.78.70.2`) before
relying on any of these numbers again if meaningful time has passed:

- Hetzner, Helsinki (AS24940); Ubuntu 24.04.4; 8 vCPU / 15 GB RAM (~7.5 GB
  free, **no swap**) / 150 GB disk (83 GB free); Docker 29.5.2 / Compose
  v5.1.4; host timezone `Etc/UTC`.
- Host Caddy (systemd, not containerised) already owns 80/443 and serves
  `admin.rwc.org.za` — this project's compose stack has no `caddy` service.
- Ports already in use on the host: 80, 443, 22, 3000, 3002, 3030, 3579,
  5000, 5432, 5433, 5434, 6379, 6380, 8000–8004, 8010, 8080, 8088, 8089,
  8100, 8101, 8642, 11434, 18789, 2019. This project claims 8102 (`web`)
  and 8103 (MinIO API, loopback-only).
- Existing tenants that must not be disturbed: `skulcozm_*`,
  `lekkerswot_*`, `oracle_postgres`, `grafana`, `uptime_kuma`,
  `opensandbox-server`, host `ollama`.
