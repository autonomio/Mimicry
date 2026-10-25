#!/usr/bin/env python3
"""Fit observational six-hour stochastic-kernel components on MIMIC-IV v3.1.

All patient-level inputs, predictions and model objects stay on s0.
This is a JOINT conditional probability factorization on the recorded
states, not a causal/genuine latent-biological transition mechanism.
2017-2019 validation calibrates models; 2020-2022 is held out.
"""
import json, warnings
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from scipy.optimize import minimize, minimize_scalar
from scipy.special import softmax, logsumexp
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
warnings.filterwarnings("ignore",category=FutureWarning)
ROOT=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
df=pd.read_parquet(ROOT/"kernel_6h_transitions.parquet")
assert df.subject_id.nunique()==df.stay_id.nunique()
assert not df.duplicated(["stay_id","step"]).any()
assert df.step.between(4,26).all()
era=df.era
tr=era.isin(["2008 - 2010","2011 - 2013","2014 - 2016"]).to_numpy()
va=era.eq("2017 - 2019").to_numpy()
te=era.eq("2020 - 2022").to_numpy()
assert tr.sum()+va.sum()+te.sum()==len(df)
assert not set(df.loc[tr,"subject_id"])&set(df.loc[te,"subject_id"])
BASE=["age","step","unit_group","sofa","hr","map","rr","spo2"]
OBS=["n_hr","n_map","n_spo2","n_rr"]
CARE=["code_state","code_age_h","prior_invasive_h","prior_pressor_h"]
FULL=BASE+OBS+CARE
TARGET_CLASSES=["STAY","EXIT","DEATH"]
def transformer(cols):
 cats=[x for x in cols if x in ("unit_group","code_state","next_code","support_state")]
 nums=[x for x in cols if x not in cats]
 return ColumnTransformer([
  ("num",Pipeline([("fill",SimpleImputer(strategy="median",add_indicator=True)),
   ("scale",StandardScaler())]),nums),
  ("cat",OneHotEncoder(handle_unknown="ignore"),cats)
 ])
def fit_logit(train_frame,cols,y):
 pipe=Pipeline([("prep",transformer(cols)),
                ("clf",LogisticRegression(max_iter=140,solver="lbfgs"))])
 pipe.fit(train_frame[cols],y)
 return pipe
def ordp(model,frame,cols,classes):
 p=model.predict_proba(frame[cols])
 m={x:i for i,x in enumerate(model.named_steps["clf"].classes_)}
 assert set(classes)<=set(m)
 return p[:,[m[k] for k in classes]]
def intercept_scale_fit(raw,y,classes,ref_idx=0,penalty=1.e-4):
 # Multinomial probability recalibration, scalar slope + K-1 intercepts
 yy=np.searchsorted(np.array(classes),y)
 # classes may not be sorted; use explicit mapping.
 yy=np.array([{c:i for i,c in enumerate(classes)}[v] for v in y],dtype=int)
 ncl=len(classes)
 logit=np.log(np.maximum(raw,1.e-10))
 nonref=[i for i in range(ncl) if i!=ref_idx]
 def predict(par,p0):
  z=np.log(np.maximum(p0,1.e-10))
  logits=(z-z[:,ref_idx:ref_idx+1])*np.exp(par[0])
  logits[:,nonref]+=par[1:]
  return softmax(logits,axis=1)
 def objective(par):
  p=predict(par,raw)
  return float(-np.log(np.maximum(p[np.arange(len(yy)),yy],1.e-12)).mean()+
   penalty*np.square(par[1:]).sum())
 r=minimize(objective,np.zeros(ncl),method="L-BFGS-B",
   bounds=[(-1.2,1.2)]+[(-3.,3.)]*(ncl-1),
   options={"maxiter":140,"gtol":1.e-8})
 assert r.success or r.fun<objective(np.zeros(ncl))
 return r.x, lambda p:predict(r.x,p)
def scores(y,p,classes):
 true=np.array([{c:i for i,c in enumerate(classes)}[v] for v in y],dtype=int)
 scores=-np.log(np.maximum(p[np.arange(len(true)),true],1.e-12))
 oh=np.eye(len(classes))[true]
 brier=float(np.mean(np.sum(np.square(p-oh),axis=1)))
 return float(scores.mean()),brier,scores
