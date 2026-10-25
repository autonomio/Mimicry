# Prophecy — Research round 02: Historical transport and recursive prediction

**Status:** Executed on MIMIC-IV v3.1; exploratory, observational, not causal.
**Research date:** 2026-10-25. **Data:** existing secure server installation only.

## Why the ICU simulator overpredicts discharge

Separate the one-step terminal hazard evaluated against REAL observed
patient histories (prequential / teacher forcing) from the complete
stochastic rollout, which recursively generates treatments, records
and physiology. For each horizon, full prediction error equals
(prequential minus observed) plus (full rollout minus prequential).
This is an algebraic prediction-error diagnostic, NOT a causal
decomposition or an orthogonal estimation framework.

### Five-day discharge trajectory, 2020–2022, N=7,147

| Hours after ICU hour 24 | Actual ICU exit | Prediction on actual histories | Complete simulation | Local error | Additional rollout error |
|---:|---:|---:|---:|---:|---:|
| 24 | 32.06% | 35.54% | 38.01% | +3.48pp | +2.47pp |
| 48 | 50.02% | 54.75% | 57.10% | +4.73pp | +2.35pp |
| 72 | 60.78% | 66.44% | 68.11% | +5.65pp | +1.67pp |
| 120 | 72.59% | 78.96% | 79.28% | +6.37pp | +0.32pp |

The 120-hour simulator overpredicts exit by 6.69 percentage points.
6.37 points are already present using actual patient histories;
only 0.32 additional points appear through recursion.
The conditional patient-bootstrap interval for prequential error is 4.49–8.28 points.

### Opposing errors can conceal poor mortality modeling

| Hours | Observed ICU death | Prediction on actual histories | Simulated mortality | Local error | Additional rollout error |
|---:|---:|---:|---:|---:|---:|
| 24 | 1.69% | 1.32% | 1.54% | -0.38pp | +0.23pp |
| 48 | 2.63% | 2.16% | 2.60% | -0.47pp | +0.44pp |
| 72 | 3.30% | 2.83% | 3.39% | -0.47pp | +0.56pp |
| 120 | 4.42% | 3.98% | 4.38% | -0.45pp | +0.40pp |

The terminal hazard underpredicts mortality on observed later-era
histories while recursively simulated patient histories increase
mortality. These errors partially cancel. Matching observed death
incidence in a full simulation is not sufficient evidence of a
correctly specified transition system.

## Earlier historical rolling-origin evaluation

Train: 2008–2013; calibrate: 2014–2016; evaluate: 2017–2019.
9,838 first-ICU-stay patients present at ICU hour 24.

| Future hours | Observed exit | Forecast on observed histories | Overprediction |
|---:|---:|---:|---:|
| 24 | 36.25% | 37.00% | +0.75pp |
| 48 | 55.05% | 56.44% | +1.39pp |
| 72 | 65.99% | 67.84% | +1.85pp |
| 120 | 77.14% | 80.01% | +2.87pp |

By 120 hours, overprediction is +2.87pp,
conditional patient-bootstrap interval 1.28–4.53pp.
Because the investigator has seen these historical cohorts already,
this is a chronological robustness check, NOT untouched confirmation.

## Historical shift after measured baseline standardization

Using a cross-fitted, outcome-blind historical-era propensity
and overlap weights at ICU hour 24, 2017–2019 N=9,838 and
2020–2022 N=7,147 are compared on observed common-support case mix.

- Raw later-minus-earlier discharge difference: -4.55 percentage points.
- Baseline-overlap-standardized difference: -3.41 points.
- Conditional 95% bootstrap interval: -4.71 to -2.18 points.
- Historical-epoch propensity AUC: 0.594.

### Exploratory ICU-specific comparisons

| Unit | 2017–19 patients | 2020–22 patients | Standardized discharge difference | Conditional 95% CI |
|---|---:|---:|---:|---:|
| CCU | 936 | 641 | -3.67pp | -8.31 to 0.63pp |
| CVICU | 2,144 | 1,604 | -2.84pp | -4.84 to -0.68pp |
| MICU | 2,626 | 1,634 | -5.80pp | -8.51 to -3.04pp |
| NEURO | 2,419 | 1,850 | -1.80pp | -4.74 to 0.76pp |
| SICU | 693 | 553 | -6.59pp | -11.48 to -1.54pp |
| TSICU | 1,002 | 737 | -0.41pp | -5.06 to 3.41pp |

Subgroup comparisons are exploratory and not multiplicity-adjusted.
Baseline standardization cannot balance unrecorded prognosis, patient
preferences, documentation changes or unobserved discharge planning.
Residual temporal differences do NOT identify a clinical policy effect.

## Engineering and methodological adversarial checks

- An executed aggregate publication QA script verifies sample sizes,
  four horizon identities, equality to the original rollout,
  confidence interval containment and preserved simulator failures.
- The long-horizon rollout still fails its discharge and
  ICU-occupancy acceptance criteria. This is not a clinical model.
- Model errors were observed on the repeatedly used 2020–2022
  historical test era; a newly unseen system or period is required
  for independent prospective validation.
- Uncertainty conditions on fitted model and overlap weights.
  The 18 Monte Carlo simulation replicates address sampling only,
  not parameter and model uncertainty.
- Patient-level records and model checkpoints were never
  copied to GitHub or the public portal.

## Reproducibility

- 89_hazard_error_decomposition.py → aggregate decomposition JSON
- 90_transport_horizon_strata.py → aggregate horizon, subgroup JSON
- 91_rolling_origin_hazard.py → rolling-origin aggregate JSON
- 92_transport_publication_qa.py → aggregate QA JSON
- Reference fitted models and patient-level Parquet only inside
  the secure MIMIC-IV v3.1 server installation.

**Research conclusion:** much of the discharge simulation error
originates in a terminal hazard that does not transport to later
recorded practice, not merely in recursive physiological simulation.
The residual era difference is an observed-data transport problem,
not an identified intervention or treatment-policy effect.

## Additional administrative endpoint audit

A first ICU stay may be followed by a second ICU stay in the **same hospital admission**. Script 93_icu_return_audit.sql checks whether this changes the historical discharge comparison among the same hour-24 patients.

| Historical period | Eligible patients | ICU exits by day six | First ICU exit without another ICU admission within 24h | First ICU exit without another ICU admission within 7d |
|---|---:|---:|---:|---:|
| 2017–2019 | 9,838 | 77.14% | 74.93% | 71.84% |
| 2020–2022 | 7,147 | 72.59% | 69.71% | 66.87% |

Among those with a first ICU exit by five days, 217 in the earlier cohort and 206 in the later cohort returned to the ICU within the subsequent 24 hours of exit. The later-minus-earlier gap is −4.55 percentage points for the original competing endpoint and −5.23 points after excluding exits followed by a short-interval ICU return. Hence the broad historical discharge difference is not an artefact that disappears when rapid readmissions are excluded.

This is **retrospective endpoint sensitivity**. Future ICU return is unknown at initial discharge; the filtered endpoint must not be used as an as-of clinical predictor. The analysis remains observational and cannot attribute the period difference to hospital discharge policy or treatment choice.

## Real-time feature availability limitation

Derived vasopressor and invasive-ventilation intervals may incorporate later charted information in their end times. Strict prediction availability must be reconstructed using order entry and storetime, not only the final retrospectively derived interval table. Consequently the historical predictive benchmark is not yet a certified deployable as-of forecasting system.
