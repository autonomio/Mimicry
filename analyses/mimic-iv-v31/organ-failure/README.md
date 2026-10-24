# In what order do organs fail before death

Terminal ICU stays of 9,438 hospital decedents (deathtime known);
primary cohort ICU LOS >= 48h (n=5,709, 83% septic). Organ failure =
SOFA subscore (trailing-24h, hourly) first reaching >= 3, sensitivity
>= 2. Onsets within 24h count as simultaneous (window blur).
Structured fields only, aggregates only.

## What fails, and first

Failure prevalence in the last 24h before death (>= 3): cardiovascular
49%, renal 37%, CNS 32%, respiratory 31%, coagulation 15%, liver 12%.
Median 2 organs failed; 16% die with none >= 3.

First-failing organ (tie-split):

![first organ](of_first.png)

- Frank failure (>= 3): cardiovascular 29%, renal 20%, CNS 20%,
  respiratory 18%, coagulation 7%, liver 5%.
- Dysfunction (>= 2): respiratory leads at 23%, then renal 21%, CV 19%.

## Pairwise order

![precedence](of_precedence.png)

Full table: `of_precedence_thr3.csv` (n, P-each-first, tie rate,
median lead). Salient pairs: respiratory-CV fail together 68% of the
time (intubation + pressors at the same crisis); CV precedes CNS 57%
and renal 33% (54% tied); respiratory precedes CNS 54%; renal
precedes CNS 45%; liver-renal is a coin flip (29/29%).

Sequences are highly dispersed: 913 distinct orders among 4,192 stays
with >= 2 failures. No single cascade dominates; the top 20 are all
CV/renal/respiratory combinations with CNS last
(`of_sequences_thr3.csv`). Median first failure -> death: 142h;
second 125h; third 110h.

## Trajectories

![trajectories](of_trajectories.png)

CV runs highest throughout and rises into death; renal second; CNS
rises late; coagulation/liver flat. Total SOFA drifts 6.6 -> 8.0 over
the last week — gradual, no terminal cliff.

![total](of_total_sofa.png)

Decedents diverge from survivors (15k sample, aligned to ICU
discharge): survivors fall toward discharge, decedents grind upward.

![subgroups](of_subgroups.png)

Subgroups (sepsis/non, 65+/-, full-code/all) share the same shape;
early-DNR stays are 46% of decedents and look no different in total
SOFA, against a pure withdrawal-driven terminal spike.

## Validation

- Vasopressors start median +0h after CV>=3 (circular by
  construction — CV score is pressor-defined — but confirms
  alignment); RRT +17h after renal>=3; invasive ventilation -3h
  before respiratory>=3 (intubation precedes the worst gas window).
- CNS caveat: GCS under sedation inflates CNS scores in ventilated
  patients, so CNS "failure" partly measures sedation depth.

## Literature correspondence

1. **"Lungs first" (Border/Baue; MODS reviews: pulmonary precedes
   cardiac/renal/hepatic) — partly upheld, refined.** Holds for
   dysfunction onset (>= 2: respiratory first). Fails for frank
   failure (>= 3: cardiovascular first at 29%, and respiratory-CV
   are simultaneous 68% of the time). Teaching update: respiratory
   dysfunction is the earliest warning; cardiovascular collapse is
   the most common first frank failure and usually arrives with
   respiratory failure, not after it.
2. **Vincent et al. 2011 ("Is worsening MOF the cause of death in
   severe sepsis?") — replicated.** Mean dSOFA(-96h -> -24h) = +0.26
   (n=4,486): increased 36.5%, stable 31.7%, decreased 31.8%.
   Persistent, not worsening, failure dominates — quantitatively
   matching "only small increases."
3. **INDEPTH (80% with >= 1 organ increase in last 4 days) —
   direction yes, magnitude lower: 56%.** Gap plausibly from our
   -24h cutoff, which excludes the agonal day where most change
   concentrates; INDEPTH's window reaches death itself.
4. **Gupta et al. (sepsis SOFA-component mortality ranking: coag >
   hepatic > resp > neuro > renal > CV) — top agrees, rest
   diverges.** Our lethality P(death | ever >= 3): liver 40% > coag
   37% > CNS 31% > CV 30% > renal 29% > respiratory 27% (baseline
   12%). Both rank coagulation/hepatic failure most ominous (rare
   but lethal — unfixable systemic collapse). Respiratory is #3 in
   Gupta but last here: common and salvageable (ventilation works),
   and Gupta's per-point adjusted ORs answer a different question
   than crude ever-failed lethality.

## Reproduce

```sh
/srv/mimic-iv/.venv/bin/python /tmp/organ_failure.py  # ~10 min on s0
```

then `make_plots.py`. Raw log: `organ_failure.out`.
