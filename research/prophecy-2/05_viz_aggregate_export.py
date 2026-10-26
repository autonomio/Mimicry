#!/usr/bin/env python3
"""Aggregate-only scientific visualization export for Prophecy 2.

Patient-level input: restricted MIMIC-IV v3.1 study on s0.
Output: two strictly aggregate, audited visual encodings.
NO individual points, identifiers, unrounded patient measures,
small-cell counts, or fabricated temporal trajectories are exported.
Assessed cohorts reflect analyst filtering, NOT patient state changes.
"""
import ast
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.optimize import minimize

BASE = Path("/srv/mimic-iv/studies/decision_feedback_20261025")
FORK = Path("/srv/mimic-iv/studies/prophecy2_dnr_20261025")
OUT = FORK / "viz_aggregate_v1.json"
SOURCE = FORK / "01_dnr_fork.py"

# Reuse the ACTUAL subtype-matching function from the executed Prophecy 2
# study instead of recreating a different matching/weighting regime.
tree = ast.parse(SOURCE.read_text())
targets = [n for n in tree.body if (
    isinstance(n, ast.Assign) and any(
        isinstance(z, ast.Name) and z.id == "spec" for z in n.targets
    )) or (isinstance(n, ast.FunctionDef) and
            n.name in {"smd","balance_subtype","rebalance"})]
assert len(targets) == 4, "Prophecy 2 matching contract changed"
compiled = compile(ast.fix_missing_locations(ast.Module(body=targets,type_ignores=[])),
                   str(SOURCE), "exec")
scope = {"np":np, "pd":pd, "minimize":minimize}
exec(compiled, scope)
rebalance = scope["rebalance"]

treated = pd.read_parquet(BASE/"risk_treated.parquet")
reference = pd.read_parquet(BASE/"risk_weighted_severityhistory.parquet")
reference = reference.merge(treated[["stay_id","first_nonfull_state"]].rename(
    columns={"stay_id":"treated_id","first_nonfull_state":"subtype"}
),on="treated_id",validate="many_to_one")
raw_support = pd.read_parquet(BASE/"risk_support_bins.parquet")[
    ["anchor_id","bin","observed_h","invasive_h","pressor_h"]]
raw_monitor = pd.read_parquet(BASE/"risk_event_bins.parquet")[
    ["anchor_id","bin","observed_h","n_map","n_hr"]]
assert treated.stay_id.is_unique
assert (reference.arm=="DNR").sum()==2014
assert set(treated.first_nonfull_state)=={"DNR_ONLY","DNR_DNI"}
assert raw_support.groupby("anchor_id").size().eq(9).all()

m_eligible = treated[["stay_id","intime","outtime","index_time",
                     "unit_group","sofa","first_nonfull_state"]].copy()
# For ALL eligible DNR stays, derive exposure using only 6h before
# first code-status order; does not depend on outcomes or future stay length.
c = duckdb.connect("/srv/mimic-iv/db/mimic4-v31.db",read_only=True)
c.execute("SET threads=4")
c.register("candidate_events",m_eligible)
v = c.sql("""
 SELECT e.stay_id,
 least(6.,coalesce(sum(greatest(0.,datediff('second',
        greatest(v.starttime,e.index_time-INTERVAL '6 hours'),
        least(v.endtime,e.index_time))/3600.0))
        FILTER(WHERE v.ventilation_status='InvasiveVent'),0)) / 6. AS invasive_pre_fraction
 FROM candidate_events e
 LEFT JOIN mimiciv_derived.ventilation v
 ON e.stay_id=v.stay_id AND v.starttime<e.index_time
 AND v.endtime>e.index_time-INTERVAL '6 hours'
 GROUP BY e.stay_id
""").df()
assert len(v)==len(m_eligible) and v.stay_id.is_unique
m_eligible=m_eligible.merge(v,on="stay_id",validate="one_to_one")
assert m_eligible.invasive_pre_fraction.between(0,1.0001).all()

