"""Synthetic-only tests. Never opens the clinical database or reads patient files.

Run: python -m unittest discover -s research/prophecy-2/validation -p test_outcomes.py
DuckDB integration cases are skipped when DuckDB is not installed; pure arithmetic,
fixed-weight estimator, state, and disclosure tests still run without it.
"""

import importlib.util
import json
from math import sqrt
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


SPEC = importlib.util.spec_from_file_location("validation_outcomes", Path(__file__).with_name("outcomes.py"))
outcomes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(outcomes)
HAS_DUCKDB = importlib.util.find_spec("duckdb") is not None
ZERO = pd.Timestamp("2100-01-02 00:00:00")


def hour(value):
    return ZERO + pd.Timedelta(hours=value)


def analysis_fixture():
    anchors = pd.DataFrame({
        "anchor_id": ["t1", "t2", "c1", "c2"],
        "subject_id": [1, 2, 3, 4], "arm": ["DNR", "DNR", "RISKSET", "RISKSET"],
        "weight": [1.0, 1.0, 1.0, 1.0],
    })
    # Four independent patients, one pre and one post four-hour bin. Treatment
    # change is -0.5; control change is zero; patient-cluster SE is 1/sqrt(24).
    rows = []
    pairs = {"t1": (4.0, 2.0), "t2": (2.0, 0.0), "c1": (2.0, 3.0), "c2": (2.0, 1.0)}
    for key, (pre, post) in pairs.items():
        rows.extend([{"anchor_id": key, "bin": -1, "observed_h": 4.0, "invasive_h": pre},
                     {"anchor_id": key, "bin": 0, "observed_h": 4.0, "invasive_h": post}])
    return anchors, pd.DataFrame(rows)


class IntervalArithmeticTests(unittest.TestCase):
    def test_overlap_is_a_union_not_capped_sum(self):
        # Naive sum is 4h and stays within a 4h bin; capping therefore cannot fix
        # the double count. The true union is 3h.
        self.assertEqual(outcomes.interval_union_hours([(hour(0), hour(2)), (hour(1), hour(3))], hour(0), hour(4)), 3.0)

    def test_nested_duplicates_and_touching_intervals(self):
        spans = [(hour(0), hour(3)), (hour(1), hour(2)), (hour(0), hour(3)), (hour(3), hour(4))]
        self.assertEqual(outcomes.interval_union_hours(spans, hour(0), hour(4)), 4.0)

    def test_clip_invalid_and_disjoint_intervals(self):
        spans = [(hour(-2), hour(1)), (hour(2), hour(6)), (hour(3), hour(2)), (pd.NaT, hour(4))]
        self.assertEqual(outcomes.interval_union_hours(spans, hour(0), hour(4)), 3.0)
        self.assertEqual(outcomes.interval_union_hours(spans, hour(4), hour(4)), 0.0)

    def test_subsecond_precision(self):
        end = hour(0) + pd.Timedelta(microseconds=500000)
        self.assertAlmostEqual(outcomes.interval_union_hours([(hour(0), end)], hour(0), hour(1)), .5/3600)


