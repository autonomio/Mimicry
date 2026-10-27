# Early ICU mortality baseline (first 6h → hospital death)

Predicts hospital mortality from data available in the first 6 hours of the
ICU stay — the actually useful direction, unlike trajectories-into-death.

## Design

- **Population**: first ICU stay per hospitalization with LOS ≥ 6h
  (landmark at 6h; 84,468 stays). First stay is picked per admission
  *before* the LOS filter, so short first stays exclude the admission
  instead of promoting a later stay.
- **Outcome**: `hospital_expire_flag` — 9,233 events (10.9%).
- **Features** (all strictly within `[intime, intime + 6h)`):
  demographics (age, gender, admission type, first care unit), HR/RR/SpO2/MAP
  (median/min/max), temperature median, GCS min/median, lactate + creatinine
  medians, and a missingness flag per signal group.
- **Model**: L2 logistic regression, stratified 80/20 split, seed 42.
- **Environment (s0)**: `/srv/mimic-iv/.venv` with
  `duckdb==1.5.6 pandas==3.0.6 scikit-learn==1.9.1`.

## Run (on s0, read-only on the database)

```sh
/srv/mimic-iv/.venv/bin/python early_mortality.py
```

Only aggregate metrics are printed; no row-level data leaves s0.

## Results (`metrics.txt`, deterministic since the ORDER BY fix)

- **AUC 0.839, AP 0.470** (base rate 0.11) on 16,894 held-out stays.
- Risk deciles spread 0.36% → 48.9% mortality — well stratified.
- Largest risk coefficients: Neuro SICU, age, lactate, medical ICU;
  most protective: CVICU, surgical same-day/elective admission, high GCS.

## Model choice (2026-10-24): logreg is the reference

HGB wins on raw metrics (+0.023 AUC), but logreg stays the reference model:
directly interpretable coefficients, trivially deployable and auditable, and
already well calibrated — more bang for buck. HGB is retained in v1 as the
nonlinear benchmark to beat. Tuning (regularization path, feature engineering,
more labs, additional landmarks) happens on logreg.

## v1 (`early_mortality_v1.py`, `metrics_v1.txt`)

- **logreg**: AUC 0.8389, AP 0.4698, Brier 0.0754 — identical to the
  base script's output (all three scripts share one cohort/split/seed).
- **HGB** (300 trees, no early stopping): **AUC 0.8615, AP 0.5162,
  Brier 0.0716** — wins on all three metrics.
- Both models are well calibrated (predicted ≈ observed in every decile).
- HGB permutation importance: GCS median dominates (0.071 AUC drop), then
  care unit (0.043), age (0.033), admission type, lactate, creatinine.
- Bit-identical across re-runs (verified): fixed row order + seed, no
  early-stopping subsample randomness.

## v2 (`early_mortality_v2.py`, `metrics_v2.txt`)

- Adds **prior-year lab trajectories** for 21 tests: last value, OLS slope
  vs days-before-admission, abnormal fraction, max, count, missing flag
  (125 features). Same split as v1, so numbers compare directly.
- **Base: AUC 0.8389 / AP 0.4698 → base+history: AUC 0.8587 / AP 0.4909**
  (+0.020 / +0.021). History-labs alone buy nearly as much as HGB did.
- Top history drivers are **utilization, not values**: Hb/potassium/sodium
  missingness, AST/glucose/WBC/creatinine measurement counts. Slopes and
  abnormal fractions don't crack the top 12 — how often you were tested
  beats the trend.
  (Single-coefficient signs inside correlated per-test groups shouldn't be
  over-read; grouped ablation is the follow-up.)

## Limitations / next

- No DNR/comfort-measures flag yet (`code_status` exists in chartevents).
- Control for care unit is coarse; age is capped at 91+.
- Next: gradient boosting, calibration curve, 4h landmark comparison,
  more labs (BUN, WBC, bicarbonate), pressor use in window as feature.