fitted={}
strict_ids={}
for sub in ("DNR_ONLY","DNR_DNI"):
    d,bal = rebalance(reference[reference.subtype==sub].copy())
    t=d[d.arm=="DNR"]
    controls=d[d.arm=="RISKSET"]
    assert t.treated_id.is_unique
    assert (controls.groupby("treated_id").weight.sum()-1).abs().max()<1e-6
    summary=controls.assign(wsq=controls.weight**2).groupby("treated_id").agg(
        sum_wsq=("wsq","sum"),max_weight=("weight","max"))
    good=summary.index[(1./summary.sum_wsq>=2)&(summary.max_weight<=.80)]
    strict_ids[sub]=set(map(int,good))
    assert len(good)>=100
    fitted[sub]=d
    print(sub, "matched",len(t),"strict",len(good),
          "balance",bal["baseline_after"]["max_abs_smd"],flush=True)

# Analytic stages must not imply patient time evolution.
stage_frames = {
    "eligible":m_eligible.assign(stay=m_eligible.stay_id,subtype=m_eligible.first_nonfull_state),
    "supported":m_eligible[m_eligible.stay_id.isin(reference.loc[
       reference.arm=="DNR","treated_id"])].assign(
          stay=lambda x:x.stay_id,subtype=lambda x:x.first_nonfull_state),
}
strict_all=strict_ids["DNR_ONLY"]|strict_ids["DNR_DNI"]
stage_frames["strict"]=m_eligible[m_eligible.stay_id.isin(strict_all)].assign(
    stay=lambda x:x.stay_id,subtype=lambda x:x.first_nonfull_state)
assert [len(stage_frames[x]) for x in ("eligible","supported","strict")][:2]==[3021,2014]

cells=[]
stage_counts={}
# Disclose only cohorts >=30 within a unit/subtype/stage; no rare outcomes
# nor selected individual coordinates.
for stage, frame in stage_frames.items():
    stage_counts[stage]={"n":len(frame),"subtypes":frame.subtype.value_counts().to_dict()}
    for sub, subgroup in frame.groupby("subtype"):
        groups=list(subgroup.groupby("unit_group"))
        small={unit for unit,q in groups if len(q)<30}
        excluded=set(small)
        # Complementary suppression: one hidden cell can be deduced
        # by subtracting visible cells from a public subtype total.
        if small:
            eligible=sorted((len(q),unit) for unit,q in groups if len(q)>=30)
            assert eligible,"No second cell to suppress"
            excluded.add(eligible[0][1])
        for unit,q in groups:
            n=len(q)
            if unit in excluded:continue
            assert n>=30
            cells.append({"stage":stage,"id":sub+"_"+unit,
                "subtype":sub,"unit":unit,"n":n,
                "sofa":round(float(q.sofa.mean()),2),
                "invasive_before":round(float(q.invasive_pre_fraction.mean()),3)})
assert sum(stage_counts["strict"]["subtypes"].values())==len(strict_all)

# Matched event-time rates, using each subtype's actual calibrated weights.
# No pointwise confidence intervals are available: do NOT draw uncertainty
# ribbons. Compare with original aggregate DID values as arithmetic QA.
rates=[]
metrics={"invasive_ventilation":("invasive_h","share"),
         "vasopressor_exposure":("pressor_h","share"),
         "map_recording":("n_map","rate")}
