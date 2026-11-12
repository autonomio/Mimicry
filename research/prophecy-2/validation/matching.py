"""Outcome-blind, capped risk-set weights for the DNR validation study.

Input and fitted rows stay on the authorized server. This module never reads
outcomes, establishes causal exchangeability, or exports patient identifiers.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import coo_matrix, csr_matrix, vstack


FEATURES = (
    "sofa", "age", "mean_hr", "mean_map", "mean_rr", "mean_spo2",
    "hr_n_early", "hr_n_recent", "map_n_early", "map_n_recent",
    "hr_n_last4", "map_n_last4", "hr_6h_change", "map_6h_change",
    "pressor_h_early8_frac", "pressor_h_last4_frac",
    "invasive_h_early8_frac", "invasive_h_last4_frac",
    "ne_mean_dose_hours_early8_frac", "ne_mean_dose_hours_last4_frac",
    "noninvasive_h_early8_frac", "noninvasive_h_last4_frac",
    "has_lact24", "n_lact24_cap", "lact_latest24", "lact_max24",
    "has_gcs12", "gcs_latest12", "gcs_min24", "creat_latest24", "bun_latest24",
)
KEYS = ("anchor_id", "treated_id", "subject_id", "arm")
WITHIN_SUBJECT_CAP = 0.5
GLOBAL_SUBJECT_CAP = 2.0
FIT_TOLERANCE = 0.05
BALANCE_GATE = 0.10
MIN_PUBLIC_N = 30
DISTANCE_SCALES = dict(zip(FEATURES, (
    2, 15, 25, 20, 8, 7, 6, 6, 6, 6, 3, 3, 12, 10,
    .25, .25, .35, .35, .2, .2, .25, .25, .5, 1.5,
    2.5, 2.5, .3, 3, 3, 1.5, 30,
)))


@dataclass
class Fit:
    weights: pd.DataFrame | None
    diagnostics: dict


def subject_fold(subject_id: int) -> int:
    digest = hashlib.sha256(str(int(subject_id)).encode("ascii")).digest()
    return int.from_bytes(digest[:8], "big", signed=False) % 2


def restrict_fold(data: pd.DataFrame, fold: int) -> pd.DataFrame:
    """Confine every role of a patient to the same partition."""
    if fold not in (0, 1):
        raise ValueError("fold must be 0 or 1")
    keep = data.subject_id.map(subject_fold).eq(fold)
    out = data.loc[keep].copy()
    case_ids = set(out.loc[out.arm.eq("DNR"), "treated_id"])
    return out.loc[out.treated_id.isin(case_ids)].copy()


def _indicator_matrix(codes: np.ndarray, n_rows: int) -> csr_matrix:
    return coo_matrix((np.ones(len(codes)), (codes, np.arange(len(codes)))),
                      shape=(n_rows, len(codes))).tocsr()


def _matrix(t: pd.DataFrame, c: pd.DataFrame, features: tuple[str, ...]):
    """Fit imputation and frozen scales using only the selected baseline frame."""
    tcols, ccols, names, all_missing = [], [], [], []
    for name in features:
        tv = pd.to_numeric(t[name], errors="raise").to_numpy(float)
        cv = pd.to_numeric(c[name], errors="raise").to_numpy(float)
        tm, cm = ~np.isfinite(tv), ~np.isfinite(cv)
        finite = tv[~tm]
        fill = float(np.median(finite)) if len(finite) else 0.0
        if not len(finite):
            all_missing.append(name)
        tcols.append(np.where(tm, fill, tv))
        ccols.append(np.where(cm, fill, cv))
        names.append(name)
        if tm.any() or cm.any():
            tcols.append(tm.astype(float))
            ccols.append(cm.astype(float))
            names.append(name + "__missing")
    xt, xc = np.column_stack(tcols), np.column_stack(ccols)
    target = xt.mean(axis=0)
    scale = np.sqrt((xt.var(axis=0) + xc.var(axis=0)) / 2)
    constant = scale < 1e-12
    # A pooled constant can still differ between arms. Demand equality; never
    # call an undefined standardised difference perfect balance.
    unequal_constants = constant & (np.abs(target - xc.mean(axis=0)) > 1e-12)
    return xt, xc, names, target, scale, constant, unequal_constants, all_missing


def fit_supported(data: pd.DataFrame, features: tuple[str, ...] = FEATURES) -> Fit:
    """Fit one locked specification; infeasibility is a result, not a tuning cue.

    Each original event remains a case. Cases with fewer than two distinct
    baseline-eligible comparator people are removed before targets are computed.
    No death, discharge, treatment outcome, or future code status enters fitting.
    """
    missing = set(KEYS + features) - set(data.columns)
    if missing:
        raise ValueError("Missing baseline columns: " + ", ".join(sorted(missing)))
    x = data.loc[:, list(KEYS + features)].copy()
    if x[list(KEYS)].isna().any().any() or x.anchor_id.duplicated().any():
        raise ValueError("Missing/duplicate anchor keys")
    if not set(x.arm).issubset({"DNR", "RISKSET"}):
        raise ValueError("Unexpected arm")
    t = x.loc[x.arm.eq("DNR")].sort_values("treated_id").copy()
    c = x.loc[x.arm.eq("RISKSET")].sort_values(["treated_id", "anchor_id"]).copy()
    if t.treated_id.duplicated().any():
        raise ValueError("More than one treated anchor per risk set")
    n_initial = len(t)
    case_subject = t.set_index("treated_id").subject_id
    c = c.loc[c.treated_id.isin(case_subject.index)].copy()
    self_match = c.subject_id.eq(c.treated_id.map(case_subject))
    if self_match.any():
        raise ValueError("A case is its own control")
    available = c.groupby("treated_id").subject_id.nunique()
    supported = set(available.index[available.ge(2)])
    t = t.loc[t.treated_id.isin(supported)].reset_index(drop=True)
    c = c.loc[c.treated_id.isin(supported)].reset_index(drop=True)
    n = len(t)
    diag = {
        "n_treated_before_support_rule": n_initial,
        "n_treated": n,
        "n_treated_subjects": int(t.subject_id.nunique()),
        "n_removed_baseline_support": n_initial - n,
        "n_control_anchors_available": len(c),
        "n_control_subjects_available": int(c.subject_id.nunique()),
        "fit_tolerance": FIT_TOLERANCE,
        "postfit_balance_gate": BALANCE_GATE,
        "within_riskset_subject_cap": WITHIN_SUBJECT_CAP,
        "global_control_subject_cap": GLOBAL_SUBJECT_CAP,
        "outcomes_used_in_design": False,
    }
    if n < MIN_PUBLIC_N:
        return Fit(None, {**diag, "status": "INSUFFICIENT_COHORT", "gate_pass": False})
    xt, xc, names, target, scale, constant, unequal, all_missing = _matrix(t, c, features)
    diag["n_balance_features_including_missingness"] = len(names)
    diag["features_entirely_missing_in_treated"] = all_missing
    if unequal.any():
        return Fit(None, {**diag, "status": "CONSTANT_FEATURE_MISMATCH", "gate_pass": False})

    case_index = {value: i for i, value in enumerate(t.treated_id)}
    groups = c.treated_id.map(case_index).to_numpy(int)
    per_case = _indicator_matrix(groups, n)
    joint_keys = pd.MultiIndex.from_frame(c[["treated_id", "subject_id"]])
    joint, joint_values = pd.factorize(joint_keys, sort=True)
    per_case_subject = _indicator_matrix(joint, len(joint_values))
    patient, patient_values = pd.factorize(c.subject_id, sort=True)
    per_patient = _indicator_matrix(patient, len(patient_values))

    safe_scale = np.where(constant, 1.0, scale)
    zt = (xt - target) / safe_scale
    zc = (xc - target) / safe_scale
    # Mean imbalance constraints are expressed on the frozen, pre-fit scale.
    balance = csr_matrix(zc.T / n)
    bounds = np.where(constant, 0.0, FIT_TOLERANCE)
    for name in all_missing:
        bounds[names.index(name + "__missing")] = 0.0
    aub = vstack([per_case_subject, per_patient, balance, -balance], format="csr")
    bub = np.r_[np.full(per_case_subject.shape[0], WITHIN_SUBJECT_CAP),
                np.full(per_patient.shape[0], GLOBAL_SUBJECT_CAP), bounds, bounds]
    distance_scale = np.array([
        1.0 if name.endswith("__missing") else DISTANCE_SCALES.get(name, safe_scale[k])
        for k, name in enumerate(names)
    ])
    distances = np.square((xc - xt[groups]) / distance_scale).sum(axis=1)
    # Row order is deterministic. No outcome-derived priorities or adjustments.
    solved = linprog(distances, A_ub=aub, b_ub=bub, A_eq=per_case,
                     b_eq=np.ones(n), bounds=(0.0, None), method="highs",
                     options={"time_limit": 180.0,
                              "primal_feasibility_tolerance": 1e-8,
                              "dual_feasibility_tolerance": 1e-8})
    diag["solver_status"] = int(solved.status)
    diag["solver_message"] = str(solved.message)
    if not solved.success:
        status = "INFEASIBLE" if solved.status == 2 else "NO_CERTIFIED_FIT"
        return Fit(None, {**diag, "status": status, "gate_pass": False})
    w = np.maximum(0.0, solved.x)
    case_totals = np.asarray(per_case @ w)
    joint_totals = np.asarray(per_case_subject @ w)
    patient_totals = np.asarray(per_patient @ w)
    joint_group = np.array([case_index[pair[0]] for pair in joint_values])
    squared_by_case = np.bincount(joint_group, weights=joint_totals**2, minlength=n)
    ess = 1.0 / squared_by_case
    total_ess = float(patient_totals.sum()**2 / np.square(patient_totals).sum())
    mu_c = np.average(xc, axis=0, weights=w)
    var_c = np.average(np.square(xc - mu_c), axis=0, weights=w)
    conventional_scale = np.sqrt((xt.var(axis=0) + var_c) / 2)
    diff = target - mu_c
    conventional = np.divide(diff, conventional_scale,
                             out=np.zeros_like(diff), where=conventional_scale > 1e-12)
    bad_constant = (conventional_scale <= 1e-12) & (np.abs(diff) > 1e-9)
    conventional[bad_constant] = np.inf
    frozen = diff / safe_scale
    max_conventional = float(np.max(np.abs(conventional)))
    max_frozen = float(np.max(np.abs(frozen)))
    gate = bool(np.max(np.abs(case_totals-1)) <= 1e-6
                and joint_totals.max() <= WITHIN_SUBJECT_CAP+1e-6
                and patient_totals.max() <= GLOBAL_SUBJECT_CAP+1e-6
                and ess.min() >= 2-1e-6
                and total_ess >= 0.5*n-1e-6
                and max_conventional <= BALANCE_GATE+1e-6
                and max_frozen <= FIT_TOLERANCE+1e-6)
    diag.update({
        "status": "PASS" if gate else "POSTFIT_GATE_FAILED",
        "gate_pass": gate,
        "max_abs_frozen_smd": max_frozen,
        "max_abs_conventional_smd": max_conventional if np.isfinite(max_conventional) else None,
        "undefined_unequal_constant_after_fit": bool(bad_constant.any()),
        "min_effective_control_people_per_case": float(ess.min()),
        "max_control_person_weight_in_one_case": float(joint_totals.max()),
        "max_control_person_total_weight": float(patient_totals.max()),
        "effective_control_people_overall": total_ess,
        "n_control_people_with_positive_weight": int((patient_totals > 1e-10).sum()),
        "max_case_normalization_error": float(np.max(np.abs(case_totals-1))),
        "mean_scaled_squared_distance": float(solved.fun/n),
    })
    if not gate:
        return Fit(None, diag)
    tw = t.loc[:, list(KEYS)].copy()
    tw["weight"] = 1.0
    cw = c.loc[:, list(KEYS)].copy()
    cw["weight"] = w
    # Keep exact solver weights: no outcome-dependent trimming or re-normalizing.
    return Fit(pd.concat([tw, cw], ignore_index=True), diag)
