#!/usr/bin/env python3
"""Conditional observation-and-physiology marks for observational kernel.

Only survivor intervals, with conditional destination code and support.
Sequence: terminal -> code -> joint support -> measurement counts ->
recorded physiologic marks. This yields a NORMALIZED joint conditional
kernel once combined with the 81 models. It does not identify latent
physiology or counterfactual causal policies. All data stay on s0.
"""
import json,warnings
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression,PoissonRegressor,Ridge
from sklearn.metrics import roc_auc_score,mean_absolute_error,mean_squared_error
warnings.filterwarnings("ignore",category=FutureWarning)
ROOT=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
df=pd.read_parquet(ROOT/"kernel_6h_transitions.parquet")
df=df.loc[df.terminal_outcome=="STAY"].copy()
df["support_state"]=np.where(df.next_invasive_h<.1,0,
  np.where(df.next_invasive_h>=5.9,2,1))*3+np.where(df.next_pressor_h<.1,0,np.where(df.next_pressor_h>=5.9,2,1))
df["support_state"]=df.support_state.astype(str)
df["code_changed"]=df.code_state.ne(df.next_code).astype(float)
df["next_n_spo2"]=df.next_n_spo2.astype(float)
base=["age","step","unit_group","sofa","hr","map","rr","spo2",
      "n_hr","n_map","n_spo2","n_rr","code_state","code_age_h","prior_invasive_h","prior_pressor_h"]
cond=base+["next_code","code_changed","support_state"]
post=cond+["next_n_hr","next_n_map","next_n_spo2","next_n_rr","next_invasive_h","next_pressor_h"]
tr=df.era.isin(["2008 - 2010","2011 - 2013","2014 - 2016"]).to_numpy()
va=df.era.eq("2017 - 2019").to_numpy()
te=df.era.eq("2020 - 2022").to_numpy()
assert tr.sum()+va.sum()+te.sum()==len(df)
assert df.loc[te].subject_id.nunique()>4000
assert df.next_icu_hours.between(5.999,6.001).all()
def prep(cols):
 cats=[x for x in cols if x in ["unit_group","code_state","next_code","support_state"]]
 nums=[x for x in cols if x not in cats]
 return ColumnTransformer([
  ("num",Pipeline([("fill",SimpleImputer(strategy="median",add_indicator=True)),
   ("scale",StandardScaler())]),nums),
  ("cats",OneHotEncoder(handle_unknown="ignore"),cats)
 ])
report={"n_survivor_transitions":int(len(df)),
 "train":int(tr.sum()),"validation":int(va.sum()),"test":int(te.sum()),
 "interpretation":"Conditional on still-in-ICU after 6h; testing conditional on actual future code/support is oracle-assisted diagnostic only.",
 "observation":[],"recorded_physiology":[]}
obs_targets=["next_n_hr","next_n_map","next_n_spo2","next_n_rr"]
val_preds={}
for target in obs_targets:
 y=df[target].to_numpy(float)
 assert np.isfinite(y).all() and (y>=0).all()
 # Hurdle count law: P(N>0) and N|N>0=1+Poisson(lambda),
 # including zero-count observation events in the stochastic kernel.
 model=Pipeline([("pre",prep(cond)),("clf",LogisticRegression(max_iter=120))])
 model.fit(df.loc[tr,cond],(y[tr]>0).astype(int))
 train_pos=tr&(y>0)
 pos=Pipeline([("pre",prep(cond)),("reg",PoissonRegressor(alpha=.07,max_iter=130))])
 pos.fit(df.loc[train_pos,cond],y[train_pos]-1.)
 pval=model.predict_proba(df.loc[va,cond])[:,1]
 ptest=model.predict_proba(df.loc[te,cond])[:,1]
 # IMPORTANT: Poisson log-link extrapolates explosively for rare feature
 # combinations. Cap the positive conditional mean at the training-only
 # 99.9th percentile, then calibrate on validation. A count can still
 # exceed this mean under the generative noise distribution.
 cap=float(np.quantile(y[train_pos],.999))
 lamval=np.clip(pos.predict(df.loc[va,cond]),0.,max(0.,cap-1.))
 lamtest=np.clip(pos.predict(df.loc[te,cond]),0.,max(0.,cap-1.))
 # Validation-only scalar calibration of positive-count mean; no test tuning.
 ratio=float(np.average(y[va])/np.mean(pval*(1+lamval)))
 ratio=float(np.clip(ratio,.5,1.5))
 lamval=np.clip((1+lamval)*ratio-1,0,max(0.,cap-1.))
 lamtest=np.clip((1+lamtest)*ratio-1,0,max(0.,cap-1.))
 muval=pval*(1+lamval)
 mutest=ptest*(1+lamtest)
 val_preds[target]=muval
 observed=y[te]
 rmse=float(np.sqrt(np.mean((observed-mutest)**2)))
 res={"measurement":target,"test_actual_mean":float(observed.mean()),
 "test_predicted_mean_conditional":float(mutest.mean()),
 "test_actual_zero_pct":float(100*np.mean(observed==0)),
 "test_predicted_zero_pct_conditional":float(100*np.mean(1-ptest)),
 "test_mae_expected_count":float(mean_absolute_error(observed,mutest)),
 "test_rmse_expected_count":rmse,
 "validation_mean_multiplier":ratio,"train_999pct_count_cap":cap,
 "test_positive_presence_auc":float(roc_auc_score((observed>0).astype(int),ptest))}
 report["observation"].append(res)
 joblib.dump({"presence":model,"positive_excess":pos,"mean_multiplier":ratio,
              "features":cond,"target":target,"train_count_cap":cap},
             ROOT/("kernel_obs_"+target+".joblib"),compress=3)
 print("observation",target,"test mean",round(observed.mean(),4),
       "pred",round(mutest.mean(),4),flush=True)

