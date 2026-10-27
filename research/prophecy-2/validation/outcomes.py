"""Independent, read-only outcome reconstruction for the DNR validation study.

This module reads the SAME MIMIC-IV v3.1 source/derived tables as the exploratory
study. It independently implements interval arithmetic and aggregate estimators;
it is not an external replication or an independent clinical phenotype review.

Patient/anchor-level DataFrames are internal, restricted-server objects. Nothing
in this module prints, writes, exports, or connects to a database. The caller must
supply a DuckDB connection opened with read_only=True. Registered pandas relations
are transient and removed before returning. Aggregate release requires the
caller's complete complementary-suppression review in addition to the safeguards
here. In particular, comparing multiple released specifications can disclose
small cells even if each individual result passes a threshold.

Definitions: bins are half-open four-hour intervals [-24h,+12h), clipped at ICU
entry, ICU exit, and recorded in-hospital death. Support is the UNION of valid
source intervals, never a capped sum. pressor_h uses a finite positive recorded
norepinephrine-equivalent dose; pressor_any_charted_h retains all valid charted
intervals, including zero/missing dose, as a sensitivity. n_map counts distinct
chart timestamps having either MAP field; n_map_source_rows audits duplicates.
No later code-status transition censors a control in these primary outcomes.

Separate legacy_* audit columns reconstruct the old SQL conventions independently:
no ICU-entry clipping, datediff('second') observation time, capped sums of strict
InvasiveVent intervals, capped sums of exactly deduplicated all-dose pressor
intervals, and MAP source-row counts. These columns are for like-for-like source
reconciliation; they are not new primary outcomes or union-exposure estimates.
"""

from contextlib import contextmanager
from math import isfinite, sqrt
from statistics import NormalDist
from uuid import uuid4

import numpy as np
import pandas as pd


BINS = tuple(range(-6, 3))
ARMS = ("DNR", "RISKSET")
HOUR_OUTCOMES = (
    "invasive_h", "invasive_plus_trach_h", "pressor_h",
    "pressor_positive_h", "pressor_any_charted_h",
)
OUTCOMES = HOUR_OUTCOMES + ("n_map", "n_map_source_rows")
LEGACY_AUDIT_COLUMNS = (
    "legacy_observed_h", "legacy_invasive_capped_sum_h",
    "legacy_pressor_capped_sum_h", "legacy_n_map_source_rows",
)
STATE_LABELS = (
    "dead", "left_icu_no_recorded_hospital_death", "alive_icu_invasive", "alive_icu_not_invasive",
)
INCLUSIVE_STATE_LABELS = (
    "dead", "left_icu_no_recorded_hospital_death", "alive_icu_invasive_or_tracheostomy",
    "alive_icu_no_invasive_or_tracheostomy",
)


def _require(frame, columns):
    if not isinstance(frame, pd.DataFrame) or not set(columns).issubset(frame.columns):
        raise ValueError("Required data columns are missing")


def _checked_anchors(anchors):
    _require(anchors, ("anchor_id", "stay_id", "anchor_time"))
    if anchors.empty or anchors.anchor_id.isna().any() or not anchors.anchor_id.is_unique:
        raise ValueError("Anchors must be nonempty with unique non-null anchor identifiers")
    out = anchors[["anchor_id", "stay_id", "anchor_time"]].copy()
    try:
        stay = pd.to_numeric(out.stay_id, errors="raise")
        times = pd.to_datetime(out.anchor_time, errors="raise")
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Anchor stay identifiers or timestamps are invalid") from None
    if stay.isna().any() or not np.isfinite(stay).all() or not (stay % 1 == 0).all():
        raise ValueError("Stay identifiers must be finite integers")
    if times.isna().any() or getattr(times.dt, "tz", None) is not None:
        raise ValueError("Anchor timestamps must be non-null and timezone-naive")
    out["stay_id"] = stay.astype("int64")
    out["anchor_time"] = times
    return out


