#!/usr/bin/env python3
"""Execute the locked validation on the authorized server; export aggregates only."""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from matching import FEATURES, fit_supported, restrict_fold, subject_fold
from outcomes import build_outcomes, build_state_frame, contrast, summarize_state_frame


SOURCE_COMMIT = "dab401a79bb63e563448dae29c5145d6377b3a17"
DEFAULT_SOURCE = Path("/srv/mimic-iv/studies/decision_feedback_20261025")
DEFAULT_DEST = Path("/srv/mimic-iv/studies/prophecy2_validation_20261027")
HERE = Path(__file__).resolve().parent
OUTCOME_MAP = {"invasive_ventilation": "invasive_h",
               "vasopressor_exposure": "pressor_h", "map_recording": "n_map"}
ARCHIVE_MAP = {"invasive_ventilation": "invasive_ventilation",
               "vasopressor_exposure": "vasopressor", "map_recording": "map_charting"}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    path.chmod(0o600)


def legacy_calibrator(path):
    """Reuse ONLY the frozen legacy baseline calibration, never its outcomes.

    The reference weights were not persisted separately. AST selection prevents
    execution of the original script's reads/writes or main outcome calculation.
    This reuse is explicitly recorded; independent reproduction concerns the
    arithmetic and source outcome construction, not independent original weights.
    """
    tree = ast.parse(Path(path).read_text())
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name in {"smd", "balance_subtype", "rebalance"}]
    spec = next(ast.literal_eval(n.value) for n in tree.body
                if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "spec" for t in n.targets))
    namespace = {"np": np, "pd": pd, "minimize": minimize, "spec": spec}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["rebalance"]


def supported_membership(data):
    """Baseline membership only, for joint disclosure checks, never for fitting."""
    cases = data.loc[data.arm.eq("DNR"), "treated_id"]
    controls = data.loc[data.arm.eq("RISKSET") & data.treated_id.isin(cases)]
    count = controls.groupby("treated_id").subject_id.nunique()
    keep = count.index[count.ge(2)]
    return data.loc[data.treated_id.isin(keep), ["anchor_id", "subject_id", "arm"]].copy()


def population_disclosure_safe(data, memberships):
    """Threshold JOINT membership cells, so all-minus-parts cannot expose a few people.

    These are distinct-person counts within anchor-membership cells, not event
    counts. All original and retained populations are considered together.
    """
    x = data[["anchor_id", "subject_id", "arm"]].copy()
    cols = []
    for i, membership in enumerate(memberships):
        name = "member_"+str(i)
        x[name] = x.anchor_id.isin(membership.anchor_id)
        cols.append(name)
    sizes = x.groupby(["arm", *cols], dropna=False).subject_id.nunique()
    return not ((sizes > 0) & (sizes < 30)).any()


def public_fit(diag, safe):
    fixed = {"status", "gate_pass", "fit_tolerance", "postfit_balance_gate",
             "within_riskset_subject_cap", "global_control_subject_cap",
             "outcomes_used_in_design", "solver_status", "solver_message"}
    if safe:
        result = {k: v for k, v in diag.items() if not k.startswith("n_")}
        result["n_treated"] = int(diag["n_treated"])
    else:
        # ESS, distance and balance values can indirectly reconstruct a hidden
        # population size. Only fixed rules and categorical verdicts survive.
        result = {k: v for k, v in diag.items() if k in fixed}
        result["n_treated"] = None
    result["count_disclosure"] = "released" if safe else "suppressed_small_joint_membership_cell"
    return result


def public_contrast(value):
    # Do not release arm means, denominators, or unique-person totals that could
    # reconstruct small changes between the nested legacy/new/subset populations.
    return {k: v for k, v in value.items()
            if k not in {"rates", "n_patient_clusters"}}


def point_contributors(anchors, bins, outcome, pre, post):
    x = bins[["anchor_id", "bin", outcome, "observed_h"]].merge(
        anchors.loc[anchors.weight > 0, ["anchor_id", "subject_id", "arm", "weight"]],
        on="anchor_id")
    pieces = []
    for arm, arm_sign in (("DNR", 1), ("RISKSET", -1)):
        for period, time_sign in ((pre, -1), (post, 1)):
            g = x.loc[x.arm.eq(arm) & x.bin.isin(period)].copy()
            denominator = float((g.weight*g.observed_h).sum())
            if denominator <= 0:
                return None
            g["contribution"] = arm_sign*time_sign*g.weight*g[outcome]/denominator
            pieces.append(g[["subject_id", "contribution"]])
    return pd.concat(pieces).groupby("subject_id").contribution.sum()


