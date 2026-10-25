#!/usr/bin/env python3
"""Unused early-pretrend window audit and weight concentration.

No post-index measurements used for this placebo. Early pretrend
(-24 to -16) vs (-16 to -12) lies outside fitted treatment-history
calibration, though baseline vitals from these periods helped original
matching. A nonzero placebo does not independently prove causal bias,
and a zero placebo does not establish identification.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
weights=pd.read_parquet(ROOT/"risk_weighted_supporthistory.parquet")
tables={
 "support":pd.read_parquet(ROOT/"risk_support_bins.parquet"),
 "monitor":pd.read_parquet(ROOT/"risk_event_bins.parquet"),
}
inputs=[("support","pressor_h"),("support","invasive_h"),
        ("support","ne_mean_dose_hours"),
        ("monitor","n_map"),("monitor","n_hr")]
out={}
for tbl,col in inputs:
 b=tables[tbl]
 b=b.loc[b.bin.isin([-6,-5,-4])].drop(columns="weight").merge(
  weights[["anchor_id","weight"]],on="anchor_id",validate="many_to_one")
 b["group"]=np.where(b.bin==-4,"late","early")
 q=b.groupby(["anchor_id","group"])[[col,"observed_h"]].sum().unstack("group")
 q.columns=["_".join(c) for c in q.columns]
 a=weights[["anchor_id","subject_id","arm","weight"]].merge(
    q.reset_index(),on="anchor_id",validate="one_to_one")
 val={}; score=[]
 for arm,g in a.groupby("arm"):
  p0=(g.weight*g[col+"_early"]).sum()/(g.weight*g.observed_h_early).sum()
  p1=(g.weight*g[col+"_late"]).sum()/(g.weight*g.observed_h_late).sum()
  val[arm]={"early":float(p0),"late":float(p1),"change":float(p1-p0)}
  n0=(g.weight*g.observed_h_early).sum()
  n1=(g.weight*g.observed_h_late).sum()
  inf=(1 if arm=="DNR" else -1)*g.weight*(
      (g[col+"_late"]-p1*g.observed_h_late)/n1 -
      (g[col+"_early"]-p0*g.observed_h_early)/n0)
  score.append(pd.DataFrame({"subject_id":g.subject_id,"influence":inf}))
 effect=val["DNR"]["change"]-val["RISKSET"]["change"]
 v=pd.concat(score).groupby("subject_id").influence.sum()
 se=float(np.sqrt(np.square(v).sum()))
 out[col]={"effect":float(effect),"ci95_conditional":
 [float(effect-1.96*se),float(effect+1.96*se)],"rates":val}
report={"window":"early PRE-only -24 to -16 vs -16 to -12 hours",
"limitations":"pre 12-0 treatment history fitted; early treatment outcomes not fitted; baseline vitals 24h helped candidate selection",
"results":out}
(ROOT/"risk_early_placebo_report.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
