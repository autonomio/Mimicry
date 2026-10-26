#!/usr/bin/env python3
"""Prophecy 2 / DNR-first fork: descriptive risk-set study on MIMIC-IV v3.1.

Scientific question: when a new *DNR-only* order is documented, does
recorded non-CPR life support change beyond the pre-order trajectory,
compared with documented-full-code eligible risk sets? DNR/DNI is an
explicitly separate exposure subtype, not pooled into a DNR "treatment."

DO NOT interpret any contrast as a DNR causal effect. Physician intent,
unrecorded orders, neuroprognosis, competing exits, anticipation, and
selective clinical recording remain unmeasured. Fixed-weight CIs omit
selection, weighting-estimation and specification uncertainty.

No patient rows are written or transferred. All output is aggregate JSON
under /srv/mimic-iv/studies/prophecy2_dnr_20261025.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

SEED = 20261025
ROOT = Path("/srv/mimic-iv/studies/decision_feedback_20261025")
DEST = Path("/srv/mimic-iv/studies/prophecy2_dnr_20261025")
DEST.mkdir(mode=0o700, parents=True, exist_ok=True)

rng = np.random.default_rng(SEED)
treated = pd.read_parquet(ROOT / "risk_treated.parquet")
assert treated.stay_id.is_unique
subtype = treated[["stay_id", "first_nonfull_state"]].rename(
    columns={"stay_id": "treated_id", "first_nonfull_state": "subtype"})
valid_subtypes = {"DNR_ONLY", "DNR_DNI"}
assert set(subtype.subtype) == valid_subtypes

cohort = pd.read_parquet(ROOT / "risk_weighted_severityhistory.parquet")
cohort = cohort.merge(subtype, on="treated_id", validate="many_to_one")
assert not cohort.anchor_id.duplicated().any()
assert (cohort.arm == "DNR").sum() == 2014
assert cohort.loc[cohort.arm == "DNR", "treated_id"].is_unique
assert cohort.loc[cohort.arm == "DNR", "weight"].eq(1).all()
assert cohort.groupby(["treated_id", "arm"]).weight.sum().sub(1).abs().max() < 1e-6

support = pd.read_parquet(ROOT / "risk_support_bins.parquet")
monitor = pd.read_parquet(ROOT / "risk_event_bins.parquet")
procedure = pd.read_parquet(ROOT / "risk_support_procedures.parquet")
assert support.groupby("anchor_id").size().eq(9).all()
assert monitor.groupby("anchor_id").size().eq(9).all()
assert len(procedure) == len(cohort)
assert support[["anchor_id","bin"]].duplicated().sum() == 0
assert monitor[["anchor_id","bin"]].duplicated().sum() == 0

# This is a post-hoc exploratory calibration; not a prespecified
# causal effect identification strategy. Controls are NOT removed
# based on their subsequent code status, death or treatment.
spec = [
    ("sofa",2.0),("age",15.0),
    ("mean_hr",25.0),("mean_map",20.0),("mean_rr",8.0),("mean_spo2",7.0),
    ("hr_n_early",6.0),("hr_n_recent",6.0),
    ("map_n_early",6.0),("map_n_recent",6.0),
    ("hr_n_last4",3.0),("map_n_last4",3.0),
    ("hr_6h_change",12.0),("map_6h_change",10.0),
    ("pressor_h_early8_frac",.25),("pressor_h_last4_frac",.25),
    ("invasive_h_early8_frac",.35),("invasive_h_last4_frac",.35),
    ("ne_mean_dose_hours_early8_frac",.2),
    ("ne_mean_dose_hours_last4_frac",.2),
    ("noninvasive_h_early8_frac",.25),("noninvasive_h_last4_frac",.25),
    ("has_lact24",.5),("n_lact24_cap",1.5),
    ("lact_latest24_clean",2.5),("lact_max24_clean",2.5),
    ("has_gcs12",.3),("gcs_latest12_clean",3.0),
    ("gcs_min24_clean",3.0),("creat24_clean",1.5),
    ("bun24_clean",30.0),
]
quantile_labels = {"DNR_ONLY":"DNR only — CPR limitation documented",
                   "DNR_DNI":"DNR and DNI — two explicit limitations"}

def smd(frame, feat):
    groups = [frame[frame.arm == v] for v in ("DNR", "RISKSET")]
    means = []
    vars_ = []
    for g in groups:
        x = g[feat].to_numpy(float)
        w = g.weight.to_numpy(float)
        mask = np.isfinite(x)
        if not np.any(mask):
            return None
        mu = np.average(x[mask], weights=w[mask])
        means.append(mu)
        vars_.append(np.average((x[mask] - mu)**2, weights=w[mask]))
    scale = np.sqrt(np.mean(vars_))
    # If both arms are constant at different values, the standardized
    # difference is undefined/unbounded, NOT perfect balance.
    if scale <= 1e-12:
        return 0.0 if abs(means[0]-means[1])<=1e-12 else float("inf")
    return float((means[0] - means[1]) / scale)

def balance_subtype(frame):
    d = []
    for name,_ in spec:
        v = smd(frame,name)
        if v is not None:
            d.append({"feature":name, "smd":v})
    return {"max_abs_smd":max(abs(x["smd"]) for x in d),
            "covariates":d}

def rebalance(data):
    # Retain each treated risk set and original control support.
    t = data[data.arm=="DNR"].set_index("treated_id",drop=False)
    c = data[data.arm=="RISKSET"].copy().sort_values(
        ["treated_id","anchor_id"]).reset_index(drop=True)
    assert len(t) > 200 and t.treated_id.is_unique
    ref = t[[name for name,_ in spec]].rename(
        columns={name:"t_"+name for name,_ in spec})
    c = c.merge(ref,left_on="treated_id",right_index=True,
                validate="many_to_one")
    unique, group = np.unique(c.treated_id.to_numpy(int), return_inverse=True)
    assert len(unique) == len(t)
    starts = np.r_[0,np.flatnonzero(np.diff(group))+1]
    features = np.column_stack([
        np.nan_to_num(
            (c[name].to_numpy(float)-c["t_"+name].to_numpy(float))/scale,
            nan=0.0)
        for name,scale in spec])
    base = np.log(np.maximum(c.weight.to_numpy(float),1e-250))
    regularization = .004
    def predict(lam):
        y=base+features@lam
        maxv=np.maximum.reduceat(y,starts)
        expo=np.exp(y-maxv[group])
        den=np.add.reduceat(expo,starts)
        return expo/den[group],float(np.mean(maxv+np.log(den)))
    def objective(lam):
        w,loss=predict(lam)
        return (loss+regularization*np.dot(lam,lam)/2,
                features.T@w/len(unique)+regularization*lam)
    res=minimize(objective,np.zeros(len(spec)),jac=True,method="L-BFGS-B",
                 bounds=[(-12,12)]*len(spec),
                 options={"maxiter":450,"gtol":1e-9,"ftol":1e-11})
    assert res.success or np.linalg.norm(res.jac)<.001, res.message
    neww,_=predict(res.x)
    c["weight"]=neww
    kept=data.columns.tolist()
    t=t[kept].copy()
    c=c[kept].copy()
    out=pd.concat([t,c],ignore_index=True)
    assert out.groupby(["treated_id","arm"]).weight.sum().sub(1).abs().max()<1e-6
    control=c
    ess = 1./control.assign(wsq=control.weight**2).groupby("treated_id").wsq.sum()
    per_subject=control.groupby("subject_id").weight.sum()
    return out, {
        "optimizer_success":bool(res.success),
        "n_treated":int(len(t)),
        "n_control_anchors":int(len(c)),
        "n_unique_control_patients":int(c.subject_id.nunique()),
        "effective_control_patients":float(per_subject.sum()**2/(per_subject**2).sum()),
        "median_effective_controls_per_case":float(ess.median()),
        "risksets_ess_lt2":int((ess<2).sum()),
        "risksets_control_max_weight_gt90_pct":int(
             (control.groupby("treated_id").weight.max()>.9).sum()),
        "max_anchor_weight":float(control.weight.max()),
        "baseline_before":balance_subtype(data),
        "baseline_after":balance_subtype(out),
    }

def difference_in_changes(a,b,var,pre,post):
    # a: pre-specified group of anchor rows with arm, weight, subject_id
    # b: each anchor's nine 4h observed support/recording time bins.
    b = b[b.bin.isin(pre+post)].copy()
    b["period"] = np.where(b.bin.isin(pre),"pre","post")
    by = b.groupby(["anchor_id","period"])[[var,"observed_h"]].sum().unstack("period")
    by.columns=["_".join(k) for k in by.columns]
    frame = a[["anchor_id","subject_id","arm","weight"]].merge(
        by.reset_index(),on="anchor_id",validate="one_to_one")
    assert len(frame) == len(a)
    rates = {}; scores=[]
    for arm,g in frame.groupby("arm"):
        h0=(g.weight*g.observed_h_pre).sum()
        h1=(g.weight*g.observed_h_post).sum()
        y0=(g.weight*g[var+"_pre"]).sum()/h0
        y1=(g.weight*g[var+"_post"]).sum()/h1
        rates[arm]={"pre":float(y0),"post":float(y1),"change":float(y1-y0),
                    "post_icu_hours":float(h1)}
        score=(1. if arm=="DNR" else -1.)*g.weight*(
            (g[var+"_post"]-y1*g.observed_h_post)/h1-
            (g[var+"_pre"]-y0*g.observed_h_pre)/h0)
        scores.append(pd.DataFrame({"subject_id":g.subject_id,"score":score}))
    est=rates["DNR"]["change"]-rates["RISKSET"]["change"]
    subject_scores=pd.concat(scores).groupby("subject_id").score.sum()
    se=float(np.sqrt((subject_scores**2).sum()))
    return {"estimate":float(est),
      "ci95_fixed_weight_patient_cluster":[float(est-1.96*se),float(est+1.96*se)],
      "rates":rates}

def binary_difference(a,y):
    g=a.copy()
    g["indicator"]=np.asarray(y,dtype=float)
    groups={}; scores=[]
    for arm,q in g.groupby("arm"):
        w=q.weight.to_numpy(float); z=q.indicator.to_numpy(float)
        mu=np.average(z,weights=w)
        groups[arm]=float(mu)
        sc=(1 if arm=="DNR" else -1)*w*(z-mu)/w.sum()
        scores.append(pd.DataFrame({"subject_id":q.subject_id,"score":sc}))
    est=groups["DNR"]-groups["RISKSET"]
    sc=pd.concat(scores).groupby("subject_id").score.sum()
    se=float(np.sqrt((sc**2).sum()))
    return {"dnr":groups["DNR"],"control":groups["RISKSET"],
       "difference":float(est),
       "ci95_fixed_weight_patient_cluster":[float(est-1.96*se),float(est+1.96*se)]}

def binary_on_frame(a, proc, name, is_proc=True):
    anchor=a[["anchor_id","subject_id","arm","weight"]]
    if is_proc:
        q=anchor.merge(proc[["anchor_id",name]],on="anchor_id",validate="one_to_one")
        return binary_difference(q,q[name].gt(0))
    return binary_difference(a,name)

s=support[["anchor_id","bin","observed_h",
   "pressor_h","invasive_h","ne_mean_dose_hours"]]
m=monitor[["anchor_id","bin","observed_h","n_map","n_hr"]]
report={
 "schema_version":1,"date":"2026-10-25",
 "study":"Prophecy 2: DNR-first event history, not mortality-model development",
 "source":"MIMIC-IV v3.1 with existing restricted DNR risk-set parquet",
 "source_fork":"first documented FULL to DNR_ONLY or DNR_DNI on ICU POE; first ICU stay and explicit documented full-code controls",
 "interpretation":"Observational before/after risk-set contrasts; NO causal ATE/LATE or proof of stopping care",
 "exclusions":"No selection on later death or ICU discharge; a subsequent control DNR order is allowed",
 "phenotype":{
    "eligible_documented_first_dnr":int(len(treated)),
    "represented_dnr":int((cohort.arm=="DNR").sum()),
    "excluded_outside_matched_support":int(
        len(treated)-(cohort.arm=="DNR").sum()),
    "status_at_index":["DNR_ONLY","DNR_DNI"],
 },
 "subtypes":{},
 "assumptions":[
 "DNR-only denotes a documented decision not to resuscitate at arrest, not withdrawal of otherwise appropriate life support.",
 "New DNR orders are clinically selected; first-day SOFA, recent laboratory tests and organ support cannot balance unrecorded prognosis or patient preferences.",
 "ICU exit and death truncate observation; post-per-ICU-hour contrasts are survivor person-time rates, not patient-level policy effects.",
 "The status code is a recorded order state, not verified latent care intention; contemporaneous goals-of-care decisions may be missing.",
 "Matching and calibration were refined after earlier exploratory outcome reviews; all intervals condition on fitted weights and may understate total uncertainty.",
 "Systematic absences of documented full-code orders restrict overlap and generalizability.",
 "DNR-only versus DNR/DNI differences are NOT causally interpretable contrasts of ventilation directives.",
 ],
 "nonnegotiable_next_test":"Independent physician-assignment/exclusion audit before using previously claimed DNR mortality IV; a strong first-stage F statistic is insufficient."
}
for sub in ["DNR_ONLY","DNR_DNI"]:
    a0=cohort[cohort.subtype==sub].copy()
    a,bal=rebalance(a0)
    subset={ "name":quantile_labels[sub],
      "n":int((a.arm=="DNR").sum()),"balance":bal,
      "outcomes":{}, "diagnostics":{}}
    for name,frame in [("vasopressor",s),("invasive_ventilation",s),("map_charting",m),("hr_charting",m)]:
        var={"vasopressor":"pressor_h","invasive_ventilation":"invasive_h",
             "map_charting":"n_map","hr_charting":"n_hr"}[name]
        clipped=frame[frame.anchor_id.isin(a.anchor_id)]
        subset["outcomes"][name]={
          "main_minus12_to_plus12":difference_in_changes(a,clipped,var,[-3,-2,-1],[0,1,2]),
          "near_order_minus4_to_plus4":difference_in_changes(a,clipped,var,[-1],[0]),
          "early_negative_control_minus24_to_minus12":difference_in_changes(a,clipped,var,[-6,-5],[-4]),
        }
    pp=procedure[procedure.anchor_id.isin(a.anchor_id)]
    for name in ["n_extub_pre_4to0","n_extub_post_0to4","n_extub_post_0to12",
                 "n_cmo_12h","n_intub_post_12h"]:
        subset["diagnostics"][name]=binary_on_frame(a,pp,name)
    a["death12"]=(a.deathtime.notna() &
      (a.deathtime>=a.anchor_time) &
      (a.deathtime<a.anchor_time+pd.Timedelta(hours=12)))
    a["icu_exit12"]=a.outtime<a.anchor_time+pd.Timedelta(hours=12)
    for name in ["death12","icu_exit12"]:
        subset["diagnostics"][name]=binary_difference(a,a[name])
    a["subsequent_control_dnr12"]=(a.arm=="RISKSET") & a.first_nonfull.notna() &(
        a.first_nonfull>a.anchor_time)&(
        a.first_nonfull<a.anchor_time+pd.Timedelta(hours=12))
    subset["diagnostics"]["control_crossover12"]=float(np.average(
        a.loc[a.arm=="RISKSET","subsequent_control_dnr12"],
        weights=a.loc[a.arm=="RISKSET","weight"]))
    subset["diagnostics"]["baseline_vent_recent"]={
       arm:float(np.average(q.vent_recent,weights=q.weight))
       for arm,q in a.groupby("arm")}
    subset["diagnostics"]["baseline_press_recent"]={
       arm:float(np.average(q.press_recent,weights=q.weight))
       for arm,q in a.groupby("arm")}
    # Positivity gate is a PRE-outcome sensitivity: controls must not be
    # almost entirely represented by one comparator after calibration.
    con=a[a.arm=="RISKSET"].copy()
    summary=con.assign(wsq=con.weight**2).groupby("treated_id").agg(
        sum_wsq=("wsq","sum"),max_weight=("weight","max"))
    ids=set(summary.index[(1./summary.sum_wsq>=2)&(summary.max_weight<=.8)])
    strict=a.loc[a.treated_id.isin(ids)].copy()
    subset["strict_common_support"]={
        "rule":"effective_controls_per_riskset >=2 AND largest control weight <=0.80; determined using pre-index covariates only",
        "n_treated":int(strict.arm.eq("DNR").sum()),
        "baseline_balance":balance_subtype(strict),
        "outcomes":{},
        "diagnostics":{}
    }
    for name,frame in (("vasopressor",s),("invasive_ventilation",s),("map_charting",m)):
        field={"vasopressor":"pressor_h","invasive_ventilation":"invasive_h","map_charting":"n_map"}[name]
        clipped=frame.loc[frame.anchor_id.isin(strict.anchor_id)]
        subset["strict_common_support"]["outcomes"][name]=difference_in_changes(
            strict,clipped,field,[-3,-2,-1],[0,1,2])
    p_strict=procedure[procedure.anchor_id.isin(strict.anchor_id)]
    subset["strict_common_support"]["diagnostics"]["extub_4h"]=binary_on_frame(
        strict,p_strict,"n_extub_post_0to4")
    subset["strict_common_support"]["diagnostics"]["death12"]=binary_difference(
        strict,strict["death12"])
    # Keep unretuned original weights as an alternative analysis to expose
    # how post-hoc subtype reweighting affects apparent association.
    subset["original_precalibration"]={
      name:difference_in_changes(a0,frame[frame.anchor_id.isin(a0.anchor_id)],
                                 field,[-3,-2,-1],[0,1,2])
      for name,frame,field in (
          ("invasive_ventilation",s,"invasive_h"),
          ("vasopressor",s,"pressor_h"),
          ("map_charting",m,"n_map"))
    }
    # Explicitly distinguish the cohort from patients with no code record
    report["subtypes"][sub]=subset

total=sum(v["n"] for v in report["subtypes"].values())
assert total==report["phenotype"]["represented_dnr"]==2014
assert all(v["balance"]["baseline_after"]["max_abs_smd"]<.15
           for v in report["subtypes"].values()), "Residual balance exceeds .15 SMD"
for v in report["subtypes"].values():
    for x in v["outcomes"].values():
        for q in x.values():
            lo,hi=q["ci95_fixed_weight_patient_cluster"]
            assert lo<=q["estimate"]<=hi
    for q in v["diagnostics"].values():
        if not isinstance(q,dict) or "difference" not in q:continue
        lo,hi=q["ci95_fixed_weight_patient_cluster"]
        assert lo<=q["difference"]<=hi
out=DEST/"dnr_fork_aggregate_report.json"
out.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
out.chmod(0o600)
print("DNR-first study aggregate report:",out,flush=True)
for key,x in report["subtypes"].items():
    print(key,"treated",x["n"],"max_smd",round(x["balance"]["baseline_after"]["max_abs_smd"],3),
    "ESS_patients",round(x["balance"]["effective_control_patients"]),flush=True)
    for k in ("invasive_ventilation","vasopressor","map_charting"):
        y=x["outcomes"][k]
        print(" ",k,"pretrend",round(y["early_negative_control_minus24_to_minus12"]["estimate"],4),
            "main",round(y["main_minus12_to_plus12"]["estimate"],4),
            "CI",[round(a,4) for a in y["main_minus12_to_plus12"]["ci95_fixed_weight_patient_cluster"]],flush=True)
    print("  extubation4h",x["diagnostics"]["n_extub_post_0to4"]["dnr"],
          x["diagnostics"]["n_extub_post_0to4"]["control"],
          "death12",x["diagnostics"]["death12"]["dnr"],x["diagnostics"]["death12"]["control"],flush=True)
