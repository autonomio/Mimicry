#!/usr/bin/env python3
"""Nonlinear terminal-hazard challenger: validation-selected, not causal.

A gradient-boosted stochastic terminal kernel challenges linear
multinomial treatment/physiology hazard specification. Validation
calibration fixed using 2017-19 only; test is 2020-22. This is an
exploratory challenger because original test has already been viewed.
"""
import json,joblib,time
from pathlib import Path
import numpy as np,pandas as pd
from scipy.optimize import minimize
from scipy.special import softmax
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import log_loss
ROOT=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
p=pd.read_parquet(ROOT/"kernel_history_6h.parquet")
pack=joblib.load(ROOT/"kernel_terminal.joblib")
history_features=['lag1_hr', 'lag1_map', 'lag1_rr', 'lag1_spo2', 'lag1_n_hr', 'lag1_n_map', 'lag1_invasive', 'lag1_pressor', 'lag2_hr', 'lag2_map', 'lag2_invasive', 'lag2_pressor', 'lag3_invasive', 'lag3_pressor']
features=pack["features"]+history_features
groups=p.era
tr=groups.isin(["2008 - 2010","2011 - 2013","2014 - 2016"])
va=groups.eq("2017 - 2019")
te=groups.eq("2020 - 2022")
classes=list(pack["classes"])
assert classes==["STAY","EXIT","DEATH"]
cat=[c for c in features if c in ("unit_group","code_state")]
X=p[features].copy()
catmaps={}
for k in cat:
 keys=sorted(X.loc[tr,k].dropna().unique())
 catmaps[k]={str(v):i for i,v in enumerate(keys)}
 X[k]=X[k].map(catmaps[k]).fillna(-1).astype(np.int32)
model=HistGradientBoostingClassifier(max_iter=165,learning_rate=.04,
 max_leaf_nodes=21,min_samples_leaf=170,l2_regularization=7.,
 max_bins=127,random_state=20261025,early_stopping=False,
 categorical_features=[f in cat for f in features])
t0=time.monotonic()
model.fit(X.loc[tr,features],p.loc[tr,"terminal_outcome"])
print("nonlinear hazard fitted sec",round(time.monotonic()-t0,2),flush=True)
order=[list(model.classes_).index(x) for x in classes]
valp=model.predict_proba(X.loc[va,features])[:,order]
testp=model.predict_proba(X.loc[te,features])[:,order]
def cal_predict(pp,theta):
 z=np.log(np.maximum(pp,1.e-10))
 z=(z-z[:,[0]])*np.exp(theta[0])
 z[:,1:]+=theta[1:]
 return softmax(z,axis=1)
actual=np.array([classes.index(v) for v in p.loc[va,"terminal_outcome"]])
def loss(theta):
 v=cal_predict(valp,theta)
 return -np.log(np.maximum(v[np.arange(len(actual)),actual],1e-12)).mean()+1.e-4*(theta[1:]**2).sum()
sol=minimize(loss,np.zeros(3),method="L-BFGS-B",
 bounds=[(-1.2,1.2),(-3,3),(-3,3)])
assert sol.success or sol.fun<loss(np.zeros(3))
pva=cal_predict(valp,sol.x)
pte=cal_predict(testp,sol.x)
lin=pack["model"]
linear_raw=lin.predict_proba(p.loc[va,pack['features']])
idx=[list(lin.named_steps["clf"].classes_).index(k) for k in classes]
linear_cal=cal_predict(linear_raw[:,idx],np.asarray(pack["calibration"]))
valactual=p.loc[va,"terminal_outcome"].to_numpy()
testactual=p.loc[te,"terminal_outcome"].to_numpy()
def audited_logloss(y,p):
 idx=np.array([classes.index(x) for x in y],int)
 return float(-np.mean(np.log(np.maximum(p[np.arange(len(y)),idx],1.e-12))))
val_hgb=audited_logloss(valactual,pva)
val_linear=audited_logloss(valactual,linear_cal)
test_hgb=audited_logloss(testactual,pte)
rates_obs={k:float((testactual==k).mean()) for k in classes}
rates_pred={k:float(pte[:,i].mean()) for i,k in enumerate(classes)}
gate={"death":0.8<=rates_pred["DEATH"]/rates_obs["DEATH"]<=1.25,
"exit":0.9<=rates_pred["EXIT"]/rates_obs["EXIT"]<=1.1}
report={"model":"HistGradientBoostingClassifier with 18h lagged support/physiology histories",
 "validation_log_loss_nonlinear":val_hgb,
 "validation_log_loss_linear":val_linear,
 "validation_select_nonlinear":bool(val_hgb<val_linear),
 "test_nonlinear_logloss":test_hgb,
 "test_linear_logloss":audited_logloss(testactual,cal_predict(
 lin.predict_proba(p.loc[te,pack['features']])[:,idx],np.asarray(pack["calibration"]))),
 "test_observed":rates_obs,"test_predicted":rates_pred,
 "test_ratio_predicted_observed":{k:rates_pred[k]/rates_obs[k] for k in classes},
 "test_gates":gate,"calibration_params":sol.x.tolist(),
 "calibration_learned_only_validation":True,
 "test_previously_examined":"Yes, this is an exploratory challenger, not a new confirmatory holdout."
}
joblib.dump({"model":model,"features":features,"classes":classes,
 "calibration":sol.x,"category_maps":catmaps,"model_type":"hgb","history_features":history_features},
 ROOT/"kernel_terminal_hgb_history.joblib",compress=3)
(ROOT/"kernel_hgb_history_report.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2),flush=True)