@contextmanager
def _registered(conn, frame):
    name = "_dnr_validation_" + uuid4().hex
    conn.register(name, frame)
    try:
        yield name
    finally:
        conn.unregister(name)


def _bounds(conn, anchors):
    """Re-read observation limits; never trust a previous outcome parquet."""
    checked = _checked_anchors(anchors)
    with _registered(conn, checked) as name:
        result = conn.execute(f"""
            SELECT a.anchor_id, a.stay_id, a.anchor_time, s.subject_id,
                   s.intime, s.outtime, h.deathtime
            FROM {name} a
            JOIN mimiciv_icu.icustays s ON s.stay_id = a.stay_id
            JOIN mimiciv_hosp.admissions h ON h.hadm_id = s.hadm_id
        """).df()
    if len(result) != len(checked) or not result.anchor_id.is_unique:
        raise ValueError("Every anchor must resolve to exactly one ICU stay and admission")
    if result[["subject_id", "intime", "outtime"]].isna().any().any():
        raise ValueError("Source observation limits or patient identifiers are missing")
    for col in ("anchor_time", "intime", "outtime", "deathtime"):
        result[col] = pd.to_datetime(result[col])
    if ((result.anchor_time < result.intime)
            | (result.anchor_time >= result.outtime)
            | (result.deathtime.notna() & (result.deathtime <= result.anchor_time))).any():
        raise ValueError("All anchors must occur during a living ICU observation interval")
    if "subject_id" in anchors.columns:
        check = anchors[["anchor_id", "subject_id"]].merge(
            result[["anchor_id", "subject_id"]], on="anchor_id", validate="one_to_one")
        if not check.subject_id_x.eq(check.subject_id_y).all():
            raise ValueError("Supplied patient identifiers disagree with source ICU stays")
    return result


def interval_union_hours(intervals, start, end):
    """Small pure-Python arithmetic oracle used by the synthetic test suite.

    Accepts (start, end) timestamp pairs. Missing/reversed/empty source intervals
    contribute nothing. Touching intervals are joined, and all intervals are
    clipped to the half-open observation window before unioning.
    """
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if pd.isna(start) or pd.isna(end):
        raise ValueError("Observation limits cannot be missing")
    if end <= start:
        return 0.0
    pieces = []
    for left, right in intervals:
        if pd.isna(left) or pd.isna(right):
            continue
        left, right = pd.Timestamp(left), pd.Timestamp(right)
        left, right = max(left, start), min(right, end)
        if right > left:
            pieces.append((left, right))
    total = pd.Timedelta(0)
    current = None
    for left, right in sorted(pieces):
        if current is None:
            current = (left, right)
        elif left <= current[1]:
            current = (current[0], max(current[1], right))
        else:
            total += current[1] - current[0]
            current = (left, right)
    if current is not None:
        total += current[1] - current[0]
    return float(total.total_seconds() / 3600.0)


