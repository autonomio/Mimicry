# Prophecy 2: locked validation protocol

**Protocol date:** 2026-10-27. **Source research commit:** `dab401a79bb63e563448dae29c5145d6377b3a17`.

This protocol is written before the new validation outcome comparisons. The source MIMIC-IV v3.1 data and the original findings have already been examined. This is a specified reanalysis and internal validation of an explored dataset, not an untouched holdout, a prospective clinical study, or external replication. Record the protocol and implementation hashes with each run; document any subsequent amendment before running the amended comparison.

## 1. Questions and boundaries

The primary question is whether the observed change in invasive-ventilation exposure around a first documented DNR-only order remains evident when measured covariate balance and control support are required simultaneously. DNR+DNI is a separate secondary exposure with an independently fitted design. Neither exposure identifies an isolated change in clinical intent.

The validation has distinct stages:

1. Independently extract treatment intervals and measurement counts and audit their definitions against the source workflow.
2. Reproduce the original numerical contrasts using its original definitions and original fitted weights, reconstructing the original calibration if those weights were not persisted. Independently implemented outcome arithmetic must not import the original rate-contrast functions. Report any reused extraction or calibration code explicitly.
3. Fit the new baseline-only constrained comparison, then calculate the locked outcomes only if its design gates pass.
4. Refit the same design separately in two patient-disjoint internal subsets.

Only the authorized MIMIC-IV v3.1 environment is in scope. No new external dataset download, patient-level export, clinical intervention, or physician-instrument claim is authorized by this protocol. Independent computation on the same source is not independent-cohort replication.

## 2. Source population and candidate graph

Use the frozen original risk-set graph and its documented index times. The source includes the first eligible ICU stay per admission, not necessarily one admission per person. Retain these original treated events; do not introduce an earliest-event-per-subject filter. Cluster all appearances of a person together in inference.

The primary design starts with all DNR-only treated events represented in the original matched graph. It cannot recover originally unmatched DNR events without constructing and specifying a new candidate graph. Report original eligible, originally represented, excluded-for-support, and retained counts separately. Do not describe the retained graph as representative of every eligible DNR event.

Controls must be eligible and explicitly full code at their index anchor. Exclude an anchor belonging to the same subject as its treated case. Before fitting, exclude a treated risk set if it has fewer than two distinct eligible control subjects. This screen uses baseline membership only. Retain all other eligible risk sets for the main fit; do not search outcome results for a favorable smaller cohort.

Do not exclude a control for subsequently receiving DNR/DNI/CMO, dying, or leaving the ICU. A currently full-code control may also contribute a later treated event. That person's observations must remain together for subject-level dependence and internal splitting. The contrast concerns initial recorded status, allowing subsequent changes; it is not a sustained twelve-hour treatment-policy contrast.

## 3. Baseline features and missingness

Use the original specification's pre-index features and distance scales:

| Feature | Distance scale |
| --- | ---: |
| `sofa` | 2 |
| `age` | 15 |
| `mean_hr` | 25 |
| `mean_map` | 20 |
| `mean_rr` | 8 |
| `mean_spo2` | 7 |
| `hr_n_early`, `hr_n_recent`, `map_n_early`, `map_n_recent` | 6 |
| `hr_n_last4`, `map_n_last4` | 3 |
| `hr_6h_change` | 12 |
| `map_6h_change` | 10 |
| `pressor_h_early8_frac`, `pressor_h_last4_frac` | 0.25 |
| `invasive_h_early8_frac`, `invasive_h_last4_frac` | 0.35 |
| `ne_mean_dose_hours_early8_frac`, `ne_mean_dose_hours_last4_frac` | 0.2 |
| `noninvasive_h_early8_frac`, `noninvasive_h_last4_frac` | 0.25 |
| `has_lact24` | 0.5 |
| `n_lact24_cap` | 1.5 |
| `lact_latest24_clean`, `lact_max24_clean` | 2.5 |
| `has_gcs12` | 0.3 |
| `gcs_latest12_clean`, `gcs_min24_clean` | 3 |
| `creat24_clean` | 1.5 |
| `bun24_clean` | 30 |

For the new design, the legacy `*_clean` labels use the following underlying raw measurements before new imputation:

| Legacy feature label | Raw source |
| --- | --- |
| `lact_latest24_clean` | `lact_latest24` |
| `lact_max24_clean` | `lact_max24` |
| `gcs_latest12_clean` | `gcs_latest12` |
| `gcs_min24_clean` | `gcs_min24` |
| `creat24_clean` | `creat_latest24` |
| `bun24_clean` | `bun_latest24` |

All other original features retain their source definitions. Within each independently fitted design, impute missing values using that design's treated baseline median and add an indicator for every feature with any missing values in either arm. Missing indicators have distance scale one. This preprocessing uses no post-index outcomes.

If a feature is missing for every treated event, use a numerical placeholder only for computation and require exact balance of the missingness indicator. Finite control measurements cannot stand in for an entirely missing treated feature. Report that this feature supplies no observed treated information. If both arms are constant but unequal, balance fails; a zero denominator must never be interpreted as perfect balance. Do not replace missing pairwise differences with zero without the declared imputation and indicators.