def patient_bootstrap(diff,patient,seed=20261025,reps=450):
 tmp=pd.DataFrame({"subject":patient,"score":diff}).groupby("subject",sort=False).agg(n=("score","size"),s=("score","sum"))
 totals=tmp[["n","s"]].to_numpy(float)
 rng=np.random.default_rng(seed)
 samples=rng.integers(0,len(totals),size=(reps,len(totals)))
 draws=totals[samples]
 vals=draws[:,:,1].sum(axis=1)/draws[:,:,0].sum(axis=1)
 return np.quantile(vals,[.025,.975]).tolist()

result={"model_type":"Observational six-hour sequential stochastic transition kernel",
 "factorization":"terminal(s)->code_next(s,stay)->joint_support(s,next_code,stay)->measurements(s,next_code,support,stay)->recorded physiology",
 "n":int(len(df)),"n_patients":int(df.subject_id.nunique()),
 "historical_split":{"train":int(tr.sum()),"validation":int(va.sum()),"test":int(te.sum())},
 "components":{}}
artifacts={"base_features":BASE,"full_features":FULL,
 "classes_terminal":TARGET_CLASSES}
# Terminal death or exit are absorbing. Code transitions within a six-hour
# window before terminal death are collisions, not absorbed here.
term={}
for kind,cols in {"physiology":BASE,"full":FULL}.items():
 model=fit_logit(df.loc[tr],cols,df.loc[tr,"terminal_outcome"])
 pv=ordp(model,df.loc[va],cols,TARGET_CLASSES)
 pt=ordp(model,df.loc[te],cols,TARGET_CLASSES)
 pars,apply=intercept_scale_fit(pv,df.loc[va,"terminal_outcome"].to_numpy(),TARGET_CLASSES)
 pc=apply(pt)
 logloss,brier,lossrow=scores(df.loc[te,"terminal_outcome"].to_numpy(),pc,TARGET_CLASSES)
 pred={k:float(pc[:,i].mean()) for i,k in enumerate(TARGET_CLASSES)}
 actual={k:float(df.loc[te,"terminal_outcome"].eq(k).mean()) for k in TARGET_CLASSES}
 ratios={k:float(pred[k]/actual[k]) if actual[k]>0 else None for k in TARGET_CLASSES}
 result["components"]["terminal_"+kind]={"test_logloss":logloss,
  "test_multiclass_brier":brier,"validation_calibration_parameters":pars.tolist(),
  "test_observed":actual,"test_predicted":pred,"predicted_to_observed":ratios,
  "fatal_event_calibration_gate_pass":(0.8<=ratios["DEATH"]<=1.25),
  "exit_calibration_gate_pass":(0.9<=ratios["EXIT"]<=1.1)}
 term[kind]={"model":model,"features":cols,"calibration":pars,
             "apply":apply,"test":pc,"loss":lossrow}
 print("terminal",kind,"test logloss",round(logloss,5),
       "death ratio",round(ratios["DEATH"],3),
       "exit ratio",round(ratios["EXIT"],3),flush=True)
joblib.dump({"model":term["full"]["model"],"features":FULL,
             "classes":TARGET_CLASSES,"calibration":term["full"]["calibration"]},
            ROOT/"kernel_terminal.joblib",compress=3)
result["terminal_logloss_improvement"]={
 "phys_minus_full":float(term["physiology"]["loss"].mean()-term["full"]["loss"].mean()),
 "cluster_bootstrap_95ci":patient_bootstrap(term["physiology"]["loss"]-term["full"]["loss"],
                                          df.loc[te,"subject_id"].to_numpy())}

# The care state is a documented label, not an intervention; only
# survivor transitions have a next-grid destination code.
alive=df.terminal_outcome.eq("STAY").to_numpy()
atr=tr&alive;ava=va&alive;ate=te&alive
assert df.loc[alive,"next_code"].notna().all()
CODE_CLASSES=sorted(df.loc[atr,"next_code"].unique().tolist())
code_model=fit_logit(df.loc[atr],FULL,df.loc[atr,"next_code"])
pv=ordp(code_model,df.loc[ava],FULL,CODE_CLASSES)
pt=ordp(code_model,df.loc[ate],FULL,CODE_CLASSES)
codepars,codeapply=intercept_scale_fit(pv,df.loc[ava,"next_code"].to_numpy(),CODE_CLASSES,penalty=.0005)
pcode=codeapply(pt)
loss,brier,_=scores(df.loc[ate,"next_code"].to_numpy(),pcode,CODE_CLASSES)
result["components"]["documented_code_destination"]={
 "classes":CODE_CLASSES,"survivor_test_rows":int(ate.sum()),
 "conditional_test_logloss":loss,"conditional_test_brier":brier,
 "test_observed":{c:float(df.loc[ate,"next_code"].eq(c).mean()) for c in CODE_CLASSES},
 "test_predicted":{c:float(pcode[:,i].mean()) for i,c in enumerate(CODE_CLASSES)},
 "test_transition_rate_observed":float(df.loc[ate].code_state.ne(df.loc[ate].next_code).mean()),
 "test_transition_rate_predicted":float((pcode*(df.loc[ate,"code_state"].to_numpy()[:,None]!=np.array(CODE_CLASSES)[None,:])).sum(axis=1).mean()),
 "validation_calibration_parameters":codepars.tolist()}
