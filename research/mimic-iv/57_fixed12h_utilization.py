#!/usr/bin/env python3
"""Fixed 12h per-index resource-delivery estimand, death/discharge absorbing.

Descriptive utilization in first 12h after code-status event:
patients who die/leave the ICU contribute zero ICU hours thereafter.
This incorporates both changes in life support and terminal/exit events.
Contrast remains observational. Conditional patient-clustered SE.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
root=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
a=pd.read_parquet(root/"risk_weighted_supporthistory.parquet")
b=pd.read_parquet(root/"risk_support_bins.parquet")
b=b.drop(columns="weight").merge(a[["anchor_id","weight"]],
   on="anchor_id",validate="many_to_one")
data=[("invasive_h","invasive_ventilation"),
      ("pressor_h","vasopressor_hours"),
      ("ne_mean_dose_hours","norepi_eq_dose_times_hours"),
      ("noninvasive_h","hfnc_niv_hours"),
      ("observed_h","icu_hours_available")]
b=b.loc[b.bin.isin([-3,-2,-1,0,1,2])].copy()
b["period"]=np.where(b.bin<0,"pre","post")
cols=[c for c,_ in data]
p=b.groupby(["anchor_id","period"])[cols].sum().unstack("period")
p.columns=["_".join(x) for x in p.columns]
df=a[["anchor_id","subject_id","arm","weight"]].merge(
 p.reset_index(),on="anchor_id",validate="one_to_one")
N=df.loc[df.arm=="DNR","weight"].sum()
assert abs(N-df.loc[df.arm=="RISKSET","weight"].sum())<1e-7
out={"estimand":"Per index patient, total documented ICU support-hours within fixed 12h windows; after death or discharge hours are zero",
     "n_treated":int(N),"results":{}}
for var,name in data:
 rates={}; scores=[]
 for arm,g in df.groupby("arm"):
  pre=(g.weight*g[var+"_pre"]).sum()/g.weight.sum()
  post=(g.weight*g[var+"_post"]).sum()/g.weight.sum()
  rates[arm]={"pre_hours":float(pre),"post_hours":float(post),
              "change_hours":float(post-pre)}
  score=(1 if arm=="DNR" else -1)*g.weight*(
      (g[var+"_post"]-g[var+"_pre"])-(post-pre))/g.weight.sum()
  scores.append(pd.DataFrame({"subject_id":g.subject_id,"score":score}))
 effect=rates["DNR"]["change_hours"]-rates["RISKSET"]["change_hours"]
 cluster=pd.concat(scores).groupby("subject_id").score.sum()
 se=float(np.sqrt((cluster**2).sum()))
 out["results"][name]={
   "difference_in_change_hours_per_index":float(effect),
   "conditional_95ci_hours":[float(effect-1.96*se),float(effect+1.96*se)],
   "difference_in_change_per_12h_fraction":float(effect/12),
   "rates":rates}
(root/"risk_fixed_12h_resource_report.json").write_text(json.dumps(out,indent=2)+"\n")
print(json.dumps(out,indent=2))
