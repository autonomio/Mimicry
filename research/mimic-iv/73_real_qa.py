#!/usr/bin/env python3
"""Adversarial structural audit for MIMIC-IV six-hour panel.

Does not establish causal identification, coding completeness or
external transportability. Fails on known serious integrity bugs.
"""
from pathlib import Path
import json
import numpy as np,pandas as pd
root=Path("/srv/mimic-iv/studies/decision_feedback_20261025")
df=pd.read_parquet(root/"multistate_6h_panel.parquet")
assert len(df)>100000
assert df.subject_id.nunique()==df.stay_id.nunique()
assert not df.duplicated(["stay_id","step"]).any()
assert df.step.between(4,27).all(), "Day1 SOFA leakage"
assert df.next_icu_hours.between(1.e-7,6.0001).all()
for col in ["prior_invasive_h","prior_pressor_h"]:
 assert df[col].between(0,6.0001).all(),col
for col in ["next_invasive_h","next_pressor_h"]:
 assert (df[col]<=df.next_icu_hours+0.001).all(),col
 assert (df[col]>=0).all(),col
assert df.next_n_map.ge(0).all() and df.next_n_hr.ge(0).all()
assert set(df.next_event.unique())=={"STABLE","CODE_CHANGE","ICU_EXIT","DEATH"}
assert (df.next_event.eq("DEATH")<=df.death_within6h).all()
assert (df.next_event.eq("ICU_EXIT")<=df.exit_within6h).all()
assert (df.next_event.eq("CODE_CHANGE")<=df.code_document_change_within6h).all()
assert df.loc[df.next_event.eq("STABLE"),"within_bin_collision"].sum()==0
pressor_rate=float((df.next_pressor_h>0.1).mean())
assert 0.03<pressor_rate<0.5,"Impossible pressor prevalence; check SQL NULL propagation"
eras=df.groupby("subject_id").era.nunique()
assert eras.max()==1,"Patient appears in multiple historical time splits"
assert df.era.nunique()==5
fit=json.loads((root/"multistate_realfit_report.json").read_text())
assert fit["splits"]["test"]==int((df.era=="2020 - 2022").sum())
assert fit["models"]["care_history"]["test_log_loss"]<fit["models"]["physiology"]["test_log_loss"]
collision=df.within_bin_collision.sum()
report={
 "status":"PASS structural checks; remaining clinical identification not established",
 "n_rows":int(len(df)),"n_patients":int(df.subject_id.nunique()),
 "min_step":int(df.step.min()),"max_step":int(df.step.max()),
 "duplicate_landmarks":0,
 "six_hour_code_terminal_collisions":int(collision),
 "documentation_unknown_pct":float(100*df.code_state.eq("UNKNOWN").mean()),
 "true_next_pressor_exposed_pct":100*pressor_rate,
 "sample_outcome_counts":df.next_event.value_counts().to_dict(),
 "no_cross_era_subject_overlap":True,
 "test_n":fit["splits"]["test"],
 "limitations":["code-status documentation != treatment intent",
 "6-hour first-event competing labels do not model every within-bin transition",
 "age/first-day SOFA available by 24h but chart vs record-availability times still require audit",
 "test-era absolute event calibration imperfect",
 "MIMIC-IV single institution not external validation",
 "does not establish causal interventions or patient preferences"]
}
(root/"multistate_structural_qa.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
