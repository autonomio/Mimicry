#!/usr/bin/env python3
"""Exploratory robustness: add prior support intensity to frozen risk sets.

This does not assert causal identification. Reweight selected risk sets
based solely on retrospective PRE-index support histories. Base cohort
and selection remain unchanged. Post-index information is never used
to select controls or estimate the new weights.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
root=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
a=pd.read_parquet(root/"risk_weighted.parquet")
b=pd.read_parquet(root/"risk_support_bins.parquet")
pre=b.loc[b.bin.isin([-3,-2,-1])].copy()
pre["part"]=np.where(pre.bin==-1,"last4","early8")
names=["pressor_h","invasive_h","ne_mean_dose_hours","noninvasive_h"]
v=(pre.groupby(["anchor_id","part"])[names+["observed_h"]]
   .sum().unstack("part"))
v.columns=["_".join(c) for c in v.columns]
v=v.reset_index()
for s in names:
 for p in ("early8","last4"):
  v[f"{s}_{p}_frac"]=v[f"{s}_{p}"]/v[f"observed_h_{p}"]
a=a.merge(v[["anchor_id"]+[f"{s}_{p}_frac" for s in names for p in ("early8","last4")]],on="anchor_id",validate="one_to_one")
t=a[a.arm=="DNR"].copy().set_index("treated_id",drop=False)
r=a[a.arm=="RISKSET"].copy()
spec=[
 ("sofa",2.0),("age",15.0),("mean_hr",25.0),("mean_map",20.0),
 ("mean_rr",8.0),("mean_spo2",7.0),
 ("hr_n_early",6.0),("hr_n_recent",6.0),
 ("map_n_early",6.0),("map_n_recent",6.0),
 ("hr_n_last4",3.0),("map_n_last4",3.0),
 ("hr_6h_change",12.0),("map_6h_change",10.0),
 ("pressor_h_early8_frac",0.25),("pressor_h_last4_frac",0.25),
 ("invasive_h_early8_frac",0.35),("invasive_h_last4_frac",0.35),
 ("ne_mean_dose_hours_early8_frac",0.2),
 ("ne_mean_dose_hours_last4_frac",0.2),
 ("noninvasive_h_early8_frac",0.25),
 ("noninvasive_h_last4_frac",0.25),
]
assert t.treated_id.is_unique
join=t[[key for key,_ in spec]].rename(columns={key:"t_"+key for key,_ in spec})
r=r.merge(join,left_on="treated_id",right_index=True,validate="many_to_one")
r=r.sort_values(["treated_id","anchor_id"]).reset_index(drop=True)
gid,ids=np.unique(r.treated_id.to_numpy(dtype=int),return_inverse=True)
starts=np.r_[0,np.flatnonzero(np.diff(ids))+1]
assert len(gid)==len(t)
Z=np.column_stack([
 np.nan_to_num((r[key].to_numpy(dtype=float)-
 r["t_"+key].to_numpy(dtype=float))/scale,nan=0.)
 for key,scale in spec
])
reg=0.003
base=np.log(np.maximum(r.weight.to_numpy(float),1e-250))
def softmax(lam):
 x=base+Z@lam
 mx=np.maximum.reduceat(x,starts)
 ex=np.exp(x-mx[ids])
 norm=np.add.reduceat(ex,starts)
 return ex/norm[ids],float(np.mean(mx+np.log(norm)))
def fn(lam):
 w,L=softmax(lam)
 return L+reg/2*np.dot(lam,lam),Z.T@w/len(gid)+reg*lam
sol=minimize(fn,np.zeros(len(spec)),jac=True,method="L-BFGS-B",
 bounds=[(-15,15)]*len(spec),
 options={"maxiter":400,"gtol":1.e-9,"ftol":1.e-11})
w,_=softmax(sol.x)
r["weight"]=w
assert np.allclose(r.groupby("treated_id").weight.sum().to_numpy(),1.0)
keeps=a.columns.to_list()
t["weight"]=1.
combined=pd.concat([t[keeps],r[keeps]],ignore_index=True)
assert (combined.arm=="DNR").sum()==len(t)
combined.to_parquet(root/"risk_weighted_supporthistory.parquet",index=False)

def smd(name):
 tt=combined.loc[combined.arm=="DNR"]
 cc=combined.loc[combined.arm=="RISKSET"]
 x=tt[name].to_numpy(dtype=float)
 y=cc[name].to_numpy(dtype=float)
 wx=tt.weight.to_numpy(dtype=float);wy=cc.weight.to_numpy(dtype=float)
 u=np.isfinite(x);v=np.isfinite(y)
 mx=np.average(x[u],weights=wx[u]);my=np.average(y[v],weights=wy[v])
 vx=np.average((x[u]-mx)**2,weights=wx[u])
 vy=np.average((y[v]-my)**2,weights=wy[v])
 sd=np.sqrt((vx+vy)/2)
 return float((mx-my)/sd) if sd>1.e-9 else 0.0

# Conditional subject-cluster uncertainty on before-after person-hour rates.
def effect(table,numerator,pre_bins=[-3,-2,-1],post_bins=[0,1,2]):
 table=table[table.bin.isin(pre_bins+post_bins)].copy()
 table["period"]=np.where(table.bin.isin(pre_bins),"pre","post")
 x=(table.groupby(["anchor_id","period"])[[numerator,"observed_h"]]
    .sum().unstack("period"))
 x.columns=["_".join(z) for z in x.columns]
 x=combined[["anchor_id","subject_id","arm","weight"]].merge(
 x.reset_index(),on="anchor_id",validate="one_to_one")
 rates={};contrib=[]
 for arm,g in x.groupby("arm"):
  nhpre=numerator+"_pre";nhpost=numerator+"_post"
  Dpre=(g.weight*g.observed_h_pre).sum()
  Dpost=(g.weight*g.observed_h_post).sum()
  pre=(g.weight*g[nhpre]).sum()/Dpre
  post=(g.weight*g[nhpost]).sum()/Dpost
  rates[arm]={"pre":float(pre),"post":float(post),"change":float(post-pre)}
  sg=1 if arm=="DNR" else -1
  influence=sg*g.weight*((g[nhpost]-post*g.observed_h_post)/Dpost-
                         (g[nhpre]-pre*g.observed_h_pre)/Dpre)
  contrib.append(pd.DataFrame({"subject_id":g.subject_id,"sc":influence}))
 es=rates["DNR"]["change"]-rates["RISKSET"]["change"]
 cl=pd.concat(contrib).groupby("subject_id").sc.sum()
 se=float(np.sqrt((cl**2).sum()))
 return {"contrast":float(es),"conditional_ci95":[float(es-1.96*se),float(es+1.96*se)],
 "group_rates":rates}

overlap=r.groupby("subject_id").weight.sum()
report={
 "design":"pre-index support-history + previous baseline calibration, within same risk sets, exploratory robustness",
 "n_treated":int(len(t)),
 "n_control_anchors":int(len(r)),
 "optimizer_success":bool(sol.success),
 "optimizer_message":str(sol.message),
 "max_abs_lambda":float(np.abs(sol.x).max()),
 "max_anchor_weight":float(r.weight.max()),
 "effective_control_anchor_records":float(r.weight.sum()**2/(r.weight**2).sum()),
 "effective_control_patients_approx":float(overlap.sum()**2/(overlap**2).sum()),
 "balance":[{"feature":name,"smd":smd(name)} for name,_ in spec],
 "results":{},
}
for table,inputs in [
 (b,[("pressor_h","pressor_exposure"),("invasive_h","invasive_ventilation"),
     ("ne_mean_dose_hours","ne_eq_dose"),("noninvasive_h","noninvasive_support")]),
 (pd.read_parquet(root/"risk_event_bins.parquet"),
  [("n_map","map_recording"),("n_hr","heart_rate_recording")])
]:
 table=table.drop(columns="weight").merge(
  combined[["anchor_id","weight"]],on="anchor_id",validate="many_to_one")
 for var,label in inputs:
  report["results"][label]={"main":effect(table,var),
   "pretrend_last4_vs_previous8":effect(table,var,pre_bins=[-3,-2],post_bins=[-1])}
report["max_abs_smd"]=max(abs(x["smd"]) for x in report["balance"])
(root/"risk_supporthistory_robustness_report.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps({k:v for k,v in report.items() if k!="balance"},indent=2))
