# Prophecy 2 — The DNR question

**Separate research track within Mimicry.** Forked at the MIMIC-IV DNR **event-history and risk-set** stage, before Prophecy's generic ICU mortality simulator.

## Central question

**Does a new DNR-only order itself change life support or mortality, or does it record a prognosis and wider care decisions already underway?**

DNR alone limits CPR at cardiac arrest. It is not a withdrawal-of-ventilation or withdrawal-of-vasopressors order. **DNR-only is not equivalent to DNR/DNI, comfort-only care, or a well-defined treatment bundle.** Changes recorded after a DNR order do not establish that writing the order caused those changes.

## Research fork and methods

Original restricted cohort: /srv/mimic-iv/studies/decision_feedback_20261025/

New independent study: /srv/mimic-iv/studies/prophecy2_dnr_20261025/

The new track reuses the already audited first ICU stay, actual hospital POE DNR-order timestamps, and eligible full-code risk sets. It does not extend or inherit the generic mortality-model research question.

The first research round uses:

- **01_dnr_fork.py:** Reconstructs separate DNR-only and DNR/DNI comparisons using previously audited restricted data, balances recorded pre-order physiology, treatment, monitoring, laboratory values and clinician-time proxies, and evaluates care changes at the order.
- **02_phenotype_provider_audit.sql:** Audits source status provenance and why ordering-provider preference cannot be assumed to be an IV.
- **03_later_limitation_audit.sql:** Audits later DNI/comfort documentation and explicit extubation; missing records do not prove absence of other clinical decisions.
- **04_publication_qa.py:** Fails publication if cohort algebra, intervals, provenance or essential unidentified-causality warnings are missing.

**Population:** 3,021 first documented FULL-to-DNR events more than 24h and fewer than 14d into ICU, of which 2,014 have common-support full-code risk-set comparators. 1,007 events have insufficient comparison support. The 2,014 comprise **792 DNR-only** and **1,222 DNR/DNI**. Unrecorded code status is UNKNOWN, never automatically full code.

**Estimand:** Weighted difference in before/after treatment or monitoring rates, newly documented DNR versus eligible documented-full-code comparison, normalized by observed ICU person-hours. It is not a potential-outcome treatment effect.

### Initial descriptive DNR-only result

- Invasive ventilation exposure: relative before–after change **−7.78 percentage points** (approximate fixed-weight patient-clustered 95% CI −10.44 to −5.12).
- Vasopressor exposure: **−5.63 points** (−7.67 to −3.58).
- MAP recordings: **−0.1005 records per observed ICU hour** (−0.1365 to −0.0645).
- Explicit extubation within 4h: **5.56%** after DNR-only versus **0.79%** after matched full-code pseudo-time.
- Hospital death within 12h: **19.32% versus 1.70%**, a critical warning of residual confounding, *not deaths caused by DNR*.

**Overlap falsification:** 414/792 DNR-only risk sets have fewer than two effective controls. With stricter control restrictions, the vasopressor comparison attenuates toward zero. That restricted cohort also **fails measured baseline balance** (max absolute standardized difference 0.318), so it cannot be presented as a better-adjusted causal result. The primary matched estimates also remain retrospective, conditional on fitted weights and unresolved unobserved prognosis.

### Why the physician-leniency IV cannot be used yet

Across 62,078 ICU-time code-status orders, only 48 were entered by the hospital admitting provider. Order-provider ID is documented at the decision; hospital admitting provider is not automatically the ICU physician assigned before the decision. Strong provider variation or first-stage F does not establish as-if-random assignment, exclusion or a causal mortality LATE.

## Scientific stopping rules

1. Do not combine DNR-only with DNI or comfort-only interventions.
2. Do not select decedents or 12h ICU survivors to define exposure groups.
3. Do not turn death, ICU discharge or monitoring cessation into proof of withdrawal; these are co-evolving processes.
4. Do not claim adjustment removed preferences, neurological prognoses, treatment intent or undocumented orders.
5. Do not quote model uncertainty as fully accounted for: current intervals condition on fitted matching weights and retrospective choices.
6. Do not infer cardiac-arrest/CPR effects without auditing arrest and resuscitation ascertainment.
7. Do not claim physician IV validity without real pre-exposure assignment, negative controls and exclusion.
8. Do not label information as prospectively available just because it has an earlier charttime; derived treatment intervals may incorporate later documentation.
9. Do not download new data or publish patient-level records, fitted models or protected PhysioNet content.

## Bounded next experiments

### Validation update — 27 October 2026

The [locked validation audit](validation/RESULTS.md) reproduced the original numerical results and independently reconstructed their source measurements. **The stricter DNR-only comparison could not be established:** the full candidate graph and both patient-disjoint partitions were infeasible under simultaneous balance and control-person weight caps. No new DNR-only effect was estimated for the failed designs. DNR+DNI passed in the full graph and one partition, but two-partition internal consistency was not established for either subtype. External replication, verified clinical intent and causal identification remain unestablished. See the [protocol](validation/PROTOCOL.md) and [reviewed aggregate output](validation/validation_aggregate.json).

**A. Phenotype:** Audit simultaneous status and withdrawal/comfort orders at the DNR timestamp.

**B. Mechanism:** Test immediate non-CPR treatment changes under defensible overlap, anticipation controls and competing exits. Accept null or nonidentification outcomes.

**C. Mortality:** Verify whether cardiac arrest/CPR data support an isolated DNR intervention and whether preassigned clinician variation satisfies IV conditions. If not, provide partial-identification bounds, not invented causal point estimates.

**No further generic ICU simulator is in scope for Prophecy 2.**

## Reproduction and access

Run **run_dnr.sh** on the authorized MIMIC-IV v3.1 server, where parent restricted Parquet files already exist. The script reads source data locally and writes only aggregate JSON. This repository contains source code and an independently reviewed aggregate release, not patient-level records.
