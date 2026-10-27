"""Hour-by-hour signal sweep (MIMIC-IV v3.1, s0 only).

How much mortality signal exists in hour 1, 2, ... after ICU admission?

1. LANDMARK: for each L in 1..24, logreg on cumulative data [0, L) for stays
   with LOS >= L hours. Reports AUC/AP/n per landmark + top coefs at 1/3/6/12/24.
2. UNIVARIATE: per vital, single-feature AUC of the hour-h median (with n).
Outputs (aggregates only): landmark_metrics.csv, topcoefs.csv, univariate.csv.

Run on s0: /srv/mimic-iv/.venv/bin/python signal_sweep.py
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
OUT = "/tmp/"

STATIC_SQL = """
SELECT s.stay_id, s.los, s.first_careunit,
       p.anchor_age, p.gender, a.admission_type, a.hospital_expire_flag AS y
FROM mimiciv_icu.icustays s
JOIN mimiciv_hosp.patients p USING (subject_id)
JOIN mimiciv_hosp.admissions a USING (hadm_id)
QUALIFY row_number() OVER (PARTITION BY s.hadm_id ORDER BY s.intime) = 1
ORDER BY s.stay_id
"""

VITALS_SQL = """
SELECT e.stay_id, CAST(date_diff('hour', f.intime, e.charttime) AS INTEGER) AS h,
  MEDIAN(CASE WHEN e.itemid = 220045 AND e.valuenum BETWEEN 10 AND 300 THEN e.valuenum END) AS hr_med,
  MIN(CASE WHEN e.itemid = 220045 AND e.valuenum BETWEEN 10 AND 300 THEN e.valuenum END) AS hr_min,
  MAX(CASE WHEN e.itemid = 220045 AND e.valuenum BETWEEN 10 AND 300 THEN e.valuenum END) AS hr_max,
  MEDIAN(CASE WHEN e.itemid = 220210 AND e.valuenum BETWEEN 0 AND 80 THEN e.valuenum END) AS rr_med,
  MIN(CASE WHEN e.itemid = 220210 AND e.valuenum BETWEEN 0 AND 80 THEN e.valuenum END) AS rr_min,
  MAX(CASE WHEN e.itemid = 220210 AND e.valuenum BETWEEN 0 AND 80 THEN e.valuenum END) AS rr_max,
  MEDIAN(CASE WHEN e.itemid = 220277 AND e.valuenum BETWEEN 50 AND 100 THEN e.valuenum END) AS spo2_med,
  MIN(CASE WHEN e.itemid = 220277 AND e.valuenum BETWEEN 50 AND 100 THEN e.valuenum END) AS spo2_min,
  MAX(CASE WHEN e.itemid = 220277 AND e.valuenum BETWEEN 50 AND 100 THEN e.valuenum END) AS spo2_max,
  MEDIAN(CASE WHEN e.itemid = 220181 AND e.valuenum BETWEEN 10 AND 200 THEN e.valuenum END) AS nbpm_med,
  MIN(CASE WHEN e.itemid = 220181 AND e.valuenum BETWEEN 10 AND 200 THEN e.valuenum END) AS nbpm_min,
  MAX(CASE WHEN e.itemid = 220181 AND e.valuenum BETWEEN 10 AND 200 THEN e.valuenum END) AS nbpm_max,
  MEDIAN(CASE WHEN e.itemid = 220052 AND e.valuenum BETWEEN 10 AND 200 THEN e.valuenum END) AS abpm_med,
  MIN(CASE WHEN e.itemid = 220052 AND e.valuenum BETWEEN 10 AND 200 THEN e.valuenum END) AS abpm_min,
  MAX(CASE WHEN e.itemid = 220052 AND e.valuenum BETWEEN 10 AND 200 THEN e.valuenum END) AS abpm_max,
  MEDIAN(CASE WHEN e.itemid = 223761 AND e.valuenum BETWEEN 86 AND 110 THEN (e.valuenum - 32) * 5 / 9 END) AS temp_med,
  MIN(CASE WHEN e.itemid = 223761 AND e.valuenum BETWEEN 86 AND 110 THEN (e.valuenum - 32) * 5 / 9 END) AS temp_min,
  MAX(CASE WHEN e.itemid = 223761 AND e.valuenum BETWEEN 86 AND 110 THEN (e.valuenum - 32) * 5 / 9 END) AS temp_max