joblib.dump({"model":code_model,"features":FULL,"classes":CODE_CLASSES,"calibration":codepars},
            ROOT/"kernel_code.joblib",compress=3)
print("code conditional destination heldout",round(loss,6),flush=True)

def state_band(h):
 arr=np.asarray(h,float)
 return np.where(arr<.1,0,np.where(arr>=5.9,2,1))
def support_state(frame):
 return (state_band(frame.next_invasive_h)*3+state_band(frame.next_pressor_h)).astype(int)
df["support_state"]=support_state(df).astype(str)
# Unlike an invalid 'oracle' forecast, the test forecast of support
# integrates over predicted NEXT code state, never conditions on it.
SUP_CLASSES=sorted(df.loc[atr,"support_state"].unique().tolist(),key=int)
EXTRA=FULL+["next_code","code_changed"]
df["code_changed"]=(df.code_state!=df.next_code).astype(float)
support_model=fit_logit(df.loc[atr],EXTRA,df.loc[atr,"support_state"])
raw_s=ordp(support_model,df.loc[ava],EXTRA,SUP_CLASSES)
supportpars,supportapply=intercept_scale_fit(raw_s,df.loc[ava,"support_state"].to_numpy(),SUP_CLASSES,penalty=.001)
# honest integrated support p(k|s) = sum_c p(c|s)*p(k|s,c)
def marginal_support(frame,pc):
 resultp=np.zeros((len(frame),len(SUP_CLASSES)))
 for j,code in enumerate(CODE_CLASSES):
  q=frame[EXTRA].copy()
  q["next_code"]=code
  q["code_changed"]=frame.code_state.ne(code).astype(float).to_numpy()
  resultp+=pc[:,j:j+1]*supportapply(ordp(support_model,q,EXTRA,SUP_CLASSES))
 return resultp
ps=marginal_support(df.loc[ate],pcode)
supp_ll,supp_brier,_=scores(df.loc[ate,"support_state"].to_numpy(),ps,SUP_CLASSES)
supp_true=df.loc[ate,"support_state"]
p1=np.array([int(k)//3 for k in SUP_CLASSES])
p2=np.array([int(k)%3 for k in SUP_CLASSES])
result["components"]["joint_support_next"]={
 "classes":SUP_CLASSES,"test_honest_marginal_logloss":supp_ll,
 "test_honest_marginal_brier":supp_brier,
 "test_actual_invasive_exposure":float(np.mean(state_band(df.loc[ate,"next_invasive_h"])>0)),
 "test_predicted_invasive_exposure":float(np.mean(ps[:,p1>0].sum(axis=1))),
 "test_actual_pressor_exposure":float(np.mean(state_band(df.loc[ate,"next_pressor_h"])>0)),
 "test_predicted_pressor_exposure":float(np.mean(ps[:,p2>0].sum(axis=1)))}
print("honest joint support next logloss",round(supp_ll,5),flush=True)
# Positive PARTIAL durations are fit from training only. Simulated full
# exposure status is always 6h (grid approximation).
durations={}
for name in ("next_invasive_h","next_pressor_h"):
 z=df.loc[atr,name].to_numpy(float)
 v=z[(z>=.1)&(z<5.9)]
 assert len(v)>100
 durations[name]=np.quantile(v,np.linspace(.005,.995,101)).tolist()
joblib.dump({"model":support_model,"features":EXTRA,"classes":SUP_CLASSES,
             "calibration":supportpars,"partial_durations":durations},
            ROOT/"kernel_support.joblib",compress=3)
(ROOT/"kernel_transition_fit_report.json").write_text(json.dumps(result,indent=2)+"\n")
print("saved terminal, code and joint-support conditional models",flush=True)
