# Prior-year labs at the admission moment

What lab history exists in the year before each hospital admission, and what
signal the last pre-admission values carry about the coming stay (death,
ICU). Structured fields only; test names are dictionary interpretation.

## Coverage (546,028 admissions)

- **92.9%** have ≥1 lab in the prior year; median **124 rows / 65 distinct
  tests** per admission (p90: 1,057 rows).
- Top tests by admissions covered: CBC panel (~497k), creatinine (486k),
  BUN (483k), eGFR (476k), K/glucose/Na/Cl/bicarb (~470k), diff (450k),
  PT/INR (~354k).
- **Workup vs history split**: of first-visit patients' prior-year labs,
  49% were drawn in the 24h before admission (ED workup); for repeat visits
  only 6%. Pure-history cut (older than 24h pre-admit) still covers **68.5%**
  of admissions.

## Signal: last pure-history value, median gaps (min n 2000/group)

**Died vs survived**: ferritin +132%, NTproBNP +125%, urine WBC +50%,
immature granulocytes +50%, basophils −40%, lymphocytes −38%, BUN +38%,
eosinophils −35%, troponin T +25%, bilirubin +25%, lactate/creatinine/WBC
up 33–40% (workup-included cut).
Pattern: cardiac strain + systemic inflammation + immune suppression
(lymphopenia, eosinopenia, left shift) + renal/liver strain — visible in
history *before* the presentation workup.

**ICU vs floor**: NTproBNP +88%, CRP +85%, urine protein markers +47–67%
(protein/creatinine, albumin/creatinine, albumin, total protein),
ESR +48%, ferritin +45%, troponin +25%.
Pattern: cardiac + inflammatory + **renal/proteinuria** markers lead ICU
selection from history alone.

Caveat: single-last-value medians; discrete low-count tests (urine cells,
casts) have coarse medians. Next: trajectories (slope/count), abnormal-burden
scores, and history-augmented admission models.

## Reproduce

On s0 (read-only): pipe `pylab_sweep.sql` / `pylab_sweep_v2.sql` into
`duckdb -readonly -csv $DB` (see early-mortality README for the pattern).
Figures: `uv run --with matplotlib python make_plots.py`.