def contrast_difference_safe(anchors, bins, first_spec, second_spec):
    a = point_contributors(anchors, bins, *first_spec)
    b = point_contributors(anchors, bins, *second_spec)
    if a is None or b is None:
        return False
    difference = a.subtract(b, fill_value=0)
    n = int((difference.abs() > 1e-12).sum())
    return n == 0 or n >= 30


def paired_definition_safe(anchors, bins, first, second, pre=(-3,-2,-1), post=(0,1,2)):
    """Guard subtraction of two overlapping outcome definitions."""
    meta = anchors.loc[anchors.weight > 0, ["anchor_id", "subject_id", "arm"]]
    x = bins[["anchor_id", "bin", first, second]].merge(meta, on="anchor_id")
    for arm in ("DNR", "RISKSET"):
        for period in (pre, post):
            g = x.loc[x.arm.eq(arm) & x.bin.isin(period)]
            changed = g.loc[(g[first]-g[second]).abs() > 1e-9, "subject_id"].nunique()
            if 0 < changed < 30:
                return False
    # A definition can differ in many people but its pre/post contrast can
    # differ in only a few. Check each person's actual contribution to the
    # difference of contrasts, with shared weighted period denominators.
    return contrast_difference_safe(anchors, bins, (first, pre, post), (second, pre, post))


def reproduction_errors(value, archived, n):
    """Compare private arm rates, denominators and implied weighted numerators."""
    errors = {"point": abs(value["estimate"]-archived["estimate"]),
              "rate": 0.0, "denominator_h": 0.0, "numerator_per_h": 0.0}
    for arm in ("DNR", "RISKSET"):
        actual, expected = value["rates"][arm], archived["rates"][arm]
        for period in ("pre", "post"):
            # Every original index is >=24h into a living ICU observation and
            # each risk set has total weight one in each arm: pre time is 12*n.
            target_h = 12.0*n if period == "pre" else expected["post_icu_hours"]
            actual_h = actual[period+"_observed_weighted_h"]
            errors["rate"] = max(errors["rate"], abs(actual[period]-expected[period]))
            errors["denominator_h"] = max(errors["denominator_h"], abs(actual_h-target_h))
            errors["numerator_per_h"] = max(errors["numerator_per_h"],
                abs(actual[period]*actual_h-expected[period]*target_h)/target_h)
    return errors


def phenotype_audit(conn, cohort):
    """Reconcile recorded status at anchors and treated POE timestamps.

    This is a structured-record check; it cannot validate clinical conversations
    or prove an isolated CPR-only treatment intention.
    """
    a = cohort[["anchor_id", "stay_id", "anchor_time", "arm", "subtype"]]
    conn.register("validation_status_anchors", a)
    try:
        q = conn.execute("""
        WITH source_status AS (
            SELECT hadm_id,charttime,
              CASE WHEN cmo=1 THEN 'CMO' WHEN dnr=1 AND dni=1 THEN 'DNR_DNI'
                   WHEN dnr=1 THEN 'DNR_ONLY' WHEN dni=1 THEN 'DNI_ONLY'
                   WHEN fullcode=1 THEN 'FULL' ELSE 'OTHER' END AS state
            FROM mimiciv_derived.code_status
        ), latest AS (
            SELECT a.anchor_id,a.arm,a.subtype,a.anchor_time,s.hadm_id,
                   max(st.charttime) AS latest_time
            FROM validation_status_anchors a JOIN mimiciv_icu.icustays s USING(stay_id)
            JOIN mimiciv_hosp.admissions ad USING(hadm_id)
            LEFT JOIN source_status st ON st.hadm_id=s.hadm_id
              AND st.charttime>=ad.admittime AND st.charttime<=a.anchor_time
            GROUP BY a.anchor_id,a.arm,a.subtype,a.anchor_time,s.hadm_id
        ), checked AS (
            SELECT l.anchor_id,l.arm,l.subtype,l.anchor_time,l.latest_time,
                   count(DISTINCT st.state) AS n_states,min(st.state) AS state,
                   EXISTS(SELECT 1 FROM mimiciv_hosp.poe p
                     WHERE p.hadm_id=l.hadm_id AND p.ordertime=l.anchor_time
                       AND p.order_type='General Care' AND p.order_subtype='Code status') AS has_poe
            FROM latest l LEFT JOIN source_status st
              ON st.hadm_id=l.hadm_id AND st.charttime=l.latest_time
            GROUP BY l.anchor_id,l.arm,l.subtype,l.anchor_time,l.latest_time,l.hadm_id
        )
        SELECT count(*) AS n,
          count(*) FILTER(WHERE n_states<>1 OR state IS NULL
            OR (arm='DNR' AND (state<>subtype OR latest_time<>anchor_time OR NOT has_poe))
            OR (arm='RISKSET' AND state<>'FULL')) AS failures
        FROM checked
        """).fetchone()
    finally:
        conn.unregister("validation_status_anchors")
    return {"status": "PASS" if q[0] == len(cohort) and q[1] == 0 else "FAIL",
            "scope": "Structured code-status state at each anchor and treated POE timestamp",
            "clinical_intent_validated": False,
            "failure_count": 0 if q[1] == 0 else "suppressed"}


