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

## Reproduce

```sh
/srv/mimic-iv/.venv/bin/python /tmp/prophecy.py  # ~8 min warm on s0
```

then `make_plots.py`. Raw log: `prophecy.out`. Stay-level
slope tables: `pr_slope_{dnr,ctl}_{hr,map}.csv`.
