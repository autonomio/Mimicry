#!/usr/bin/env bash
set -euo pipefail
umask 077
R=/srv/mimic-iv/studies/decision_feedback_20261025
DB=/srv/mimic-iv/db/mimic4-v31.db
PY=/srv/mimic-iv/.venv/bin/python
test -f "$DB"
test -e /srv/mimic-iv/db/.pipeline-complete
cd "$R"
duckdb -readonly "$DB" -csv < 70_multistate_panel.sql
"$PY" 71_realfit.py
"$PY" 72_real_components.py
"$PY" 73_real_qa.py
chmod 600 multistate_6h_panel.parquet multistate_*report.json multistate_structural_qa.json
sha256sum 70_multistate_panel.sql 71_realfit.py 72_real_components.py 73_real_qa.py > multistate_source.sha256
chmod 600 multistate_source.sha256
printf 'VERIFIED real MIMIC-IV multistate pipeline replay completed.\n'
