# Hour-by-hour signal sweep (first 24h → hospital death)

How much mortality signal exists in hour 1, 2, … after ICU admission, and
which signals carry it. Logreg throughout (the reference model).

## Design

- Same cohort as `../early-mortality/` (first ICU stays, hospital death).
- **Landmark sweep**: for each L in 1..24, cumulative data over `[0, L)` for
  stays with LOS ≥ L hours. Reports AUC/AP/n + top-8 |coefs| at 1/3/6/12/24.
- **Univariate sweep**: per vital, single-feature AUC of the hour-h median
  (complete cases that hour). Direction-free strength `max(AUC, 1-AUC)`:
  HIGH values kill for HR/RR/lactate/creatinine; LOW values kill for
  MAP/SpO2/GCS; temperature is U-shaped (both extremes kill), so its linear
  AUC ≈ 0.5 by construction.
- Run on s0: `/srv/mimic-iv/.venv/bin/python signal_sweep.py`
  (read-only on the DB; aggregates only leave s0).
- Figures regenerate: `uv run --with matplotlib python make_plots.py`.

## Findings (2026-10-24)

- **Signal arrives fast, then saturates**: AUC 0.753 (1h) → 0.804 (2h) →
  0.821 (3h) → ~0.834 by hour 5–6, then flat ~0.84 through 24h
  (late wiggles are noise + short-stay dropout: n falls 85k → 67k).
  AP follows the same shape (0.30 → 0.46).
- **Triage dominates early**: top coefficients at every landmark are static
  (care unit, admission type) — where you land stratifies before physiology
  accumulates. GCS is the first physiological feature in the top 8 (by 12h).
- **Per-signal strength** (univariate, all 24h):
  lactate 0.69–0.75 (strongest, present from hour 0),
  GCS 0.66 → 0.78 inverted (strengthens over the day, partly selection),
  creatinine 0.63–0.69, RR ~0.61 fading late, HR ~0.59 flat,
  MAP ~0.58 inverted, SpO2 ~0.51 (ceiling effect — nearly useless alone),
  temperature ~0.51 (U-shape).
- Practical read: a 3–6h model captures ~everything the first day offers;
  gains after that must come from better features (trends, more labs,
  pressors, code status), not more hours.
