#!/usr/bin/env python3
"""Risk-set matching on exclusively pre-index features, MIMIC-IV v3.1.

All patient-level data stay on the s0 server, under an access-restricted
study directory. Do not upload matched.parquet or the source files to GitHub.
No post-index measurements or outcomes participate in matching.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import min_weight_full_bipartite_matching

ROOT = Path("/srv/mimic-iv/studies/decision_feedback_20261025")
INPUT = ROOT / "risk_pre_features.parquet"
df = pd.read_parquet(INPUT)
t = df.loc[df.arm.eq("DNR")].copy().set_index("treated_id", drop=False)
r = df.loc[df.arm.eq("RISKSET")].copy()
assert t.treated_id.is_unique
assert r.groupby(["treated_id","stay_id"]).size().max() == 1
assert (r["treated_id"] != r["stay_id"]).all()

FEATURES = [
    ("sofa", 2.0, 1.3),
    ("age", 15.0, 1.2),
    ("mean_hr", 25.0, 2.0),
    ("mean_map", 20.0, 1.3),
    ("mean_rr", 8.0, 1.2),
    ("mean_spo2", 7.0, 0.9),
    ("hr_n_early", 6.0, 0.5),
    ("hr_n_recent", 6.0, 1.1),
    ("map_n_early", 6.0, 0.5),
    ("map_n_recent", 6.0, 1.1),
    ("hr_n_last4", 3.0, 0.7),
    ("map_n_last4", 3.0, 0.7),
    ("hr_6h_change", 12.0, 0.65),
    ("map_6h_change", 10.0, 0.65),
]
# Candidate pools already exact-match 6-hour clock bin, historical cohort,
# ICU group, and elapsed ICU time; age +/-20 and SOFA +/-3.
# Hard-match current organ support and impose physiological/monitoring calipers.
MAX_DISTANCE = 5.5
K_CONTROLS = 2

cols = ["treated_id","subject_id","press_recent","vent_recent"] + [f[0] for f in FEATURES]
r = r.merge(t[cols].rename(columns={
    "subject_id":"t_subject_id",
    "press_recent":"t_press_recent",
    "vent_recent":"t_vent_recent",
    **{f[0]:"t_"+f[0] for f in FEATURES}
}),left_on="treated_id",right_index=True,validate="many_to_one")
r = r.loc[
    (r["press_recent"] == r["t_press_recent"])
    & (r["vent_recent"] == r["t_vent_recent"])
    & (r["mean_hr"].sub(r["t_mean_hr"]).abs().le(35))
    & (r["mean_map"].sub(r["t_mean_map"]).abs().le(25))
    & (r["hr_n_recent"].sub(r["t_hr_n_recent"]).abs().le(8))
    & (r["map_n_recent"].sub(r["t_map_n_recent"]).abs().le(8))
].copy()
squared = np.zeros(len(r),dtype=float)
for name,scale,weight in FEATURES:
    left = r[name].to_numpy(dtype=float)
    right = r["t_"+name].to_numpy(dtype=float)
    either_nan = np.isnan(left) ^ np.isnan(right)
    both_nan = np.isnan(left) & np.isnan(right)
    delta = (np.nan_to_num(left,nan=0.0)-np.nan_to_num(right,nan=0.0))/scale
    delta[both_nan] = 0
    delta[either_nan] = 2.0
    squared += weight*delta**2
r["distance"] = np.sqrt(squared)
r = r.loc[r.distance <= MAX_DISTANCE].copy()
r.sort_values(["treated_id","distance","stay_id"],inplace=True)

# Sparse minimum-cost bipartite assignment with one unique control patient.
# Each treated event has two unit-capacity demand slots, first-slot dummy
# costs 500 (prioritize finding >=1 match) and second-slot dummy costs 6.
# Global assignment minimizes total pre-index covariate mismatch; no outcomes.
r = r.sort_values(["treated_id","subject_id","distance","anchor_id"]).drop_duplicates(
    ["treated_id","subject_id"],keep="first").copy()
treated_ids = np.sort(t.index.to_numpy(dtype=int))
control_subjects = np.sort(r.subject_id.unique().astype(int))
n_t = len(treated_ids)
n_c = len(control_subjects)
ti = np.searchsorted(treated_ids,r.treated_id.to_numpy(dtype=int))
ci = np.searchsorted(control_subjects,r.subject_id.to_numpy(dtype=int))
row_ids = np.concatenate([ti,ti+n_t,np.arange(2*n_t)])
col_ids = np.concatenate([ci,ci,n_c+np.arange(2*n_t)])
costs = np.concatenate([
    r.distance.to_numpy(dtype=float)+0.001,
    r.distance.to_numpy(dtype=float)+0.011,
    np.repeat(500.0,n_t),np.repeat(6.0,n_t),
])
mat = coo_matrix((costs,(row_ids,col_ids)),shape=(2*n_t,n_c+2*n_t)).tocsr()
matched_rows,matched_cols = min_weight_full_bipartite_matching(mat)
chosen = matched_cols < n_c
anchor_lookup = {
    (int(z.treated_id),int(z.subject_id)):int(z.anchor_id)
    for z in r.itertuples()
}
selected = [
    anchor_lookup[(int(treated_ids[int(ri)%n_t]),int(control_subjects[int(ci)]))]
    for ri,ci in zip(matched_rows[chosen],matched_cols[chosen])
]
selected_treated = sorted({
    int(treated_ids[int(ri)%n_t])
    for ri in matched_rows[chosen]
})
# This construction can include a subject as a control earlier and treated
# later; that is intentionally allowed (no future-treatment conditioning).
control = df.loc[df.anchor_id.isin(selected)].copy()
treatment = df.loc[df.arm.eq("DNR") & df.treated_id.isin(selected_treated)].copy()
nc = control.groupby("treated_id").size()
control["weight"] = 1.0/control["treated_id"].map(nc)
treatment["weight"] = 1.0
matched = pd.concat([treatment,control],ignore_index=True)
assert treatment.treated_id.is_unique
assert matched.loc[matched.arm.eq("RISKSET"),"subject_id"].is_unique
assert matched.loc[matched.arm.eq("DNR"),"treated_id"].is_unique
assert abs(control.weight.sum()-len(treatment)) < 1e-9
# Make the final matched set available to the outcome stage only after
# baseline matching and diagnostics are completely determined.
matched.to_parquet(ROOT/"risk_matched.parquet",index=False)

def smd(frame,field):
    a = frame[frame.arm.eq("DNR")]
    b = frame[frame.arm.eq("RISKSET")]
    x = a[field].to_numpy(dtype=float)
    y = b[field].to_numpy(dtype=float)
    wx = a.weight.to_numpy(dtype=float)
    wy = b.weight.to_numpy(dtype=float)
    maskx = np.isfinite(x)
    masky = np.isfinite(y)
    if not maskx.any() or not masky.any():
        return None
    mx = np.average(x[maskx],weights=wx[maskx])
    my = np.average(y[masky],weights=wy[masky])
    vx = np.average((x[maskx]-mx)**2,weights=wx[maskx])
    vy = np.average((y[masky]-my)**2,weights=wy[masky])
    pooled = np.sqrt((vx+vy)/2)
    return float((mx-my)/pooled) if pooled>1e-9 else 0.0

raw = df.copy()
raw["weight"] = 1.0
balance_fields = [
    "sofa","age","press_recent","vent_recent","mean_hr","mean_map",
    "mean_rr","mean_spo2","hr_n_early","hr_n_recent",
    "map_n_early","map_n_recent","hr_n_last4","map_n_last4",
    "hr_6h_change","map_6h_change"
]
balance = [
    {"variable":f,"candidate_smd":smd(raw,f),"matched_smd":smd(matched,f)}
    for f in balance_fields
]
selected_r = r.loc[r.anchor_id.isin(selected)]
report = {
    "design":"global minimum-cost sparse bipartite assignment; one treated event and up to two patient-unique controls; historical epoch/ICU group/clock-bin exact; same elapsed ICU time; current pressor and ventilation exact",
    "source_db":"MIMIC-IV 3.1",
    "all_eligible_treated": int(len(t)),
    "candidate_rows_before_organ_support": int(len(df)-len(t)),
    "candidate_rows_after_preindex_restrictions": int(len(r)),
    "matched_treated": int(len(treatment)),
    "matched_control_records": int(len(control)),
    "controls_per_case":{"one":int((nc==1).sum()),"two":int((nc==2).sum())},
    "unmatched_treated": int(len(t)-len(treatment)),
    "unique_control_patients": int(control.subject_id.nunique()),
    "unique_treated_patients": int(treatment.subject_id.nunique()),
    "patients_in_both_arms":int(len(set(control.subject_id)&set(treatment.subject_id))),
    "median_match_distance":float(selected_r.distance.median()) if len(selected_r) else None,
    "p90_match_distance":float(selected_r.distance.quantile(.9)) if len(selected_r) else None,
    "balance":balance,
    "max_abs_smd_after":float(max(abs(x["matched_smd"]) for x in balance if x["matched_smd"] is not None)),
    "design_provenance":"All matching features are strictly pre-index; future control status is not a selection condition; only current documented status is used."
}
(ROOT/"risk_matching_report.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