## 4. Simultaneous balance and support

Use a sparse linear program with one nonnegative weight per eligible control anchor. Every retained treated event has weight one. Minimize the sum of the original-scale squared pre-index distances, including missingness-indicator differences, subject to all of these constraints:

- Control weights sum to one within each treated risk set.
- Within each risk set, the **sum** of weights belonging to any one control subject is at most **0.5**. An anchor-level cap alone does not satisfy this rule.
- Across the entire fitted design, any control subject contributes at most **2.0** total case-equivalents.
- Each pooled control feature mean differs from the treated mean by at most **0.05** frozen baseline standard deviations. Freeze the scale as the square root of the mean of the two unweighted arm-specific baseline variances after preprocessing. Use the fixed scale in the linear constraints; do not substitute a weight-dependent denominator. Zero-scale variables require the constant-value check above and exact mean agreement.

Use the same constraints for each subtype and each internal subset. No outcome value enters the objective, candidate eligibility, feasibility decision, or constraint selection.

After fitting, independently check:

1. Solver feasibility, nonnegative weights, risk-set normalizations, and both subject-level weight caps.
2. Frozen-scale absolute SMD at most **0.10** for every feature and missingness indicator, with the tighter **0.05** linear bound also checked against numerical tolerance.
3. Conventional weighted absolute SMD at most **0.10** for every feature and missingness indicator. Its scale is the square root of the mean of the two weighted arm variances. Constant unequal arms fail.
4. At least two distinct positive-weight control subjects and effective control-subject count at least **2** in every risk set. Calculate ESS after aggregating a person's anchors within that set.
5. Global control-patient ESS at least **0.5 times the retained treated-event count**, after summing each person's control contributions across all risk sets.

These are declared diagnostic thresholds, not proof of unmeasured exchangeability. Report treated events, unique treated people, control anchors, unique control people, patient ESS, maximum patient contribution, and all balance failures.

**A failed or infeasible design produces no validated comparison cohort.** Record the failure and do not loosen constraints, remove difficult covariates, or select a smaller cohort after inspecting outcomes. A missing or empty candidate cohort is also an explicit failure to establish the comparison, not a zero effect. Any later population restriction requires a new documented analysis and new target means, weights, and checks.

## 5. Independent outcome extraction and definition checks

Extract intervals independently and union overlapping intervals before calculating exposure duration. Clip intervals to the relevant observation window and verify that exposure duration cannot exceed observed ICU duration. Keep source timestamps, duration rules, and duplicate handling explicit in the run metadata.

- **Invasive ventilation, primary:** intervals classified `InvasiveVent`. Report a separate inclusive sensitivity adding tracheostomy intervals. Do not silently equate the two definitions.
- **Vasopressors, secondary:** union of intervals with a positive recorded dose (`dose > 0`) using the applicable source dose field. Retain the legacy any-pressor-interval definition as a separate sensitivity. Do not call a zero-dose interval active exposure.
- **MAP charting, secondary:** count distinct timestamps with a non-null MAP measurement in the specified window. Retain source-row counts as a separate sensitivity. This measures documentation, not all monitoring performed.

Original-definition arithmetic reproduction and the new outcome-definition analysis are separate outputs. Differences caused by a declared stricter ventilation, pressor, MAP, or observation-window definition are not automatically arithmetic reproduction errors. Compare like definitions and denominators first, then quantify definition sensitivity.

The original-reproduction gate requires agreement of eligible counts, weighted numerators, denominators, and point contrasts with the archived source result, subject to an absolute rate tolerance of **1e-8** when inputs and definitions are identical. Explain every larger discrepancy. Reuse of cached outcome tables alone does not pass independent extraction.

## 6. Primary contrast and competing events

The primary contrast is the weighted difference in changes in recorded invasive-ventilation exposure per observed ICU hour: DNR-only minus full-code controls, comparing **[-12, 0) hours** with **[0, 12) hours** around the index. The **[-4, 0) versus [0, 4)** contrast is secondary. Vasopressor exposure and MAP charting use the corresponding twelve-hour contrast as secondary outcomes. DNR+DNI results are separately estimated secondary findings.

This primary measure is an observed-person-time rate. It is not a patient-level policy effect and can change when the composition of surviving, observed ICU time changes. Do not fill time after recorded death or ICU exit with zero treatment. Report the original source denominator convention for reproduction and the independently calculated denominator convention for validation; reconcile any difference.

Required accompanying summaries at **4 and 12 hours** classify each anchor into mutually exclusive states, using recorded hospital death by the horizon first, followed by ICU exit and recorded ventilation:

1. Recorded hospital death by the horizon.
2. ICU exit by the horizon without recorded hospital death by that horizon.
3. Still in the indexed ICU, with recorded primary invasive ventilation at the horizon.
4. Still in the indexed ICU, without recorded primary invasive ventilation at the horizon.
5. Unknown or contradictory timing/state information.

