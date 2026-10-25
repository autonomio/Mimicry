#!/usr/bin/env python3
"""Dissect time-horizon bias under observed practice, NOT a causal simulator.
All rows remain on s0. Separates one-step transport errors on actual
histories from recursive state-distribution feedback in synthetic rollouts.
"""
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from scipy.special import softmax

ROOT=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
d=pd.read_parquet(ROOT/"kernel_history_6h.parquet")
p=joblib.load(ROOT/"kernel_terminal_hgb_history.joblib")
classes=list(p["classes"])
assert classes==["STAY","EXIT","DEATH"]
x=d[p["features"]].copy()
for k,m in p["category_maps"].items():
 x[k]=x[k].map(m).fillna(-1).astype(np.int32)
raw=p["model"].predict_proba(x)
idx=[list(p["model"].classes_).index(z) for z in classes]
raw=raw[:,idx]
theta=np.asarray(p["calibration"],float)
logp=np.log(np.maximum(raw,1e-10))
v=(logp-logp[:,[0]])*np.exp(theta[0])
v[:,1:]+=theta[1:]
pred=softmax(v,axis=1)
d["p_exit"]=pred[:,classes.index("EXIT")]
d["p_death"]=pred[:,classes.index("DEATH")]
d["y_exit"]=d.terminal_outcome.eq("EXIT").astype(np.int8)
d["y_death"]=d.terminal_outcome.eq("DEATH").astype(np.int8)
reports={"model":"HGB with finite history; prequential predictions on actual observed paths; exploratory; no causal interpretation",
         "horizons":[],"step_strata":[],"code_strata":[],"warnings":[
         "test era was already viewed during development; this is not an untouched confirmatory holdout",
         "rolling error decomposition compares distinct estimands: prequential on real histories versus synthetic trajectories",
         "terminal discharge/died event type depends on ICU charted timestamps and derived time shifts",
         "patient-level bootstrap conditional on fit and sampled initial patients"
         ]}
run=json.loads((ROOT/"kernel_rollout_hgb_history_full_test.json").read_text())
sim={int(q["hours_after_initial_landmark"]):q for q in run["results"]}
rng=np.random.default_rng(20261025)
for era in ["2017 - 2019","2020 - 2022"]:
 q=d[d.era==era].copy()
 N=int(q.step.eq(4).sum())
 assert N==q.subject_id.nunique()
 q["id"]=q.subject_id
 s=q.groupby("id").agg(first_step=("step","min"))
 assert s.first_step.eq(4).all()
 for h in [4,8,12,20]:
  sub=q[q.step<4+h]
  per=sub.groupby("id").agg(obs_exit=("y_exit","sum"),obs_death=("y_death","sum"),
                              pre_exit=("p_exit","sum"),pre_death=("p_death","sum"))
  assert len(per)==N
  obs=per[["obs_exit","obs_death"]].mean()
  ex=per[["pre_exit","pre_death"]].mean()
  boot={}
  for event in ["exit","death"]:
   delta=(per["pre_"+event]-per["obs_"+event]).to_numpy(float)
   draws=np.empty(400,float)
   for j in range(len(draws)):
    k=rng.integers(0,len(delta),len(delta))
    draws[j]=delta[k].mean()
   boot[event]=np.quantile(draws,[.025,.975]).tolist()
  row={"era":era,"hours":h*6,"n_initial":N,"n_actual_atrisk_intervals":int(len(sub)),
    "exit":{"observed":float(obs.obs_exit),"prequential":float(ex.pre_exit),
            "local_error":float(ex.pre_exit-obs.obs_exit),"bootstrap_ci95":boot["exit"]},
    "death":{"observed":float(obs.obs_death),"prequential":float(ex.pre_death),
            "local_error":float(ex.pre_death-obs.obs_death),"bootstrap_ci95":boot["death"]}}
  if era=="2020 - 2022":
   for ev in ["exit","death"]:
    simulated=float(sim[h*6]["metrics"][ev]["simulated"])
    row[ev].update({"simulated":simulated,
                    "full_error":simulated-row[ev]["observed"],
                    "recursive_feedback_component":simulated-row[ev]["prequential"]})
  reports["horizons"].append(row)
 # Model-conditional hazard changes by ICU elapsed time
 q["icu_time_group"]=pd.cut(q.step,bins=[3,5,7,11,19,27],labels=["24-36h","36-48h","48-72h","72-120h","120-168h"])
 for g,t in q.groupby("icu_time_group",observed=True):
  reports["step_strata"].append({"era":era,"stratum":str(g),"n":int(len(t)),
    "observed_exit":float(t.y_exit.mean()),"pred_exit":float(t.p_exit.mean()),
    "observed_death":float(t.y_death.mean()),"pred_death":float(t.p_death.mean())})
 for g,t in q.groupby("code_state"):
  if len(t)<100: continue
  reports["code_strata"].append({"era":era,"stratum":str(g),"n":int(len(t)),
    "observed_exit":float(t.y_exit.mean()),"pred_exit":float(t.p_exit.mean()),
    "observed_death":float(t.y_death.mean()),"pred_death":float(t.p_death.mean())})
pout=ROOT/"kernel_hgb_history_error_decomposition.json"
pout.write_text(json.dumps(reports,indent=2)+"\n")
for r in reports["horizons"]:
 print(r["era"],r["hours"],"observed exit",round(r["exit"]["observed"],4),"prequential",round(r["exit"]["prequential"],4),"sim",round(r["exit"].get("simulated",-1),4),
 "death",round(r["death"]["observed"],4),"pre",round(r["death"]["prequential"],4),"sim",round(r["death"].get("simulated",-1),4),flush=True)
print("SAVED",pout)
