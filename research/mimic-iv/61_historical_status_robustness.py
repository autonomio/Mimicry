#!/usr/bin/env python3
"""Historical-period/decision-status robustness of descriptive differences.

Weights from preindex physiological, support-history and laboratory
features. Sign comparisons are exploratory and do not constitute
causal heterogeneous treatment effects or independent validation.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
root=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
w=pd.read_parquet(root/"risk_weighted_severityhistory.parquet")
s=pd.read_parquet(root/"risk_support_bins.parquet").drop(columns="weight")
m=pd.read_parquet(root/"risk_event_bins.parquet").drop(columns="weight")
t=pd.read_parquet(root/"risk_treated.parquet")[
    ["stay_id","first_nonfull_state"]].rename(
        columns={"stay_id":"treated_id","first_nonfull_state":"dnr_type",
                 "unit_group":"unit"})
w=w.merge(t,on="treated_id",validate="many_to_one")
def summarize(table,var,subgrp):
    q=table[table.bin.between(-3,2)].copy()
    q["period"]=np.where(q.bin<0,"pre","post")
    v=(q.groupby(["anchor_id","period"])[[var,"observed_h"]]
       .sum().unstack("period"))
    v.columns=["_".join(x) for x in v.columns]
    merged=w[["anchor_id","arm","weight","subject_id"]+[subgrp]].merge(
         v.reset_index(),on="anchor_id",validate="one_to_one")
    result=[]
    for key,g in merged.groupby(subgrp,dropna=False):
        n=int((g.arm=="DNR").sum())
        if n<50: continue
        vals={}
        for arm,k in g.groupby("arm"):
            p=(k.weight*k[f"{var}_pre"]).sum()/(k.weight*k.observed_h_pre).sum()
            po=(k.weight*k[f"{var}_post"]).sum()/(k.weight*k.observed_h_post).sum()
            vals[arm]=po-p
        result.append({"group":str(key),"n_dnr":n,"contrast":float(vals["DNR"]-vals["RISKSET"])})
    return result
tables={"support":s,"monitor":m}
out={}
for grp in ["era","dnr_type","unit_group"]:
 for var in ["invasive_h","pressor_h","ne_mean_dose_hours","n_map"]:
    tb=s if var!="n_map" else m
    out[grp+"__"+var]=summarize(tb,var,grp)
(root/"risk_historical_and_status_report.json").write_text(json.dumps(out,indent=2)+"\n")
for grp in ["era","dnr_type","unit_group"]:
 print("\n==",grp,"==")
 vals={x["group"]:x for x in out[grp+"__invasive_h"]}
 for row in out[grp+"__pressor_h"]:
  key=row["group"]
  x=vals.get(key)
  if x:
   print(key, "N=",x["n_dnr"],"invasive delta=",round(x["contrast"],4),
         "pressor delta=",round(row["contrast"],4))
