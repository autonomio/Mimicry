#!/usr/bin/env bash
# Exploratory MIMIC-IV v3.1: organ-support, measurement and severity audit.
# Never runs a download, changes source data, commits patient rows or deploys.
set -euo pipefail
umask 077
DIR=/srv/mimic-iv/studies/decision_feedback_20261025
DB=/srv/mimic-iv/db/mimic4-v31.db
PY=/srv/mimic-iv/.venv/bin/python
test -f "$DB"
test -f /srv/mimic-iv/db/.pipeline-complete
test -f "$DIR/risk_weighted.parquet"
test -f "$DIR/risk_event_bins.parquet"
test -f "$DIR/risk_treated.parquet"
cd "$DIR"
duckdb -readonly "$DB" -csv < 52_support_intervals.sql
"$PY" 53_analyze_support.py
duckdb -readonly "$DB" -csv < 54_treatment_procedures.sql
"$PY" 55_support_history_calibration.py
"$PY" 56_early_pretreatment_placebo.py
"$PY" 57_fixed12h_utilization.py
duckdb -readonly "$DB" -csv < 59_predecision_severity.sql
"$PY" 60_severity_history_calibration.py
"$PY" 61_historical_status_robustness.py
chmod 600 ./*.parquet ./*.json ./*.log 2>/dev/null || true
printf 'Support-delivery and severity sensitivity analyses reproduced on s0.\n'