def _legacy_audit_bins(conn, bounds):
    """Rebuild the legacy 43/52 SQL definitions from source tables, not caches.

    `bounds` has already been independently resolved from ICU/admission tables.
    The old windows deliberately do not clip at ICU entry. Ventilation source
    duplicates remain separate contributions. Pressor intervals are deduplicated
    on (stay_id,starttime,endtime), regardless of dose, before capped summation.
    Use datediff-second arithmetic exactly, including its subsecond boundary
    behavior; changing it to epoch arithmetic would not reproduce the old SQL.
    """
    with _registered(conn, bounds) as name:
        result = conn.execute(f"""
        WITH windows AS (
            SELECT a.anchor_id,a.stay_id,k.i AS bin,
                   a.anchor_time+k.i*INTERVAL '4 hours' AS lo,
                   least(a.outtime,coalesce(a.deathtime,a.outtime),
                         a.anchor_time+(k.i+1)*INTERVAL '4 hours') AS hi
            FROM {name} a CROSS JOIN range(-6,3) k(i)
        ), active AS (
            SELECT * FROM windows WHERE hi>lo
        ), ranges AS (
            SELECT stay_id,min(lo) AS lo,max(hi) AS hi
            FROM active GROUP BY stay_id
        ), vent_source AS (
            SELECT v.stay_id,v.starttime,v.endtime
            FROM mimiciv_derived.ventilation v JOIN ranges r USING(stay_id)
            WHERE v.ventilation_status='InvasiveVent'
              AND v.starttime<r.hi AND v.endtime>r.lo
        ), press_source AS (
            SELECT DISTINCT p.stay_id,p.starttime,p.endtime
            FROM mimiciv_derived.norepinephrine_equivalent_dose p
            JOIN ranges r USING(stay_id)
            WHERE p.endtime>p.starttime
              AND p.starttime<r.hi AND p.endtime>r.lo
        ), vent AS (
            SELECT b.anchor_id,b.bin,
                   coalesce(sum(greatest(0.0,datediff('second',
                       greatest(v.starttime,b.lo),least(v.endtime,b.hi))/3600.0))
                       FILTER(WHERE v.stay_id IS NOT NULL),0.0) AS raw_h
            FROM active b LEFT JOIN vent_source v
              ON v.stay_id=b.stay_id AND v.starttime<b.hi AND v.endtime>b.lo
            GROUP BY b.anchor_id,b.bin
        ), press AS (
            SELECT b.anchor_id,b.bin,
                   coalesce(sum(greatest(0.0,datediff('second',
                       greatest(p.starttime,b.lo),least(p.endtime,b.hi))/3600.0))
                       FILTER(WHERE p.stay_id IS NOT NULL),0.0) AS raw_h
            FROM active b LEFT JOIN press_source p
              ON p.stay_id=b.stay_id AND p.starttime<b.hi AND p.endtime>b.lo
            GROUP BY b.anchor_id,b.bin
        ), maps AS (
            SELECT b.anchor_id,b.bin,count(v.charttime) FILTER (
                       WHERE coalesce(v.mbp,v.mbp_ni) IS NOT NULL) AS n_map
            FROM active b LEFT JOIN mimiciv_derived.vitalsign v
              ON v.stay_id=b.stay_id AND v.charttime>=b.lo AND v.charttime<b.hi
            GROUP BY b.anchor_id,b.bin
        ), observed AS (
            SELECT *,greatest(0.0,datediff('second',lo,hi)/3600.0) AS hours
            FROM windows
        )
        SELECT b.anchor_id,b.bin,b.hours AS legacy_observed_h,
               least(b.hours,coalesce(v.raw_h,0.0)) AS legacy_invasive_capped_sum_h,
               least(b.hours,coalesce(p.raw_h,0.0)) AS legacy_pressor_capped_sum_h,
               coalesce(m.n_map,0) AS legacy_n_map_source_rows
        FROM observed b LEFT JOIN vent v USING(anchor_id,bin)
        LEFT JOIN press p USING(anchor_id,bin)
        LEFT JOIN maps m USING(anchor_id,bin)
        ORDER BY b.anchor_id,b.bin
        """).df()
    if len(result) != 9 * len(bounds) or result[["anchor_id", "bin"]].duplicated().any():
        raise AssertionError("Legacy audit did not produce exactly nine bins per anchor")
    values = result[list(LEGACY_AUDIT_COLUMNS)].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise AssertionError("Legacy audit values must be finite and nonnegative")
    if (result.legacy_observed_h > 4.0 + 1e-8).any():
        raise AssertionError("Legacy observation time exceeds four hours")
    for col in ("legacy_invasive_capped_sum_h", "legacy_pressor_capped_sum_h"):
        if (result[col] > result.legacy_observed_h + 1e-8).any():
            raise AssertionError("Legacy capped support exceeds legacy observation time")
    return result


