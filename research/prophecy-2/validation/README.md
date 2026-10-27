# Prophecy 2 validation

[Results and decision](RESULTS.md) · [Locked protocol](PROTOCOL.md) · [Aggregate evidence](validation_aggregate.json)

This iteration reproduced the original computation and measurements but did not establish the stricter DNR-only comparison. It is an internal validation attempt in the same MIMIC-IV v3.1 source, not replication in another hospital.

## Files

- `matching.py`: baseline-only constrained weights and independent post-fit gates.
- `outcomes.py`: independent source queries, legacy-equivalent audit queries, patient-clustered contrasts and fixed-horizon follow-up states.
- `run_validation.py`: freezes every design before outcomes, checks archived arithmetic and source reconciliation, and writes a reviewed aggregate boundary.
- `original_reference.json`: published counts and primary contrasts from source commit `dab401a79bb63e563448dae29c5145d6377b3a17`.
- `test_*.py`: synthetic tests; no clinical records are included.

## Reproduce on an authorized research server

Use the existing authorized source environment and its installed Python packages; do not download additional clinical data. Keep all outputs in a restricted directory with `umask 077`. Required packages are NumPy, pandas, SciPy, DuckDB and a pandas Parquet engine. Exact versions used are recorded in `validation_aggregate.json`.

First run the full synthetic suite:

```bash
python -m unittest -v test_matching.py test_outcomes.py test_runner.py
```

Copy the frozen source study's `01_dnr_fork.py` into the restricted run directory as `legacy_01_dnr_fork.py`. It is used only to reconstruct the original baseline calibration through explicitly selected AST nodes, not to run the old study again.

Then run the locked analysis, supplying the actual commit being executed:

```bash
umask 077
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -u run_validation.py \
  --db /srv/mimic-iv/db/mimic4-v31.db \
  --source /srv/mimic-iv/studies/decision_feedback_20261025 \
  --dest /srv/mimic-iv/studies/prophecy2_validation_20261027 \
  --legacy-code legacy_01_dnr_fork.py \
  --legacy-report /srv/mimic-iv/studies/prophecy2_dnr_20261025/dnr_fork_aggregate_report.json \
  --code-commit f233dfd6046dc188b243859583b6df66744f3685
```

The four required source Parquet files are `risk_treated`, `risk_weighted_severityhistory`, `risk_support_bins` and `risk_event_bins`. They remain restricted. The runner opens the DuckDB database read-only and writes intermediate weights and diagnostics only to the restricted destination. Its final `validation_aggregate.json` still requires review before publication. Never copy the destination directory wholesale to GitHub.

`min_cell` values below 30 in the estimator support synthetic tests and private numerical reconciliation of already published results. They do not authorize public release of small cells. The runner's public boundary applies the declared threshold and additional complementary checks.

The original frozen commit remains the provenance anchor for the completed run; subsequent commits add the reviewed results and documentation. Re-running modified analysis code requires recording its actual commit and hashes, and documenting any method amendment before execution.
