#!/usr/bin/env python3
"""Further retrospective severity-calibration sensitivity in same risk sets.

Uses pre-index GCS, lactate and chemistry only. These features are
retrospectively timestamped; physician result availability at t is not
proven. This is a descriptive robustness check, not a prospectively
deployable causal target trial.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.optimize import minimize

root=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
a=pd.read_parquet(root/"risk_weighted_supporthistory.parquet")
z=pd.read_parquet(root/"risk_pre_severity.parquet")
a=a.merge(z.drop(columns=["treated_id","stay_id","subject_id","arm","weight"]),
          on="anchor_id",validate="one_to_one")
# Encode measurement presence separately from measured value.
a["has_lact24"]=(a.n_lact24>0).astype(float)
a["has_gcs12"]=a.gcs_latest12.notna().astype(float)
a["lact_latest24_clean"]=a.lact_latest24.clip(0,15).fillna(2)
a["lact_max24_clean"]=a.lact_max24.clip(0,15).fillna(2)
a["gcs_latest12_clean"]=a.gcs_latest12.clip(3,15).fillna(15)
a["gcs_min24_clean"]=a.gcs_min24.clip(3,15).fillna(15)
a["creat24_clean"]=a.creat_latest24.clip(0,10).fillna(1)
a["bun24_clean"]=a.bun_latest24.clip(0,200).fillna(20)
a["n_lact24_cap"]=a.n_lact24.clip(0,8)
t=a[a.arm=="DNR"].copy().set_index("treated_id",drop=False)
r=a[a.arm=="RISKSET"].copy()
baseline=[
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
severity=[
 ("has_lact24",0.5),("n_lact24_cap",1.5),
 ("lact_latest24_clean",2.5),("lact_max24_clean",2.5),
 ("has_gcs12",0.3),("gcs_latest12_clean",3.0),
 ("gcs_min24_clean",3.0),("creat24_clean",1.5),
 ("bun24_clean",30.0)
]
spec=baseline+severity
refs=t[[n for n,_ in spec]].rename(columns={n:"t_"+n for n,_ in spec})
r=r.merge(refs,left_on="treated_id",right_index=True,validate="many_to_one")
r=r.sort_values(["treated_id","anchor_id"]).reset_index(drop=True)
gid,ix=np.unique(r.treated_id.to_numpy(dtype=int),return_inverse=True)
starts=np.r_[0,np.flatnonzero(np.diff(ix))+1]
Z=np.column_stack([np.nan_to_num((r[n].to_numpy(float)-r["t_"+n].to_numpy(float))/scale,nan=0)
 for n,scale in spec])
prior=np.log(np.maximum(r.weight.to_numpy(float),1e-250))
reg=0.003
def softmax(lam):
 x=prior+Z@lam
 maxima=np.maximum.reduceat(x,starts)
 ex=np.exp(x-maxima[ix])
 denom=np.add.reduceat(ex,starts)
 return ex/denom[ix],float(np.mean(maxima+np.log(denom)))
def fun(lam):
 w,L=softmax(lam)
 return L+reg/2*np.dot(lam,lam),Z.T@w/len(gid)+reg*lam
sol=minimize(fun,np.zeros(len(spec)),jac=True,method="L-BFGS-B",
 bounds=[(-15,15)]*len(spec),options={"maxiter":450,"gtol":1e-9,"ftol":1e-11})
w,_=softmax(sol.x)
r["weight"]=w
assert np.allclose(r.groupby("treated_id").weight.sum().to_numpy(),1.0)
t["weight"]=1.
keep=a.columns
joined=pd.concat([t[keep],r[keep]],ignore_index=True)
joined.to_parquet(root/"risk_weighted_severityhistory.parquet",index=False)

def smd(var):
 treated=joined[joined.arm=="DNR"]
 control=joined[joined.arm=="RISKSET"]
 x=treated[var].to_numpy(float);y=control[var].to_numpy(float)
 wx=treated.weight.to_numpy(float);wy=control.weight.to_numpy(float)
 okx=np.isfinite(x);oky=np.isfinite(y)
 if not okx.any() or not oky.any():return None
 mx=np.average(x[okx],weights=wx[okx]);my=np.average(y[oky],weights=wy[oky])
 vx=np.average((x[okx]-mx)**2,weights=wx[okx])
 vy=np.average((y[oky]-my)**2,weights=wy[oky])
 den=np.sqrt((vx+vy)/2)
 return float((mx-my)/den) if den>1e-12 else 0.0

def comparative_outcome(table,n,pre=[-3,-2,-1],post=[0,1,2]):
 tb=table.loc[table.bin.isin(pre+post)].copy()
 tb["period"]=np.where(tb.bin<0,"pre","post")
 p=tb.groupby(["anchor_id","period"])[[n,"observed_h"]].sum().unstack("period")
 p.columns=["_".join(x) for x in p.columns]
 x=joined[["anchor_id","arm","subject_id","weight"]].merge(
   p.reset_index(),on="anchor_id",validate="one_to_one")
 o={};score=[]
 for arm,g in x.groupby("arm"):
  npre=n+"_pre";npost=n+"_post"
  dp=(g.weight*g.observed_h_pre).sum();dq=(g.weight*g.observed_h_post).sum()
  yp=(g.weight*g[npre]).sum()/dp
  yq=(g.weight*g[npost]).sum()/dq
  o[arm]={"pre":float(yp),"post":float(yq)}
  s=(1 if arm=="DNR" else -1)*g.weight*((g[npost]-yq*g.observed_h_post)/dq-
    (g[npre]-yp*g.observed_h_pre)/dp)
  score.append(pd.DataFrame({"subject_id":g.subject_id,"s":s}))
 diff=(o["DNR"]["post"]-o["DNR"]["pre"])-(o["RISKSET"]["post"]-o["RISKSET"]["pre"])
 ps=pd.concat(score).groupby("subject_id").s.sum()
 se=float(np.sqrt((ps**2).sum()))
 return {"contrast":float(diff),"conditional_ci95":[float(diff-1.96*se),float(diff+1.96*se)],"rates":o}
person=r.groupby("subject_id").weight.sum()
output={
 "n_treated":int(len(t)),
 "n_control_anchors":int(len(r)),
 "optimizer_success":bool(sol.success),
 "optimizer_message":str(sol.message),
 "max_abs_lambda":float(np.abs(sol.x).max()),
 "max_control_anchor_weight":float(r.weight.max()),
 "effective_control_anchor_records":float(r.weight.sum()**2/(r.weight**2).sum()),
 "effective_control_patients":float(person.sum()**2/(person**2).sum()),
 "balance":[{"variable":n,"smd":smd(n)} for n,_ in spec],
 "results":{}
}
support=pd.read_parquet(root/"risk_support_bins.parquet").drop(columns="weight")
monitor=pd.read_parquet(root/"risk_event_bins.parquet").drop(columns="weight")
for tb,keys in [(support,["pressor_h","invasive_h","ne_mean_dose_hours"]),
                (monitor,["n_map","n_hr"])]:
 for n in keys:
  output["results"][n]=comparative_outcome(tb,n)
# Unmeasured prognostic imbalance diagnostic, not a causal mortality contrast.
a0=joined.copy()
a0["death12"]=((a0.deathtime>=a0.anchor_time)&
 (a0.deathtime<a0.anchor_time+pd.Timedelta(hours=12))).astype(float)
output["death12_pct"]={arm:float(100*np.average(g.death12,weights=g.weight))
 for arm,g in a0.groupby("arm")}
output["latest_lactate_mean_observed"]={
 arm:float(np.average(g.loc[g.lact_latest24.notna(),"lact_latest24"],
 weights=g.loc[g.lact_latest24.notna(),"weight"]))
 for arm,g in joined.groupby("arm")}
output["latest_gcs_mean_observed"]={
 arm:float(np.average(g.loc[g.gcs_latest12.notna(),"gcs_latest12"],
 weights=g.loc[g.gcs_latest12.notna(),"weight"]))
 for arm,g in joined.groupby("arm")}
output["max_abs_smd"]=float(max(abs(z["smd"]) for z in output["balance"] if z["smd"] is not None))
(root/"risk_severityhistory_robustness_report.json").write_text(json.dumps(output,indent=2)+"\n")
print(json.dumps({k:v for k,v in output.items() if k!="balance"},indent=2))