def build_outcomes(conn, anchors):
    """Return one internal row per anchor/bin, reconstructing from source tables.

    Required anchor fields: anchor_id, stay_id, anchor_time. A supplied subject_id
    is checked against source data. Metadata/weights are not used to build outcomes.
    No source rows outside the selected stay/time ranges are returned to Python.
    """
    bounds = _bounds(conn, anchors)
    with _registered(conn, bounds) as name:
        result = conn.execute(f"""
        WITH windows AS (
            SELECT a.anchor_id, a.stay_id, k.i AS bin,
                   greatest(a.intime, a.anchor_time + k.i * INTERVAL '4 hours') AS lo,
                   least(a.outtime, coalesce(a.deathtime, a.outtime),
                         a.anchor_time + (k.i+1) * INTERVAL '4 hours') AS hi
            FROM {name} a CROSS JOIN range(-6, 3) k(i)
        ), active AS (
            SELECT * FROM windows WHERE hi > lo
        ), ranges AS (
            SELECT stay_id, min(lo) AS lo, max(hi) AS hi
            FROM active GROUP BY stay_id
        ), vent_source AS (
            SELECT v.stay_id, v.starttime, v.endtime, v.ventilation_status
            FROM mimiciv_derived.ventilation v JOIN ranges r USING(stay_id)
            WHERE v.endtime > v.starttime AND v.starttime < r.hi AND v.endtime > r.lo
              AND v.ventilation_status IN ('InvasiveVent', 'Tracheostomy')
        ), press_source AS (
            SELECT p.stay_id, p.starttime, p.endtime,
                   try_cast(p.norepinephrine_equivalent_dose AS DOUBLE) AS dose
            FROM mimiciv_derived.norepinephrine_equivalent_dose p
            JOIN ranges r USING(stay_id)
            WHERE p.endtime > p.starttime AND p.starttime < r.hi AND p.endtime > r.lo
        ), interval_candidates AS (
            SELECT b.anchor_id, b.bin, 'invasive_h' AS channel,
                   greatest(v.starttime,b.lo) AS lo, least(v.endtime,b.hi) AS hi
            FROM active b JOIN vent_source v USING(stay_id)
            WHERE v.starttime < b.hi AND v.endtime > b.lo
              AND v.ventilation_status = 'InvasiveVent'
            UNION ALL
            SELECT b.anchor_id, b.bin, 'invasive_plus_trach_h',
                   greatest(v.starttime,b.lo), least(v.endtime,b.hi)
            FROM active b JOIN vent_source v USING(stay_id)
            WHERE v.starttime < b.hi AND v.endtime > b.lo
            UNION ALL
            SELECT b.anchor_id, b.bin, 'pressor_positive_h',
                   greatest(p.starttime,b.lo), least(p.endtime,b.hi)
            FROM active b JOIN press_source p USING(stay_id)
            WHERE p.starttime < b.hi AND p.endtime > b.lo
              AND isfinite(p.dose) AND p.dose > 0
            UNION ALL
            SELECT b.anchor_id, b.bin, 'pressor_any_charted_h',
                   greatest(p.starttime,b.lo), least(p.endtime,b.hi)
            FROM active b JOIN press_source p USING(stay_id)
            WHERE p.starttime < b.hi AND p.endtime > b.lo
        ), intervals AS (
            -- Unique sort keys make island numbering deterministic even if the
            -- source has exact duplicates or clipping makes intervals identical.
            SELECT DISTINCT anchor_id,bin,channel,lo,hi FROM interval_candidates
        ), previous AS (
            SELECT *, max(hi) OVER (
                PARTITION BY anchor_id,bin,channel ORDER BY lo,hi
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prior_hi
            FROM intervals
        ), numbered AS (
            SELECT *, sum(CASE WHEN prior_hi IS NULL OR lo > prior_hi THEN 1 ELSE 0 END)
                OVER (PARTITION BY anchor_id,bin,channel ORDER BY lo,hi
                      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS island
            FROM previous
        ), unions AS (
            SELECT anchor_id,bin,channel,island,min(lo) AS lo,max(hi) AS hi
            FROM numbered GROUP BY anchor_id,bin,channel,island
        ), durations AS (
            SELECT anchor_id,bin,channel,sum(epoch(hi-lo)/3600.0) AS hours
            FROM unions GROUP BY anchor_id,bin,channel
        ), support AS (
            SELECT anchor_id,bin,
                   sum(hours) FILTER(WHERE channel='invasive_h') AS invasive_h,
                   sum(hours) FILTER(WHERE channel='invasive_plus_trach_h') AS invasive_plus_trach_h,
                   sum(hours) FILTER(WHERE channel='pressor_positive_h') AS pressor_positive_h,
                   sum(hours) FILTER(WHERE channel='pressor_any_charted_h') AS pressor_any_charted_h
            FROM durations GROUP BY anchor_id,bin
        ), maps AS (
            SELECT b.anchor_id,b.bin,
                   count(DISTINCT v.charttime) FILTER (
                       WHERE coalesce(v.mbp,v.mbp_ni) IS NOT NULL) AS n_map,
                   count(v.charttime) FILTER (
                       WHERE coalesce(v.mbp,v.mbp_ni) IS NOT NULL) AS n_map_source_rows
            FROM active b LEFT JOIN mimiciv_derived.vitalsign v
              ON v.stay_id=b.stay_id AND v.charttime>=b.lo AND v.charttime<b.hi
            GROUP BY b.anchor_id,b.bin
        )
        SELECT b.anchor_id,b.bin,greatest(0.0,epoch(b.hi-b.lo)/3600.0) AS observed_h,
               coalesce(s.invasive_h,0.0) AS invasive_h,
               coalesce(s.invasive_plus_trach_h,0.0) AS invasive_plus_trach_h,
               coalesce(s.pressor_positive_h,0.0) AS pressor_h,
               coalesce(s.pressor_positive_h,0.0) AS pressor_positive_h,
               coalesce(s.pressor_any_charted_h,0.0) AS pressor_any_charted_h,
               coalesce(m.n_map,0) AS n_map,
               coalesce(m.n_map_source_rows,0) AS n_map_source_rows
        FROM windows b LEFT JOIN support s USING(anchor_id,bin)
        LEFT JOIN maps m USING(anchor_id,bin)
        ORDER BY b.anchor_id,b.bin
        """).df()
    if len(result) != 9 * len(bounds) or result[["anchor_id", "bin"]].duplicated().any():
        raise AssertionError("Outcome construction did not produce exactly nine bins per anchor")
    _validate_bins(result, OUTCOMES)
    legacy = _legacy_audit_bins(conn, bounds)
    combined = result.merge(legacy, on=["anchor_id", "bin"], validate="one_to_one")
    if len(combined) != len(result):
        raise AssertionError("Legacy reconciliation changed primary outcome-bin coverage")
    return combined


