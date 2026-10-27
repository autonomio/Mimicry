# Compound profiles: pre-admission prescriptions and in-ICU intake

What drugs patients were on coming in (prior stays' prescriptions, GSN-coded)
and what they received during the ICU stay (eMAR administrations + IV
ingredients), contrasted by outcome. Structured fields only; drug/formulary
names are controlled vocabulary used for grouping and interpretation.

## Pre-admission prescriptions (`rx_pre.*`)

- Coverage: 302,707/546,028 admissions (55%) have prior GSN-coded
  prescriptions; median **41 distinct drugs** (p90: 112).
- Top prior drug (GSN 006549): 241,544 admissions.
- Exposure lift in died vs survived (min 500 exposed): lorazepam 2.57x,
  norepinephrine 2.44x, vancomycin 2.37x, albumin 2.30x, phytonadione 2.2x,
  cefepime 2.19x, dexamethasone ~2.1x, amiodarone 1.92x, allopurinol 1.89x —
  a prior-critical-illness footprint (pressors, broad-spectrum abx, albumin,
  antiarrhythmics) predicts death.
- Lift < 1 (NSAIDs 0.59–0.63x, oxycodone-APAP, Milk of Magnesia, gabapentin):
  **confounding by indication in reverse** — patients well enough for NSAIDs
  survive more. Markers of fitness, not protective effects.

## In-ICU intake, died-in-ICU (5,632) vs survived (75,767) (`rx_icu.*`)

- Coverage: eMAR 50% (starts ~2014 — recent-era only), ingredients 89%,
  inputevents 90%.
- eMAR leaders: micafungin 14.5x, CRRT priming 13.4x, glycopyrrolate 13.0x,
  hydrocortisone/bicarb 9.6x, citrate 9.1x, artificial tears 8.6x,
  meropenem 5.2x, midazolam 4.7x — salvage therapies (CRRT, shock steroids,
  acidosis rescue, antifungals) plus care markers (eye ointment = comatose).
- IV ingredients: TPN bundle 4.07x (gut failure), enteral feeds 2.86x,
  blood 1.47x; IVF 1.03x and water 0.99x (universal, no signal — sanity
  check passes); oral/gastric 0.77x and OR intake 0.61x (eating / surgical
  path = healthier — negative controls behave).
- Read everything here as **markers of dying, not causes**.

## Reproduce

On s0 (read-only): pipe `rx_pre.sql` / `rx_icu.sql` into
`duckdb -readonly -csv $DB`. Figures: `uv run --with matplotlib python
make_plots.py` (values transcribed from the committed `.out` files).
Next: dose/duration (amount/rate), timing within stay, history-rx features
for the early-mortality model.
