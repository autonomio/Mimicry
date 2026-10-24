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

## Results (`metrics.txt`)

- **AUC 0.838, AP 0.47** (base rate 0.11) on 16,941 held-out stays.
- Risk deciles spread 0.35% → 48.1% mortality — well stratified.
- Largest risk coefficients: Neuro SICU, age, lactate, medical ICU;
  most protective: CVICU, surgical same-day/elective admission, high GCS.

## Limitations / next

- No DNR/comfort-measures flag yet (`code_status` exists in chartevents).
- Control for care unit is coarse; age is capped at 91+.
- Next: gradient boosting, calibration curve, 4h landmark comparison,
  more labs (BUN, WBC, bicarbonate), pressor use in window as feature.
