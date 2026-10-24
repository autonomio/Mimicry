# Triage reverse-engineering: who goes where, and why

Reconstruct the triage moment for every first ICU stay (85,242) from
structured fields only, and model the hospital's de-facto triage decisions:
which unit, and direct (<6h) vs delayed ICU admission.

## Rules of this study

- **No free text, ever.** No notes, no descriptions, no value text. Diagnoses
  enter only as ICD-code prefixes, DRG only as code (+APR severity/mortality
  integers). Dictionary labels (item names, DRG titles) are used solely to
  *interpret* fitted coefficients, never as features.
- **No post-decision data as features.** ICU vitals/labs come after unit
  assignment, so they are excluded — the model sees only what triage saw
  (plus retrospective dx/DRG descriptors, flagged as such).
- Aggregates and coefficients only leave s0.

## Assumed framework (not BIDMC's actual SOP)

BIDMC does not publish internal triage protocols. The assumed background is
the public US framework: ED triage on the 5-level ESI scale, ICU admission
per SCCM admission/discharge/triage guidelines (diagnosis, severity,
reversibility, code status, bed availability). This study recovers the
*de-facto* playbook empirically; the ED module (triage acuity, chief
complaint) would be needed for the ED leg itself and requires its own DUA.

## The triage moment as a whole (feature blocks)

- **Presentation**: age/gender/race/insurance/language/marital, admission
  type/location, admitting provider experience, anchor year group.
- **Structured history**: prior admission/ICU counts, prior LOS, days since
  discharge, prior-year utilization, prior Charlson max, 9 prior-dx bucket
  flags (cardiac/heart-failure/stroke/renal/COPD/diabetes/onc/sepsis/liver),
  prior procedure count, prior max lactate/creatinine.
- **Current condition**: same 9 dx buckets for this admission + Charlson +
  HCFA-DRG (top 30) + APR severity/mortality — retrospective descriptors
  of the underlying condition triage perceived.
- **System ("gov") state**: admission hour + night flag + true year group.

## Hard date-shifting limits (verified empirically)

MIMIC-IV carries per-patient random whole-day offsets (shifted span covers
63+ years vs 14 real ones), so cross-patient simultaneity is destroyed:
**bed census is uncomputable**, and weekday/season are noise (admission
weekdays are exactly uniform). Time-of-day survives (lab draws show the real
5–7 AM peak), as does the true year via `anchor_year_group`. Note
`anchor_year` itself is shifted — only the group is real.

## Findings (2026-10-24)

- **Units are highly predictable**: multinomial logreg accuracy 0.51 (vs 0.22
  majority); per-unit OvR AUC 0.78–0.97. NeuroIMC/NeuroSD/CVICU most
  rule-bound (0.92–0.96); SICU/TSICU least (0.78–0.79).
- Unit assignment is driven by diagnosis/procedure (cardiac-surgery DRGs →
  CVICU +3.3..+4.7; craniotomy/stroke DRGs → neuro units; vent/respiratory
  DRGs → MICU), then admission type and history.
- **Direct ICU (<6h)**: AUC 0.824 full vs 0.812 presentation-only —
  history + system state add a real but modest +0.011.
- **Operational rhythms**: direct-ICU rate collapses at midnight (~0.35),
  runs ~0.8 overnight, dips mid-morning/mid-afternoon; CVICU share halves
  at night (scheduled surgery is daytime) while MICU rises.
- **Practice drift**: direct-ICU rate fell 0.70 → 0.61 from 2008–2010 to
  2017–2019 — admissions increasingly via floor/boarding over the years.

## Run

On s0 (read-only on the DB):
`/srv/mimic-iv/.venv/bin/python triage_playbook.py`.
Figures: `uv run --with matplotlib python make_plots.py`.
