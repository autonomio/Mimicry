# MIMIC-IV v3.1 test runs: vitals and labs before ICU death

First analyses on the MIMIC-IV v3.1 DuckDB build (`/srv/mimic-iv/db/mimic4-v31.db`
on s0): hourly and 5-minute trajectories of vitals, labs, pressor exposure and
GCS in the last 24h before ICU death vs ICU discharge.

## Data use

This directory contains **aggregate results only** (medians, quantiles, counts,
percentages) plus the SQL that produced them. No row-level MIMIC data is stored
here or anywhere else in this repo. Queries run read-only against s0; the DUA
terms apply — keep the database on s0, do not redistribute.

## Cohorts

- **died**: 6,747 ICU stays with date of death inside the stay
  (`patients.dod BETWEEN icustays.intime AND icustays.outtime`).
- **survived**: ICU stays with `hospital_expire_flag = 0`, sampled 1:1 per
  first care unit with deterministic `hash(stay_id)` ordering, so every output
  shares one control sample and re-runs are exact.
- Anchor for both: ICU `outtime` (≈ hour of death for decedents).

## Queries (`sql/`, run in order)

| File | Output |
|---|---|
| `00_cohorts_withdrawal.sql` | monitoring-stop gap distribution + 2x2 table |
| `01_trajectories_sensitivity.sql` | hourly HR/RR/SpO2/MAP/temp for died_all, died_gap2h, survived |
| `02_finegrain_5min.sql` | 5-min HR/SpO2/MAP over the last 6h, gap<=1h subset |
| `03_labs.sql` | lactate + creatinine in 6h bins |
| `04_pressors.sql` | hourly % of stays on vasopressors |
| `05_gcs.sql` | hourly median GCS total |

Run read-only, e.g.:

```sh
ssh root@65.109.147.74 'duckdb -readonly -csv /srv/mimic-iv/db/mimic4-v31.db' \
  < sql/01_trajectories_sensitivity.sql > outputs/mimic_sensitivity.csv
```

Regenerate figures: `cd plots && uv run --with matplotlib python make_plots.py`.

## Findings (2026-10-24)

- **MAP** is the strongest vital signal: decedents 71 → 52 mmHg over the final
  ~6h; survivors flat at ~80.
- **SpO2** 97 → 90%, **RR** 22 → 15 in the last hours; **HR** runs ~9 bpm hot
  all day then dips; **temperature** flat (no signal).
- **Lactate** climbs 3.5 → 8.5 mmol/L across the last 24h (survivors ~1.6);
  **creatinine** 1.7 → 2.0 vs 1.0 flat.
- **Pressors**: ~42% of decedents on vasopressors 24–7h out, withdrawn to 10%
  in the final hour (comfort-care transition); survivors 4% → 0%.
- **GCS**: decedents 6 → 3 (floor) by 6h out; survivors flat at 15.
- **Monitoring withdrawal is signal, not just missingness**: median chart-stop
  gap 2.67h (died) vs 0.82h (survived); gap > 2h has LR+ ≈ 8.6 for death.
  Final-hour medians rest on small n — treat "monitoring stopped" as a
  feature. Sensitivity run on continuously-monitored decedents (gap ≤ 2h)
  reproduces all trajectory shapes.
- At 5-minute resolution the terminal crashes (HR → ~45, SpO2 → ~70,
  MAP → ~30) concentrate in the last ~30 minutes.