FROM mimiciv_icu.chartevents e
JOIN (SELECT stay_id, intime FROM mimiciv_icu.icustays
      QUALIFY row_number() OVER (PARTITION BY hadm_id ORDER BY intime) = 1) f USING (stay_id)
WHERE e.charttime >= f.intime AND e.charttime < f.intime + INTERVAL 24 HOUR
  AND e.itemid IN (220045, 220210, 220277, 220181, 220052, 223761)
GROUP BY 1, 2
"""

GCS_SQL = """
SELECT stay_id, h, MIN(total) AS gcs_min, MEDIAN(total) AS gcs_med FROM (
  SELECT stay_id, h, (eye + verbal + motor) AS total FROM (
    SELECT e.stay_id, CAST(date_diff('hour', f.intime, e.charttime) AS INTEGER) AS h,
      MAX(CASE WHEN e.itemid = 220739 AND e.valuenum BETWEEN 1 AND 4 THEN e.valuenum END) AS eye,
      MAX(CASE WHEN e.itemid = 223900 AND e.valuenum BETWEEN 1 AND 5 THEN e.valuenum END) AS verbal,
      MAX(CASE WHEN e.itemid = 223901 AND e.valuenum BETWEEN 1 AND 6 THEN e.valuenum END) AS motor
    FROM mimiciv_icu.chartevents e
    JOIN (SELECT stay_id, intime FROM mimiciv_icu.icustays
          QUALIFY row_number() OVER (PARTITION BY hadm_id ORDER BY intime) = 1) f USING (stay_id)
    WHERE e.charttime >= f.intime AND e.charttime < f.intime + INTERVAL 24 HOUR
      AND e.itemid IN (220739, 223900, 223901)
    GROUP BY 1, 2, e.charttime
  )
  WHERE eye IS NOT NULL AND verbal IS NOT NULL AND motor IS NOT NULL
) GROUP BY 1, 2
"""

LABS_SQL = """
SELECT f.stay_id, CAST(date_diff('hour', f.intime, l.charttime) AS INTEGER) AS h,
  MEDIAN(CASE WHEN l.itemid = 50813 AND l.valuenum BETWEEN 0 AND 30 THEN l.valuenum END) AS lactate_med,
  MEDIAN(CASE WHEN l.itemid = 50912 AND l.valuenum BETWEEN 0 AND 20 THEN l.valuenum END) AS creat_med
FROM (SELECT stay_id, subject_id, intime FROM mimiciv_icu.icustays
      QUALIFY row_number() OVER (PARTITION BY hadm_id ORDER BY intime) = 1) f
JOIN mimiciv_hosp.labevents l
  ON l.subject_id = f.subject_id
 AND l.charttime >= f.intime AND l.charttime < f.intime + INTERVAL 24 HOUR
 AND l.itemid IN (50813, 50912)
