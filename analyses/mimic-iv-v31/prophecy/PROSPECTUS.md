# Paper prospectus: The Self-Fulfilling Prophecy in the ICU

**Working title:** *Do-Not-Resuscitate Orders and the Measurement of
Dying: Quantifying the Prophecy Loop in 94,458 ICU Stays*
**Status:** Analyses complete, committed, reproducible. Seeking
clinical/methods collaborators for interpretation, validation, and
authorship.

## The pitch

Everyone knows most ICU deaths follow a decision to limit treatment —
but nobody has quantified how much of "dying" is the disease and how
much is the decision, or what that does to mortality prediction. We
dissect the full loop in MIMIC-IV: expected death predicts DNR, DNR
predicts death at ~4x adjusted odds, physiology measurably breaks at
the DNR timestamp — and an imminent-death predictor owes part of its
accuracy to detecting withdrawal rather than dying. The model
survives the dissection, but the catch-22 is now quantified.

## The gap

- Prendergast (1990s): ~90% of ICU deaths follow withholding /
  withdrawal. Widely cited, never decomposed into decision vs
  disease with modern causal methods at scale.
- Imminent-death prediction literature (PaP AUC 0.82, surprise
  question, clinician judgment wrong 1 in 3 at 72h) never adjusts
  for the fact that the predicted event is usually *chosen*.
- No study we know of measures a physiological discontinuity at
  the DNR timestamp against matched controls, or reports a
  prophecy-free ("death under full code") prediction estimand.

## Data and design

- MIMIC-IV v3.1 (Beth Israel Deaconess, 2008–2022): 94,458 ICU
  stays, structured fields only. Terminal-ICU decedents: 9,438.
- Landmark designs at 24/48h (no immortal-time bias); rich
  adjustment (SOFA subscores, supports, lactate, demographics,
  cause); 1:1 propensity matching; unit-practice IV; within-stay
  slope discontinuity with matched controls, placebo cuts, and a
  survivor-with-DNR falsification arm; 5-fold CV prediction with
  paired bootstrap gap CIs.

## Key findings

1. **The loop is large:** day-1 SOFA predicts DNR within 24–72h
   (AUC 0.76, OR 1.24/point); DNR before 48h carries adjusted OR
   **3.9–4.1** for hospital death (crude 37% vs 12%), E-value 7.7.
2. **Matching confirms:** 1:1 PS matching (balance 0.76 → 0.04)
   gives OR **2.91 [2.64–3.20]**. No SOFA tertile near 1.0;
   largest effect (5.7) where physiology says "fine."
3. **Physiology breaks at the timestamp:** HR/MAP decline slopes
   roughly triple after DNR vs matched controls (p≈1e–12/1e–34);
   placebo cuts null; survivors with DNR slope *upward*.
4. **Prediction owes ~0.05 AUC to prophecy:** 6/12/24h AUCs
   0.81/0.79/0.77 overall vs 0.76/0.73/0.70 under full code
   (CV-confirmed, gaps significant at 6/12h, gone at 24h).
5. **The chart ≈ the model:** "DNR already written" alone reaches
   AUC 0.79 vs 0.81 physiology; combined 0.90. The model adds
   most where the chart is silent — where false positives cost
   the most.

## Why this matters

- First causal-decomposition of the ICU prophecy loop at scale.
- Reframes every ICU mortality model ever published: reported
  AUCs partly measure withdrawal detection. Reviewers and
  regulators should demand prophecy-free estimands.
- Quantifies the deployment catch-22 for bedside death
  prediction, with a concrete mitigation (prophecy-aware
  protocols).
- Directly relevant to end-of-life ethics, ICU policy, and ML
  evaluation methodology.

## Honest limitations

- Single center (BIDMC), retrospective; needs multi-center
  replication (eICU available to credentialed teams).
- DNR/CMO chart flags ≠ verified withdrawal of specific
  therapies; granularity limited without notes review.
- IV magnitude not credible (direction only); full-code decedents
  die 2.3x later with different cause mix (stated, bounded).
- ICU only; ward deaths and post-discharge mortality out of scope.

## What collaborators add

- Clinical interpretation + framing (intensivist, palliative
  care, bioethics angles all publishable).
- Chart/notes validation of withdrawal granularity (optional).
- External replication (eICU or local ICU data).
- Methods co-ownership (causal inference, prediction evaluation).

## Practical requirements

- MIMIC-IV access requires PhysioNet credentialing + CITI
  training + signed data use agreement (individual, ~1–2 weeks).
  Code and aggregates are already built; credentialed
  collaborators can reproduce everything on our server or their
  own.
- Target venues: *Critical Care Medicine*, *Intensive Care
  Medicine*, *Critical Care*, *AJRCCM*; methods spin-off
  possible.

## Proposed next steps

1. Intro call + shared repo/code walkthrough.
2. Agree scope (single paper vs clinical + methods pair),
   target journal, authorship order.
3. Collaborator-led: framing, replication cohort, limitations
   review; we lead: revisions, robustness, figures.
4. Submit within ~8–12 weeks.

---
*Analyses: `analyses/mimic-iv-v31/{prophecy,signs-of-death,
organ-failure}/` — scripts, logs, aggregates, plots. Contact:
[your name here].*
