"""Early ICU mortality baseline (MIMIC-IV v3.1, s0 only).

Population: first ICU stay per hospitalization with LOS >= 6h (landmark at 6h).
Outcome: hospital_expire_flag (~10.9% events).
Features: demographics + first-6h vitals/labs/GCS summaries + missingness flags.
Model: L2 logistic regression, stratified 80/20 split, seed 42.
Prints only aggregate metrics (AUC/AP, risk deciles, top coefficients).

Run on s0: /srv/mimic-iv/.venv/bin/python early_mortality.py
"""
import duckdb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

DB = "/srv/mimic-iv/db/mimic4-v31.db"

COHORT_SQL = """
WITH first_stay AS (
  SELECT s.stay_id, s.subject_id, s.intime, s.first_careunit,
         p.anchor_age, p.gender, a.admission_type, a.hospital_expire_flag AS y
  FROM mimiciv_icu.icustays s
  JOIN mimiciv_hosp.patients p USING (subject_id)
  JOIN mimiciv_hosp.admissions a USING (hadm_id)
  WHERE s.los >= 0.25
  QUALIFY row_number() OVER (PARTITION BY s.hadm_id ORDER BY s.intime) = 1
),
vitals AS (
  SELECT e.stay_id,
    MEDIAN(CASE WHEN e.itemid = 220045 AND e.valuenum BETWEEN 10 AND 300 THEN e.valuenum END) AS hr_med,
    MIN(CASE WHEN e.itemid = 220045 AND e.valuenum BETWEEN 10 AND 300 THEN e.valuenum END) AS hr_min,
    MAX(CASE WHEN e.itemid = 220045 AND e.valuenum BETWEEN 10 AND 300 THEN e.valuenum END) AS hr_max,
    MEDIAN(CASE WHEN e.itemid = 220210 AND e.valuenum BETWEEN 0 AND 80 THEN e.valuenum END) AS rr_med,
    MIN(CASE WHEN e.itemid = 220210 AND e.valuenum BETWEEN 0 AND 80 THEN e.valuenum END) AS rr_min,
    MAX(CASE WHEN e.itemid = 220210 AND e.valuenum BETWEEN 0 AND 80 THEN e.valuenum END) AS rr_max,
    MEDIAN(CASE WHEN e.itemid = 220277 AND e.valuenum BETWEEN 50 AND 100 THEN e.valuenum END) AS spo2_med,
    MIN(CASE WHEN e.itemid = 220277 AND e.valuenum BETWEEN 50 AND 100 THEN e.valuenum END) AS spo2_min,
    MEDIAN(CASE WHEN e.itemid = 220181 AND e.valuenum BETWEEN 10 AND 200 THEN e.valuenum END) AS nbpm_med,
    MIN(CASE WHEN e.itemid = 220181 AND e.valuenum BETWEEN 10 AND 200 THEN e.valuenum END) AS nbpm_min,
    MEDIAN(CASE WHEN e.itemid = 220052 AND e.valuenum BETWEEN 10 AND 200 THEN e.valuenum END) AS abpm_med,
    MIN(CASE WHEN e.itemid = 220052 AND e.valuenum BETWEEN 10 AND 200 THEN e.valuenum END) AS abpm_min,
    MEDIAN(CASE WHEN e.itemid = 223761 AND e.valuenum BETWEEN 86 AND 110 THEN (e.valuenum - 32) * 5 / 9 END) AS temp_med
  FROM mimiciv_icu.chartevents e
  JOIN first_stay f USING (stay_id)
  WHERE e.charttime >= f.intime AND e.charttime < f.intime + INTERVAL 6 HOUR
    AND e.itemid IN (220045, 220210, 220277, 220181, 220052, 223761,
                     220739, 223900, 223901)
  GROUP BY 1
),
gcs AS (
  SELECT stay_id, MIN(total) AS gcs_min, MEDIAN(total) AS gcs_med FROM (
    SELECT stay_id, charttime, (eye + verbal + motor) AS total FROM (
      SELECT e.stay_id, e.charttime,
        MAX(CASE WHEN e.itemid = 220739 AND e.valuenum BETWEEN 1 AND 4 THEN e.valuenum END) AS eye,
        MAX(CASE WHEN e.itemid = 223900 AND e.valuenum BETWEEN 1 AND 5 THEN e.valuenum END) AS verbal,
        MAX(CASE WHEN e.itemid = 223901 AND e.valuenum BETWEEN 1 AND 6 THEN e.valuenum END) AS motor
      FROM mimiciv_icu.chartevents e
      JOIN first_stay f USING (stay_id)
      WHERE e.charttime >= f.intime AND e.charttime < f.intime + INTERVAL 6 HOUR
        AND e.itemid IN (220739, 223900, 223901)
      GROUP BY 1, 2
    )
    WHERE eye IS NOT NULL AND verbal IS NOT NULL AND motor IS NOT NULL
  ) GROUP BY 1
),
labs AS (
  SELECT f.stay_id,
    MEDIAN(CASE WHEN l.itemid = 50813 AND l.valuenum BETWEEN 0 AND 30 THEN l.valuenum END) AS lactate_med,
    MEDIAN(CASE WHEN l.itemid = 50912 AND l.valuenum BETWEEN 0 AND 20 THEN l.valuenum END) AS creat_med
  FROM first_stay f
  JOIN mimiciv_hosp.labevents l
    ON l.subject_id = f.subject_id
   AND l.charttime >= f.intime AND l.charttime < f.intime + INTERVAL 6 HOUR
   AND l.itemid IN (50813, 50912)
  GROUP BY 1
)
SELECT f.stay_id, f.anchor_age, f.gender, f.admission_type, f.first_careunit, f.y,
       v.*, g.gcs_min, g.gcs_med, l.lactate_med, l.creat_med
FROM first_stay f
LEFT JOIN vitals v USING (stay_id)
LEFT JOIN gcs g USING (stay_id)
LEFT JOIN labs l USING (stay_id)
ORDER BY f.stay_id
"""


