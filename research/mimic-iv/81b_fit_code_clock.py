#!/usr/bin/env python3
"""Timestamped code-status reaffirmation clock in stochastic kernel.

A status that does not change can still be re-charted, resetting the
time-since-last-recorded-status feature. Fit this event explicitly
using survivor histories. The model is about documentation, NOT
clinical decision intent or patient wishes.
"""
from pathlib import Path
import json,joblib
import numpy as np,pandas as pd
from scipy.special import expit,logit
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss,brier_score_loss
ROOT=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
df=pd.read_parquet(ROOT/"kernel_6h_transitions.parquet")
df=df.loc[df.terminal_outcome.eq("STAY")&df.code_state.eq(df.next_code)].copy()
df["reaffirm"]=(df.next_code_age_h<df.code_age_h+5).astype(int)
tr=df.era.isin(["2008 - 2010","2011 - 2013","2014 - 2016"])
va=df.era.eq("2017 - 2019")
te=df.era.eq("2020 - 2022")
cols=["age","step","unit_group","sofa","hr","map","rr","spo2",
      "n_hr","n_map","n_spo2","n_rr","code_state","code_age_h","prior_invasive_h","prior_pressor_h"]
cats=["unit_group","code_state"];nums=[x for x in cols if x not in cats]
pre=ColumnTransformer([
 ("nums",Pipeline([("impute",SimpleImputer(strategy="median",add_indicator=True)),
  ("scale",StandardScaler())]),nums),
 ("cats",OneHotEncoder(handle_unknown="ignore"),cats)
])
mdl=Pipeline([("pre",pre),("clf",LogisticRegression(max_iter=130))])
mdl.fit(df.loc[tr,cols],df.loc[tr,"reaffirm"])
pval=mdl.predict_proba(df.loc[va,cols])[:,1]
shift=float(logit(np.clip(df.loc[va,"reaffirm"].mean(),1.e-5,1-1.e-5))-
 logit(np.clip(pval.mean(),1.e-5,1-1.e-5)))
shift=float(np.clip(shift,-1,1))
ptest=expit(logit(np.clip(mdl.predict_proba(df.loc[te,cols])[:,1],1e-7,1-1e-7))+shift)
true=df.loc[te,"reaffirm"].to_numpy()
observed_reset_ages=df.loc[tr&(df.reaffirm.eq(1)),"next_code_age_h"].clip(0,6).to_numpy(float)
changed=pd.read_parquet(ROOT/"kernel_6h_transitions.parquet")
changed=changed.loc[changed.era.isin(["2008 - 2010","2011 - 2013","2014 - 2016"])&
 changed.terminal_outcome.eq("STAY")&changed.code_state.ne(changed.next_code)]
changed_ages=changed.next_code_age_h.clip(0,6).to_numpy(float)
assert len(changed_ages)>1000
assert len(observed_reset_ages)>1000
report={"survivor_samecode_test_n":int(te.sum()),
"test_documentation_reaffirm_pct":float(100*true.mean()),
"predicted_reaffirm_pct":float(100*ptest.mean()),
"brier":float(brier_score_loss(true,ptest)),
"logloss":float(log_loss(true,ptest)),
"validation_log_odds_offset":shift,
"training_reaffirm_age_quantiles":np.quantile(observed_reset_ages,np.linspace(.005,.995,101)).tolist(),
"training_code_changed_age_quantiles":np.quantile(changed_ages,np.linspace(.005,.995,101)).tolist(),
"meaning":"documented status freshness, not new decision evidence"}
joblib.dump({"model":mdl,"features":cols,"offset":shift,
 "reset_age_quantiles":report["training_reaffirm_age_quantiles"],
 "changed_age_quantiles":report["training_code_changed_age_quantiles"]},
 ROOT/"kernel_code_clock.joblib",compress=3)
(ROOT/"kernel_code_clock_fit_report.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps({k:v for k,v in report.items() if not k.endswith("_quantiles")},indent=2))
