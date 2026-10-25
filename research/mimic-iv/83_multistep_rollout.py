#!/usr/bin/env python3
"""Generate and validate longitudinal paths under learned OBSERVED ICU practice.

Mathematically normalized observational transition kernel:
  P(terminal|history)
  * P(next documented code|history,stay)
  * P(code-reaffirm timing|history,next code,stay)
  * P(joint organ-support regime|history,next code,stay)
  * P(observation-count vector|history,next code,support,stay)
  * P(recorded physiology marks|history,next code,support,counts,stay).

Clinical preferences, latent physiology and intervening 6h event order
are NOT identified. Forecast does not simulate a causal DNR policy.
All patient-level rows stay on s0. Synthetic path states are restricted.
"""
import argparse,json,time,warnings
from pathlib import Path
import joblib,numpy as np,pandas as pd
from scipy.special import softmax,expit,logit
warnings.filterwarnings("ignore",category=FutureWarning)
ROOT=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
p=argparse.ArgumentParser()
p.add_argument("--n-subjects",type=int,default=1600)
p.add_argument("--reps",type=int,default=8)
p.add_argument("--seed",type=int,default=20261025)
p.add_argument("--terminal-model",choices=["linear","hgb","hgb-history"],default="linear")
p.add_argument("--era",default="2020 - 2022",choices=["2017 - 2019","2020 - 2022"])
p.add_argument("--shared-prognosis-sigma",type=float,default=0.0,
 help="Persistent latent prognosis sensitivity; NOT causal or measured frailty")
p.add_argument("--out",default="kernel_rollout_report.json")
args=p.parse_args()
tic=time.monotonic()
terminal_file={"linear":"kernel_terminal.joblib",
"hgb":"kernel_terminal_hgb_challenger.joblib",
"hgb-history":"kernel_terminal_hgb_history.joblib"}[args.terminal_model]
terminal=joblib.load(ROOT/terminal_file)
code=joblib.load(ROOT/"kernel_code.joblib")
clock=joblib.load(ROOT/"kernel_code_clock.joblib")
support=joblib.load(ROOT/"kernel_support.joblib")
obs={name:joblib.load(ROOT/("kernel_obs_"+name+".joblib")) for name in
 ["next_n_hr","next_n_map","next_n_spo2","next_n_rr"]}
phys={name:joblib.load(ROOT/("kernel_phys_"+name+".joblib")) for name in
 ["next_mean_hr","next_mean_map","next_rr","next_spo2"]}
mark=json.loads((ROOT/"kernel_observation_mark_fit_report.json").read_text())
cov=np.asarray(mark["recorded_physiology_covariance"]["shrunken_covariance"],float)
k_gamma=float(mark["observation_correlation"]["shared_gamma_shape_for_simulation"])
rng_select=np.random.default_rng(args.seed)
data=pd.read_parquet(ROOT/"kernel_6h_transitions.parquet")
initial=data.loc[(data.era==args.era)&(data.step==4)].copy()
assert initial.subject_id.is_unique
N=min(args.n_subjects,len(initial))
initial=initial.sample(n=N,random_state=args.seed).sort_values("stay_id").reset_index(drop=True)
ids=initial.subject_id.to_numpy()
raw=data.loc[data.subject_id.isin(ids)].copy()
horizons=[4,8,12,20]  # 24,48,72,120 additional hours after ICU hour24
codes=list(code["classes"])
state_cols=["age","step","unit_group","sofa","hr","map","rr","spo2",
 "n_hr","n_map","n_spo2","n_rr","code_state","code_age_h",
 "prior_invasive_h","prior_pressor_h"]
history_cols=list(terminal.get("history_features",[]))
# Initial hour24 has no earlier grid landmarks; history is genuinely
# unavailable, not imputed from future windows.
for col in history_cols:
 initial[col]=np.nan
state_cols=state_cols+history_cols
def predict_calibrated(pkg,frame):
 cls=list(pkg["classes"])
 m=pkg["model"]
 if pkg.get("model_type")=="hgb":
  X=frame[pkg["features"]].copy()
  for c,mapping in pkg["category_maps"].items():
   X[c]=X[c].map(mapping).fillna(-1).astype(np.int32)
  names=list(m.classes_)
  out=m.predict_proba(X)[:,[names.index(v) for v in cls]]
 else:
  names=list(m.named_steps["clf"].classes_)
  out=m.predict_proba(frame[pkg["features"]])[:,[names.index(v) for v in cls]]
 par=np.asarray(pkg["calibration"],float)
 logp=np.log(np.maximum(out,1.e-10))
 z=(logp-logp[:,[0]])*np.exp(par[0])
 z[:,1:]+=par[1:]
 return softmax(z,axis=1)
