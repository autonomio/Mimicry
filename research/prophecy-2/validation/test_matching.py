"""Synthetic checks for patient caps, missingness, and outcome-blind fitting."""
import unittest
import numpy as np
import pandas as pd
from matching import fit_supported, restrict_fold, subject_fold


def population(n=40):
    rows = []
    anchor = 0
    for i in range(n):
        value = float(i % 4)
        rows.append(dict(anchor_id=anchor, treated_id=i, subject_id=1000+i,
                         arm="DNR", value=value))
        anchor += 1
        for j in range(3):
            rows.append(dict(anchor_id=anchor, treated_id=i,
                             subject_id=2000+3*i+j, arm="RISKSET", value=value))
            anchor += 1
    return pd.DataFrame(rows)


class MatchingTests(unittest.TestCase):
    def test_feasible_caps_and_balance(self):
        out = fit_supported(population(), features=("value",))
        self.assertTrue(out.diagnostics["gate_pass"])
        c = out.weights.query("arm == 'RISKSET'")
        self.assertLessEqual(c.groupby(["treated_id", "subject_id"]).weight.sum().max(), .500001)
        self.assertLessEqual(c.groupby("subject_id").weight.sum().max(), 2.000001)
        self.assertLess(out.diagnostics["max_abs_conventional_smd"], 1e-7)

    def test_repeated_anchor_person_is_not_two_controls(self):
        x = population()
        x.loc[x.arm.eq("RISKSET"), "subject_id"] = x.loc[x.arm.eq("RISKSET"), "treated_id"]+2000
        out = fit_supported(x, features=("value",))
        self.assertFalse(out.diagnostics["gate_pass"])
        self.assertEqual(out.diagnostics["n_treated"], 0)

    def test_global_control_reuse_fails(self):
        x = population()
        mask = x.arm.eq("RISKSET")
        x.loc[mask, "subject_id"] = np.tile([2000, 2001, 2002], 40)
        self.assertFalse(fit_supported(x, features=("value",)).diagnostics["gate_pass"])

    def test_missingness_cannot_be_ignored(self):
        x = population()
        x.loc[x.arm.eq("DNR"), "value"] = np.nan
        out = fit_supported(x, features=("value",))
        self.assertFalse(out.diagnostics["gate_pass"])
        self.assertEqual(out.diagnostics["n_balance_features_including_missingness"], 2)

    def test_unequal_constant_covariates_fail(self):
        x = population()
        x["value"] = x.arm.eq("RISKSET").astype(float)
        self.assertEqual(fit_supported(x, features=("value",)).diagnostics["status"],
                         "CONSTANT_FEATURE_MISMATCH")

    def test_future_outcomes_do_not_affect_design(self):
        x = population()
        first = fit_supported(x, features=("value",))
        x["death12"] = np.arange(len(x)) % 2
        x["outtime"] = "2099-12-31"
        second = fit_supported(x, features=("value",))
        np.testing.assert_array_equal(first.weights.weight, second.weights.weight)

    def test_fold_is_patient_disjoint_across_roles(self):
        x = population()
        p0, p1 = restrict_fold(x, 0), restrict_fold(x, 1)
        self.assertFalse(set(p0.subject_id) & set(p1.subject_id))
        self.assertTrue(all(subject_fold(v) == 0 for v in p0.subject_id))
        for p in (p0, p1):
            self.assertTrue(set(p.loc[p.arm.eq("RISKSET"), "treated_id"]).issubset(
                set(p.loc[p.arm.eq("DNR"), "treated_id"])))

    def test_self_match_is_rejected(self):
        x = population()
        x.loc[1, "subject_id"] = x.loc[0, "subject_id"]
        with self.assertRaises(ValueError):
            fit_supported(x, features=("value",))


if __name__ == "__main__":
    unittest.main()
