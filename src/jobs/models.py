# Scheduler process + job functions (spec §17.1: expire_holds,
# materialise_days, close_out_days, purge_proofs,
# purge_throttle_and_idempotency, heartbeat, disk_check). `manage.py
# run_scheduler` (docker-compose.yml's `scheduler` service command) will
# live here. No models of its own — reads/writes core.JobHeartbeat and
# other core/models.py tables. Out of scope for this milestone (models
# only); see core/models.py's JobHeartbeat for the one table this app
# will eventually own the writes to.
