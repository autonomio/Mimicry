#!/usr/bin/env python3
"""Aggregate measurement-rate analysis after frozen preindex risk-set weights.

Reports patient-clustered conditional sandwich uncertainty; this omits
uncertainty from constructing/calibrating the risk-set weights and is NOT
sufficient for causal effect claims. All MIMIC-level rows stay on s0.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
bins=pd.read_parquet(ROOT/"risk_event_bins.parquet")
anchors=pd.read_parquet(ROOT/"risk_weighted.parquet")
assert bins.anchor_id.nunique()==len(anchors)
assert bins.groupby("anchor_id").size().eq(9).all()
assert bins.groupby(["anchor_id"]).weight.nunique().max()==1
assert len(bins.groupby("treated_id"))==anchors.loc[anchors.arm=="DNR","treated_id"].nunique()

vars=["observed_h","censored_h","n_hr","n_map","n_hr_censored","n_map_censored"]
bins["period"]=np.select([
 bins.bin<=-4,(bins.bin>=-3)&(bins.bin<=-1),bins.bin>=0
],["pre_24to12","pre_12to0","post_0to12"],default="ERROR")
by=(bins.groupby(["anchor_id","period"])[vars].sum().unstack("period"))
by.columns=["_".join(z) for z in by.columns.to_flat_index()]
by=by.reset_index()
a=anchors.merge(by,on="anchor_id",validate="one_to_one")
a["is_treated"]=a.arm=="DNR"
n_t=int(a.is_treated.sum())
assert np.isclose(a.loc[a.is_treated,"weight"].sum(),n_t)
assert np.isclose(a.loc[~a.is_treated,"weight"].sum(),n_t)
assert (a["observed_h_pre_12to0"]>11.99).all()

def rate(frame,numer,denom):
    return float((frame.weight*frame[numer]).sum()/(frame.weight*frame[denom]).sum())
def group_rate(frame,metric,censor=False):
    pre_n=f"n_{metric}_pre_12to0"
    post_n=f"n_{metric}{'_censored' if censor else ''}_post_0to12"
    post_h=f"{'censored' if censor else 'observed'}_h_post_0to12"
    return rate(frame,post_n,post_h),rate(frame,pre_n,"observed_h_pre_12to0")
def effect(frame,metric,censor=False,cluster=True):
    tr=frame.loc[frame.is_treated]
    co=frame.loc[~frame.is_treated]
    post_t,pre_t=group_rate(tr,metric,censor)
    post_c,pre_c=group_rate(co,metric,censor)
    estimate=(post_t-pre_t)-(post_c-pre_c)
    out={"effect":float(estimate),"dnr_pre":pre_t,"dnr_post":post_t,
         "control_pre":pre_c,"control_post":post_c,
         "dnr_change":float(post_t-pre_t),
         "control_change":float(post_c-pre_c)}
    if cluster:
        per_arm=[]
        for group,sign,rp,r0 in [(tr,1.,post_t,pre_t),(co,-1.,post_c,pre_c)]:
            npst=f"n_{metric}{'_censored' if censor else ''}_post_0to12"
            hpst=f"{'censored' if censor else 'observed'}_h_post_0to12"
            npre=f"n_{metric}_pre_12to0"
            hpre="observed_h_pre_12to0"
            score=(sign*group.weight*(
                (group[npst]-rp*group[hpst])/(group.weight*group[hpst]).sum()
                -(group[npre]-r0*group[hpre])/(group.weight*group[hpre]).sum()
            ))
            per_arm.append(pd.DataFrame({"subject_id":group.subject_id,"score":score}))
        influence=pd.concat(per_arm,ignore_index=True).groupby("subject_id").score.sum()
        se=float(np.sqrt(np.square(influence).sum()))
        out["subject_cluster_se_conditional"]=se
        out["ci95_conditional"]=[estimate-1.96*se,estimate+1.96*se]
        out["n_unique_subjects"]=int(influence.size)
    return out

report={
 "design":"DNR-vs-documented-full-code at-risk pseudo-events, calibrated only on preindex histories",
 "n_treated":n_t,
 "n_control_anchor_rows":int((~a.is_treated).sum()),
 "matching_source":"risk_weighting_report.json",
 "main":{
  "heart_rate_recordings_per_icu_hour":effect(a,"hr"),
  "map_recordings_per_icu_hour":effect(a,"map")
 },
 "sensitivity_censor_controls_at_subsequent_code_transition":{
  "heart_rate":effect(a,"hr",censor=True),
  "map":effect(a,"map",censor=True)
 },
}
# Attrition/death are outcomes, NEVER eligibility conditions.
a["death_12h"]=a.deathtime.notna() & (a.deathtime>=a.anchor_time) & (
 a.deathtime<a.anchor_time+pd.Timedelta(hours=12))
a["death_4h"]=a.deathtime.notna() & (a.deathtime>=a.anchor_time) & (
 a.deathtime<a.anchor_time+pd.Timedelta(hours=4))
a["icu_exit_12h"]=a.outtime<a.anchor_time+pd.Timedelta(hours=12)
a["later_status_12h"]=(a.arm=="RISKSET") & a.first_nonfull.notna() & (
 a.first_nonfull>a.anchor_time) & (
 a.first_nonfull<a.anchor_time+pd.Timedelta(hours=12))
attrition={}
for arm,g in a.groupby("arm"):
    wt=g.weight.to_numpy()
    attrition[arm]={
     "weighted_n":float(wt.sum()),
     "death_within_4h_pct":float(100*np.average(g.death_4h,weights=wt)),
     "death_within_12h_pct":float(100*np.average(g.death_12h,weights=wt)),
     "icu_exit_within_12h_pct":float(100*np.average(g.icu_exit_12h,weights=wt)),
     "mean_atrisk_icu_hours_post12":float(np.average(g.observed_h_post_0to12,weights=wt)),
     "new_treatment_limit_by12h_pct":float(100*np.average(g.later_status_12h,weights=wt))
    }
report["terminal_events_and_crossover"]=attrition

# 4-hour event-time rates, retaining differential death/discharge person-time.
event=[]
for (arm,idx),g in bins.groupby(["arm","bin"],sort=True):
    event.append({
      "arm":arm,"hours_from_event":int(idx*4),"n_weighted":float(g.weight.sum()),
      "hr_rate":float((g.weight*g.n_hr).sum()/(g.weight*g.observed_h).sum()),
      "map_rate":float((g.weight*g.n_map).sum()/(g.weight*g.observed_h).sum()),
      "person_hours_weighted":float((g.weight*g.observed_h).sum())
    })
report["four_hour_trajectories"]=event

# Subgroup descriptive effects; same frozen preindex weighting, no post-selection.
strata=[]
for col in ["unit_group","era","first_nonfull_state"]:
    if col=="first_nonfull_state":
        treatment_state=pd.read_parquet(ROOT/"risk_treated.parquet")[["stay_id","first_nonfull_state"]].rename(columns={"stay_id":"treated_id"})
        aa=a.merge(treatment_state,on="treated_id",how="left",validate="many_to_one")
    else:
        aa=a
    for key,g in aa.groupby(col,dropna=False):
        n=int(g.is_treated.sum())
        if n<50:
            continue
        strata.append({
          "subgroup":col,"value":str(key),"n_treated":n,
          "map_rate_diff_in_diff":effect(g,"map",cluster=False)["effect"],
          "hr_rate_diff_in_diff":effect(g,"hr",cluster=False)["effect"],
        })
report["subgroups_descriptive"]=strata
(ROOT/"risk_outcome_report.json").write_text(json.dumps(report,indent=2)+"\n")
# Print only report key summaries rather than patient-level data.
print(json.dumps({k:v for k,v in report.items()
 if k!="four_hour_trajectories"},indent=2))
