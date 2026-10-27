# DNR validation audit — 27 October 2026

## Decision

**The DNR-only finding was computationally reproduced, but a stronger comparison was not established.** The locked design could not simultaneously balance the recorded baseline features and prevent a few control people from dominating the comparison. It failed in the full DNR-only candidate graph and in both patient-disjoint internal partitions. No new DNR-only effect estimate was calculated for these failed designs.

This strengthens confidence that the original published numbers were calculated as described. It does **not** upgrade the DNR-only finding to a validated treatment effect or an independently replicated clinical result. Failure is specific to the declared rules and existing candidate graph; it is neither evidence of zero effect nor proof that every possible comparison design must fail.

The machine-readable evidence is [validation_aggregate.json](validation_aggregate.json). The rules are in [PROTOCOL.md](PROTOCOL.md); the implementation was committed at `f233dfd6046dc188b243859583b6df66744f3685` before this clinical-data run.

## What passed, and what did not

| Check | Result | Meaning |
| --- | --- | --- |
| Original numerical reproduction | **Passed**, both subtypes | Independently implemented arithmetic reproduced the archived arm rates, denominators, rate-implied numerators and published contrasts. |
| Independent source extraction | **Passed** | New source queries reproduced the old measurement definitions, including observation time, ventilation, pressors and MAP recording. |
| Recorded status and order time | **Passed** | Structured status at the anchors and treated order timestamps reconciled. This does not verify clinical intent or conversations. |
| DNR-only comparison quality | **Not established** | Full design and both internal partitions were infeasible under the locked balance and support constraints. |
| DNR+DNI comparison quality | **Passed in full design and partition 1** | These are secondary, separate findings; partition 0 failed. |
| Two-partition internal consistency | **Not established**, either subtype | Neither subtype had two passing, independently fitted partitions. |
| Death/ICU-exit interpretation | **Not established by the public output** | Required states were constructed; all partitions were withheld by the disclosure rules. Withheld values are not zero or absent events. |
| Full-pipeline uncertainty | **Not established** | Reported intervals condition on the selected graph, fitted design and weights. |
| Independent-cohort replication | **Not performed** | The same MIMIC-IV v3.1 hospital dataset was used throughout. |
| Clinical-intent validation and causal identification | **Not established** | Recorded DNR-only is not verified isolated CPR-only intent. |

## The stricter comparison

The original graph contains 792 represented DNR-only events and 1,222 represented DNR+DNI events, from 3,021 eligible events overall. It does not contain all otherwise eligible cases or every possible control. This validation retained the graph rather than searching new populations after viewing outcomes.

For each treated event, control weights had to sum to one, with no one control person supplying more than half that comparison. Across a fitted design, a control person could supply at most two case-equivalents. Simultaneously, each recorded baseline feature and missingness indicator had to satisfy the prespecified mean-balance constraint; independent post-fit checks required conventional absolute standardized differences no greater than 0.10 and adequate effective control counts.

All six designs were fitted before the outcome stage. The solver explicitly reported mathematical infeasibility for the failed fits, rather than a timeout. Constraints were not relaxed after failure.

| Recorded status | Design | Treated events after the baseline membership screen | Verdict |
| --- | --- | ---: | --- |
| DNR only | Full graph | 792 | Infeasible |
| DNR only | Internal partition 0 | 363 | Infeasible |
| DNR only | Internal partition 1 | 346 | Infeasible |
| DNR+DNI | Full graph | 1,222 | Passed |
| DNR+DNI | Internal partition 0 | 558 | Infeasible |
| DNR+DNI | Internal partition 1 | 563 | Passed |

These are **events, not unique people**. All appearances of a person, including control and treated roles, were assigned to the same internal partition. Partition screening removes risk sets with fewer than two distinct control people. The full design overlaps its partitions, so full-design agreement with partition 1 is not two independent replications.

The full DNR+DNI design had maximum conventional absolute standardized difference 0.0686, at least two effective control people per risk set and overall control-person effective count 1,468.8. Its within-case and overall person-weight caps were satisfied. Passing these measured checks does not establish similarity in unrecorded prognosis, preferences or treatment decisions.

## Secondary DNR+DNI results