class EstimatorTests(unittest.TestCase):
    def test_hand_calculated_contrast_and_cluster_variance(self):
        a, b = analysis_fixture()
        result = outcomes.contrast(a, b, "invasive_h", pre=(-1,), post=(0,), min_cell=1)
        self.assertEqual(result["status"], "ok")
        self.assertAlmostEqual(result["estimate"], -.5)
        self.assertAlmostEqual(result["rates"]["DNR"]["pre"], .75)
        self.assertAlmostEqual(result["rates"]["DNR"]["post"], .25)
        self.assertAlmostEqual(result["se_conditional_patient_cluster"], sqrt(1/24))
        json.dumps(result, allow_nan=False)

    def test_repeated_anchors_of_same_patient_do_not_create_precision(self):
        a, b = analysis_fixture()
        baseline = outcomes.contrast(a, b, "invasive_h", pre=(-1,), post=(0,), min_cell=1)
        copies_a, copies_b = [], []
        for suffix in ("a", "b"):
            aa, bb = a.copy(), b.copy()
            aa["anchor_id"] += suffix
            bb["anchor_id"] += suffix
            aa["weight"] /= 2
            copies_a.append(aa)
            copies_b.append(bb)
        repeated = outcomes.contrast(pd.concat(copies_a), pd.concat(copies_b), "invasive_h", pre=(-1,), post=(0,), min_cell=1)
        self.assertAlmostEqual(repeated["estimate"], baseline["estimate"])
        self.assertAlmostEqual(repeated["se_conditional_patient_cluster"], baseline["se_conditional_patient_cluster"])
        self.assertEqual(repeated["n_patient_clusters"], 4)

    def test_patient_contributions_cluster_across_both_arms(self):
        a, b = analysis_fixture()
        # Identical paired DNR/control patient trajectories must cancel exactly
        # in cluster scores rather than generate independent-arm uncertainty.
        a.loc[a.arm == "RISKSET", "subject_id"] = [1, 2]
        for t, c in (("t1", "c1"), ("t2", "c2")):
            b.loc[b.anchor_id == c, "invasive_h"] = b.loc[b.anchor_id == t, "invasive_h"].to_numpy()
        result = outcomes.contrast(a, b, "invasive_h", pre=(-1,), post=(0,), min_cell=1)
        self.assertAlmostEqual(result["estimate"], 0)
        self.assertAlmostEqual(result["se_conditional_patient_cluster"], 0)

    def test_person_time_denominator_not_unweighted_patient_mean(self):
        a, b = analysis_fixture()
        b.loc[(b.anchor_id == "t1") & (b.bin == 0), ["observed_h", "invasive_h"]] = [2., 2.]
        result = outcomes.contrast(a, b, "invasive_h", pre=(-1,), post=(0,), min_cell=1)
        self.assertAlmostEqual(result["rates"]["DNR"]["post"], 2/6)

    def test_empty_post_observation_is_undefined_not_zero(self):
        a, b = analysis_fixture()
        mask = b.anchor_id.str.startswith("t") & (b.bin == 0)
        b.loc[mask, ["observed_h", "invasive_h"]] = 0
        result = outcomes.contrast(a, b, "invasive_h", pre=(-1,), post=(0,), min_cell=1)
        self.assertEqual(result["status"], "not_estimable")
        self.assertIsNone(result["estimate"])

    def test_missing_bin_is_rejected_not_silently_dropped(self):
        a, b = analysis_fixture()
        with self.assertRaises(ValueError):
            outcomes.contrast(a, b.iloc[1:], "invasive_h", pre=(-1,), post=(0,), min_cell=1)

    def test_duplicate_bin_and_support_overcount_rejected(self):
        a, b = analysis_fixture()
        with self.assertRaises(ValueError):
            outcomes.contrast(a, pd.concat([b, b.iloc[:1]]), "invasive_h", pre=(-1,), post=(0,), min_cell=1)
        b.loc[0, "invasive_h"] = 4.1
        with self.assertRaises(ValueError):
            outcomes.contrast(a, b, "invasive_h", pre=(-1,), post=(0,), min_cell=1)

    def test_public_default_suppresses_small_patient_groups(self):
        a, b = analysis_fixture()
        result = outcomes.contrast(a, b, "invasive_h", pre=(-1,), post=(0,))
        self.assertEqual(result["status"], "suppressed")
        self.assertIsNone(result["rates"])
        self.assertNotIn("n_patient_clusters", result)