def sample_cat(prob,rng):
 return np.minimum((rng.random(len(prob))[:,None]>np.cumsum(prob,axis=1)).sum(axis=1),prob.shape[1]-1)
def age_draw(quantiles,rng,n):
 arr=np.asarray(quantiles,float)
 return arr[rng.integers(0,len(arr),size=n)]
def select_hours(band,quantiles,rng):
 b=np.asarray(band,int)
 result=np.zeros(len(b),float)
 result[b==2]=6.
 k=int((b==1).sum())
 if k:
  result[b==1]=age_draw(quantiles,rng,k)
 return result
def genuine_observed(subject_frame,h):
 until=4+h
 pre=raw[raw.step<until]
 outcome=(pre.loc[pre.terminal_outcome!="STAY",["subject_id","step","terminal_outcome"]]
 .sort_values("step").drop_duplicates("subject_id"))
 truths=pd.DataFrame({"subject_id":ids}).merge(outcome,on="subject_id",how="left")
 state=np.where(truths.terminal_outcome.eq("DEATH"),"DEATH",
       np.where(truths.terminal_outcome.eq("EXIT"),"EXIT","ICU"))
 s=raw.loc[raw.step==until,
 ["subject_id","code_state","prior_invasive_h","prior_pressor_h",
 "n_hr","n_map","n_spo2","n_rr","hr","map","rr","spo2"]]
 truths=truths.merge(s,on="subject_id",how="left")
 assert not np.any((state=="ICU") & truths.code_state.isna()),"Missing observed next landmark"
 return state,truths
def summary(state,frame):
 # Probabilities are over the whole initial cohort; dead/exit absorbing.
 v={"icu":float(np.mean(state=="ICU")),"exit":float(np.mean(state=="EXIT")),
    "death":float(np.mean(state=="DEATH"))}
 alive=(state=="ICU")
 for c in codes:
  v["icu_"+c]=float(np.mean(alive & (frame["code_state"].to_numpy()==c)))
 v["icu_invasive_exposure"]=float(np.mean(alive & (frame["prior_invasive_h"].to_numpy(dtype=float)>.1)))
 v["icu_pressor_exposure"]=float(np.mean(alive & (frame["prior_pressor_h"].to_numpy(dtype=float)>.1)))
 if alive.any():
  for x in ("n_hr","n_map","n_spo2","n_rr"):
   v["record_rate_"+x]=float(np.nanmean(frame.loc[alive,x].to_numpy(float))/6.)
  for x in ("hr","map","rr","spo2"):
   v["observed_mean_"+x]=float(np.nanmean(frame.loc[alive,x].to_numpy(float)))
 return v
truths={}
for h in horizons:
 status,df=genuine_observed(initial,h)
 observed_frame=pd.DataFrame(index=range(N),columns=state_cols)
 for col in ("code_state","prior_invasive_h","prior_pressor_h","n_hr","n_map","n_spo2","n_rr","hr","map","rr","spo2"):
  observed_frame[col]=df[col].to_numpy()
 truths[h]=summary(status,observed_frame)

