# Prior-year constipation vs hospital survival

Robust statistical analysis: does suffering from constipation in the year
before admission predict surviving the hospitalization? Structured fields
only (`diagnoses_icd`, `prescriptions`, prior-admission summaries), all
546,028 admissions, 11,801 hospital deaths (2.16%).

## Exposure (window: [admittime - 365d, admittime))

| definition | rule | prevalence | crude death rate |
|---|---|---|---|
| coded | ICD 564.0x / K59.0x in prior admissions | 5.55% | 3.29% vs 2.10%, OR 1.59 |
| lax_any | >= 1 laxative Rx fill (formulary match) | 33.49% | 2.60% vs 1.94%, OR 1.35 |
| either | coded OR lax_any | 33.59% | 2.59% vs 1.94%, OR 1.34 |
| both | coded AND lax_any | 5.44% | 3.33% vs 2.09%, OR 1.61 |

Covariates (identical set in adjusted logistic and propensity models):
age, sex, race, insurance, admission type/location, anchor year group,
prior-admission count, prior total LOS, prior-year admission count, prior
Charlson max (+ missingness flag), 9 prior-dx flags (cardiac/HF/stroke/
renal/COPD/diabetes/onc/sepsis/liver); second spec adds ICU-stay flag.

## Result: no robust association (negative study)

- Adjusted logistic: **coded OR 1.17 [1.09-1.27], both OR 1.19
  [1.10-1.28]**; laxative-only definitions null (~1.01).
- Propensity 1:1 matching (full-caliper search, caliper 0.2 SD, same
  covariates): **matched-coded OR 0.97 [0.89-1.06], p=0.57, 30,272
  pairs (100% matched), all |SMD| <= 0.11** — the adjusted signal
  fully attenuates.
- Matched-either is protective (OR 0.78 [0.72-0.85]) but that estimate
  lives on a 36%-matched overlap population and disagrees with both the
  adjusted model and the coded match — not a robust claim either.
- Dose-response: flat (1 class 0.94, 2+ classes 1.02, both null).
- Recency (days since LATEST exposure): 30-day recent 1.14
  (p=0.0002), remote 0.89; 6-month sensitivity null (recent 1.06,
  p=0.087). A ≤30-day blip with no dose gradient and no matched
  support — not a robust gradient.
- Subgroups: age split null; never-ICU OR 1.24 [1.08-1.41] but this is
  adjusted-only and subject to the same residual confounding the matching
  exposes.
- E-values 1.54-1.78: weak unmeasured confounding (frailty, severity not
  captured by prior-admission summaries) explains away the adjusted ORs.

Read: coded constipation marks sicker patients (crude +59%), and a +17%
adjusted residue survives a rich covariate set — but it does not survive
propensity matching, has no dose gradient, an inconsistent recency
pattern, and needs only a ~1.6x unmeasured confounder to vanish.
**Not a survival predictor.**

![forest plot](const_forest.png)

## Reproduce

Run `constipation.py` on s0 (needs the MIMIC-IV v3.1 sqlite db +
`duckdb, pandas, scikit-learn, statsmodels, scipy` in the venv):

```sh
/srv/mimic-iv/.venv/bin/python /tmp/constipation.py  # ~8 min
```

then `make_plots.py` (matplotlib) on the fetched `const_forest.csv`.
Raw log: `constipation.out`. Balance diagnostics: `const_balance.csv`.
