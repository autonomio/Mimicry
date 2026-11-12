"""Synthetic release-boundary and original-reproduction regression checks."""
import copy
import unittest

import pandas as pd

from run_validation import (contrast_difference_safe, paired_definition_safe,
    population_disclosure_safe, public_fit, reproduction_errors)


class ReleaseBoundaryTests(unittest.TestCase):
    def test_repeated_events_are_not_distinct_people(self):
        a = pd.DataFrame({"anchor_id": range(60), "subject_id": [1]*30+list(range(2,32)),
                          "arm": ["DNR"]*60})
        self.assertFalse(population_disclosure_safe(a, [a.iloc[30:]]))

    def test_joint_partition_difference_is_suppressed(self):
        a = pd.DataFrame({"anchor_id": range(792), "subject_id": range(792), "arm": "DNR"})
        self.assertFalse(population_disclosure_safe(a, [a, a.iloc[:400], a.iloc[400:791]]))
        self.assertTrue(population_disclosure_safe(a, [a, a.iloc[:400], a.iloc[400:]]))

    def test_unsafe_population_hides_ess_and_other_fitted_values(self):
        d = {"n_treated": 791, "status": "PASS", "gate_pass": True,
             "effective_control_people_overall": 1582.0,
             "max_abs_conventional_smd": .01, "mean_scaled_squared_distance": .2,
             "within_riskset_subject_cap": .5}
        result = public_fit(d, False)
        self.assertIsNone(result["n_treated"])
        self.assertNotIn("effective_control_people_overall", result)
        self.assertNotIn("max_abs_conventional_smd", result)
        self.assertNotIn("mean_scaled_squared_distance", result)
        self.assertTrue(result["gate_pass"])

    @staticmethod
    def examples():
        a = pd.DataFrame({"anchor_id": range(60), "subject_id": range(60),
                          "arm": ["DNR"]*30+["RISKSET"]*30, "weight": 1.0})
        b = pd.DataFrame([{"anchor_id": i, "bin": k, "observed_h": 4.0,
                           "invasive_h": 1.0, "invasive_plus_trach_h": 2.0}
                          for i in range(60) for k in range(-3,3)])
        return a, b

    def test_many_definition_differences_can_hide_one_changed_person(self):
        a, b = self.examples()
        self.assertTrue(paired_definition_safe(a, b, "invasive_h", "invasive_plus_trach_h"))
        b.loc[b.anchor_id.eq(0) & b.bin.eq(0), "invasive_plus_trach_h"] = 3.0
        self.assertFalse(paired_definition_safe(a, b, "invasive_h", "invasive_plus_trach_h"))

    def test_nested_time_windows_guard_one_contributor(self):
        a, b = self.examples()
        full = ("invasive_h", (-3,-2,-1), (0,1,2))
        near = ("invasive_h", (-1,), (0,))
        self.assertTrue(contrast_difference_safe(a, b, full, near))
        b.loc[b.anchor_id.eq(0) & b.bin.eq(0), "invasive_h"] = 2.0
        self.assertFalse(contrast_difference_safe(a, b, full, near))

    def test_reproduction_checks_denominators_and_arm_rates(self):
        archived = {"estimate": -.1, "rates": {arm: {"pre": .5, "post": .25,
                    "post_icu_hours": 300.0} for arm in ("DNR", "RISKSET")}}
        actual = {"estimate": -.1, "rates": {arm: {"pre": .5, "post": .25,
                  "pre_observed_weighted_h": 360.0, "post_observed_weighted_h": 300.0}
                  for arm in ("DNR", "RISKSET")}}
        self.assertEqual(max(reproduction_errors(actual, archived, 30).values()), 0.0)
        broken = copy.deepcopy(actual)
        broken["rates"]["DNR"]["post_observed_weighted_h"] += 1
        self.assertGreater(reproduction_errors(broken, archived, 30)["denominator_h"], .9)
        broken = copy.deepcopy(actual)
        broken["rates"]["DNR"]["pre"] += .01
        self.assertGreater(reproduction_errors(broken, archived, 30)["rate"], .009)


if __name__ == "__main__":
    unittest.main()
