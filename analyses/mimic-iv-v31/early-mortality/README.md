# Early ICU mortality baseline (first 6h → hospital death)

Predicts hospital mortality from data available in the first 6 hours of the
ICU stay — the actually useful direction, unlike trajectories-into-death.

## Design

- **Population**: first ICU stay per hospitalization with LOS ≥ 6h
  (landmark at 6h; 84,703 stays).
- **Outcome**: `hospital_expire_flag` — 9,270 events (10.9%).
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

- **AUC 0.838, AP 0.47** (base rate 0.11) on 16,941 held-out stays.
- Risk deciles spread 0.35% → 48.1% mortality — well stratified.
- Largest risk coefficients: Neuro SICU, age, lactate, medical ICU;
  most protective: CVICU, surgical same-day/elective admission, high GCS.

## Model choice (2026-10-24): logreg is the reference

HGB wins on raw metrics (+0.023 AUC), but logreg stays the reference model:
directly interpretable coefficients, trivially deployable and auditable, and
already well calibrated — more bang for buck. HGB is retained in v1 as the
nonlinear benchmark to beat. Tuning (regularization path, feature engineering,
more labs, additional landmarks) happens on logreg.

## v1 (`early_mortality_v1.py`, `metrics_v1.txt`)

- **logreg**: AUC 0.8358, AP 0.4528, Brier 0.0769.
- **HGB** (300 trees, no early stopping): **AUC 0.8587, AP 0.4871,
  Brier 0.0738** — wins on all three metrics.
- Both models are well calibrated (predicted ≈ observed in every decile).
- HGB permutation importance: GCS median dominates (0.075 AUC drop), then
  care unit (0.045), age (0.035), admission type, lactate, creatinine.
- Bit-identical across re-runs (verified): fixed row order + seed, no
  early-stopping subsample randomness.

## v2 (`early_mortality_v2.py`, `metrics_v2.txt`)

- Adds **prior-year lab trajectories** for 21 tests: last value, OLS slope
  vs days-before-admission, abnormal fraction, max, count, missing flag
  (125 features). Same split as v1, so numbers compare directly.
- **Base: AUC 0.8358 / AP 0.4528 → base+history: AUC 0.8546 / AP 0.4771**
  (+0.019 / +0.024). History-labs alone buy nearly as much as HGB did.
- Top history drivers are **utilization, not values**: creatinine/BUN/WBC
  measurement counts, Hb/platelet missingness. Slopes and abnormal fractions
  don't crack the top 12 — how often you were tested beats the trend.
  (Single-coefficient signs inside correlated per-test groups shouldn't be
  over-read; grouped ablation is the follow-up.)

## Limitations / next

- No DNR/comfort-measures flag yet (`code_status` exists in chartevents).
- Control for care unit is coarse; age is capped at 91+.
- Next: gradient boosting, calibration curve, 4h landmark comparison,
  more labs (BUN, WBC, bicarbonate), pressor use in window as feature.