all_runs={h:[] for h in horizons}
clip_total=0
clip_count=0
for rep in range(args.reps):
 rng=np.random.default_rng(args.seed+1001+rep)
 status=np.full(N,"ICU",dtype=object)
 # Persistent shared unmeasured prognosis shock: worse latent prognosis
 # can raise death odds while reducing discharge odds. Distributional
 # assumption, calibrated only on historical validation when used.
 latent_prognosis=rng.standard_normal(N)
 current=initial[state_cols].copy()
 current.index=np.arange(N)
 initial_code=current.code_state.to_numpy(copy=True)
 for dt in range(1,max(horizons)+1):
  who=np.flatnonzero(status=="ICU")
  if len(who):
   cur=current.loc[who,state_cols].copy()
   # Step 1: absorbing competing exits.
   termprob=predict_calibrated(terminal,cur)
   sig=float(args.shared_prognosis_sigma)
   if sig>0:
    logits=np.log(np.maximum(termprob,1.e-12))
    classes_term=list(terminal["classes"])
    # Shared patient-specific random effect held constant across steps.
    logits[:,classes_term.index("EXIT")]+=-sig*latent_prognosis[who]-sig*sig/2.
    logits[:,classes_term.index("DEATH")]+=sig*latent_prognosis[who]-sig*sig/2.
    termprob=softmax(logits,axis=1)
   termdraw=sample_cat(termprob,rng)
   next_term=np.asarray(terminal["classes"],object)[termdraw]
   status[who[next_term=="DEATH"]]="DEATH"
   status[who[next_term=="EXIT"]]="EXIT"
   keep=next_term=="STAY"
   ids_keep=who[keep]
   if len(ids_keep):
    x=cur.loc[ids_keep,state_cols].copy()
    # Step 2: destination documented code status.
    cp=predict_calibrated(code,x)
    cd=sample_cat(cp,rng)
    nextcode=np.asarray(code["classes"],object)[cd]
    codechanged=x.code_state.to_numpy()!=nextcode
    # Step 3: same-status repeated documentation clock.
    age=x.code_age_h.to_numpy(float)+6.
    if codechanged.any():
     age[codechanged]=age_draw(clock["changed_age_quantiles"],rng,int(codechanged.sum()))
    if (~codechanged).any():
     mask=np.flatnonzero(~codechanged)
     xx=x.iloc[mask][clock["features"]]
     rawp=clock["model"].predict_proba(xx)[:,1]
     prob=expit(logit(np.clip(rawp,1e-8,1-1e-8))+clock["offset"])
     repeat=(rng.random(len(mask))<prob)
     resetids=mask[repeat]
     if len(resetids):
      age[resetids]=age_draw(clock["reset_age_quantiles"],rng,len(resetids))
    # Step 4: joint organ support, conditional on sampled next code.
    z=x.copy()
    z["next_code"]=nextcode
    z["code_changed"]=codechanged.astype(float)
    sp=predict_calibrated(support,z)
    sd=sample_cat(sp,rng)
    support_state=np.asarray(support["classes"],object)[sd]
    support_index=np.asarray([int(k) for k in support_state],int)
    invasive=select_hours(support_index//3,
       support["partial_durations"]["next_invasive_h"],rng)
    pressor=select_hours(support_index%3,
       support["partial_durations"]["next_pressor_h"],rng)
    z["support_state"]=support_state
    # Step 5: observation intensities, with common gamma count noise.
    shared=rng.gamma(shape=k_gamma,scale=1./k_gamma,size=len(z))
    count_pred={}
    for name,pkg in obs.items():
     xx=z[pkg["features"]]
     present_prob=pkg["presence"].predict_proba(xx)[:,1]
     rawlam=pkg["positive_excess"].predict(xx)
     lim=float(pkg["train_count_cap"])
     lam=np.clip((1+np.clip(np.nan_to_num(rawlam,nan=0.,posinf=lim),
                          0.,max(0.,lim-1.)))*
                          float(pkg["mean_multiplier"])-1.,0.,max(0.,lim-1.))
     sampled=1+rng.poisson(lam*shared)
     sampled[rng.random(len(z))>=present_prob]=0
     clip_count+=int(np.sum(sampled>120))
     clip_total+=len(sampled)
     count_pred[name]=np.minimum(sampled,120)
     z[name]=count_pred[name]
    z["next_invasive_h"]=invasive
    z["next_pressor_h"]=pressor
    # Step 6: jointly correlated Gaussian marks conditional on observed
    # recording counts. Missing observations remain missing, not latent truth.
    innovations=rng.multivariate_normal(np.zeros(4),cov,size=len(z))
    names=["next_mean_hr","next_mean_map","next_rr","next_spo2"]
    limits=[(20,240),(20,180),(1,80),(50,100)]
    phys_count_names=["next_n_hr","next_n_map","next_n_rr","next_n_spo2"]
    generated={}
    for j,name in enumerate(names):
     pkg=phys[name]
     val=np.clip(pkg["model"].predict(z[pkg["features"]])+
         float(pkg["bias"])+innovations[:,j],*limits[j])
     val[count_pred[phys_count_names[j]]==0]=np.nan
     generated[name]=val
    # Shift the finite-order state memory BEFORE replacing current state.
    # This matches the SQL lag definition exactly when following real data.
    if history_cols:
     hist_map={
      "lag3_invasive":"lag2_invasive","lag3_pressor":"lag2_pressor",
      "lag2_hr":"lag1_hr","lag2_map":"lag1_map",
      "lag2_invasive":"lag1_invasive","lag2_pressor":"lag1_pressor",
      "lag1_hr":"hr","lag1_map":"map","lag1_rr":"rr","lag1_spo2":"spo2",
      "lag1_n_hr":"n_hr","lag1_n_map":"n_map",
      "lag1_invasive":"prior_invasive_h","lag1_pressor":"prior_pressor_h"}
     for k,prev in hist_map.items():
      current.loc[ids_keep,k]=x[prev].to_numpy()
    # Only survivors receive next state; state remains measurable/documented.
    current.loc[ids_keep,"step"]=x.step.to_numpy(int)+1
    current.loc[ids_keep,"code_state"]=nextcode
    current.loc[ids_keep,"code_age_h"]=age
    current.loc[ids_keep,"prior_invasive_h"]=invasive
    current.loc[ids_keep,"prior_pressor_h"]=pressor
    for nm,old in [("next_n_hr","n_hr"),("next_n_map","n_map"),
                   ("next_n_rr","n_rr"),("next_n_spo2","n_spo2")]:
     current.loc[ids_keep,old]=count_pred[nm]
    for nm,old in [("next_mean_hr","hr"),("next_mean_map","map"),
                   ("next_rr","rr"),("next_spo2","spo2")]:
     current.loc[ids_keep,old]=generated[nm]
  if dt in horizons:
   all_runs[dt].append(summary(status,current))
 print("rep",rep+1,"of",args.reps,"complete; secs",round(time.monotonic()-tic,1),flush=True)