# Empirical common recording multiplier. Conditional residual covariance
# can create dependence across sensor counts even after care-state features.
yy=np.column_stack([df.loc[va,t].to_numpy(float) for t in obs_targets])
mu=np.column_stack([val_preds[t] for t in obs_targets])
scaled=(yy-mu)/np.maximum(mu,.25)
scaled=np.clip(scaled,-8,8)
corr=np.corrcoef(scaled,rowvar=False)
off=np.array([corr[0,1],corr[0,2],corr[1,2]])
# Shared gamma overdispersion is a parsimonious positive-correlation
# approximation, not an exact identification of staff workflow.
gamma_var=float(np.clip(np.maximum(off.mean(),0),0,0.2))
gamma_shape=10000. if gamma_var<.0001 else float(1/gamma_var)
report["observation_correlation"]={
 "validation_standardized_residual_correlation":corr.tolist(),
 "shared_gamma_shape_for_simulation":gamma_shape,
 "not_an_exact_joint_count_fit":True}

# Physiological marks: measured 6h means condition on observed events.
# Unobserved physiology is NOT treated as observed/known.
phys_targets=["next_mean_hr","next_mean_map","next_rr","next_spo2"]
models={}
val_resids={}
for yname in phys_targets:
 y=df[yname].to_numpy(float)
 fit=tr&np.isfinite(y)
 vmask=va&np.isfinite(y)
 tmask=te&np.isfinite(y)
 mdl=Pipeline([("pre",prep(post)),("ridge",Ridge(alpha=35.))])
 mdl.fit(df.loc[fit,post],y[fit])
 pv=mdl.predict(df.loc[vmask,post])
 bias=float(np.mean(y[vmask]-pv))
 pt=mdl.predict(df.loc[tmask,post])+bias
 residual=y[tmask]-pt
 metric={"target":yname,"train_obs_rows":int(fit.sum()),
 "validation_obs_rows":int(vmask.sum()),
 "test_obs_rows":int(tmask.sum()),
 "test_observed_fraction_among_survivors":float(tmask.sum()/te.sum()),
 "conditional_test_rmse":float(np.sqrt(np.mean(residual**2))),
 "conditional_test_mae":float(np.mean(np.abs(residual))),
 "test_error_mean":float(np.mean(residual)),
 "calibration_bias_validation":bias}
 report["recorded_physiology"].append(metric)
 mdl_pack={"model":mdl,"features":post,"target":yname,"bias":bias}
 joblib.dump(mdl_pack,ROOT/("kernel_phys_"+yname+".joblib"),compress=3)
 # Align residual vector with whole val group; absent if no recorded output.
 fullres=np.full(int(va.sum()),np.nan)
 fullres[np.isfinite(y[va])]=y[vmask]-pv-bias
 val_resids[yname]=fullres
 print("phys",yname,"test RMSE",round(metric["conditional_test_rmse"],3),flush=True)
resmat=np.column_stack([val_resids[k] for k in phys_targets])
complete=np.isfinite(resmat).all(axis=1)
assert complete.sum()>10000
cov=np.cov(resmat[complete].T)
cov=.93*cov+.07*np.diag(np.diag(cov))
eig=np.linalg.eigvalsh(cov)
assert eig.min()>1.e-9
report["recorded_physiology_covariance"]={
 "order":phys_targets,"validation_complete_cases":int(complete.sum()),
 "shrunken_covariance":cov.tolist(),"eigenvalues":eig.tolist(),
 "gaussian_mark_model_approximation":True}
(ROOT/"kernel_observation_mark_fit_report.json").write_text(json.dumps(report,indent=2)+"\n")
print("Saved conditional measurement and correlated physiology-mark components",flush=True)
