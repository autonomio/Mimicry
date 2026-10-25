#!/usr/bin/env python3
"""Earlier rolling-origin external-in-time validation of terminal hazards.

Train 2008-2013, calibrate 2014-2016, test 2017-2019.
A SECOND time-series split used as historical replication of calibration
drift, exploratory after observing the 2020-22 results. No policy effect.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from scipy.optimize import minimize
from scipy.special import softmax
ROOT=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
p=pd.read_parquet(ROOT/"kernel_history_6h.parquet")
fields=["age","step","unit_group","sofa","hr","map","rr","spo2",
 "n_hr","n_map","n_spo2","n_rr","code_state","code_age_h",
 "prior_invasive_h","prior_pressor_h",
 "lag1_hr","lag1_map","lag1_rr","lag1_spo2","lag1_n_hr","lag1_n_map",
 "lag1_invasive","lag1_pressor","lag2_hr","lag2_map",
 "lag2_invasive","lag2_pressor","lag3_invasive","lag3_pressor"]
tr=p.era.isin(["2008 - 2010","2011 - 2013"]).to_numpy()
va=p.era.eq("2014 - 2016").to_numpy()
te=p.era.eq("2017 - 2019").to_numpy()
assert (tr & va).sum()==(tr & te).sum()==(va & te).sum()==0
classes=["STAY","EXIT","DEATH"]
cats=["unit_group","code_state"]
X=p[fields].copy()
for name in cats:
 mapping={x:i for i,x in enumerate(sorted(X.loc[tr,name].dropna().unique()))}
 X[name]=X[name].map(mapping).fillna(-1).astype(np.int32)
m=HistGradientBoostingClassifier(max_iter=165,learning_rate=.04,
 max_leaf_nodes=21,min_samples_leaf=170,l2_regularization=7.,
 max_bins=127,random_state=20261025,early_stopping=False,
 categorical_features=[f in cats for f in fields])
m.fit(X.loc[tr,fields],p.loc[tr,"terminal_outcome"])
order=[list(m.classes_).index(c) for c in classes]
qva=m.predict_proba(X.loc[va,fields])[:,order]
qte=m.predict_proba(X.loc[te,fields])[:,order]
def apply(pp,t):
 logp=np.log(np.maximum(pp,1e-10))
 logits=(logp-logp[:,[0]])*np.exp(t[0])
 logits[:,1:]+=t[1:]
 return softmax(logits,axis=1)
yv=np.array([classes.index(z) for z in p.loc[va,"terminal_outcome"]])
def obj(theta):
 q=apply(qva,theta)
 return -np.log(np.maximum(q[np.arange(len(yv)),yv],1e-10)).mean()+1e-4*np.square(theta[1:]).sum()
sol=minimize(obj,np.zeros(3),method="L-BFGS-B",bounds=[(-1.2,1.2),(-3,3),(-3,3)])
assert sol.success or sol.fun<obj(np.zeros(3))
pv=apply(qva,sol.x);pt=apply(qte,sol.x)
data=p.loc[te,["subject_id","step","terminal_outcome"]].copy()
data["p_exit"]=pt[:,1];data["p_death"]=pt[:,2]
data["obs_exit"]=data.terminal_outcome.eq("EXIT").astype(int)
data["obs_death"]=data.terminal_outcome.eq("DEATH").astype(int)
N=int(data.step.eq(4).sum())
assert N==data.subject_id.nunique()
rng=np.random.default_rng(20261025)
out={"model":"fixed HGB architecture, rolling-origin 2008-13 train, 2014-16 calibrate, 2017-19 evaluate",
"n_training_rows":int(tr.sum()),"n_calibration_rows":int(va.sum()),"n_evaluation_rows":int(te.sum()),
"n_hour24_patients":N,"calibration_only_prior_era":True,"results":[]}
for h in [4,8,12,20]:
 sub=data[data.step<4+h]
 by=sub.groupby("subject_id").agg(p_exit=("p_exit","sum"),p_death=("p_death","sum"),
 obs_exit=("obs_exit","sum"),obs_death=("obs_death","sum"))
 assert len(by)==N
 record={"hours":h*6}
 for ev in ["exit","death"]:
  pre=float(by["p_"+ev].mean()); obs=float(by["obs_"+ev].mean())
  scores=(by["p_"+ev]-by["obs_"+ev]).to_numpy()
  boot=np.empty(400)
  for j in range(400):
   i=rng.integers(0,N,N);boot[j]=scores[i].mean()
  record[ev]={"observed":obs,"prequential_expected":pre,
   "relative_ratio":pre/obs if obs else None,
   "error":pre-obs,"fixed_fit_patient_bootstrap_ci95":np.quantile(boot,[.025,.975]).tolist()}
 out["results"].append(record)
 print("rolling origin",h*6,"EXIT obs",round(record["exit"]["observed"],4),
 "expected",round(record["exit"]["prequential_expected"],4),
 "DEATH obs",round(record["death"]["observed"],4),
 "expected",round(record["death"]["prequential_expected"],4))
out["limitation"]="2017-19 now serves as an exploratory earlier test; historical recurrence cannot establish future transport or causal effect."
(ROOT/"kernel_rolling_origin_report.json").write_text(json.dumps(out,indent=2)+"\n")