for sub,d in fitted.items():
    anchor=d[["anchor_id","arm","weight"]]
    supported=anchor.merge(raw_support,on="anchor_id",validate="one_to_many")
    measured=anchor.merge(raw_monitor,on="anchor_id",validate="one_to_many")
    for metric,(field,scale) in metrics.items():
        frame=supported if metric!="map_recording" else measured
        for (arm,binid),group in frame.groupby(["arm","bin"]):
            if not (-6<=binid<=2):continue
            exposure=float(np.sum(group.weight*group.observed_h))
            events=float(np.sum(group.weight*group[field]))
            assert exposure>0
            fraction=events/exposure
            if scale=="share": assert -.001<=fraction<=1.001
            rates.append({"subtype":sub,"metric":metric,
                          "arm":"DNR" if arm=="DNR" else "RISKSET",
                          "from_hour":int(binid*4),"to_hour":int((binid+1)*4),
                          "value":round(fraction,5)})
        # Quantitatively reconcile the 12h DID from the published output.
        vals={(x["arm"],x["from_hour"]):x["value"] for x in rates
              if x["subtype"]==sub and x["metric"]==metric}
        # Using *unrounded* data to calculate the reference DID.
        xs=frame.groupby(["arm","bin"]).apply(
            lambda g: pd.Series({"expo":float(np.sum(g.weight*g.observed_h)),
                                 "num":float(np.sum(g.weight*g[field]))}),
            include_groups=False).reset_index()
        def period(arm,bins):
            a=xs[(xs.arm==arm)&(xs.bin.isin(bins))]
            return float(a.num.sum()/a.expo.sum())
        computed=(period("DNR",[0,1,2])-period("DNR",[-3,-2,-1])) - (
                  period("RISKSET",[0,1,2])-period("RISKSET",[-3,-2,-1]))
        # Source report uses the same callable for difference-in-changes.
        source=json.loads((FORK/"dnr_fork_aggregate_report.json").read_text())
        src_key={"invasive_ventilation":"invasive_ventilation",
            "vasopressor_exposure":"vasopressor",
            "map_recording":"map_charting"}[metric]
        original=source["subtypes"][sub]["outcomes"][src_key]["main_minus12_to_plus12"]["estimate"]
        assert abs(computed-original)<1e-9,(sub,metric,computed,original)
        print("DID verified",sub,metric,round(computed,5),flush=True)

result={"schema_version":1,"kind":"scientific-viz-aggregate",
        "track":"prophecy-2","release_id":"2026-10-25-dnr-question-fork",
        "source":"MIMIC-IV v3.1, audited Prophecy 2 risk sets",
        "cohort_bubbles":{"axes":{"x":"Mean first-day SOFA","y":"Pre-order invasive ventilation fraction"},
                          "units":"ICU unit × documented DNR subtype, aggregate only",
                          "stages":[{"id":"eligible","label":"Eligible DNR orders",
                                     "explanation":"All first documented DNR orders after explicit full code; no suitable comparison yet."},
                                    {"id":"supported","label":"Measured common support",
                                     "explanation":"Only DNR events with clinically eligible weighted full-code controls."},
                                    {"id":"strict","label":"Stricter control support",
                                     "explanation":"Controls must have effective number ≥2 and no single weight above 80%. Causal validity is NOT established."}],
                          "counts":stage_counts,"points":cells,
                          "min_cell_n":30,"complementary_suppression":True},
        "event_time":{"description":"Measured 4-hour aggregate bins anchored on a documented DNR order or eligible full-code pseudo-time. The display follows record counts and treatment exposure per observed ICU person-hour; differential exit/death changes risk sets.",
                      "from_hours":[-24,-20,-16,-12,-8,-4,0,4,8],
                      "metrics":[{"id":"invasive_ventilation","label":"Invasive ventilation","unit":"fraction of ICU patient-hours"},
                                 {"id":"vasopressor_exposure","label":"Vasopressor exposure","unit":"fraction of ICU patient-hours"},
                                 {"id":"map_recording","label":"MAP recordings","unit":"records per ICU patient-hour"}],
                      "series":rates,
                      "pointwise_ci_available":False,
                      "event_time_is_endogenous":True},
        "provenance":{"script":"research/prophecy-2/05_viz_aggregate_export.py",
                      "source_subtype_estimates":"research/prophecy-2/01_dnr_fork.py",
                      "patient_rows_exported":False,
                      "interpretation":"Filtered analytical cohorts are NOT individual trajectories; displayed changes are associations, not treatment effects."}}
raw=json.dumps(result,allow_nan=False)
for forbidden in ('"subject_id"','"stay_id"','"hadm_id"','"anchor_id"','"index_time"','"deathtime"'):
    assert forbidden not in raw, forbidden
assert all(x["n"]>=30 for x in cells)
assert len(rates)==2*3*2*9
OUT.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
OUT.chmod(0o600)
print("EXPORTED aggregate only",OUT,"n_cells",len(cells),"series",len(rates),
      "sizes",stage_counts,flush=True)