def main():
    con = duckdb.connect(DB, read_only=True)
    df = con.execute(COHORT_SQL).fetchdf()
    con.close()
    print(f"cohort: {len(df)} stays, events: {int(df.y.sum())} ({df.y.mean():.3f})")

    num_cols = ["anchor_age", "hr_med", "hr_min", "hr_max", "rr_med", "rr_min",
                "rr_max", "spo2_med", "spo2_min", "nbpm_med", "nbpm_min",
                "abpm_med", "abpm_min", "temp_med", "gcs_min", "gcs_med",
                "lactate_med", "creat_med"]
    # MAP: prefer NIBP, fall back to arterial; add missingness flags
    df["map_med"] = df["nbpm_med"].fillna(df["abpm_med"])
    df["map_min"] = df["nbpm_min"].fillna(df["abpm_min"])
    num_cols += ["map_med", "map_min"]
    for c in ["hr_med", "rr_med", "spo2_med", "map_med", "temp_med",
              "gcs_med", "lactate_med", "creat_med"]:
        df[f"miss_{c}"] = df[c].isna().astype(int)
    num_cols += [f"miss_{c}" for c in ["hr_med", "rr_med", "spo2_med", "map_med",
                                       "temp_med", "gcs_med", "lactate_med", "creat_med"]]
    cat_cols = ["gender", "admission_type", "first_careunit"]

    X, y = df[num_cols + cat_cols], df["y"].to_numpy()
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)
    print(f"train: {len(Xtr)} (events {ytr.sum()}), test: {len(Xte)} (events {yte.sum()})")

    pre = ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")),
                          ("sc", StandardScaler())]), num_cols),
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
    ])
    clf = Pipeline([("pre", pre),
                    ("lr", LogisticRegression(C=1.0, max_iter=5000))])
    clf.fit(Xtr, ytr)
    p = clf.predict_proba(Xte)[:, 1]
    print(f"AUC: {roc_auc_score(yte, p):.4f}")
    print(f"AP:  {average_precision_score(yte, p):.4f} (base rate {yte.mean():.4f})")

    q = pd.qcut(p, 10, labels=False, duplicates="drop")
    print("decile,n,events,rate")
    for d in sorted(set(q)):
        m = q == d
        print(f"{d},{m.sum()},{yte[m].sum()},{yte[m].mean():.4f}")

    names = list(num_cols) + list(
        clf.named_steps["pre"].named_transformers_["cat"].get_feature_names_out(cat_cols))
    coefs = clf.named_steps["lr"].coef_[0]
    order = np.argsort(coefs)
    print("most negative coef:")
    for i in order[:8]:
        print(f"  {names[i]}: {coefs[i]:+.3f}")
    print("most positive coef:")
    for i in order[-8:][::-1]:
        print(f"  {names[i]}: {coefs[i]:+.3f}")


if __name__ == "__main__":
    main()
