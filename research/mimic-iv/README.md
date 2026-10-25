# Prophecy — reproducible MIMIC-IV research

This directory contains analysis **source code only**, recovered from the isolated server study at `/srv/mimic-iv/studies/decision_feedback_20261025/` on 2026-10-25. The data are *not* vendored. Run the programs on the authorized research host with the licensed MIMIC-IV v3.1 dataset already installed.

## Research areas

- Event-time DNR order provenance; inherited versus new code status; competing ICU exits.
- Risk-set eligibility, pre-decision calibration and monitoring intensity.
- Vasopressor, ventilation and extubation measurement audits; informative termination.
- Longitudinal six-hour state transitions, historical transportability and patient-cluster bootstrap.
- Sequential stochastic rollout and competing-exit calibration. Some simulators fail primary acceptance gates; failures must remain published.

## Reproduction and restrictions

Source references paths under `/srv/mimic-iv` and requires a local installation. No PhysioNet download is performed by these analyses. Use `run_riskset.sh`, `run_support.sh`, and `run_multistate.sh` for the previously validated core pipelines; newer experimental scripts are explicitly exploratory and may require additional local setup.

Public-facing, curated **aggregate** metrics are independently versioned under `../../portal/data/rounds/`; never publish patient identifiers, extracted stay-level or encounter-level rows, model artifacts, or credentials. Observational prediction and recorded-care associations must not be described as identified causal intervention effects.

Note: code and publication are placed on GitHub to permit review, not to certify that all endpoints, simulation variants, and sensitivity analyses are independently verified. Exact claims are bounded by each published release's methodology and acceptance status.
