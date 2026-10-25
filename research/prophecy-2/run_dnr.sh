#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT=/srv/mimic-iv/studies/prophecy2_dnr_20261025
DB=/srv/mimic-iv/db/mimic4-v31.db
PY=/srv/mimic-iv/.venv/bin/python
test -f "$DB"
test -f /srv/mimic-iv/studies/decision_feedback_20261025/risk_weighted_severityhistory.parquet
test -f /srv/mimic-iv/studies/decision_feedback_20261025/risk_support_bins.parquet
test -f /srv/mimic-iv/studies/decision_feedback_20261025/risk_event_bins.parquet
cd "$ROOT"
"$PY" 01_dnr_fork.py
duckdb -readonly "$DB" -csv < 02_phenotype_provider_audit.sql
duckdb -readonly "$DB" -csv < 03_later_limitation_audit.sql
"$PY" 04_publication_qa.py
chmod 600 ./*.json
printf 'Prophecy 2 DNR-first aggregate study completed; no patient data exported.\n'
