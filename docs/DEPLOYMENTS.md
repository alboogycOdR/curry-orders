# Deployments

What is actually live right now, where, and how current it is. This is
separate from `RUNBOOK.md`, which documents the *planned production*
deploy of the real Django app (spec §17.4, D-28) — nothing described
there has happened yet. This file tracks what's already running.

## Static prototype — Clawsrv, port 8104

| | |
|---|---|
| URL | http://204.168.249.99:8104/ |
| Host | Clawsrv VPS (`ssh clawusr@100.78.70.2`), Docker container `brandons-kitchen-prototype` |
| Serves | `design/prototype/index.html` — a single self-contained static HTML file, no backend |
| Redeploy | `deploy/deploy-prototype.sh` — scp's the file over; no restart needed, Caddy reads it straight off disk |
| Isolation | Own container on its own port (8104), separate from the ports reserved for the real app (8102/8103 per §17.5); no root access used, no shared Caddy config touched |

**Status as of 2026-08-30: stale.** This is still serving the **dark
jewel-tone theme**, which decision **D-30** retired permanently in favour
of the Broadsheet newsprint design. It predates the real Django
application entirely — checkout, the capacity engine, staff auth, the
kitchen/collection boards all now exist and work (see `README.md`
Status), and none of that is reflected here. Anyone opening this link
today sees an old, superseded mock, not current work.

This hasn't been resolved yet — one of three things needs to happen,
owner's call:
1. **Tear it down** — `docker rm -f brandons-kitchen-prototype` on
   Clawsrv. Fully superseded by the real app; this was only ever "something
   to show Brandon" before real functionality existed.
2. **Leave it, labelled historical** — keep the container, but it stops
   being a "here's the current state" link for anyone.
3. **Repoint it at the real thing** — deploy the actual Django app to
   Clawsrv on this port (or a new one) instead of a static file. This is
   genuinely Milestone 10 work already scoped in `PHASE_2_PLAN.md`, just
   pulled forward.

## Production Django app — not yet deployed anywhere

Planned target is also Clawsrv (D-28, spec §17.5/§17.6): its own compose
stack (`web`, `scheduler`, `db`, `minio`), no `caddy` container (the
host's own Caddy reverse-proxies in), ports **8102** (`web`) and **8103**
(MinIO S3 API) reserved and confirmed free against the host's port map.
None of this stack has been built or deployed yet — see
`docs/PHASE_2_PLAN.md` for what's outstanding before it can go live
(backups, monitoring, swap/mem_limits, load and security passes).
