# Mimicry Visual Engine — implemented MVP (v0.1)

**Status:** Executable research-storytelling prototype. **First adapter:** Prophecy 2, DNR decision. **Research standard:** all marks are source-linked aggregates; animation changes analytical views, not patient outcomes.

**MVP URL:** \`/tracks/prophecy-2/stories/the-dnr-order/\`

## 1. Product premise

Mimicry is neither a PDF site nor a BI dashboard. Each investigation opens with **one falsifiable scientific question** and reveals the empirical argument in stages. A reader can follow one understandable narrative, then interrogate the same evidence as a scientist. The user controls the pace and can always inspect an exact numerical table and source methods.

**Gapminder inspiration:** use spatial comparison, interactive cohort selection, persistent marks, play/pause, and visible motion to make a system of relationships legible. Do not use motion to imply a transition the data do not observe. A circle should never represent a fictitious patient.

### Story grammar

\`Question → Defined exposure → Population selection → Observed process → Design sensitivity → Mortality association → Claim boundary\`

This structure is independent of the underlying disease or research track.

| Story element | Role | Not allowed |
|---|---|---|
| **Hero question** | State the clinical or scientific tension in ordinary language | Make an unidentified causal claim |
| **CohortSpace** | Show where aggregate strata sit and what study filters remove | Animate movement as though individuals physically changed state |
| **EventTime** | Reveal directly observed rates and discrete time bins | Smooth/interpolate invented physiological observations |
| **EvidenceMatrix** | Show sensitivity to analysis specification, balance and intervals | Present conditional intervals as randomized treatment effects |
| **ClaimAudit** | Show observed mortality on a fixed axis and the four-step identification ladder | Draw hypothetical deaths prevented or omit the failed IV and overlap audits |

## 2. Implemented source modules

- \`site/viz/core.js\`: shared semantic palette, number formatting, DOM helpers, area-proportional bubble radii, publication/source validator, and scientific labels.
- \`site/viz/cohort-space.js\`: responsive SVG aggregates with x/y scales, stage transition animation, hover/focus details, keyboard-selectable aggregate marks, accessible table and study-selection playback.
- \`site/viz/event-time.js\`: measured four-hour step-chart, zero-hour decision line, timeline scrubber, play/pause, outcome switching, subtype switching and all-bin numeric table.
- \`site/viz/evidence-matrix.js\`: reusable uncertainty-whisker grid, explicit zero references, early-placebo/near-order/primary/strict-overlap comparisons, support/positivity warnings and keyboard-operable estimate selection.
- \`site/viz/story.js\`: four-scene Prophecy 2 story adapter; shares selected subtype across all three core visual modules.
- \`site/viz/viz.css\`: portable visual tokens and responsive research layout.
- \`data/stories.json\`: declarative story registry; each entry binds a track, route, public aggregate source and original research release.
- \`data/viz/prophecy2-observations-v1.json\`: privacy-screened aggregate data only (no patient-level rows).

The existing Mimicry releases/methods pages are preserved. The new story is another navigable interface to the same release and must not mutate its numerical claims.

## 3. Data contract (strict)

Every story identifies a **canonical release ID**. Its visual dataset must assert the same \`track\`, \`release_id\`, cohort totals, status subtypes and analyzed outcome units.

MVP data:

\`\`\`text
scientific-viz-aggregate@1
 ├─ track / release_id / provenance
 ├─ cohort_bubbles
 │   ├─ stages[]                  [eligible, supported, strict]
 │   ├─ counts[stage].n
 │   ├─ counts[stage].subtypes
 │   ├─ min_cell_n = 30
 │   ├─ complementary_suppression = true
 │   ├─ stable_partition = true
 │   ├─ min_cross_stage_attrition = 30
 │   └─ points[] {stage, id, subtype, unit, n, sofa, invasive_before}
 └─ event_time
     ├─ from_hours = [-24,-20,-16,-12,-8,-4,0,4,8]
     ├─ metrics[] {id, label, unit}
     ├─ series[] {subtype, metric, arm, from_hour, to_hour, value}
     ├─ pointwise_ci_available = false
     └─ event_time_is_endogenous = true
\`\`\`

The cohort circles are **stable, nonoverlapping MICU versus pooled non-MICU × order-subtype cells**, not stay-level records. Bubble area is proportional to the **number of orders**; x is **mean first-day SOFA**, y is **mean invasive-ventilation exposure in the six hours before the index**. The stage change modifies eligibility and therefore may change both the mean and count; it does not depict an individual transition.

The event-time plot is a **recording/exposure rate per observed ICU patient-hour** in four-hour bins. It does not display a patient-level mean latent physiological value, and differences between groups cannot be read as treatment effects. Exact values are given in the accessible source table.

The privacy model considers **differences between nested analytical stages**, not merely the size of each displayed cell. If one subgroup shows 111 orders in the supported cohort and 106 under stricter overlap, publishing both would expose a five-person excluded cohort and allow reconstruction of its approximate mean physiology by subtraction. The MVP therefore uses a **stable, disjoint, exhaustive partition of MICU versus all remaining ICU units pooled together** in every stage and DNR subtype. Every public cell and every nonzero difference between successive stages contains at least 30 orders. This deliberately sacrifices unit-specific detail to prevent tiny excluded cohorts from being revealed.

The export script resides in \`research/prophecy-2/05_viz_aggregate_export.py\`. It runs only in the restricted server environment and validates every displayed 12-hour difference-in-changes estimate against the previously audited Prophecy 2 scientific report before emitting the aggregate file. No new PhysioNet download is required.

## 4. Visual design tokens

Use tokens defined in \`viz.css\`; avoid scattering styling decisions across chart code.

| Semantic purpose | MVP token | Meaning |
|---|---|---|
| Deep editorial scene | \`--mv-deep\` / \`--mv-deeper\` | Immersive context, not data category |
| Reading surface | \`--mv-cream\` / \`--mv-paper\` | Warm, high-legibility scientific canvas |
| DNR-only | \`--mv-coral\` | Consistent categorical encoding |
| DNR + DNI | \`--mv-mint\` | Separate clinical exposure |
| Eligible full-code controls | \`--mv-slate\` | Comparison arm |
| Measurement event zero | Warm dashed marker | Date-aligned DNR order, not randomization |
| Conditional uncertainty | Center mark + whisker with caps | Estimate + reported interval, never fabricated ribbon |

The first concern of visual encoding is **truth**, then accessibility, then aesthetics. Color should never be the sole distinction: legend text, labels, selected rows, shapes and tables are available independently. Every chart has a descriptive SVG \`aria-label\`, a live region or selection summary, and an underlying data table.

### Motion

- Cohort stage transitions: 680 ms cubic-out, triggered by explicit user choice.
- Cohort playback: 1500 ms per **analytic filter stage**. The UI repeatedly labels this as *not patient time*.
- Event-time playback: 1150 ms per **actual 4-hour observed bin**. Each bin uses step geometry; no patient data are interpolated.
- Reduced motion: respect \`prefers-reduced-motion\`, change stages immediately, keep all data available.
- No autoplay when the page loads. Pause when the user moves the scrubber or changes an outcome.

## 5. Interaction grammar

Each chart exposes \`mount(container, data, options)\` and a small control interface:

\`\`\`js
const cohort = mountCohortSpace(node, dataset, {
  getSubtype: () => activeSubtype,
  onSubtypeChange: next => selectSubtype(next)
});
cohort.setStage("strict");
cohort.setSubtype("DNR_ONLY");

const timing = mountEventTime(node, dataset, release, {
  getSubtype: () => activeSubtype
});
timing.setMetric("invasive_ventilation");
timing.setBin(6);
timing.stop();

const evidence = mountEvidenceMatrix(node, release, {
  getSubtype: () => activeSubtype
});
evidence.setSubtype();

const claims = mountClaimAudit(node, release, {
  getSubtype: () => activeSubtype
});
claims.setSubtype();
\`\`\`

The story adapter owns **shared selection** and narrative order; charts remain decoupled from the main application's DOM and from other tracks' research logic. The next track may use the same chart with a new publication-specific adapter and newly validated aggregate series. The MVP does not claim that all future research schemas are automatically supported.

## 6. Scientific and accessibility acceptance gates

**Must pass before publishing:**

1. Public chart data contain no patient IDs, stay IDs, admission IDs, individual charttimes, raw rows, model checkpoints or credentials.
2. Every released aggregate matches the canonical research report: eligibility, subtype counts, strict-overlap population and the actual published 12-hour contrasts.
3. Privacy is checked jointly across the nested selection stages: public groups must be stable and disjoint; all cells and all nonzero stage differences must contain at least 30 orders. Tests explicitly reject the originally reviewed small-cohort subtraction failure.
4. No mark implies that comparison-group patients were randomly assigned, and no animation depicts unobserved patient movement.
5. Event-time visual values do not display pointwise confidence ribbons because those were never calculated.
6. Sensitivity matrices and the mortality ClaimAudit preserve stringent-overlap measured-balance **failures**, nonrandom group prognosis, invalid provider-assignment shortcuts, and mortality-effect **non-identification**.
7. Desktop, mobile and keyboard controls operate, data tables render, the content security policy remains intact, and no uncaught script errors occur.
8. Chrome-based smoke tests cover staged cohort selection, subtype switching, outcome switching, timeline scrubbing, strict-overlap caveats, reduced-motion behavior and mobile overflow.
9. GitHub publication remains review gated; Cloudflare previews may be deployed for review, but protected production is not bypassed.
10. New releases may update research views automatically only after a new aggregate source passes the validator and is merged.

## 7. Honest scope and next component evolution

This is **A/MVP**, not the final general-purpose library. It establishes a shared data validator, chart geometry, interaction conventions, a reusable source adapter and a complete applied investigation.

Future additions should be justified by actual datasets: competing-state flow for multistate cohorts; pointwise uncertainty bands only with proper jointly reported intervals; annotated cohort comparison across locations/eras; consistency-aware chart linking; portable story layouts for non-DNR research; strict real-time/as-of timestamp audits; and independent user tests with clinicians and nonspecialists.

Preserve the same principle throughout: **The graphics move only when the evidence moves.**
