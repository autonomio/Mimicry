#!/usr/bin/env python3
"""Fail-fast aggregate scientific checks for Prophecy historical shift release.

No patient-level data involved. No p-hacking gate tuning: compare displayed
metrics against raw aggregate research reports and verify algebra and
sample denominators; a FAIL gate remains a scientific result.
"""
from pathlib import Path
import json,math,hashlib
R=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
source=json.loads((R/"kernel_hgb_history_error_decomposition.json").read_text())
roll=json.loads((R/"kernel_rollout_hgb_history_full_test.json").read_text())
prior=json.loads((R/"kernel_rolling_origin_report.json").read_text())
shift=json.loads((R/"kernel_transport_horizon_and_subgroup_report.json").read_text())
later=[v for v in source["horizons"] if v["era"]=="2020 - 2022"]
earlier=[v for v in source["horizons"] if v["era"]=="2017 - 2019"]
assert len(later)==len(earlier)==len(prior["results"])==len(roll["results"])==4
assert [x["hours"] for x in later]==[24,48,72,120]
assert all(x["n_initial"]==7147 for x in later)
assert all(x["n_initial"]==9838 for x in earlier)
issues=[]
for a,b in zip(later,roll["results"]):
 assert a["hours"]==b["hours_after_initial_landmark"]
 for ev in ("exit","death"):
  x=a[ev];y=b["metrics"][ev]
  assert abs(x["observed"]-y["observed"])<1e-8
  assert abs(x["simulated"]-y["simulated"])<1e-8
  assert abs((x["prequential"]-x["observed"])-x["local_error"])<1e-10
  assert abs((x["simulated"]-x["prequential"])-x["recursive_feedback_component"])<1e-10
  assert abs(x["full_error"]-x["local_error"]-x["recursive_feedback_component"])<1e-10
  assert x["bootstrap_ci95"][0]<=x["local_error"]<=x["bootstrap_ci95"][1]
  assert all(math.isfinite(float(x[z])) for z in ("observed","simulated","prequential"))
  assert 0<=x["observed"]<=1 and 0<=x["simulated"]<=1
 if b["all_primary_gates_pass"]:issues.append(a["hours"])
assert not issues,"Unexpected simulator gate pass must be reviewed (not suppressed)"
assert abs(later[-1]["exit"]["local_error"])>0.04
assert abs(later[-1]["exit"]["recursive_feedback_component"])<0.025
h120=[r for r in shift["horizons"] if r["hours_after_hour24"]==120 and r["state"]=="EXIT"]
assert len(h120)==1
case=h120[0]
assert case["n_prior"]==9838 and case["n_later"]==7147
assert case["bootstrap_ci95_fixed_weights"][0]<=case["overlap_later_minus_prior"]<=case["bootstrap_ci95_fixed_weights"][1]
assert prior["n_hour24_patients"]==9838
assert prior["results"][-1]["hours"]==120
before=prior["results"][-1]["exit"]
assert before["fixed_fit_patient_bootstrap_ci95"][0]<=before["error"]<=before["fixed_fit_patient_bootstrap_ci95"][1]
paths=["89_hazard_error_decomposition.py","90_transport_horizon_strata.py","91_rolling_origin_hazard.py"]
assert all((R/p).is_file() for p in paths)
report={"status":"PASS","data":"MIMIC-IV v3.1 — aggregate audit only",
 "later_initial_patients":7147,"earlier_initial_patients":9838,
 "five_day_exit":{"observed":later[-1]["exit"]["observed"],
 "prequential":later[-1]["exit"]["prequential"],
 "simulated":later[-1]["exit"]["simulated"],
 "historical_error":later[-1]["exit"]["local_error"],
 "recursive_error":later[-1]["exit"]["recursive_feedback_component"],
 "full_error":later[-1]["exit"]["full_error"]},
 "early_origin_5d_exit_error":before["error"],
 "baseline_standardized_5d_exit_shift":case["overlap_later_minus_prior"],
 "every_simulation_horizon_failed":True,
 "source_checksums":{p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in paths},
 "warnings":["Predictive, not causal","Holdout previously examined, exploratory",
 "Fixed-fit uncertainty does not cover all model uncertainty","No patient-level rows included"]}
(R/"kernel_transport_publication_qa.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