GROUP BY 1, 2
"""

SIGS = ["hr", "rr", "spo2", "nbpm", "abpm", "temp"]
NUM_BASE = ["anchor_age"] + [f"{s}_{st}" for s in SIGS for st in ("med", "min", "max")] \
    + ["gcs_min", "gcs_med", "lactate_med", "creat_med"]
CATS = ["gender", "admission_type", "first_careunit"]
MISS_SRC = ["hr_med", "rr_med", "spo2_med", "map_med", "temp_med",
            "gcs_med", "lactate_med", "creat_med"]


def main():
    con = duckdb.connect(DB, read_only=True)
    static = con.execute(STATIC_SQL).fetchdf()
    vit = con.execute(VITALS_SQL).fetchdf()
    gcs = con.execute(GCS_SQL).fetchdf()
    labs = con.execute(LABS_SQL).fetchdf()
    con.close()
    hourly = vit.merge(gcs, on=["stay_id", "h"], how="outer").merge(
        labs, on=["stay_id", "h"], how="outer")
    print(f"stays: {len(static)}, stay-hours: {len(hourly)}", flush=True)

    # ---- 1. landmark sweep ----
    num_cols = [c for c in NUM_BASE if c not in
                ("nbpm_med", "nbpm_min", "nbpm_max", "abpm_med", "abpm_min", "abpm_max")]
    num_cols += ["map_med", "map_min", "map_max"] + [f"miss_{c}" for c in MISS_SRC]
    rows, coef_rows = [], []
    for L in range(1, 25):
        elig = static[static.los >= L / 24.0]
        w = hourly[hourly.h < L]
        agg = {"stay_id": "first"}
        g = w.groupby("stay_id")
        parts = {"stay_id": g["stay_id"].first()}
        for c in [c for c in NUM_BASE if c != "anchor_age"]:
            mn = c.endswith("_min")
            mx = c.endswith("_max")
            parts[c] = g[c].min() if mn else (g[c].max() if mx else g[c].median())
        cum = pd.DataFrame(parts).reset_index(drop=True)
        df = elig.merge(cum, on="stay_id", how="left")
        for base, a, b in (("map_med", "nbpm_med", "abpm_med"),
                           ("map_min", "nbpm_min", "abpm_min"),
                           ("map_max", "nbpm_max", "abpm_max")):
            df[base] = df[a].fillna(df[b])
        for c in MISS_SRC:
            df[f"miss_{c}"] = df[c].isna().astype(int)
        X, y = df[num_cols + CATS], df["y"].to_numpy()
        Xtr, Xte, ytr, yte = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y)
        pre = ColumnTransformer([
            ("num", Pipeline([("imp", SimpleImputer(strategy="median")),
                              ("sc", StandardScaler())]), num_cols),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATS),
        ])
        clf = Pipeline([("pre", pre),
                        ("lr", LogisticRegression(C=1.0, max_iter=5000))])
        clf.fit(Xtr, ytr)
        p = clf.predict_proba(Xte)[:, 1]
        rows.append((L, len(df), int(df.y.sum()),
                     round(roc_auc_score(yte, p), 4),
                     round(average_precision_score(yte, p), 4)))
        if L in (1, 3, 6, 12, 24):
            names = list(num_cols) + list(
                clf.named_steps["pre"].named_transformers_["cat"]
                .get_feature_names_out(CATS))
            coefs = clf.named_steps["lr"].coef_[0]
            for i in np.argsort(np.abs(coefs))[::-1][:8]:
                coef_rows.append((L, names[i], round(float(coefs[i]), 3)))
        print(f"L={L}: n={len(df)} ev={int(df.y.sum())} "
              f"AUC={rows[-1][3]} AP={rows[-1][4]}", flush=True)
    pd.DataFrame(rows, columns=["L", "n", "events", "auc", "ap"]).to_csv(
        OUT + "landmark_metrics.csv", index=False)
    pd.DataFrame(coef_rows, columns=["L", "feature", "coef"]).to_csv(
        OUT + "topcoefs.csv", index=False)

    # ---- 2. univariate per vital per hour ----
    hourly["map_med"] = hourly["nbpm_med"].fillna(hourly["abpm_med"])
    uni = []
    for v in ["hr_med", "rr_med", "spo2_med", "map_med", "temp_med",
              "gcs_med", "lactate_med", "creat_med"]:
        sub = hourly[["stay_id", "h", v]].dropna().merge(
            static[["stay_id", "y"]], on="stay_id")
        for h, g in sub.groupby("h"):
            if g.y.nunique() < 2:
                continue
            uni.append((v, int(h), round(roc_auc_score(g.y, g[v]), 4),
                        len(g), int(g.y.sum())))
    pd.DataFrame(uni, columns=["vital", "h", "auc", "n", "events"]).to_csv(
        OUT + "univariate.csv", index=False)
    print("wrote landmark_metrics.csv, topcoefs.csv, univariate.csv", flush=True)


if __name__ == "__main__":
    main()
