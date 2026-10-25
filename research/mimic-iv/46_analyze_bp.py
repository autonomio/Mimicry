#!/usr/bin/env python3
"""Source-specific blood-pressure charting contrasts, aggregate-only output."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
b=pd.read_parquet(ROOT/"risk_bp_channel_bins.parquet")
b["period"]=np.select([b.bin<=-4,b.bin<=-1,b.bin>=0],
 ["early_pre","recent_pre","post"],default="BAD")
cols=["observed_h","n_art","n_cuff","n_both","n_any"]
a=(b.groupby(["anchor_id","subject_id","arm","weight","period"])[cols]
 .sum().unstack("period"))
a.columns=["_".join(x) for x in a.columns.to_flat_index()]
a=a.reset_index()
def contrast(name):
    groups={}
    for arm,df in a.groupby("arm"):
        pre_n=f"n_{name}_recent_pre"
        post_n=f"n_{name}_post"
        def rate(n,h):
            return float((df.weight*df[n]).sum()/(df.weight*df[h]).sum())
        pre=rate(pre_n,"observed_h_recent_pre")
        post=rate(post_n,"observed_h_post")
        groups[arm]={"pre":pre,"post":post,"change":post-pre}
    impact=groups["DNR"]["change"]-groups["RISKSET"]["change"]
    parts=[]
    for arm,df in a.groupby("arm"):
        sign=1 if arm=="DNR" else -1
        pre_n=f"n_{name}_recent_pre";post_n=f"n_{name}_post"
        gp=groups[arm]["post"];ga=groups[arm]["pre"]
        dp=(df.weight*df.observed_h_post).sum()
        da=(df.weight*df.observed_h_recent_pre).sum()
        infl=sign*df.weight*((df[post_n]-gp*df.observed_h_post)/dp
            -(df[pre_n]-ga*df.observed_h_recent_pre)/da)
        parts.append(pd.DataFrame({"subject_id":df.subject_id,"infl":infl}))
    subjects=pd.concat(parts).groupby("subject_id").infl.sum()
    se=float(np.sqrt(np.square(subjects).sum()))
    return {"contrast":impact,"se_conditional":se,
     "ci95_conditional":[impact-1.96*se,impact+1.96*se],
     "rates":groups}
results={k:contrast(k) for k in ["art","cuff","both","any"]}
report={"n_treated":int(b.loc[(b.arm=="DNR") & (b.bin==0)].shape[0]),
"channels":"ART 220052,225312; cuff 220181; plausible recorded values >0 and <300",
"overlap":"One chart timestamp may include ART and cuff concurrently, so channel contrasts do not add exactly",
"results":results}
(ROOT/"risk_bp_channel_report.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