The primary window compares the twelve hours before with the twelve hours after the recorded order. Each value below is the DNR+DNI change minus the control change, measured per observed ICU hour. A percentage-point value is a difference in the share of observed time receiving the recorded treatment; it is not a patient-level probability or a causal treatment effect.

| Design and outcome | Difference in changes | Approximate conditional 95% interval |
| --- | ---: | ---: |
| Full DNR+DNI: invasive ventilation | −6.72 percentage points | −8.86 to −4.58 |
| Full DNR+DNI: positive-dose pressor exposure | −4.13 percentage points | −5.70 to −2.56 |
| Partition 1 DNR+DNI: invasive ventilation | −7.79 percentage points | −10.86 to −4.72 |
| Partition 1 DNR+DNI: positive-dose pressor exposure | −3.68 percentage points | −5.84 to −1.52 |

The separate four-hour ventilation comparison was also negative in the two passing DNR+DNI designs; exact results are in the aggregate JSON. Positive-dose and any-charted-pressor results were identical in these designs. MAP and the ventilation-plus-tracheostomy sensitivity were suppressed by the disclosure rules. No inference of absence or a null effect follows from suppression.

Intervals cluster a person's contributions across all anchors and both arms, with a finite-cluster correction. They omit uncertainty from selecting the graph, fitting weights and choosing among prior exploratory analyses. These secondary results are not adjusted for multiple testing. Death and ICU exit truncate observation; the public follow-up state summaries cannot establish that these processes explain or fail to explain the associations.

## Reproduction and independent measurement audit

The new arithmetic reused the original baseline calibration because separately persisted original fitted weights were unavailable. It did not import the original outcome-contrast functions. Its inputs and the source study commit were hashed.

Across both subtypes, the maximum absolute published point-estimate discrepancy was approximately `2.09e-14`; the largest weighted-observation-time discrepancy was approximately `3.64e-11` hours. Both are far below the declared `1e-8` tolerance. Archived numerator references were reconstructed from archived arm rates and denominators; pre-order time follows the original twelve-hours-per-risk-set convention. This is a numerical consistency check, not independently collected evidence.

Independent source queries then rebuilt all nine four-hour bins around every represented anchor. The legacy-equivalent observation times, strict invasive-ventilation capped sums, deduplicated pressor capped sums and MAP source-row counts all reconciled within tolerance. Unioned strict ventilation, unioned any-charted pressors, distinct MAP timestamps and independently reconstructed observation time also agreed with the corresponding cached measures in this graph. Potential overlap and duplicate-handling problems were explicitly tested; they did not change those measurements here.

The outcome queries share the original MIMIC-IV derived source tables. They validate implementation against those sources, not the correctness of every bedside event, the entire upstream derivation, or the underlying clinical intent.

## Verification, provenance and release boundary

The complete synthetic suite passed on the research server: **36 tests**, including all seven DuckDB integration checks. It covers interval unions, duplicate handling, clipping, fractional timestamps, fixed-horizon death/exit states, patient clustering, matching caps, missingness, infeasible support and disclosure by subtraction. Separate computational and disclosure reviews checked the implementation and actual aggregate release. These are not peer review or independent clinical adjudication.

The clinical run began at **2026-10-27 17:03:22 UTC** and completed at **17:03:33 UTC**. The source database was opened read-only; its size and modification time were unchanged. Runtime versions and input, protocol and implementation hashes are recorded in the aggregate JSON.

Patient records, row-level weights and private diagnostics remained on the authorized server. The release applies the minimum of 30 distinct people to nonzero cells, joint design memberships, paired definitions and nested time-window contributions. Public contrasts omit arm rates, denominators and patient-cluster totals. Suppressed outputs must not be reconstructed from private diagnostics in a later publication.

## Next decision

Keep the DNR-only result as a **preliminary observed association with a failed stronger-comparison check**. A further study needs a separately specified, clinically defensible population or candidate graph, followed by another hospital cohort and verification of what the recorded orders actually meant. None of those additional gates has been completed here. A baseline-ventilated discontinuation analysis with competing events also remains future work.

Do not promote the present result as a causal effect of writing a DNR order or as independent clinical replication.
