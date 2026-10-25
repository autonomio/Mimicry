#!/usr/bin/env python3
"""Pre-index weighted treatment delivery trajectories, not causal DNR effects.

Four-hour bins -24 through +12, with post ICU person-time ending at ICU
exit or death. Standard errors are subject-clustered, conditional on
estimated pre-index weights, and exclude risk-set fitting uncertainty.
Patient-level results are retained only on s0.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
b=pd.read_parquet(ROOT/"risk_support_bins.parquet")
a=pd.read_parquet(ROOT/"risk_weighted.parquet")
t=pd.read_parquet(ROOT/"risk_treated.parquet")[["stay_id","first_nonfull_state","sofa","unit_group"]].rename(columns={"stay_id":"treated_id","sofa":"treated_sofa","unit_group":"treated_unit"})
assert b.groupby("anchor_id").size().eq(9).all()
assert (b.pressor_h<=b.observed_h+1.e-7).all()
assert (b.invasive_h<=b.observed_h+1.e-7).all()
for c in ["weight","observed_h","pressor_h","invasive_h","trach_h","noninvasive_h","oxygen_h","ne_mean_dose_hours","ne_max_dose_hours"]:
    b[c]=b[c].astype(float)

spec=[
 ("pressor_h","Vasopressor-exposed ICU hour fraction","share"),
 ("invasive_h","Invasive ventilation ICU hour fraction","share"),
 ("trach_h","Tracheostomy-status ICU hour fraction","share"),
 ("noninvasive_h","HFNC/NIV ICU hour fraction","share"),
 ("oxygen_h","Supplemental oxygen ICU hour fraction","share"),
 ("ne_mean_dose_hours","Norepinephrine-equivalent mean dose per ICU hour, cap5","dose"),
 ("ne_max_dose_hours","Norepinephrine-equivalent max duplicate dose per ICU hour, cap5","dose"),
]
b["period"]=np.select([
 b.bin<=-4, (b.bin>=-3)&(b.bin<=-2),b.bin==-1,b.bin==0,b.bin>=1
],["pre_24to12","pre_12to4","pre_last4","post_first4","post_4to12"],default="ERROR")
cols=["observed_h"]+[x[0] for x in spec]
by=b.groupby(["anchor_id","period"])[cols].sum().unstack("period")
by.columns=["_".join(k) for k in by.columns]
wide=a.merge(by.reset_index(),on="anchor_id",validate="one_to_one")
wide=wide.merge(t,on="treated_id",validate="many_to_one")
assert wide.loc[wide.arm=="DNR","treated_id"].is_unique
assert wide.loc[wide.arm=="DNR","weight"].eq(1.).all()

def rate(group,num,period):
    hn=f"observed_h_{period}"
    nn=f"{num}_{period}"
    return float((group.weight*group[nn]).sum()/(group.weight*group[hn]).sum())
def contrast(group,num,post_periods,pre_periods,uncertainty=True):
    # Two intervals can be combined to preserve rate denominators correctly.
    group=group.copy()
    group["_pre_n"]=sum(group[f"{num}_{p}"] for p in pre_periods)
    group["_pre_h"]=sum(group[f"observed_h_{p}"] for p in pre_periods)
    group["_post_n"]=sum(group[f"{num}_{p}"] for p in post_periods)
    group["_post_h"]=sum(group[f"observed_h_{p}"] for p in post_periods)
    res={}
    scores=[]
    for arm,g in group.groupby("arm"):
        pre_n=(g.weight*g._pre_n).sum()
        pre_h=(g.weight*g._pre_h).sum()
        post_n=(g.weight*g._post_n).sum()
        post_h=(g.weight*g._post_h).sum()
        pre=pre_n/pre_h
        post=post_n/post_h
        res[arm]={"pre":float(pre),"post":float(post),"change":float(post-pre),
                  "weighted_post_person_hours":float(post_h)}
        if uncertainty:
            sign=1 if arm=="DNR" else -1
            score=sign*g.weight*((g._post_n-post*g._post_h)/post_h -
                                 (g._pre_n-pre*g._pre_h)/pre_h)
            scores.append(pd.DataFrame({"subject_id":g.subject_id,"score":score}))
    diff=res["DNR"]["change"]-res["RISKSET"]["change"]
    out={"contrast":float(diff),"group_rates":res}
    if uncertainty:
        influences=pd.concat(scores).groupby("subject_id").score.sum()
        se=float(np.sqrt((influences**2).sum()))
        out.update({"conditional_patient_cluster_se":se,
                    "conditional_ci95":[float(diff-1.96*se),float(diff+1.96*se)]})
    return out

results={"design":"Fixed preindex risk-set weights, dynamic ICU-at-risk person-time; observational",
         "n_dnr_events":int(wide.arm.eq("DNR").sum()),
         "n_control_anchors":int(wide.arm.eq("RISKSET").sum()),
         "definitions":{key:label for key,label,_ in spec},
         "main_last12h_to_next12h":{},
         "near_order_pre4h_to_next4h":{},
         "pretrend_12to4h_vs_last4h":{},
         "source_dose_sensitivity":{},
         "subgroups":[]}
for var,label,unit in spec:
    results["main_last12h_to_next12h"][var]=contrast(wide,var,
       ["post_first4","post_4to12"],["pre_12to4","pre_last4"])
    results["near_order_pre4h_to_next4h"][var]=contrast(wide,var,
       ["post_first4"],["pre_last4"])
    results["pretrend_12to4h_vs_last4h"][var]=contrast(wide,var,
       ["pre_last4"],["pre_12to4"])
# Grouped subset results keep each riskset/control group intact.
for field in ["first_nonfull_state","treated_unit"]:
    for key,g in wide.groupby(field):
        count=int((g.arm=="DNR").sum())
        if count<60: continue
        results["subgroups"].append({
          "type":field,"value":str(key),"n_treated":count,
          "pressor_h":contrast(g,"pressor_h",["post_first4","post_4to12"],
             ["pre_12to4","pre_last4"],uncertainty=False)["contrast"],
          "invasive_h":contrast(g,"invasive_h",["post_first4","post_4to12"],
             ["pre_12to4","pre_last4"],uncertainty=False)["contrast"],
          "ne_mean_dose_hours":contrast(g,"ne_mean_dose_hours",
             ["post_first4","post_4to12"],["pre_12to4","pre_last4"],
             uncertainty=False)["contrast"],
        })
# raw rates at each 4h bin, by arm, to see anticipation in trajectories
four_hour=[]
for (arm,idx),g in b.groupby(["arm","bin"],sort=True):
    rates={v:float((g.weight*g[v]).sum()/(g.weight*g.observed_h).sum())
           for v,_,_ in spec}
    four_hour.append({"arm":arm,"from_hour":int(idx*4),
       "weighted_icu_hours":float((g.weight*g.observed_h).sum()), **rates})
results["event_time_series"]=four_hour
(ROOT/"risk_support_report.json").write_text(json.dumps(results,indent=2)+"\n")
print(json.dumps({k:v for k,v in results.items()
    if k not in ("event_time_series","definitions")},indent=2))
