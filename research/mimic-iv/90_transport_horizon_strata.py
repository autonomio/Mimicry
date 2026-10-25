#!/usr/bin/env python3
"""Baseline-overlap standardized historical transport by horizon and ICU strata.

Observational comparison of 2017-19 vs 2020-22 from hour24, NOT
identification of policy/care effect. Propensity crossfit on baseline
states only, with no outcomes used in matching. No patient-level export.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score

ROOT=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
d=pd.read_parquet(ROOT/"kernel_6h_transitions.parquet")
epochs=["2017 - 2019","2020 - 2022"]
base=d[(d.era.isin(epochs))&(d.step==4)].copy()
assert base.subject_id.is_unique
base=base.sort_values(["era","stay_id"]).reset_index(drop=True)
features=["age","sofa","hr","map","rr","spo2","n_hr","n_map","n_spo2","n_rr",
          "prior_invasive_h","prior_pressor_h","code_age_h","unit_group","code_state"]
cats=["unit_group","code_state"]
nums=[c for c in features if c not in cats]
base["later"]=base.era.eq(epochs[1]).astype(int)
prop=np.empty(len(base))
for fold,(a,b) in enumerate(StratifiedKFold(n_splits=5,shuffle=True,random_state=20261025).split(base,base.later)):
 pre=ColumnTransformer([
  ("numeric",Pipeline([("imp",SimpleImputer(strategy="median",add_indicator=True)),("scale",StandardScaler())]),nums),
  ("category",OneHotEncoder(handle_unknown="ignore"),cats)])
 mod=Pipeline([("pre",pre),("clf",LogisticRegression(C=.3,max_iter=250))])
 mod.fit(base.iloc[a][features],base.later.iloc[a])
 prop[b]=mod.predict_proba(base.iloc[b][features])[:,1]
base["propensity"]=np.clip(prop,.025,.975)
base["overlap_weight"]=np.where(base.later.eq(1),1-base.propensity,base.propensity)
base["sofa_band"]=pd.cut(base.sofa,bins=[-1,4,8,12,50],labels=["SOFA 0–4","SOFA 5–8","SOFA 9–12","SOFA 13+"])
events=d[(d.era.isin(epochs))&(d.step.between(4,23))&(d.terminal_outcome!="STAY")].copy()
events=events.sort_values(["subject_id","step"]).drop_duplicates("subject_id")
base=base.merge(events[["subject_id","step","terminal_outcome"]].rename(columns={"step":"event_step","terminal_outcome":"event_type"}),how="left",on="subject_id",validate="one_to_one")
rng=np.random.default_rng(20261025)
def stats(q,label,bstrap=200):
 old=q.loc[q.later==0]
 new=q.loc[q.later==1]
 if len(old)<100 or len(new)<100:return None
 a=old["event_flag"].to_numpy(float);b=new["event_flag"].to_numpy(float)
 wa=old.overlap_weight.to_numpy(float);wb=new.overlap_weight.to_numpy(float)
 raw=float(b.mean()-a.mean())
 wm=float(np.average(b,weights=wb)-np.average(a,weights=wa))
 draw=np.empty(bstrap)
 for j in range(bstrap):
  u=rng.integers(0,len(a),len(a));v=rng.integers(0,len(b),len(b))
  draw[j]=np.average(b[v],weights=wb[v])-np.average(a[u],weights=wa[u])
 return {"label":str(label),"n_prior":int(len(old)),"n_later":int(len(new)),
 "raw_prior":float(a.mean()),"raw_later":float(b.mean()),"raw_later_minus_prior":raw,
 "overlap_prior":float(np.average(a,weights=wa)),"overlap_later":float(np.average(b,weights=wb)),
 "overlap_later_minus_prior":wm,"bootstrap_ci95_fixed_weights":np.quantile(draw,[.025,.975]).tolist(),
 "effective_prior":float(wa.sum()**2/(wa*wa).sum()),
 "effective_later":float(wb.sum()**2/(wb*wb).sum())}
out={"title":"Historical shifts after baseline common-support weighting",
 "status":"Exploratory observational comparisons, not treatment policy identification",
 "eras":epochs,"crossfit_domain_propensity_auc":float(roc_auc_score(base.later,prop)),
 "n_prior":int((base.later==0).sum()),"n_later":int((base.later==1).sum()),
 "horizons":[],"subgroups":[],"caveats":[
 "Overlap weighting balances recorded first-24h state only; patients may differ in unrecorded prognosis",
 "Bootstrap intervals condition on fitted crossfitted propensity, not a full semiparametric causal CI",
 "Test era used before to identify drift; subgroup results are exploratory",
 "ICU exit and death are mutually exclusive first terminal endpoints, measured within first 120h after hour24"
 ]}
for h in [4,8,12,20]:
 for ev in ["EXIT","DEATH","ICU"]:
  q=base.copy()
  within=(q.event_step.notna())&(q.event_step < 4+h)
  q["event_flag"]=np.where(ev=="ICU",(~within).astype(int),
                           (within & q.event_type.eq(ev)).astype(int))
  z=stats(q,f"{ev}@{h*6}h",400)
  out["horizons"].append({"hours_after_hour24":h*6,"state":ev,**z})
for grp in ["unit_group","sofa_band","code_state"]:
 for val,frame in base.groupby(grp,observed=True):
  for ev in ["EXIT","DEATH"]:
   q=frame.copy()
   within=(q.event_step.notna())&(q.event_step<24)
   q["event_flag"]=(within & q.event_type.eq(ev)).astype(int)
   row=stats(q,f"{grp}:{val}:{ev}",300)
   if row:
    out["subgroups"].append({"group":grp,"value":str(val),"state":ev,**row})
(ROOT/"kernel_transport_horizon_and_subgroup_report.json").write_text(json.dumps(out,indent=2)+"\n")
for r in out["horizons"]:
 if r["state"]!="ICU":
  print(r["hours_after_hour24"],r["state"],"raw_difference",round(r["raw_later_minus_prior"],4),
        "case_mix_adjusted",round(r["overlap_later_minus_prior"],4),
        "CI",tuple(round(x,4) for x in r["bootstrap_ci95_fixed_weights"]))
print("subgroups",len(out["subgroups"]),"saved")
