# Self-fulfilling prophecy dissection

Follow-up to the signs-of-death prediction result (AUC 0.78-0.82):
with ~90% of ICU deaths preceded by DNR/CMO orders, does an
imminent-death model predict dying — or the decision to let die?
Four analyses on all 94,458 ICU stays, structured fields only.

## A. Expected death predicts DNR (first half of the loop)

Landmark 24h, stays with LOS >= 24h and no DNR before 24h (n=64,303):
day-1 SOFA predicts a DNR/CMO order within (24,72]h with AUC 0.759,
OR 1.24 per SOFA point. Decisions track early risk closely.

## B. DNR predicts death beyond physiology (second half)

Landmark 48h (n=44,652, 12.4% exposed): death 37.4% with DNR vs
11.6% full-code; adjusted for SOFA@48 + age + sepsis + cause + sex,
**adjusted OR 3.89** (24h landmark: 3.77). A DNR order carries ~4x
adjusted odds of hospital death. Confounding by indication surely
contributes — but so does the decision itself (see discontinuity).

Within-stay discontinuity at DNR time (7,617 matched full-code
controls at the same elapsed hour):

![slopes](pr_slope.png)

- HR slope -0.022 -> -0.145 /h (p=0.0005), level -0.5 bpm;
  controls flat (0.000).
- MAP slope -0.062 -> -0.158 /h (p=0.0003), level -1.0 mmHg;
  controls +0.092 / +0.50 (improving).

Decline steepens significantly after DNR vs matched controls.
Understated: the acute +/-2h transition is excluded, and DNR
includes no-CPR-only orders, not just active withdrawal.

## C. Honest estimand: death under full code

6/12/24h prediction restricted to full-code decedents (3,111 stays;
670/602/514 cases):

![prediction](pr_pred.png)

| horizon | all decedents | full-code only |
|---|---|---|
| 6h | 0.811 | 0.761 |
| 12h | 0.785 | 0.725 |
| 24h | 0.771 | 0.697 |

AUC drops 0.05-0.08 but holds at 0.70-0.76: the prophecy inflates
the model, it does not fabricate it. Roughly 90% physiology, 10%
withdrawal pattern.

## D. Model vs chart

On all decedents, "DNR already written at landmark" alone: AUC
0.791/0.763/0.737 — nearly as good as physiology
(0.811/0.785/0.771). Combined: 0.896/0.873/0.856. The team already
knows, almost as well as the model — and the two stack.

## Verdict

The loop is real, large, and measurable — but the model survives
it. The deployment catch-22, quantified: the model adds most where
the chart is silent (full-code patients, AUC 0.70-0.76 with no
chart signal to lean on) — exactly where a false positive could
trigger the DNR it predicts. Any bedside use needs a
prophecy-aware protocol: predict, but blind the prediction from
the withdrawal decision, or the 0.90 combined AUC is a
self-licking ice cream cone.

## Adversarial battery (`adversarial.py`)

Every headline above, attacked:

![or specs](adv_or.png)

- **Richer adjustment** (SOFA subscores, vent/pressor/RRT@48,
  lactate, creatinine): OR rises 3.89 -> **4.09**, E-value 7.7.
  An unmeasured confounder needs OR 7.7 on both sides.
- **Timing split**: DNR<24h OR 3.48, DNR 24-48h OR 7.45 — later
  DNR tracks unfolding decline (indication gradient), yet even
  day-1 DNR carries 3.5x.
- **SOFA tertiles**: low 5.71 / mid 3.67 / high 3.57. Largest
  where physiology says "fine" — the decision does the work in
  low-SOFA deaths (neuro catastrophes, comfort transitions).
- **1:1 PS matching** (rich covariates, balance 0.76 -> 0.04):
  OR **2.91 [2.64-3.20]** — attenuated, decisively above 1.
- **Unit-rate IV** (first-stage F=1609): direction confirmed,
  magnitude not credible (risk-diff 0.79 vs OLS 0.21) — LATE on
  marginal patients plus residual unit case-mix. Reported as
  direction-only.
- **Discontinuity**: regression-adjusted for pre-slope, pre-level,
  SOFA, age, sepsis — HR coef -1.53 (p=3.5e-12), MAP -1.24
  (p=3.4e-34). Off-center placebo cuts null (p=0.07-0.78).
  Survivor-with-DNR falsification: slopes go UP (+0.13/+0.10,
  p<1e-5) — the break marks the fork, not the timestamp.
- **Prediction out-of-sample**: 5-fold CV confirms ALL AUCs
  (0.814/0.784/0.762, no optimism). FC gaps significant at 6h
  (0.052 [0.025-0.076]) and 12h (0.067 [0.039-0.093]), gone at
  24h (0.029 [-0.004-0.061]) — withdrawal patterns contribute
  only at short horizons.
- **Case-mix caveat**: full-code decedents die 2.3x later
  (median 219h vs 97h) with different cause mix — the FC gap
  conflates prophecy-free signal with a different dying
  population. Stated, not solved.

![cv auc](adv_auc.png)

Net: the central numbers survive matching, placebos,
falsification, cross-validation, and case-mix scrutiny. The IV
magnitude fails credibility (reported honestly). The 24h FC gap
vanishing bounds the prophecy contribution to short horizons.

## Reproduce

```sh
/srv/mimic-iv/.venv/bin/python /tmp/prophecy.py  # ~8 min warm on s0
/srv/mimic-iv/.venv/bin/python /tmp/adversarial.py  # ~12 min warm
```

then `make_plots.py`. Raw log: `prophecy.out`. Stay-level
slope tables: `pr_slope_{dnr,ctl}_{hr,map}.csv`.
