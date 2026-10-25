#!/usr/bin/env python3
"""Pre/post laboratory measurement rate contrast, with subject clusters."""
from pathlib import Path
import pandas as pd, numpy as np, json
root=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
a=pd.read_parquet(root/"risk_lab_anchor.parquet")
a["pre_h"]=a["pre_h"].astype(float)
a["post_h"]=a["post_h"].astype(float)
results={}
for lab in ("chem","cbc"):
    arm_result={}
    arm_data={}
    for arm,g in a.groupby("arm"):
        rpre=(g.weight*g["pre_"+lab]).sum()/(g.weight*g.pre_h).sum()
        rpost=(g.weight*g["post_"+lab]).sum()/(g.weight*g.post_h).sum()
        arm_result[arm]={"pre":float(rpre),"post":float(rpost),"delta":float(rpost-rpre)}
        arm_data[arm]=g
    est=arm_result["DNR"]["delta"]-arm_result["RISKSET"]["delta"]
    contributions=[]
    for arm,g in arm_data.items():
        sign=1 if arm=="DNR" else -1
        r0=arm_result[arm]["pre"];r1=arm_result[arm]["post"]
        D0=(g.weight*g.pre_h).sum();D1=(g.weight*g.post_h).sum()
        score=sign*g.weight*((g["post_"+lab]-r1*g.post_h)/D1-
                             (g["pre_"+lab]-r0*g.pre_h)/D0)
        contributions.append(pd.DataFrame({"subject_id":g.subject_id,"score":score}))
    combined=pd.concat(contributions).groupby("subject_id").score.sum()
    se=float(np.sqrt((combined*combined).sum()))
    results[lab]={"contrast":float(est),"subject_cluster_se_conditional":se,
       "ci95_conditional":[float(est-1.96*se),float(est+1.96*se)],
       "rates":arm_result}
(root/"risk_labs_report.json").write_text(json.dumps(results,indent=2)+"\n")
print(json.dumps(results,indent=2))
