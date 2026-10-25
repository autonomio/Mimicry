#!/usr/bin/env python3
"""MIMIC-IV 3.1 ancillary joint-process forecasting, historical holdout.

Observed-practice conditional models, not causal or deployable policies.
Only pre-landmark features enter models. Outcomes are next 6h measurements,
ventilator/pressor recording and observed physiology.
"""
import json,warnings
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression,PoissonRegressor,Ridge
from sklearn.metrics import brier_score_loss,roc_auc_score,mean_squared_error,mean_absolute_error
warnings.filterwarnings("ignore",category=FutureWarning)
ROOT=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
df=pd.read_parquet(ROOT/"multistate_6h_panel.parquet")
base=["age","step","unit_group","sofa","hr","map","rr","spo2"]
full=base+["code_state","code_age_h","n_hr","n_map","n_spo2","prior_invasive_h","prior_pressor_h"]
train=df.era.isin(["2008 - 2010","2011 - 2013","2014 - 2016"]).to_numpy()
val=df.era.eq("2017 - 2019").to_numpy()
test=df.era.eq("2020 - 2022").to_numpy()
assert train.sum()>100000 and test.sum()>50000
assert not np.intersect1d(df.subject_id.to_numpy()[train],df.subject_id.to_numpy()[test]).size
assert (df.step>=4).all()
assert (df.next_icu_hours>0).all()
assert (df.next_invasive_h<=df.next_icu_hours+1e-5).all()
assert (df.next_pressor_h<=df.next_icu_hours+1e-5).all()
def prep(fields):
 cats=[x for x in fields if x in ["code_state","unit_group"]]
 nums=[x for x in fields if x not in cats]
 return ColumnTransformer([
 ("numeric",Pipeline([("impute",SimpleImputer(strategy="median",add_indicator=True)),("scale",StandardScaler())]),nums),
 ("category",OneHotEncoder(handle_unknown="ignore"),cats)
 ])
results={"split":{"train":int(train.sum()),"val":int(val.sum()),"test":int(test.sum())},
         "interpretation":"historical observed-practice predictions; not causal","outcomes":{}}
for name,cols in {"physiology":base,"care_history":full}.items():
 X=prep(cols)
 Xtrain=X.fit_transform(df.loc[train,cols])
 Xval=X.transform(df.loc[val,cols])
 Xtest=X.transform(df.loc[test,cols])
 for target,threshold in [("next_invasive_h",0.1),("next_pressor_h",0.1)]:
  y=(df[target].to_numpy()>threshold).astype(int)
  model=LogisticRegression(max_iter=125,solver="lbfgs")
  model.fit(Xtrain,y[train])
  p=model.predict_proba(Xtest)[:,1]
  result={"n_test":int(test.sum()),"observed_frequency":float(y[test].mean()),"predicted_frequency":float(p.mean()),
   "brier":float(brier_score_loss(y[test],p)),
   "auc":float(roc_auc_score(y[test],p))}
  results["outcomes"].setdefault(target,{})[name]=result
 for count in ["next_n_hr","next_n_map"]:
  # Rate is conditional on observed ICU person-time. This is NOT a
  # prospectively known exposure offset and not a count forecasting model.
  hours=df.next_icu_hours.to_numpy(dtype=float)
  rate=df[count].to_numpy(dtype=float)/hours
  model=PoissonRegressor(alpha=0.4,max_iter=120)
  model.fit(Xtrain,rate[train],sample_weight=hours[train])
  pred=model.predict(Xtest)
  obs=rate[test]; w=hours[test]
  eps=1e-9
  dev=2*np.sum(w*(np.where(obs>0,obs*np.log(np.maximum(obs,eps)/np.maximum(pred,eps)),0)-(obs-pred)))/w.sum()
  result={"test_weighted_observed_rate":float(np.average(obs,weights=w)),
   "test_weighted_predicted_rate":float(np.average(pred,weights=w)),
   "poisson_deviance_per_icu_hour":float(dev),
   "weighted_mae_rate":float(np.average(np.abs(obs-pred),weights=w))}
  results["outcomes"].setdefault(count,{})[name]=result
 for measure in ["next_mean_hr","next_mean_map"]:
  good=df[measure].notna().to_numpy()
  fit=train&good; obs=test&good
  # Recorded-only target, selective monitoring (conditional estimand).
  X2=prep(cols)
  tr=X2.fit_transform(df.loc[fit,cols]);te=X2.transform(df.loc[obs,cols])
  model=Ridge(alpha=10.0)
  model.fit(tr,df.loc[fit,measure])
  yp=model.predict(te)
  ytrue=df.loc[obs,measure].to_numpy(float)
  result={"test_observed_rows":int(obs.sum()),"fraction_test_rows_with_measurement":float(obs.sum()/test.sum()),
   "rmse":float(np.sqrt(mean_squared_error(ytrue,yp))),
   "mae":float(mean_absolute_error(ytrue,yp))}
  results["outcomes"].setdefault(measure,{})[name]=result
 print("completed",name,flush=True)
(ROOT/"multistate_component_report.json").write_text(json.dumps(results,indent=2)+"\n")
print(json.dumps(results["outcomes"],indent=2))
