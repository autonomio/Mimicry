#!/usr/bin/env python3
"""Baseline-overlap-standardized historical transport audit, MIMIC-IV 3.1.

Compare actual cumulative death/ICU exit from hour24 to hour144
(120-hour follow-up) in 2017-19 versus 2020-22.
Propensity for historical era uses ONLY hour24 measured patient states,
cross-fitted out of sample. Overlap weighting balances observed baseline
case mix. No interpretation as randomized policy differences.
"""
from pathlib import Path
import json
import numpy as np,pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score
ROOT=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
df=pd.read_parquet(ROOT/"kernel_6h_transitions.parquet")
eras=["2017 - 2019","2020 - 2022"]
base=df.loc[df.era.isin(eras)&(df.step==4)].copy()
assert base.subject_id.is_unique
events=df.loc[df.era.isin(eras)&df.step.between(4,23)&df.terminal_outcome.ne("STAY"),
 ["subject_id","step","terminal_outcome"]]
events=events.sort_values(["subject_id","step"]).drop_duplicates("subject_id")
base=base.merge(events[["subject_id","terminal_outcome"]].rename(columns={"terminal_outcome":"first_terminal_120h"}),
 on="subject_id",how="left",validate="one_to_one")
base["end_status"]=base.first_terminal_120h.fillna("ICU")
base["test_era"]=base.era.eq("2020 - 2022").astype(int)
features=["age","sofa","hr","map","rr","spo2","n_hr","n_map","n_spo2","n_rr",
 "prior_invasive_h","prior_pressor_h","code_age_h","unit_group","code_state"]
cats=["unit_group","code_state"];nums=[x for x in features if x not in cats]
p=np.zeros(len(base))
kf=StratifiedKFold(n_splits=5,shuffle=True,random_state=20261025)
for fi,(train,test) in enumerate(kf.split(base,base.test_era)):
 prep=ColumnTransformer([
 ("num",Pipeline([("impute",SimpleImputer(strategy="median",add_indicator=True)),("scale",StandardScaler())]),nums),
 ("cat",OneHotEncoder(handle_unknown="ignore"),cats)])
 mdl=Pipeline([("prep",prep),("clf",LogisticRegression(max_iter=240,C=.3))])
 mdl.fit(base.iloc[train][features],base.iloc[train].test_era)
 p[test]=mdl.predict_proba(base.iloc[test][features])[:,1]
base["p_test_era"]=np.clip(p,.025,.975)
base["w"]=np.where(base.test_era==1,1-base.p_test_era,base.p_test_era)
def weighted_mean(g,y):
 return float(np.average(g[y],weights=g.w))
def smd(x,y,wx,wy):
 x=np.asarray(x,dtype=float);y=np.asarray(y,dtype=float)
 ax=np.isfinite(x);ay=np.isfinite(y)
 mx=np.average(x[ax],weights=wx[ax]);my=np.average(y[ay],weights=wy[ay])
 vx=np.average((x[ax]-mx)**2,weights=wx[ax])
 vy=np.average((y[ay]-my)**2,weights=wy[ay])
 pooled=np.sqrt((vx+vy)/2)
 return float((mx-my)/pooled) if pooled>1e-8 else 0.
val=base.loc[base.test_era==0].copy();test=base.loc[base.test_era==1].copy()
fields={}
for key in nums:
 fields[key]=smd(val[key],test[key],val.w.to_numpy(),test.w.to_numpy())
for k in cats:
 for value in sorted(base[k].dropna().unique()):
  fields[k+"_"+str(value)]=smd(val[k].eq(value).astype(float),test[k].eq(value).astype(float),
     val.w.to_numpy(),test.w.to_numpy())
rng=np.random.default_rng(20261025)
output={"n_historical_validation":len(val),"n_later_test":len(test),
 "overlap_propensity_out_of_fold_auc":float(roc_auc_score(base.test_era,p)),
 "n_effective_validation":float(val.w.sum()**2/(val.w**2).sum()),
 "n_effective_test":float(test.w.sum()**2/(test.w**2).sum()),
 "max_abs_smd_after":float(max(abs(x) for x in fields.values())),
 "smd_after":fields,
 "estimates":{}}
for kind in ("EXIT","DEATH","ICU"):
 v=(val.end_status==kind).to_numpy(float)
 t=(test.end_status==kind).to_numpy(float)
 raw0=float(v.mean());raw1=float(t.mean())
 ww0=val.w.to_numpy();ww1=test.w.to_numpy()
 m0=float(np.average(v,weights=ww0));m1=float(np.average(t,weights=ww1))
 # Independent patient bootstraps; propensity fixed and crossfitted.
 samples=[]
 for _ in range(400):
  i=rng.integers(0,len(val),len(val));j=rng.integers(0,len(test),len(test))
  u0=np.average(v[i],weights=ww0[i])
  u1=np.average(t[j],weights=ww1[j])
  samples.append(u1-u0)
 output["estimates"][kind]={"raw_validation":raw0,"raw_later":raw1,
 "raw_later_minus_validation":raw1-raw0,
 "overlap_weighted_validation":m0,"overlap_weighted_later":m1,
 "overlap_weighted_difference":m1-m0,
 "bootstrap_ci95_fixed_weights":np.quantile(samples,[.025,.975]).tolist()}
(ROOT/"kernel_historical_transport_report.json").write_text(json.dumps(output,indent=2)+"\n")
print(json.dumps({k:v for k,v in output.items() if k!="smd_after"},indent=2))