class StateTests(unittest.TestCase):
    def test_death_exit_and_ventilation_are_mutually_exclusive(self):
        raw = pd.DataFrame({
            "anchor_id": ["dead", "exit", "vent", "trach", "off"], "subject_id": range(5),
            "horizon_h": [4.] * 5, "at_time": [hour(4)] * 5,
            "outtime": [hour(2), hour(3), hour(20), hour(20), hour(20)],
            "deathtime": [hour(4), pd.NaT, pd.NaT, pd.NaT, pd.NaT],
            "invasive_active": [False, True, True, False, False],
            "inclusive_active": [False, True, True, True, False],
        })
        result = outcomes._classify_states(raw).set_index("anchor_id")
        self.assertEqual(result.loc["dead", "state"], "dead")
        self.assertEqual(result.loc["exit", "state"], "left_icu_no_recorded_hospital_death")
        self.assertEqual(result.loc["vent", "state"], "alive_icu_invasive")
        self.assertEqual(result.loc["trach", "state"], "alive_icu_not_invasive")
        self.assertEqual(result.loc["trach", "state_inclusive"], "alive_icu_invasive_or_tracheostomy")

    def test_small_state_suppresses_complete_partition(self):
        a, _ = analysis_fixture()
        s = a[["anchor_id", "subject_id"]].copy()
        s["horizon_h"] = 4.
        s["state"] = ["dead", "alive_icu_invasive", "alive_icu_invasive", "alive_icu_invasive"]
        s["state_inclusive"] = ["dead", "alive_icu_invasive_or_tracheostomy", "alive_icu_invasive_or_tracheostomy", "alive_icu_invasive_or_tracheostomy"]
        result = outcomes.summarize_state_frame(a, s, min_cell=2)
        treated, control = result["states"]
        self.assertEqual(treated["status"], "suppressed")
        self.assertNotIn("state", treated)
        self.assertEqual(control["status"], "ok")
        self.assertAlmostEqual(sum(v["weighted_fraction"] for v in control["state"].values()), 1.)
        json.dumps(result, allow_nan=False)

    def test_nested_definitions_suppress_small_difference_despite_large_marginals(self):
        # Treated margins are 40/60 for primary and 50/50 for inclusive: every
        # nonzero marginal exceeds 30. Releasing both reveals the 10 patients
        # in the tracheostomy-only joint cell. Control's joint cells are 40/60.
        a = pd.DataFrame({
            "anchor_id": [f"a{i}" for i in range(200)],
            "subject_id": list(range(200)),
            "arm": ["DNR"] * 100 + ["RISKSET"] * 100,
            "weight": [1.] * 200,
        })
        s = a[["anchor_id", "subject_id"]].copy()
        s["horizon_h"] = 4.
        s["state"] = (["alive_icu_invasive"] * 40 + ["alive_icu_not_invasive"] * 60) * 2
        s["state_inclusive"] = (
            ["alive_icu_invasive_or_tracheostomy"] * 50
            + ["alive_icu_no_invasive_or_tracheostomy"] * 50
            + ["alive_icu_invasive_or_tracheostomy"] * 40
            + ["alive_icu_no_invasive_or_tracheostomy"] * 60
        )
        treated_rows = s.iloc[:100]
        for column in ("state", "state_inclusive"):
            self.assertTrue((treated_rows.groupby(column).subject_id.nunique() >= 30).all())
        result = outcomes.summarize_state_frame(a, s)
        treated, control = result["states"]
        self.assertEqual(treated["status"], "suppressed")
        self.assertNotIn("state", treated)
        self.assertNotIn("state_inclusive", treated)
        self.assertEqual(control["status"], "ok")
        json.dumps(result, allow_nan=False)


