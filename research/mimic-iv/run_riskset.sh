#!/usr/bin/env bash
# Deterministic server-only MIMIC-IV risk-set analysis. Do not run on a client.
set -euo pipefail
umask 077
DIR=/srv/mimic-iv/studies/decision_feedback_20261025
DB=/srv/mimic-iv/db/mimic4-v31.db
PY=/srv/mimic-iv/.venv/bin/python
test -f "$DB"
test -f /srv/mimic-iv/db/.pipeline-complete
test -d "$DIR"
cd "$DIR"
duckdb -readonly "$DB" -csv < 40_riskset_candidates.sql
duckdb -readonly "$DB" -csv < 41_pre_features.sql
"$PY" 42b_riskset_calibrate.py
duckdb -readonly "$DB" -csv < 43_event_outcomes.sql
"$PY" 44_analyze_outcomes.py
duckdb -readonly "$DB" -csv < 45_bp_channels.sql
"$PY" 46_analyze_bp.py
duckdb -readonly "$DB" -csv < 48_other_vitals.sql
"$PY" 49_analyze_other_vitals.py
duckdb -readonly "$DB" -csv < 50_lab_measurement.sql
"$PY" 51_analyze_labs.py
chmod 600 "$DIR"/*.parquet "$DIR"/*.json
printf 'Validated aggregate reports saved on s0. No rows exported.\n'
