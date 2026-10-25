#!/usr/bin/env python3
"""One-step predicted terminal events along ACTUAL patient histories.

This prequential diagnostic is NOT a counterfactual simulation.
It identifies local historical calibration separately from feedback
error produced by recursively sampling the stochastic model.
"""
from pathlib import Path
import json,joblib
import numpy as np,pandas as pd
from scipy.special import softmax
ROOT=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
df=pd.read_parquet(ROOT/"kernel_6h_transitions.parquet")
models={"linear":joblib.load(ROOT/"kernel_terminal.joblib"),
        "hgb":joblib.load(ROOT/"kernel_terminal_hgb_challenger.joblib")}
def calibrated(pkg,frame):
 m=pkg["model"]
 if pkg.get("model_type")=="hgb":
  X=frame[pkg["features"]].copy()
  for c,mp in pkg["category_maps"].items():
   X[c]=X[c].map(mp).fillna(-1).astype(np.int32)
  names=list(m.classes_)
  z=m.predict_proba(X)
 else:
  names=list(m.named_steps["clf"].classes_)
  z=m.predict_proba(frame[pkg["features"]])
 p=z[:,[names.index(k) for k in pkg["classes"]]]
 logits=np.log(np.maximum(p,1e-10))
 par=np.asarray(pkg["calibration"])
 logits=(logits-logits[:,[0]])*np.exp(par[0])
 logits[:,1:]+=par[1:]
 return softmax(logits,axis=1)
reports=[]
for era in ["2017 - 2019","2020 - 2022"]:
 q=df.loc[df.era==era].copy()
 n0=int(q.step.eq(4).sum())
 for model_name,pkg in models.items():
  p=calibrated(pkg,q)
  q2=q[["subject_id","step","terminal_outcome"]].copy()
  for i,kind in enumerate(pkg["classes"]):
   q2["p_"+kind]=p[:,i]
  for h in [4,8,12,20]:
   subset=q2[q2.step<4+h]
   r={"era":era,"model":model_name,"horizon_hours":h*6,
      "initial_n":n0,"actual_at_risk_patient_intervals":int(len(subset))}
   for state in ("EXIT","DEATH"):
    obs=float(subset.terminal_outcome.eq(state).sum()/n0)
    pred=float(subset["p_"+state].sum()/n0)
    r[state]={"observed_population_fraction":obs,
               "prequential_expected_fraction":pred,
               "relative_ratio":pred/obs if obs>0 else None}
   reports.append(r)
   print(era,model_name,h*6,
    'exit',(round(r['EXIT']['observed_population_fraction'],4),
            round(r['EXIT']['prequential_expected_fraction'],4)),
    'death',(round(r['DEATH']['observed_population_fraction'],4),
            round(r['DEATH']['prequential_expected_fraction'],4)),flush=True)
out={"meaning":"Expected event counts using true sequential histories, not simulator-generated states or causal policy", "results":reports}
(ROOT/"kernel_prequential_vs_rollout_report.json").write_text(json.dumps(out,indent=2)+"\n")