def _validate_bins(bins, outcomes):
    _require(bins, ("anchor_id", "bin", "observed_h", *outcomes))
    if bins[["anchor_id", "bin"]].duplicated().any():
        raise ValueError("Duplicate anchor/bin rows are not allowed")
    cols = ["observed_h", *outcomes]
    values = bins[cols].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Outcome values and observed time must be finite and nonnegative")
    if (bins.observed_h > 4.0 + 1e-8).any():
        raise ValueError("Observed bin time exceeds four hours")
    for col in outcomes:
        if col in HOUR_OUTCOMES and (bins[col] > bins.observed_h + 1e-8).any():
            raise ValueError("Unioned support exceeds observed ICU time")
        if (bins.loc[bins.observed_h == 0, col] != 0).any():
            raise ValueError("Unobserved bins must have zero outcome values")


def _analysis_anchors(anchors):
    _require(anchors, ("anchor_id", "subject_id", "arm", "weight"))
    result = anchors[["anchor_id", "subject_id", "arm", "weight"]].copy()
    if result.empty or result[["anchor_id", "subject_id", "arm", "weight"]].isna().any().any():
        raise ValueError("Analysis metadata must be nonempty and complete")
    if not result.anchor_id.is_unique or set(result.arm.unique()) != set(ARMS):
        raise ValueError("Analysis needs unique anchors and exactly DNR/RISKSET arms")
    if not np.isfinite(result.weight).all() or (result.weight < 0).any():
        raise ValueError("Analysis weights must be finite and nonnegative")
    if (result.groupby("arm").weight.sum() <= 0).any():
        raise ValueError("Both arms need positive total analysis weight")
    return result


