#!/usr/bin/env python3
"""Prophecy 2: aggregate-only DNR research integrity gates.

This gate audits consistency, not clinical causal identification.
"""
from pathlib import Path
import json
R=Path("/srv/mimic-iv/studies/prophecy2_dnr_20261025")
v=json.loads((R/"dnr_fork_aggregate_report.json").read_text())
assert v["schema_version"]==1
assert v["source"].startswith("MIMIC-IV v3.1")
assert v["phenotype"]["eligible_documented_first_dnr"]==3021
assert v["phenotype"]["represented_dnr"]==2014
assert v["phenotype"]["excluded_outside_matched_support"]==1007
assert set(v["subtypes"])=={"DNR_ONLY","DNR_DNI"}
assert sum(x["n"] for x in v["subtypes"].values())==2014
findings={}
for code,x in v["subtypes"].items():
 assert x["n"]>=100
 assert x["balance"]["baseline_after"]["max_abs_smd"]<0.1
 assert x["balance"]["risksets_ess_lt2"]>=0
 assert x["strict_common_support"]["n_treated"]<=x["n"]
 for outcome,arr in x["outcomes"].items():
  for name,item in arr.items():
   assert item["estimate"]>=item["ci95_fixed_weight_patient_cluster"][0]
   assert item["estimate"]<=item["ci95_fixed_weight_patient_cluster"][1]
 assert x["diagnostics"]["death12"]["dnr"]>x["diagnostics"]["death12"]["control"],"Fatal prognosis imbalance must be visible"
 assert x["strict_common_support"]["baseline_balance"]["max_abs_smd"]>=0
 findings[code]={
  "n":x["n"],
  "smd":x["balance"]["baseline_after"]["max_abs_smd"],
  "risksets_effective_control_count_below_two":x["balance"]["risksets_ess_lt2"],
  "strict_n":x["strict_common_support"]["n_treated"],
  "strict_max_smd":x["strict_common_support"]["baseline_balance"]["max_abs_smd"],
  "death12_dnr":x["diagnostics"]["death12"]["dnr"],
  "death12_control":x["diagnostics"]["death12"]["control"]
 }
assert v["subtypes"]["DNR_ONLY"]["strict_common_support"]["baseline_balance"]["max_abs_smd"]>.1, "Strict DNR-only overlap warning unexpectedly changed; review independently"
assert "NO causal ATE/LATE" in v["interpretation"]
blob=json.dumps(v)
for marker in ['"subject_id":','"stay_id":','"hadm_id":','"patient_id":','"raw_rows":','"name": "Patient']:
 assert marker not in blob,"Protected patient rows/identifiers in aggregate release"
out={"status":"PASS STRUCTURE / NOT A CAUSAL GO SIGNAL",
"original_dnr_events":3021,"represented":2014,"outside_overlap":1007,
"subtypes":findings,
"causal_identification":"NOT IDENTIFIED",
"warnings":["DNR-only strict-subset measured balance fails","Short-term death disparities imply serious residual prognosis selection","Order provider lacks verified pre-exposure assignment","Report exploratory fixed-weight intervals only"]}
(R/"publication_qa.json").write_text(json.dumps(out,indent=2)+"\n")
print(json.dumps(out,indent=2))