def extraction_audit(anchors, legacy, rebuilt):
    compare = legacy.merge(rebuilt, on=["anchor_id", "bin"], suffixes=("_old", "_new"),
                           validate="one_to_one")
    if len(compare) != len(legacy):
        raise AssertionError("Independent extraction changed anchor/bin coverage")
    compare = compare.merge(anchors[["anchor_id", "subject_id"]], on="anchor_id",
                            validate="many_to_one")
    records = {}
    like_for_like_pass = True
    for key, old, new in (
        ("legacy_observed_h", "observed_h_old", "legacy_observed_h"),
        ("legacy_invasive_capped_sum", "invasive_h_old", "legacy_invasive_capped_sum_h"),
        ("legacy_pressor_capped_sum", "pressor_h_old", "legacy_pressor_capped_sum_h"),
        ("legacy_map_rows", "n_map_old", "legacy_n_map_source_rows"),
        ("definition_observed_h", "observed_h_old", "observed_h_new"),
        ("definition_invasive_union", "invasive_h_old", "invasive_h_new"),
        ("definition_any_pressor_union", "pressor_h_old", "pressor_any_charted_h"),
        ("definition_map_distinct_timestamp", "n_map_old", "n_map_new"),
    ):
        delta = (compare[old]-compare[new]).abs()
        changed = compare.loc[delta > 1e-8, "subject_id"].nunique()
        if key.startswith("legacy_") and changed:
            like_for_like_pass = False
        if 0 < changed < 30:
            records[key] = {"exact_agreement": False,
                            "detail": "suppressed_small_difference_population"}
        else:
            records[key] = {"exact_agreement": changed == 0,
                            "n_people_with_different_bins": int(changed)}
    return {"status": "PASS" if like_for_like_pass else "UNRESOLVED_LIKE_FOR_LIKE_DIFFERENCE",
            "same_underlying_dataset": True,
            "independent_source_queries": True,
            "like_for_like_reconciled": like_for_like_pass,
            "definition_change_note": "Legacy-equivalent source queries must reconcile. Union intervals, positive doses and distinct MAP timestamps are separately specified changes, not automatic reproduction failures.",
            "source_tables_shared": "MIMIC-IV ICU/admission and derived ventilation/pressor/vital tables",
            "comparisons": records}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="/srv/mimic-iv/db/mimic4-v31.db")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    parser.add_argument("--legacy-code", type=Path, required=True)
    parser.add_argument("--code-commit", required=True,
                        help="Git commit freezing this implementation before the run")
    parser.add_argument("--legacy-report", type=Path,
        default=Path("/srv/mimic-iv/studies/prophecy2_dnr_20261025/dnr_fork_aggregate_report.json"))
    args = parser.parse_args()
    os.umask(0o077)
    args.dest.mkdir(parents=True, exist_ok=True, mode=0o700)
    before_db = Path(args.db).stat()
    inputs = ["risk_treated.parquet", "risk_weighted_severityhistory.parquet",
              "risk_support_bins.parquet", "risk_event_bins.parquet"]
    metadata = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": SOURCE_COMMIT,
        "frozen_implementation_commit": args.code_commit,
        "protocol_sha256": sha256(HERE/"PROTOCOL.md"),
        "implementation_sha256": {p.name: sha256(p) for p in HERE.glob("*.py")},
        "legacy_calibration_source_sha256": sha256(args.legacy_code),
        "legacy_aggregate_report_sha256": sha256(args.legacy_report),
        "input_sha256": {name: sha256(args.source/name) for name in inputs},
        "dataset": "MIMIC-IV v3.1; same single-institution dataset as original study",
        "new_external_data_downloaded": False,
        "runtime_versions": {"python": platform.python_version(),
            **{name: version(name) for name in ("numpy", "pandas", "scipy", "duckdb")}},
    }
    print("Protocol and input hashes recorded; fitting baseline-only comparisons.", flush=True)
    reference = json.loads((HERE/"original_reference.json").read_text())
    treated = pd.read_parquet(args.source/inputs[0])
    cohort = pd.read_parquet(args.source/inputs[1])
    labels = treated[["stay_id", "first_nonfull_state"]].rename(
        columns={"stay_id": "treated_id", "first_nonfull_state": "subtype"})
    cohort = cohort.merge(labels, on="treated_id", validate="many_to_one")
    if len(treated) != reference["eligible"] or cohort.arm.eq("DNR").sum() != reference["represented"]:
        raise AssertionError("Source cohort changed from frozen original release")

    # Fit every locked design before reading outcome tables or source outcomes.
    fits = {}
    memberships = {}
    private_designs = {}
    for subtype in ("DNR_ONLY", "DNR_DNI"):
        data = cohort.loc[cohort.subtype.eq(subtype)].copy()
        if data.arm.eq("DNR").sum() != reference["subtypes"][subtype]["n"]:
            raise AssertionError("Subtype count changed")
        for fold in (None, 0, 1):
            key = subtype + ("_all" if fold is None else "_part"+str(fold))
            design_data = data if fold is None else restrict_fold(data, fold)
            fitted = fit_supported(design_data)
            membership = supported_membership(design_data)
            if membership.arm.eq("DNR").sum() != fitted.diagnostics["n_treated"]:
                raise AssertionError("Disclosure membership differs from fitted design")
            memberships[key] = [membership]
            if fitted.weights is not None:
                memberships[key].append(fitted.weights.loc[fitted.weights.weight > 0,
                    ["anchor_id", "subject_id", "arm"]])
            fits[key] = fitted
            private_designs[key] = fitted.diagnostics
            if fitted.weights is not None:
                fitted.weights.to_parquet(args.dest/(key+"_restricted_weights.parquet"), index=False)
            print(key+": "+fitted.diagnostics["status"], flush=True)
    write_json(args.dest/"restricted_design_diagnostics.json", private_designs)
    # Immutable run checkpoint records decisions before the outcome stage.
    metadata["designs_frozen_at_utc"] = datetime.now(timezone.utc).isoformat()
    metadata["design_diagnostics_sha256"] = sha256(args.dest/"restricted_design_diagnostics.json")
    write_json(args.dest/"run_provenance.json", metadata)

    # Independent estimator, shared legacy calibration and cached old measurements.
    support = pd.read_parquet(args.source/inputs[2])
    monitor = pd.read_parquet(args.source/inputs[3])
    old = support[["anchor_id", "bin", "observed_h", "invasive_h", "pressor_h"]].merge(
        monitor[["anchor_id", "bin", "n_map"]], on=["anchor_id", "bin"], validate="one_to_one")
    legacy_rebalance = legacy_calibrator(args.legacy_code)
    archived = json.loads(args.legacy_report.read_text())
    reproduction = {}
    for subtype in ("DNR_ONLY", "DNR_DNI"):
        data, _ = legacy_rebalance(cohort.loc[cohort.subtype.eq(subtype)].copy())
        errors = {}
        archived_subtype = archived["subtypes"][subtype]
        if archived_subtype["n"] != reference["subtypes"][subtype]["n"]:
            raise AssertionError("Archived subtype count differs from public release")
        for published, outcome in OUTCOME_MAP.items():
            # Existing published contrasts only. Private calculation may inspect
            # all cells; release exposes only agreement, not new small-cell values.
            value = contrast(data, old, outcome, min_cell=1)
            expected = archived_subtype["outcomes"][ARCHIVE_MAP[published]]["main_minus12_to_plus12"]
            if abs(expected["estimate"]-reference["subtypes"][subtype]["primary"][published]["estimate"]) > 1e-12:
                raise AssertionError("Archived result differs from immutable public release")
            errors[published] = reproduction_errors(value, expected, archived_subtype["n"])
        maxima = {kind: float(max(err[kind] for err in errors.values()))
                  for kind in ("point", "rate", "denominator_h", "numerator_per_h")}
        reproduction[subtype] = {"status": "PASS" if max(maxima.values()) <= 1e-8 else "FAIL",
                                "maximum_absolute_errors": maxima,
                                "pre_denominator_reference": "12 hours per original risk set; each arm sums to one per set",
                                "numerator_reference": "Reconstructed from archived arm rates and denominator; numerator error normalized by denominator"}
    if any(x["status"] != "PASS" for x in reproduction.values()):
        write_json(args.dest/"reproduction_failure.json", reproduction)
        raise AssertionError("Independent arithmetic did not reproduce the published points")
    print("Independent original rates, numerators, denominators and contrasts reconciled.", flush=True)

    import duckdb
    conn = duckdb.connect(str(args.db), read_only=True)
    conn.execute("SET threads=4")
    conn.execute("SET memory_limit='10GB'")
    conn.execute("SET preserve_insertion_order=false")
    try:
        phenotype = phenotype_audit(conn, cohort)
        print("Structured status reconciliation: "+phenotype["status"], flush=True)
        if phenotype["status"] != "PASS":
            raise AssertionError("Structured status provenance failed")
        rebuilt = build_outcomes(conn, cohort)
        states = build_state_frame(conn, cohort, horizons=(4,12))
    finally:
        conn.close()
    audit = extraction_audit(cohort, old, rebuilt)
    if audit["status"] != "PASS":
        write_json(args.dest/"extraction_failure.json", audit)
        raise AssertionError("Independent legacy-equivalent source extraction did not reconcile")
    print("Independent source extraction completed; applying frozen weights.", flush=True)
    disclosure_safe = {}
    for subtype in ("DNR_ONLY", "DNR_DNI"):
        population = cohort.loc[cohort.subtype.eq(subtype)]
        membership_sets = [frame for key, frames in memberships.items()
                           if key.startswith(subtype+"_") for frame in frames]
        disclosure_safe[subtype] = bool(population_disclosure_safe(population, membership_sets))
    results = {}
    for key, fitted in fits.items():
        subtype = "DNR_ONLY" if key.startswith("DNR_ONLY") else "DNR_DNI"
        result = {"design": public_fit(fitted.diagnostics, disclosure_safe[subtype])}
        if fitted.weights is None:
            result["outcome_status"] = "NOT_ESTIMATED_DESIGN_FAILED"
            results[key] = result
            continue
        a = cohort.drop(columns="weight").merge(
            fitted.weights[["anchor_id", "weight"]], on="anchor_id", validate="one_to_one")
        outcome_results = {}
        for outcome in ("invasive_h", "pressor_h", "n_map"):
            outcome_results[outcome] = public_contrast(contrast(a, rebuilt, outcome))
        if contrast_difference_safe(a, rebuilt, ("invasive_h", (-3,-2,-1), (0,1,2)),
                                    ("invasive_h", (-1,), (0,))):
            outcome_results["invasive_h_near_order"] = public_contrast(
                contrast(a, rebuilt, "invasive_h", pre=(-1,), post=(0,)))
        else:
            outcome_results["invasive_h_near_order"] = {"status": "suppressed",
                "reason": "Small population distinguishable by comparing time windows"}
        for primary, sensitivity in (("invasive_h", "invasive_plus_trach_h"),
                                     ("pressor_h", "pressor_any_charted_h"),
                                     ("n_map", "n_map_source_rows")):
            if paired_definition_safe(a, rebuilt, primary, sensitivity):
                outcome_results[sensitivity] = public_contrast(contrast(a, rebuilt, sensitivity))
            else:
                outcome_results[sensitivity] = {"status": "suppressed",
                    "reason": "Small population distinguishable by subtracting definitions"}
        result["outcomes"] = outcome_results
        s = states.loc[states.anchor_id.isin(a.anchor_id)].copy()
        if result["design"]["count_disclosure"] == "released":
            result["followup_states"] = summarize_state_frame(a, s)
        else:
            result["followup_states"] = {"status": "suppressed",
                "reason": "Small nested population change from already published cohort"}
        estimate = outcome_results["invasive_h"]
        ci = estimate.get("ci95_conditional_patient_cluster")
        result["primary_association_status"] = (
            "NEGATIVE_CONDITIONAL_ASSOCIATION" if ci and ci[1] < 0 else
            "POSITIVE_CONDITIONAL_ASSOCIATION" if ci and ci[0] > 0 else
            "INCONCLUSIVE" if ci else "NOT_PUBLICLY_ESTIMABLE")
        result["outcome_status"] = "ESTIMATED_WITH_CONDITIONAL_UNCERTAINTY"
        results[key] = result

    internal = {}
    for subtype in ("DNR_ONLY", "DNR_DNI"):
        parts = [results[subtype+"_part"+str(k)] for k in (0,1)]
        pass_design = all(p["design"]["gate_pass"] for p in parts)
        statuses = [p.get("primary_association_status", "DESIGN_FAILED") for p in parts]
        internal[subtype] = {
            "patient_disjoint": True,
            "both_designs_pass": pass_design,
            "both_negative_conditional_intervals": all(s == "NEGATIVE_CONDITIONAL_ASSOCIATION" for s in statuses),
            "part_statuses": statuses,
            "external_replication": False,
        }
    after_db = Path(args.db).stat()
    unchanged = (before_db.st_size, before_db.st_mtime_ns) == (after_db.st_size, after_db.st_mtime_ns)
    if not unchanged:
        raise AssertionError("Source database metadata changed during validation")
    metadata["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    metadata["database_opened_read_only"] = True
    metadata["database_size_and_mtime_unchanged"] = unchanged
    report = {
        "schema_version": 1, "kind": "dnr-internal-validation", "track": "prophecy-2",
        "title": "Independent computation and supported-comparison audit of newly documented DNR",
        "provenance": metadata,
        "numerical_reproduction": reproduction,
        "reproduction_scope": "Reused original baseline calibration; independent contrast arithmetic on identical cached measurements. Archived arm rates, weighted denominators, rate-implied numerators and point estimates compared; new conditional intervals use G/(G-1) finite-sample correction.",
        "structured_status_audit": phenotype,
        "independent_extraction": audit,
        "analyses": results,
        "internal_checks": internal,
        "limitations": {
            "external_replication": "NOT_ESTABLISHED; same hospital dataset",
            "clinical_intent_validation": "NOT_ESTABLISHED; structured labels do not verify isolated CPR-only intent",
            "full_pipeline_uncertainty": "NOT_ESTABLISHED; intervals condition on fitted design and weights",
            "causal_identification": "NOT_ESTABLISHED",
            "independent_clinical_review": "PENDING",
            "previously_unseen_data": False,
            "original_unmatched_events_recovered": False,
            "outcome_inference": "Exploratory observed-person-time associations; death and ICU exit change observation",
        },
        "disclosure": "Aggregate only; minimum 30 distinct people in nonzero outcome cells; joint state and paired-definition suppression; arm means/denominators omitted to limit nested-cohort disclosure",
    }
    # No patient identifier keys can pass the public boundary.
    def check(value):
        if isinstance(value, dict):
            for k,v in value.items():
                if k in {"subject_id", "stay_id", "hadm_id", "anchor_id", "patient_id", "treated_id", "rows"}:
                    raise AssertionError("Forbidden field in aggregate report")
                check(v)
        elif isinstance(value, list):
            for v in value: check(v)
    check(report)
    write_json(args.dest/"validation_aggregate.json", report)
    print("Aggregate validation report completed. External replication and causal identification remain unestablished.", flush=True)


if __name__ == "__main__":
    main()