def _check_min_cell(min_cell):
    if isinstance(min_cell, bool) or not isinstance(min_cell, (int, np.integer)) or min_cell < 1:
        raise ValueError("min_cell must be a positive integer")


def contrast(anchors, bins, outcome, pre=(-3, -2, -1), post=(0, 1, 2), *, min_cell=30):
    """Weighted difference in changes of observed-person-time rates.

    The CI clusters each patient's contributions across every anchor and both
    arms. It conditions on the cohort, matching and fitted weights; it omits
    design selection, weight-estimation and specification uncertainty. It is
    neither a patient-level policy effect nor a causal confidence interval.
    Root orchestration may add design/bootstrap uncertainty independently.
    min_cell<30 is intended solely for synthetic tests, not public release.
    """
    _check_min_cell(min_cell)
    if outcome not in OUTCOMES:
        raise ValueError("Unknown outcome definition")
    pre, post = tuple(pre), tuple(post)
    all_bins = pre + post
    if (not pre or not post or len(set(all_bins)) != len(all_bins)
            or not set(all_bins).issubset(BINS)):
        raise ValueError("Pre and post windows must be disjoint, nonempty valid bins")
    frame = _analysis_anchors(anchors)
    selected = bins.loc[bins.anchor_id.isin(frame.anchor_id) & bins.bin.isin(all_bins)].copy()
    _validate_bins(selected, (outcome,))
    sizes = selected.groupby("anchor_id").size()
    if len(sizes) != len(frame) or not sizes.eq(len(all_bins)).all():
        raise ValueError("Every analyzed anchor must have every requested bin, including empty bins")
    selected["period"] = np.where(selected.bin.isin(pre), "pre", "post")
    summed = selected.groupby(["anchor_id", "period"])[[outcome, "observed_h"]].sum().unstack()
    summed.columns = [f"{col}_{period}" for col, period in summed.columns]
    frame = frame.merge(summed, left_on="anchor_id", right_index=True, validate="one_to_one")
    active = frame.loc[frame.weight > 0]
    suppressed = {"status": "suppressed", "reason": "Minimum patient-cell threshold not met",
                  "outcome": outcome, "estimate": None,
                  "ci95_conditional_patient_cluster": None, "rates": None}
    for _, group in active.groupby("arm"):
        if group.subject_id.nunique() < min_cell:
            return suppressed
        # Continuous exposure rates can still disclose sparse outcome contributors.
        for period in ("pre", "post"):
            for condition in (group[f"{outcome}_{period}"] > 0,
                              group[f"{outcome}_{period}"] == 0):
                n = group.loc[condition, "subject_id"].nunique()
                if 0 < n < min_cell:
                    return suppressed
    rates, scores = {}, []
    for arm in ARMS:
        group = active.loc[active.arm == arm]
        numerator, denominator = {}, {}
        for period in ("pre", "post"):
            numerator[period] = float((group.weight * group[f"{outcome}_{period}"]).sum())
            denominator[period] = float((group.weight * group[f"observed_h_{period}"]).sum())
        if min(denominator.values()) <= 0:
            return {"status": "not_estimable", "reason": "An arm/period has no observed ICU time",
                    "outcome": outcome, "estimate": None,
                    "ci95_conditional_patient_cluster": None, "rates": None}
        rate = {p: numerator[p] / denominator[p] for p in ("pre", "post")}
        rate.update(change=rate["post"] - rate["pre"],
                    pre_observed_weighted_h=denominator["pre"],
                    post_observed_weighted_h=denominator["post"])
        rates[arm] = rate
        derivative = sum(
            sign * group.weight * (group[f"{outcome}_{p}"] - rate[p] * group[f"observed_h_{p}"])
            / denominator[p]
            for p, sign in (("post", 1.0), ("pre", -1.0))
        )
        if arm == "RISKSET":
            derivative = -derivative
        scores.append(pd.DataFrame({"subject_id": group.subject_id, "score": derivative}))
    clustered = pd.concat(scores).groupby("subject_id").score.sum()
    n_clusters = len(clustered)
    if n_clusters < 2:
        return {"status": "not_estimable", "reason": "Fewer than two patient clusters",
                "outcome": outcome, "estimate": None,
                "ci95_conditional_patient_cluster": None, "rates": None}
    se = sqrt(float(np.square(clustered).sum()) * n_clusters / (n_clusters - 1))
    estimate = rates["DNR"]["change"] - rates["RISKSET"]["change"]
    z = NormalDist().inv_cdf(0.975)
    return {
        "status": "ok", "outcome": outcome,
        "estimand": "difference in changes of weighted observed-ICU-person-time rates",
        "estimate": float(estimate), "se_conditional_patient_cluster": float(se),
        "ci95_conditional_patient_cluster": [float(estimate-z*se), float(estimate+z*se)],
        "ci_method": "normal approximation; patient-cluster sandwich with G/(G-1) correction",
        "conditional_on": "selected anchors, matched risk sets, and fitted analysis weights",
        "rates": rates, "pre_bins": list(pre), "post_bins": list(post),
        "n_patient_clusters": n_clusters,
    }


