# Prior-year common ailments vs serious illness

Same rigor as the constipation study, widened to a screen: 16 common,
innocent-seeming prior-year ailments, each tested against three serious
outcomes. Structured fields only, 546,028 admissions.

## Design

- Exposure window [admittime - 365d, admittime): coded dx (ICD-9/10
  prefixes in prior admissions) OR drug-class Rx fills (generic-stem
  formulary match on `prescriptions`). Primary definition: either.
- Outcomes: (1) hospital death (11,801 events), (2) any ICU stay during
  the hospitalization (85,242), (3) elective admission -> ICU transfer
  ("unexpected ICU", 2,806 / 13,130 elective admissions).
- Covariates (same set for all 48 cells): age, sex, race, insurance,
  admission type/location, prior-admission count, prior total LOS,
  prior-year admission count, prior Charlson, 9 prior-comorbidity flags,
  admission year group.
- Stage 1 (all 48 cells): crude ORs (dx / Rx / either) + adjusted
  logistic + E-value + BH-FDR over all cells.
- Stage 2 (FDR q<0.05 AND >10% effect only): adjusted dx/Rx
  decomposition, 1:1 propensity matching + balance, dose-response
  (Rx fills 0/1/2+, coded-only), recency (none / 6-12 mo / 0-6 mo).

Caveat: the uniform covariate set includes prior-comorbidity flags that
are downstream of some ailments (e.g. cardiac/renal disease for
hypertension). For those, the adjusted estimate is closer to a direct
than a total effect and can land paradoxically protective — read stage-2
matching and crude rates alongside.

## Screen (adjusted ORs, * = q<0.05)

![screen heatmap](ail_screen_heatmap.png)

## Results

![screen heatmap](ail_screen_heatmap.png)

Full numbers: `ail_screen.csv`. Forest plots: `forest_death.png`,
`forest_icu.png`, `forest_unexpected_icu.png`. Balance: `ail_balance.csv`.
Reference check: death|constipation adj OR 0.975, p=0.42 — replicates
the standalone constipation study exactly.

Harm signals (adjusted OR > 1, q < 0.05):

| cell | adj OR | matched OR | verdict |
|---|---|---|---|
| death / anxiety (benzos) | 1.16 | 1.12, dose -> 1.27, recent 1.23 | robust |
| ICU / asthma-COPD (albuterol) | 1.16 | 1.06, dose 2+ 1.35, recent 1.16 | robust, attenuated |
| elective->ICU / hyperlipidemia | 1.23 | 1.21, dx and Rx agree | robust (surgery marker?) |
| death / asthma-COPD | 1.13 | 1.01, p=0.89 | NOT robust, matching kills it |
| ICU / diabetes (1.05), death / anemia (1.08) | small | below 10% gate, no stage 2 | marginal |

Protective hits (all q < 0.05, all matched-robust unless noted):

- death: hypertension 0.73 -> matched 0.62; hyperlipidemia 0.78 ->
  0.73; depression 0.89 -> 0.88; obesity 0.88 -> 0.80 (99.7%
  matched); headache 0.83 -> 0.83, p=0.063 borderline.
- ICU: hypertension 0.83 -> 0.81; back pain 0.85 -> 0.77; UTI 0.88
  -> 0.84; allergy 0.87 -> 0.86.
- elective->ICU: UTI 0.57 -> 0.60; back pain 0.68 -> 0.70; anxiety
  0.71 -> 0.81; allergy 0.80 -> 0.80, p=0.05.

Nulls: sleep, hypothyroidism, GERD (death 0.92 significant but <10%),
diabetes->death, UTI->death, constipation->death.

## Read

1. **Drugs carry the signal, labels don't.** In nearly every hit the
   dx-only estimate is null while the Rx component drives the result —
   in both directions (benzos/albuterol harm; statins/antihistamines/
   antibiotics protective). A diagnostic label without treatment marks
   mild or inactive disease; fills mark active disease and care
   engagement.
2. **Protectives are engagement/selection markers, not shields.** They
   survive matching with dose gradients (more fills -> lower odds),
   so they are real associations — of treated, monitored, previously-
   seen patients vs everyone else — not causal protection. ICU
   protectives additionally reflect case-mix: much ICU volume is
   planned post-surgical care in previously-well patients, while
   prior-contact patients are admitted through medical channels to
   the floor.
3. **Context flips exist.** Benzos predict death (matched 1.12) but
   protect against elective->ICU transfer (matched 0.81): different
   denominators, different mechanisms.
4. **Matching discriminates.** death|asthma (adjusted 1.13) attenuates
   to 1.01 under matching while icu|asthma survives — same exposure,
   outcome-specific robustness, exactly the constipation lesson.
5. **E-values 1.5-1.8** on the harm signals: even the robust positives
   fall to unmeasured confounding of ~1.6x (frailty, severity). No
   causal claims.
6. **UTI splits by definition**: coded UTI predicts ICU (1.08) while
   UTI-antibiotic Rx protects (0.85) — susceptibility/frailty marker
   vs treatment-engagement marker. Coded-without-antibiotics is null
   (1.03).

## Reproduce

```sh
/srv/mimic-iv/.venv/bin/python /tmp/ailment_sweep.py  # ~55 min on s0
```

then `make_plots.py` on the fetched CSVs. Raw log:
`ailment_sweep.out`. Screen table: `ail_screen.csv`. Forest rows:
`ail_forest.csv`. Balance: `ail_balance.csv`.
