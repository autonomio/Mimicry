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

- **died**: 7,329 ICU stays with death inside the stay
  (`admissions.deathtime BETWEEN icustays.intime AND
  icustays.outtime`; deathtime is a true timestamp — the earlier
  `patients.dod` date-only version misclassified same-day cases).
- **survived**: ICU stays with `hospital_expire_flag = 0`, sampled 1:1 per
  first care unit with deterministic `hash(stay_id)` ordering, so every output
  shares one control sample and re-runs are exact.
- Anchor: `deathtime` for decedents, ICU `outtime` for survivors.
  Charting after the anchor never counts toward monitoring gaps;
  bins use elapsed (not boundary-counted) hours; pressor hours are
  restricted to observed ICU time with strict infusion overlap.

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

- **MAP** is the strongest vital signal: decedents 72 → 49 mmHg over the final
  ~6h; survivors flat at ~80.
- **SpO2** 97 → 87%, **RR** 22 → 18 in the last hours; **HR** runs hot
  all day then dips to 84; **temperature** flat (no signal).
- **Lactate** climbs 3.2 → 7.6 mmol/L across the last 24h (survivors ~1.6);
  **creatinine** 1.7 → 1.9 vs ~1.0 flat.
- **Pressors**: ~44% of decedents on vasopressors through the last day,
  easing to 36% in the final hour; survivors 5.5% → 0.5%. (An earlier
  "withdrawn to 10%" reading was an artifact of counting post-death
  hours as unexposed final hours.)
- **GCS**: decedents 7 → 3 (floor); survivors flat at 15.
- **Monitoring withdrawal is NOT signal** (corrected): median chart-stop
  gap 0.33h (died) vs 0.92h (survived); gap > 2h in 5.5% vs 9.4%.
  Decedents are monitored at least as closely — the earlier LR+ ≈ 8.6
  was an artifact of date-only death matching plus post-death anchor
  hours. Sensitivity run on gap ≤ 2h decedents reproduces all shapes.
- At 5-minute resolution the terminal crashes (HR → ~52, MAP → ~28)
  concentrate in the last ~30 minutes.