scores=[]
for h in horizons:
 truth=truths[h]
 df=pd.DataFrame(all_runs[h])
 predicted=df.mean().to_dict()
 uncertainty={k:np.quantile(df[k],[.05,.95]).tolist() for k in df.columns}
 metrics={}
 for key in ("death","exit","icu","icu_FULL","icu_UNKNOWN","icu_DNR_ONLY",
             "icu_DNR_DNI","icu_invasive_exposure","icu_pressor_exposure"):
  obsval=float(truth[key])
  predval=float(predicted[key])
  metrics[key]={"observed":obsval,"simulated":predval,
     "relative_ratio":float(predval/obsval) if obsval>1e-8 else None,
     "absolute_error":abs(predval-obsval),
     "replicate_5to95pct":uncertainty[key]}
 gates={
  "death_ratio_0p8_to1p25":.8<=metrics["death"]["relative_ratio"]<=1.25 if metrics["death"]["relative_ratio"] is not None else False,
  "exit_ratio_0p9_to1p1":.9<=metrics["exit"]["relative_ratio"]<=1.1 if metrics["exit"]["relative_ratio"] is not None else False,
  "icu_occupancy_abs_error_lt0p05":metrics["icu"]["absolute_error"]<.05,
  "coded_state_mass_abs_errors_lt0p05":all(metrics[x]["absolute_error"]<.05 for x in
     ("icu_FULL","icu_UNKNOWN","icu_DNR_ONLY","icu_DNR_DNI")),
 }
 scores.append({"hours_after_initial_landmark":h*6,
 "initial_icu_hour":24,"target_icu_hour":24+6*h,
 "gates":gates,"all_primary_gates_pass":all(gates.values()),
 "metrics":metrics,
 "measurement_rates_and_marks":{
  v:{"observed":float(truth[v]),"simulated":float(predicted[v]),
     "abs_difference":abs(float(truth[v])-float(predicted[v]))}
  for v in truth if v.startswith("record_rate_") or v.startswith("observed_mean_")}})
report={"type":"Observational stochastic multistate rollout, not a causal intervention",
 "initial_group":args.era+" ICU patients alive/in-ICU at hour24",
 "terminal_hazard_model":args.terminal_model,
 "shared_prognosis_sigma":float(args.shared_prognosis_sigma),
 "selected_distinct_patients":N,"replicates":args.reps,
 "seed":args.seed,"max_horizon_hours_after_hour24":max(horizons)*6,
 "observation_gamma_shared_shape":k_gamma,
 "drawn_observation_count_above120_before_clip":clip_count,
 "drawn_observation_count_total":clip_total,
 "elapsed_seconds":round(time.monotonic()-tic,1),
 "results":scores,
 "limitations":[
 "simulated absorbing terminal at end of 6h bin; no exact intra-bin event order",
 "recorded documented code status is not latent goals-of-care state",
 "no causal identification of counterfactual treatment policies",
 "simulation learned under one hospital and transported to later era",
 "continuously latent true physiology unobserved; marks are recorded measurements",
 "patient preference, clinician prognostic information and future resource constraints unavailable",
 "Monte Carlo intervals measure simulation randomness only, not patient sampling or estimation uncertainty"]}
(ROOT/args.out).write_text(json.dumps(report,indent=2)+"\n")
for x in scores:
 print("H",x["hours_after_initial_landmark"],"hours",
       "all gates",x["all_primary_gates_pass"],
       "death",round(x["metrics"]["death"]["observed"],4),round(x["metrics"]["death"]["simulated"],4),
       "exit",round(x["metrics"]["exit"]["observed"],4),round(x["metrics"]["exit"]["simulated"],4),flush=True)
print("saved",args.out,flush=True)