def _classify_states(frame):
    """Classify death first; absence of ventilation after death is never 'off'."""
    dead = frame.deathtime.notna() & (frame.deathtime <= frame["at_time"])
    exited = frame.outtime <= frame["at_time"]
    out = frame[["anchor_id", "subject_id", "horizon_h"]].copy()
    out["state"] = np.select(
        [dead, exited, frame.invasive_active.astype(bool)], STATE_LABELS[:3],
        default=STATE_LABELS[3])
    out["state_inclusive"] = np.select(
        [dead, exited, frame.inclusive_active.astype(bool)], INCLUSIVE_STATE_LABELS[:3],
        default=INCLUSIVE_STATE_LABELS[3])
    return out


def build_state_frame(conn, anchors, horizons=(4, 12)):
    """Return internal mutually exclusive states at exact post-anchor horizons.

    The ICU-exit state means no recorded in-hospital death by that horizon. Death
    outside the index admission is not ascertained. Tracheostomy is included only
    in state_inclusive and does not by itself prove active mechanical ventilation.
    """
    horizons = tuple(horizons)
    if (not horizons or len(set(horizons)) != len(horizons)
            or any(isinstance(h, bool) or not isfinite(float(h)) or float(h) < 0 for h in horizons)):
        raise ValueError("State horizons must be distinct nonnegative finite hours")
    bounds = _bounds(conn, anchors)
    horizon_frame = pd.DataFrame({"horizon_h": [float(h) for h in horizons]})
    with _registered(conn, bounds) as name, _registered(conn, horizon_frame) as hname:
        states = conn.execute(f"""
            WITH points AS (
                SELECT a.anchor_id,a.stay_id,a.subject_id,a.outtime,a.deathtime,h.horizon_h,
                       a.anchor_time+h.horizon_h*INTERVAL '1 hour' AS at_time
                FROM {name} a CROSS JOIN {hname} h
            )
            SELECT p.anchor_id,p.subject_id,p.horizon_h,p.at_time,p.outtime,p.deathtime,
                   coalesce(bool_or(v.ventilation_status='InvasiveVent'),false) AS invasive_active,
                   coalesce(bool_or(v.ventilation_status IN ('InvasiveVent','Tracheostomy')),false)
                       AS inclusive_active
            FROM points p LEFT JOIN mimiciv_derived.ventilation v
              ON v.stay_id=p.stay_id AND v.starttime<=p.at_time AND v.endtime>p.at_time
             AND v.endtime>v.starttime
             AND v.ventilation_status IN ('InvasiveVent','Tracheostomy')
            GROUP BY p.anchor_id,p.subject_id,p.horizon_h,p.at_time,p.outtime,p.deathtime
            ORDER BY p.anchor_id,p.horizon_h
        """).df()
    if len(states) != len(bounds) * len(horizons):
        raise AssertionError("State construction lost or duplicated anchors")
    for col in ("at_time", "outtime", "deathtime"):
        states[col] = pd.to_datetime(states[col])
    return _classify_states(states)


