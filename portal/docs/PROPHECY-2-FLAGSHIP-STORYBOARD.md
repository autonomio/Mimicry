# Prophecy 2 — flagship visual investigation
## Scientific storyboard and interaction specification (B, v1)

**Title:** **A small order. A very big inference.**

**Central question:** *When clinicians document “do not resuscitate,” what else changes in recorded ICU care—and can we attribute those changes or deaths to the DNR order itself?*

**Reader promise:** In seven minutes, a nonspecialist should understand DNR versus DNI, see why who receives the order matters, recognize what changes before and after it, and understand why association does **not** establish causality. A scientist should be able to test those claims by changing study selections and reading the exact estimates, uncertainties, and provenance without leaving the narrative.

**Live MVP route:** \`/tracks/prophecy-2/stories/the-dnr-order/\`

**Research record:** Prophecy 2 Round 01, \`2026-10-25-dnr-question-fork\`. All displays use MIMIC-IV 3.1 only, with patient records remaining on the restricted server.

---

## Scene 0. Opening — The dilemma

**Question on screen:** “A small order. A very big inference.”

**Composition:** Dark editorial canvas, oversized restrained serif typography; a single DNR symbol surrounded by concentric, intentionally *nonquantitative* circles. No meaningless decorative patient-flow lines. A live link to the underlying estimates is always available.

**First 20 seconds:** The reader sees a simple clinical sentence: “When clinicians record do not resuscitate in intensive care, what changes next?” The next sentence asks the scientifically harder question: *Do we know why?*

**Interaction:** One “Follow the evidence” entry point, a table-of-contents strip for five scenes, no autoplay.

**Scientific boundary:** The illustration is symbolic. It carries no data. The empirical displays begin in Scene 2.

## Scene 1. Define the actual directive

**Question on screen:** “First, name the decision.”

Three clearly separated cards:

| Documented state | Clinical meaning | What it does not imply |
|---|---|---|
| Full code | Documented absence of a CPR limitation in this record | An undocumented chart must not be presumed full code |
| **DNR only** | No CPR attempted at cardiac arrest | Does not itself mean stop ventilation, vasopressors or other treatment |
| **DNR + DNI** | CPR and intubation limitations documented together | Not equivalent to universal comfort-only care |

**Progressive reveal:** Clinical definition before any statistics. Hover/focus can give more terminology in later versions, but the MVP keeps complete definitions visible.

**Plain-language anchor:** “The words on the order matter.” A nonspecialist should be able to restate that DNR is not a general instruction to stop care.

**Scientific anchor:** This choice is an *exposure definition*. If DNR-only and DNR/DNI are pooled, we no longer know what clinical intervention the reported association represents.

**Data:** Only definitions, not patient data. CMO is explicitly a separate care-goals state.

## Scene 2. Who entered the study?

**Question:** “Watch the study shrink.”

**Canonical graphic:** Gapminder-inspired aggregate-cohort bubble space.

- **X:** mean first-day SOFA (severity; higher implies more observed organ dysfunction).
- **Y:** proportion of ICU patient-hours on recorded invasive ventilation in the **six hours preceding** the first DNR order.
- **Bubble area:** number of qualifying DNR orders in each \`ICU group × DNR subtype\` aggregate.
- **Color:** coral DNR-only; mint DNR + DNI.
- **Interaction:** hover/focus = exact aggregate count, mean SOFA, mean previous-six-hour exposure; click = update active subtype for subsequent scenes.

**Three analytically defined states, not physiological time:**

| Selection rule | DNR-only | DNR + DNI | Total |
|---|---:|---:|---:|
| First eligible documented orders | 1,324 | 1,697 | 3,021 |
| Documented full-code comparator on measured common support | 792 | 1,222 | 2,014 |
| Stricter effective-control support | 378 | 1,045 | 1,423 |

**Choreography:** On button press or play, the circles move to the new *cohort-level means*, shrink as counts decline, and disappear if the cell is suppressed or excluded. The stage-level total changes from 3,021 to 2,014 to 1,423. The subtitle constantly states **“analytic stage — not patient time.”**

**Critical annotation:** 1,007 potentially informative DNR orders lie outside the standard matchable sample. The stringent restriction removes another 591. This is not “cleaning away noise”; it changes the population about which the research speaks.

**Privacy:** Source patient rows never enter the site. Displayed cells require \`n >= 30\`; complementary suppression protects small cells from being inferred through subtype totals. Suppressed cells stay in total counts and are not represented by invented bubbles.

**Avoid:** Do not animate patients crossing from DNR-only to DNR/DNI or imply individual trajectories from these cross-sectional stage means.

**Suggested exploratory extension:** Make “controls-per-case effective sample size” a toggleable bubble-axis variable only after exporting valid unit-level, privacy-safe aggregates with no hidden-source arithmetic problems. It is *not* a valid plot option until those data exist.

## Scene 3. What happens around the actual order?

**Question:** “The order is written. What moves?”

**Canonical graphic:** A **discrete event-time step plot**. No smoothed splines.

- Three outcome buttons: invasive ventilation exposure, vasopressor exposure, MAP recording intensity.
- Two explicit exposure buttons: DNR-only and DNR+DNI.
- Two observational series: indexed DNR orders and eligible documented-full-code risk sets aligned to equivalent ICU time.
- Nine complete, published source bins: \[-24, -20), ..., \[+8, +12) hours.
- Distinct dashed vertical line at **0 hours: recorded DNR order**.
- Play/pause and scrubber to inspect each four-hour bin.
- Tooltip/readout with the exact observed rate in each arm, anchored to the selected bin.

**Temporal choreography:**

1. Begin with \[-4,0) hours—immediately before the decision.
2. Allow scrubbing back to show the earlier trajectory; warning: some changes were already underway.
3. Reveal the \[0,+4) hours window only as the reader advances.
4. Invite switching from ventilation to blood-pressure recording, and from DNR-only to DNR+DNI.
5. Display the exact published *12-hour difference-in-changes* and approximate conditional interval as a separate summary. **Do not reuse that CI as a pointwise ribbon**.

**Important observations for DNR-only:**

- Invasive-ventilation exposure primary contrast about −7.78 percentage points; earlier-placebo estimate close to zero.
- Vasopressor exposure primary contrast about −5.63 percentage points; see the much weaker strict-overlap result in Scene 4.
- MAP measurement intensity primary contrast about −0.101 recordings per observed ICU patient-hour.
- Recorded extubation within four hours occurs in approximately 5.56% of the DNR-only events and 0.79% of weighted full-code comparators. These are procedure records, not unambiguous proof of palliative extubation.

**Causal warning:** The index time is endogenous. Clinicians may anticipate goals-of-care decisions and adjust other treatments before formal order documentation. Differential ICU discharge/death after time zero changes available measurement and support person-time.

**Never say:** “The DNR order caused a 7.78-point reduction in ventilation.”

**Acceptable claim:** “A documented DNR-only transition coincides with a larger change in recorded ventilation exposure than the selected observational comparison, under the displayed specification.”

## Scene 4. Try to break the estimate

**Question:** “Now try to break the finding.”

**Canonical graphic:** Sensitivity/identification matrix; rows are recorded outcomes, columns are analytical challenges:

| Outcome | Earlier pre-order trend | Immediate event window | Main window | Strict control overlap |
|---|---|---|---|---|
| Invasive ventilation | Estimate + CI | Estimate + CI | Estimate + CI | Estimate + CI |
| Vasopressors | Estimate + CI | Estimate + CI | Estimate + CI | Estimate + CI |
| MAP recording | Estimate + CI | Estimate + CI | Estimate + CI | Estimate + CI |

**Encoding:** Small intervals, zero-reference marks, conditional CIs, one highlighted selected cell. Selection opens a full-language explanation of what was estimated and whether the interval includes zero.

**Key “Aha” moment:**

DNR-only vasopressor result changes from roughly **−5.63 pp** to **−0.45 pp**, with an interval spanning zero, under the stricter control-support rule.

**But the stricter DNR-only sample itself fails measured covariate balance** (maximum absolute SMD 0.318). It does not restore causal credibility. The narrative must explicitly avoid claiming that either one of these specifications is a better causal estimate.

**Reader choices:** Switch outcome, subtype, and specification; preserve comparison semantics in the selected-cell explanation. No hidden regression table required to understand why the headline gets weaker.

**Scientist details:** exact estimates, intervals, sample counts, effective controls and measured-balance failures; link to the original matched-risk-set design.

## Scene 5. Can we say the order caused deaths?

**Question:** “Did the order cause the deaths?”

The audience now knows how much evidence was filtered, how treatment/monitoring changed, and how sensitivity affects the association. We can finally reveal the apparently dramatic mortality contrast.

**Zero-based risk bars, common 0–30% axis:**

- DNR-only: approximately **19.32%** in-hospital death within 12 hours.
- Weighted full-code comparison: approximately **1.70%**.
- The corresponding **17.62 percentage-point observational difference** has a published fixed-weight approximate CI of 14.83–20.40 pp.

The bars describe **observed outcomes**. They do not encode counterfactual lives saved/lost or imply that CPR itself was attempted.

**The evidence ladder:**

1. **Observed:** Outcomes differ.
2. **Fragile:** Rich matching still leaves important unrecorded prognosis, preferences and large selection differences. The strict overlap sample loses 414 of 792 DNR-only cases, and the resulting measured-balance diagnostic fails.
3. **IV unvalidated:** Only 48 of 62,078 ICU-time code-status orders were entered by the recorded hospital admitting provider. This is a **provenance warning**, not proof that no possible provider-style instrument could ever work. No credible preassignment/exclusion mechanism has been established.
4. **Not identified:** The isolated causal contribution of a DNR-only designation to death remains unknown.

**Last line:** “We observe decisions. We do not observe every reason.”

**Exit paths:** Original research methods, source code, exact quantitative release, and an ordinary-language explanation of why selection bias matters. No clinical action recommendation.

---

## Story synchronization: what should stay consistent

The selected **DNR subtype** propagates between scenes 2, 3, 4 and 5. The selected study stage affects **only** the bubble-space population, not the full-study outcome estimates elsewhere; doing otherwise would silently misrepresent the analytical sample. The event-time scrubber changes the highlighted recording window, not the 12-hour estimator. The sensitivity matrix changes the *specification*, not the state of the simulated patient.

Each control must advertise which dimension it changes. All statistical terms have a reader-friendly explanation in place and an inspectable source record.

| Control | Changes | Must not change |
|---|---|---|
| DNR-only / DNR+DNI | Explicit exposure subtype across all scenes | Underlying eligibility rules, released sample totals |
| Cohort stage | Analysis-population means and counts in CohortSpace | Retrospective time index or already published treatment-effect estimands |
| Outcome button | Variable and unit in event-time chart | Code status or anchor-time definition |
| Scrubber | Highlighted observed four-hour rate | Full-window estimate or CI |
| Sensitivity cell | Analytical specification being interpreted | The raw record or causal identification status |

## Visual and scientific acceptance test

A successful first-time reader should answer all four questions correctly:

1. Is DNR-only equivalent to withdrawing ventilatory support? **No.**
2. Did the 1,007 unmatched DNR events simply have “bad data”? **No; the sample changed because appropriate controls could not be found.**
3. Does seeing a decline after time zero prove the order initiated it? **No; the event time is endogenous and clinical changes may precede documentation.**
4. Does the 19% versus 1.7% short-term death difference establish DNR caused excess deaths? **No; prognosis, care goals and other decisions remain unobserved.**

An expert should additionally be able to identify the person-time denominator, the difference-in-changes estimand, absence of pointwise bands, subtype distinctions, failed balance, and the limitations of the provider-preference IV.

## Design evolution after v1

The current MVP implements the five scenes and canonical cohort, time, matrix and claim components. A next iteration can add a true competing-state flow **only if a validated state-history aggregate exists**, pointwise uncertainty only if correctly estimated, narrated scroll-trigger annotation steps without autoplay, multi-device reader testing, and formal accessibility audits. Those are extensions, not claims that the present implementation is already a validated causal research application.

**The editorial purpose remains fixed:** make the DNR question and its limits easy to see, difficult to distort, and impossible to confuse with the unrelated general mortality simulator.