State 2 does not establish that the person is alive; absence of recorded hospital death after ICU exit does not verify post-exit survival. State 4 does not establish absence of every form of support. Report state definitions, observation time, and any unknown-state imbalance. If the required state information cannot be constructed, mark the competing-event interpretation gate **unmet**.

Do not restrict the main analysis to people who survive or remain in the ICU for twelve hours. Do not remove or adjust away subsequent CMO/DNI to claim that the remaining observations represent isolated clinical intent. Subsequent limitation documentation is descriptive follow-up information.

A baseline-ventilated extubation/discontinuation analysis with competing events would help distinguish discontinuation from reduced initiation. It is **not promised or required as implemented in this iteration**; report it as future work if unavailable, not as a completed mechanism validation.

## 7. Conditional uncertainty only

Report approximate **95% fixed-design, fixed-weight subject-cluster intervals**. Aggregate each person's influence contributions across all anchors and both arms before calculating variance, preserving pre/post covariance and control reuse. Use delta-method ratio contributions for person-time rates and the corresponding weighted-mean contributions for proportions; the difference-in-changes contribution combines the two periods and two arms with their appropriate signs.

These intervals condition on the chosen candidate graph, retained cohort, imputation, fitted LP weights, and outcome specification. They do not include matching/weight-estimation uncertainty, selection among exploratory analyses, or uncertainty about unrecorded clinical intent. Do not label them full-pipeline or causal confidence intervals.

**Full-pipeline uncertainty is NOT ESTABLISHED in this iteration.** No bootstrap claim is made. Resampling subjects would change the sparse candidate graph, caps, optimization, and feasibility; a valid refitting procedure requires a separately specified implementation and validation. Conditional intervals cannot pass this unmet gate.

For the primary rate contrast, a conditional interval entirely below zero supports a negative association conditional on the design; an interval including zero is inconclusive, not evidence of no association. Neither outcome establishes causation. Secondary endpoint intervals are exploratory and are not multiplicity-adjusted confirmatory tests.

## 8. Patient-disjoint internal checks

Assign each subject deterministically to one of two strata using SHA-256 of the ASCII decimal subject ID: interpret the first eight digest bytes as an unsigned big-endian integer and take modulo two. Keep every admission, treated event, and control anchor belonging to that person in the same stratum.

Within each stratum, retain only treated and control subjects assigned to that stratum. Repeat the fewer-than-two-control-subject screen, imputation, scale calculation, LP fit, and all gates independently. Do not reuse full-sample weights or move a control to the other stratum to rescue feasibility.

These are internal checks in already seen data. Report each stratum's design status, retained population, conditional estimate and interval. One failed, empty, or imbalanced stratum means that a two-stratum comparison was **not established**. A directionally consistent but imprecise result is distinguishable from two statistically supported results. Neither is external replication.

An early pre-event comparison, if reported, is a descriptive diagnostic. Non-significance is not evidence of equivalence; a trajectory constrained or selected through matching is not independent causal validation. This iteration makes no new untouched-negative-control claim.

## 9. Disclosure and final verdicts

Patient records, identifiers, database credentials, and row-level intermediate files remain in the restricted environment. Public outputs contain aggregate results only. Apply the existing minimum of **30 unique people** per disclosed nonzero cell, with complementary suppression. For a state partition, suppress the whole partition if any nonzero category has fewer than 30 unique people. Check differences between nested cohorts and subsets before disclosing counts or denominators that would reconstruct a suppressed group.

Evaluate joint anchor-membership cells across the original graph, full design and both internal partitions, counting distinct contributing people within each cell. If any nonzero cell is too small, suppress the related counts, fitted numerical diagnostics and state partitions together; retain fixed rules and categorical gate verdicts. For paired outcome definitions or nested time windows, also suppress a secondary contrast when subtracting it from the primary contrast isolates contributions from fewer than 30 people. Source rows and private diagnostics may be inspected inside the restricted environment, but only the reviewed aggregate release crosses that boundary.

Report separate verdicts for:

| Gate | Requirement or explicit limitation |
| --- | --- |
| Independent extraction | Source-derived intervals/counts audited; cached-table reuse alone is insufficient |
| Numerical reproduction | Original definitions and weights reconcile within declared tolerance |
| Comparable measured support | LP feasibility and every post-fit balance/support gate pass |
| Observed ventilation association | Primary conditional estimate and interval reported only for a valid design |
| Competing-event interpretation | Required recorded-death/ICU-exit/ventilation states and denominators available |
| Internal checks | Independently fitted, patient-disjoint strata with their own pass/fail status |
| Full-pipeline uncertainty | **Not established in this iteration** |
| External replication | **Unmet unless a separately authorized independent cohort is actually available and analyzed** |
| Clinical-intent validation | **Unmet unless independently verified intent data are actually available and analyzed** |
| Causal identification | **Not established by this observational validation** |

Accept failure and inconclusiveness as results. A successful computational or balance check must not be presented as clinical validation, external replication, or proof that writing a DNR order caused treatment withdrawal or death.
