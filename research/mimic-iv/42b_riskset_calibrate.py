#!/usr/bin/env python3
"""Pre-index-only risk-set calibration, MIMIC-IV v3.1.

For every DNR event, draw its historically eligible, still-full-code
pseudo-time controls. Weight via a convex exponential-tilting dual
to match observed preindex covariate moments. All patient records stay
on server; only aggregate diagnostics are printed.
No outcomes, follow-up, or future treatment status used in weighting.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
df=pd.read_parquet(ROOT/"risk_pre_features.parquet")
t=df.loc[df.arm=="DNR"].copy()
r=df.loc[df.arm=="RISKSET"].copy()
spec=[
 ("sofa",2.0,1.3),("age",15.0,1.2),
 ("mean_hr",25.0,2.0),("mean_map",20.0,1.3),
 ("mean_rr",8.0,1.2),("mean_spo2",7.0,0.9),
 ("hr_n_early",6.0,0.5),("hr_n_recent",6.0,1.1),
 ("map_n_early",6.0,0.5),("map_n_recent",6.0,1.1),
 ("hr_n_last4",3.0,0.7),("map_n_last4",3.0,0.7),
 ("hr_6h_change",12.0,0.65),("map_6h_change",10.0,0.65),
]
cols=["treated_id","press_recent","vent_recent"]+[s[0] for s in spec]
r=r.merge(t[cols].rename(columns={
 "press_recent":"t_press_recent","vent_recent":"t_vent_recent",
 **{s[0]:"t_"+s[0] for s in spec}
}),on="treated_id",validate="many_to_one")
# All eligibility and support restrictions use pre-decision facts only.
r=r.loc[
 (r.press_recent==r.t_press_recent)
 &(r.vent_recent==r.t_vent_recent)
 &(r.mean_hr.sub(r.t_mean_hr).abs()<=35)
 &(r.mean_map.sub(r.t_mean_map).abs()<=25)
 &(r.hr_n_recent.sub(r.t_hr_n_recent).abs()<=8)
 &(r.map_n_recent.sub(r.t_map_n_recent).abs()<=8)
].copy()
diffs=[]
d2=np.zeros(len(r))
for name,scale,penalty in spec:
    a=r[name].to_numpy(dtype=float)
    b=r["t_"+name].to_numpy(dtype=float)
    z=(a-b)/scale
    missing_one=np.isnan(z)
    # Small numbers of missing preevent recordings; exclude from moment
    # difference and penalize their proximity score, rather than impute
    # fictitious vital-sign values.
    z[missing_one]=0.
    diffs.append(z)
    d2+=penalty*(z*z+4.0*missing_one.astype(float))
r["distance"]=np.sqrt(d2)
r=r.loc[r.distance<=5.5].copy()
avail=r.groupby("treated_id").size()
eligible_ids=set(avail[avail>=3].index)
r=r.loc[r.treated_id.isin(eligible_ids)].sort_values(
 ["treated_id","distance","anchor_id"]).copy()
t=t.loc[t.treated_id.isin(eligible_ids)].copy()
assert t.treated_id.is_unique
if len(t)<200:
    raise RuntimeError("Too few treatment risk sets on common support")

Z=np.column_stack([
 np.nan_to_num(
   (r[name].to_numpy(dtype=float)-r["t_"+name].to_numpy(dtype=float))/scale,
   nan=0.0)
 for name,scale,_ in spec
])
# Base weights prefer physiologically close comparators, then minimally
# tilt them to balance the global treated covariate moments.
gid,ids=np.unique(r.treated_id.to_numpy(dtype=int),return_inverse=True)
assert len(gid)==len(t)
starts=np.r_[0,np.flatnonzero(np.diff(ids))+1]
TEMP=2.6
REG=0.003
baseline=-0.5*(r.distance.to_numpy(dtype=float)/TEMP)**2
def softmax(lam):
    s=baseline+Z@lam
    a=np.maximum.reduceat(s,starts)
    es=np.exp(s-a[ids])
    denom=np.add.reduceat(es,starts)
    return es/denom[ids],np.mean(a+np.log(denom))
def objgrad(lam):
    w,lse=softmax(lam)
    loss=lse+REG/2*np.dot(lam,lam)
    grad=np.sum(w[:,None]*Z,axis=0)/len(gid)+REG*lam
    return loss,grad
sol=minimize(objgrad,np.zeros(len(spec)),method="L-BFGS-B",jac=True,
    bounds=[(-12.,12.)]*len(spec),
    options={"maxiter":350,"ftol":1.e-11,"gtol":1.e-8})
w,_=softmax(sol.x)
r["weight"]=w
t["weight"]=1.0
assert np.allclose(r.groupby("treated_id").weight.sum().to_numpy(),1.0)
weighted=pd.concat([t,r[df.columns.to_list()+["weight"]]],ignore_index=True)
# Read-only source DB; patient-level weighted data are saved ONLY on s0.
weighted.to_parquet(ROOT/"risk_weighted.parquet",index=False)

def smd(s,field):
    tr=s.loc[s.arm=="DNR"]
    co=s.loc[s.arm=="RISKSET"]
    x=tr[field].to_numpy(dtype=float)
    y=co[field].to_numpy(dtype=float)
    wt=tr.weight.to_numpy(dtype=float)
    wc=co.weight.to_numpy(dtype=float)
    xt=np.isfinite(x);yc=np.isfinite(y)
    mu_x=np.average(x[xt],weights=wt[xt])
    mu_y=np.average(y[yc],weights=wc[yc])
    var_x=np.average((x[xt]-mu_x)**2,weights=wt[xt])
    var_y=np.average((y[yc]-mu_y)**2,weights=wc[yc])
    denom=np.sqrt((var_x+var_y)/2)
    return float((mu_x-mu_y)/denom) if denom>1e-8 else 0.0

control_mass_by_person=r.groupby("subject_id").weight.sum()
eff_controls_events=float(r.weight.sum()**2/(r.weight**2).sum())
eff_controls_people=float(control_mass_by_person.sum()**2/(control_mass_by_person**2).sum())
group_eff=1./r.assign(wsq=r.weight**2).groupby("treated_id").wsq.sum()
balance=[{"feature":name,"smd":smd(weighted,name)} for name,_,_ in spec]
balance.extend([
 {"feature":"press_recent","smd":smd(weighted,"press_recent")},
 {"feature":"vent_recent","smd":smd(weighted,"vent_recent")}
])
report={
 "status":"exploratory; no postindex data used",
 "design":"exact unit/era/6h-clock-bin, same elapsed ICU time, known full-code at t, no earlier limitations, exact organ support, physiologic calipers, convex tilting",
 "treated_in_initial_candidate_pool":int(df.loc[df.arm=="DNR"].shape[0]),
 "treated_common_support_min_3":int(len(t)),
 "unmatched_treated":int(df.loc[df.arm=="DNR"].shape[0]-len(t)),
 "weighted_control_anchor_records":int(len(r)),
 "unique_control_stays":int(r.stay_id.nunique()),
 "unique_control_patients":int(r.subject_id.nunique()),
 "treated_patients":int(t.subject_id.nunique()),
 "patients_in_both_arms":int(len(set(t.subject_id)&set(r.subject_id))),
 "median_controls_per_event":float(avail.loc[list(eligible_ids)].median()),
 "effective_control_anchor_records":eff_controls_events,
 "effective_control_patients_approx":eff_controls_people,
 "median_effective_controls_per_event":float(group_eff.median()),
 "p10_effective_controls_per_event":float(group_eff.quantile(.1)),
 "max_single_control_weight":float(r.weight.max()),
 "fraction_control_weight_top_1pct_anchors":float(r.nlargest(max(1,len(r)//100),"weight").weight.sum()/r.weight.sum()),
 "optimizer_success":bool(sol.success),
 "optimizer_message":str(sol.message),
 "optimizer_iters":int(sol.nit),
 "lambda_maxabs":float(np.abs(sol.x).max()),
 "lambda_on_bound":int((np.abs(sol.x)>11.99).sum()),
 "balancing_regularizer":REG,
 "balance":balance,
 "max_abs_smd":float(max(abs(x["smd"]) for x in balance))
}
(ROOT/"risk_weighting_report.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