@unittest.skipUnless(HAS_DUCKDB, "DuckDB is not installed; synthetic SQL integration requires DuckDB")
class DuckDBIntegrationTests(unittest.TestCase):
    def setUp(self):
        import duckdb
        self.conn = duckdb.connect(":memory:")
        for schema in ("mimiciv_icu", "mimiciv_hosp", "mimiciv_derived"):
            self.conn.execute(f"CREATE SCHEMA {schema}")
        self.conn.execute("CREATE TABLE mimiciv_icu.icustays(stay_id BIGINT, hadm_id BIGINT, subject_id BIGINT, intime TIMESTAMP, outtime TIMESTAMP)")
        self.conn.execute("CREATE TABLE mimiciv_hosp.admissions(hadm_id BIGINT, deathtime TIMESTAMP)")
        self.conn.execute("CREATE TABLE mimiciv_derived.ventilation(stay_id BIGINT, starttime TIMESTAMP, endtime TIMESTAMP, ventilation_status VARCHAR)")
        self.conn.execute("CREATE TABLE mimiciv_derived.norepinephrine_equivalent_dose(stay_id BIGINT, starttime TIMESTAMP, endtime TIMESTAMP, norepinephrine_equivalent_dose DOUBLE)")
        self.conn.execute("CREATE TABLE mimiciv_derived.vitalsign(stay_id BIGINT, charttime TIMESTAMP, mbp DOUBLE, mbp_ni DOUBLE)")
        self.conn.execute("INSERT INTO mimiciv_icu.icustays VALUES (1,11,101,?,?),(2,22,202,?,?)", [hour(-2), hour(10), hour(-24), hour(3)])
        self.conn.execute("INSERT INTO mimiciv_hosp.admissions VALUES (11,?),(22,NULL)", [hour(6)])
        self.anchors = pd.DataFrame({"anchor_id": ["one", "two"], "stay_id": [1, 2], "anchor_time": [ZERO, ZERO], "subject_id": [101, 202]})

    def tearDown(self):
        self.conn.close()

    def test_legacy_capped_sums_keep_vent_duplicates_but_deduplicate_pressors(self):
        # Hand-calculated legacy vent sum: 1+1+1=3h; union=1.5h. The
        # tracheostomy interval is excluded from both strict definitions.
        for lo, hi, status in [(0, 1, "InvasiveVent"), (0, 1, "InvasiveVent"),
                               (.5, 1.5, "InvasiveVent"), (2, 4, "Tracheostomy")]:
            self.conn.execute("INSERT INTO mimiciv_derived.ventilation VALUES (1,?,?,?)",
                              [hour(lo), hour(hi), status])
        # Exact duplicates with different doses count once in the legacy
        # time-only exposure. Non-identical overlaps still add: 1+1+.5+.5=3h.
        # Any-dose union is 2.5h; positive-dose union is 1.5h.
        for lo, hi, dose in [(0, 1, .1), (0, 1, .2), (.5, 1.5, .3),
                             (2, 2.5, 0.), (3, 3.5, None)]:
            self.conn.execute("INSERT INTO mimiciv_derived.norepinephrine_equivalent_dose VALUES (1,?,?,?)",
                              [hour(lo), hour(hi), dose])
        r = outcomes.build_outcomes(self.conn, self.anchors).set_index(["anchor_id", "bin"])
        self.assertEqual(r.loc[("one", 0), "legacy_invasive_capped_sum_h"], 3.)
        self.assertEqual(r.loc[("one", 0), "invasive_h"], 1.5)
        self.assertEqual(r.loc[("one", 0), "invasive_plus_trach_h"], 3.5)
        self.assertEqual(r.loc[("one", 0), "legacy_pressor_capped_sum_h"], 3.)
        self.assertEqual(r.loc[("one", 0), "pressor_any_charted_h"], 2.5)
        self.assertEqual(r.loc[("one", 0), "pressor_h"], 1.5)

    def test_legacy_windows_do_not_clip_entry_and_map_counts_source_rows(self):
        # The synthetic stay begins at -2h. Its legacy [-4h,0h) bin nevertheless
        # has 4h observation, includes pre-entry rows, and counts duplicate MAPs.
        self.conn.execute("INSERT INTO mimiciv_derived.ventilation VALUES (1,?,?, 'InvasiveVent')",
                          [hour(-3), hour(-1)])
        for time, mbp, mbp_ni in [(-3, 65., None), (-3, None, 70.),
                                 (-3, None, None), (-1, 75., None)]:
            self.conn.execute("INSERT INTO mimiciv_derived.vitalsign VALUES (1,?,?,?)",
                              [hour(time), mbp, mbp_ni])
        r = outcomes.build_outcomes(self.conn, self.anchors).set_index(["anchor_id", "bin"])
        self.assertEqual(r.loc[("one", -1), "legacy_observed_h"], 4.)
        self.assertEqual(r.loc[("one", -1), "observed_h"], 2.)
        self.assertEqual(r.loc[("one", -1), "legacy_invasive_capped_sum_h"], 2.)
        self.assertEqual(r.loc[("one", -1), "invasive_h"], 1.)
        self.assertEqual(r.loc[("one", -1), "legacy_n_map_source_rows"], 3)
        self.assertEqual(r.loc[("one", -1), "n_map_source_rows"], 1)
        self.assertEqual(r.loc[("one", -1), "n_map"], 1)

    def test_legacy_second_boundary_arithmetic_is_distinct_from_elapsed_time(self):
        # datediff('second', .250s, 1.200s) counts one second boundary, whereas
        # actual elapsed time is .950s. The same distinction affects support.
        anchor = ZERO + pd.Timedelta(milliseconds=250)
        self.conn.execute("INSERT INTO mimiciv_icu.icustays VALUES (3,33,303,?,?)",
                          [hour(-24), ZERO + pd.Timedelta(milliseconds=1200)])
        self.conn.execute("INSERT INTO mimiciv_hosp.admissions VALUES (33,NULL)")
        self.conn.execute("INSERT INTO mimiciv_derived.ventilation VALUES (3,?,?, 'InvasiveVent')",
                          [ZERO + pd.Timedelta(milliseconds=900),
                           ZERO + pd.Timedelta(milliseconds=1100)])
        a = pd.DataFrame({"anchor_id": ["fractional"], "stay_id": [3],
                          "anchor_time": [anchor], "subject_id": [303]})
        r = outcomes.build_outcomes(self.conn, a).set_index(["anchor_id", "bin"])
        self.assertAlmostEqual(r.loc[("fractional", 0), "legacy_observed_h"], 1/3600)
        self.assertAlmostEqual(r.loc[("fractional", 0), "observed_h"], .95/3600)
        self.assertAlmostEqual(r.loc[("fractional", 0), "legacy_invasive_capped_sum_h"], 1/3600)
        self.assertAlmostEqual(r.loc[("fractional", 0), "invasive_h"], .2/3600)

    def test_legacy_and_primary_agree_for_disjoint_positive_second_aligned_data(self):
        # When definitions coincide, the independently extracted legacy columns
        # must agree exactly with the primary columns rather than merely execute.
        for lo, hi in [(0, 1), (1, 2)]:
            self.conn.execute("INSERT INTO mimiciv_derived.ventilation VALUES (2,?,?, 'InvasiveVent')",
                              [hour(lo), hour(hi)])
        for lo, hi, dose in [(0, 1, .1), (2, 3, .2)]:
            self.conn.execute("INSERT INTO mimiciv_derived.norepinephrine_equivalent_dose VALUES (2,?,?,?)",
                              [hour(lo), hour(hi), dose])
        for time, mbp, mbp_ni in [(0, 65., None), (1, None, 70.), (2, 75., None)]:
            self.conn.execute("INSERT INTO mimiciv_derived.vitalsign VALUES (2,?,?,?)",
                              [hour(time), mbp, mbp_ni])
        r = outcomes.build_outcomes(self.conn, self.anchors.loc[self.anchors.stay_id == 2])
        for legacy, primary in (("legacy_observed_h", "observed_h"),
                                ("legacy_invasive_capped_sum_h", "invasive_h"),
                                ("legacy_pressor_capped_sum_h", "pressor_h"),
                                ("legacy_n_map_source_rows", "n_map")):
            np.testing.assert_array_equal(r[legacy], r[primary])

    def test_union_clipping_positive_dose_map_boundaries_and_empty_bins(self):
        for lo, hi, status in [(0, 2, "InvasiveVent"), (0, 2, "InvasiveVent"), (.5, 1, "InvasiveVent"), (1, 3, "InvasiveVent"), (2, 5, "Tracheostomy"), (5, 9, "InvasiveVent")]:
            self.conn.execute("INSERT INTO mimiciv_derived.ventilation VALUES (1,?,?,?)", [hour(lo), hour(hi), status])
        for lo, hi, dose in [(0, 2, .1), (1, 3, .2), (3, 4, 0.), (4, 9, None)]:
            self.conn.execute("INSERT INTO mimiciv_derived.norepinephrine_equivalent_dose VALUES (1,?,?,?)", [hour(lo), hour(hi), dose])
        for time, invasive, noninvasive in [(0, 65., None), (1, None, 70.), (1, 70., None), (2, None, None), (4, 80., None), (6, 90., None)]:
            self.conn.execute("INSERT INTO mimiciv_derived.vitalsign VALUES (1,?,?,?)", [hour(time), invasive, noninvasive])
        result = outcomes.build_outcomes(self.conn, self.anchors)
        self.assertEqual(len(result), 18)
        r = result.set_index(["anchor_id", "bin"])
        self.assertEqual(r.loc[("one", -1), "observed_h"], 2.)
        self.assertEqual(r.loc[("one", 0), "invasive_h"], 3.)
        self.assertEqual(r.loc[("one", 0), "legacy_invasive_capped_sum_h"], 4.)
        self.assertEqual(r.loc[("one", 0), "invasive_plus_trach_h"], 4.)
        self.assertEqual(r.loc[("one", 0), "pressor_h"], 3.)
        self.assertEqual(r.loc[("one", 0), "pressor_any_charted_h"], 4.)
        self.assertEqual(r.loc[("one", 0), "n_map"], 2)
        self.assertEqual(r.loc[("one", 0), "n_map_source_rows"], 3)
        self.assertEqual(r.loc[("one", 1), "observed_h"], 2.)
        self.assertEqual(r.loc[("one", 1), "invasive_h"], 1.)
        self.assertEqual(r.loc[("one", 1), "n_map"], 1)
        self.assertEqual(r.loc[("one", 2), "observed_h"], 0.)
        self.assertEqual(r.loc[("two", 0), "observed_h"], 3.)
        self.assertEqual(r.loc[("two", 0), "invasive_h"], 0.)
        for col in outcomes.HOUR_OUTCOMES:
            self.assertTrue((result[col] <= result.observed_h).all())
        self.assertEqual(self.conn.execute("SELECT count(*) FROM duckdb_views() WHERE view_name LIKE '_dnr_validation_%'").fetchone()[0], 0)

    def test_state_at_boundary_and_death_after_exit(self):
        self.conn.execute("INSERT INTO mimiciv_derived.ventilation VALUES (1,?,?, 'InvasiveVent')", [hour(0), hour(4)])
        self.conn.execute("INSERT INTO mimiciv_derived.ventilation VALUES (1,?,?, 'Tracheostomy')", [hour(4), hour(10)])
        r = outcomes.build_state_frame(self.conn, self.anchors).set_index(["anchor_id", "horizon_h"])
        self.assertEqual(r.loc[("one", 4.), "state"], "alive_icu_not_invasive")
        self.assertEqual(r.loc[("one", 4.), "state_inclusive"], "alive_icu_invasive_or_tracheostomy")
        self.assertEqual(r.loc[("one", 12.), "state"], "dead")
        self.assertEqual(r.loc[("two", 4.), "state"], "left_icu_no_recorded_hospital_death")

    def test_source_patient_mismatch_rejected(self):
        self.anchors.loc[0, "subject_id"] = 999
        with self.assertRaises(ValueError):
            outcomes.build_outcomes(self.conn, self.anchors)


if __name__ == "__main__":
    unittest.main()