def summarize_state_frame(anchors, states, *, min_cell=30):
    """Produce aggregate-only partitions, suppressing the complete arm/horizon
    if ANY nonzero marginal OR joint-definition cell is smaller than min_cell
    patients. The joint check prevents the nested invasive/tracheostomy definitions
    from revealing a small tracheostomy-only group by subtraction.
    """
    _check_min_cell(min_cell)
    metadata = _analysis_anchors(anchors)
    _require(states, ("anchor_id", "subject_id", "horizon_h", "state", "state_inclusive"))
    if states[["anchor_id", "horizon_h"]].duplicated().any():
        raise ValueError("Duplicate anchor/horizon states are not allowed")
    horizons = sorted(states.horizon_h.unique().tolist())
    if not horizons or len(states) != len(metadata) * len(horizons):
        raise ValueError("Every analyzed anchor needs every horizon state")
    frame = states.merge(metadata, on=["anchor_id", "subject_id"], validate="many_to_one")
    if len(frame) != len(states):
        raise ValueError("State/anchor identifiers disagree")
    frame = frame.loc[frame.weight > 0]
    records = []
    for horizon in horizons:
        for arm in ARMS:
            group = frame.loc[(frame.arm == arm) & (frame.horizon_h == horizon)]
            suppress = group.subject_id.nunique() < min_cell
            for column, labels in (("state", STATE_LABELS), ("state_inclusive", INCLUSIVE_STATE_LABELS)):
                if not set(group[column]).issubset(labels):
                    raise ValueError("Unexpected state label")
                counts = group.groupby(column).subject_id.nunique()
                suppress |= bool(((counts > 0) & (counts < min_cell)).any())
            joint_counts = group.groupby(["state", "state_inclusive"]).subject_id.nunique()
            suppress |= bool(((joint_counts > 0) & (joint_counts < min_cell)).any())
            record = {"horizon_h": float(horizon), "arm": arm,
                      "status": "suppressed" if suppress else "ok"}
            if suppress:
                record["reason"] = "Minimum patient-cell threshold not met; whole partition suppressed"
            else:
                total = float(group.weight.sum())
                for column, labels in (("state", STATE_LABELS), ("state_inclusive", INCLUSIVE_STATE_LABELS)):
                    record[column] = {
                        label: {"weighted_fraction": float(group.loc[group[column] == label, "weight"].sum()/total)}
                        for label in labels
                    }
            records.append(record)
    return {
        "definition": "Mutually exclusive fixed-horizon states; death takes precedence over ICU exit",
        "death_ascertainment": "Index-admission deathtime only; ICU-exit state means no recorded hospital death by horizon, not known survival after discharge",
        "denominator": "All positive-weight anchors in the arm, including deaths and ICU exits",
        "tracheostomy_caveat": "Inclusive state is a sensitivity, not proof of active mechanical ventilation",
        "states": records,
    }


def state_summaries(conn, anchors, horizons=(4, 12), *, min_cell=30):
    """Convenience aggregate API; intermediate patient rows remain in memory."""
    return summarize_state_frame(anchors, build_state_frame(conn, anchors, horizons), min_cell=min_cell)
