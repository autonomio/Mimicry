"""Early ICU mortality v2 (MIMIC-IV v3.1, s0 only).

v1 base features (first-6h vitals/labs/GCS + demographics) PLUS prior-year
lab trajectories: per test, last value, OLS slope vs days-before-admission
(negative = rising into admission), abnormal fraction, max, count, and a
missingness flag. Logreg only (the reference model): base vs base+history
on the identical split. Prints only aggregate metrics.

Run on s0: /srv/mimic-iv/.venv/bin/python early_mortality_v2.py
"""
import duckdb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# itemid -> (short name, plausibility lo, hi)
TESTS = {
    50813: ("lactate", 0, 30), 50912: ("creat", 0, 20),
    51006: ("bun", 0, 150), 50963: ("bnp", 0, 100000),
    50924: ("ferritin", 0, 50000), 51003: ("trop", 0, 50),
    50889: ("crp", 0, 500), 51301: ("wbc", 0, 200),
    50920: ("egfr", 0, 200), 50885: ("bili", 0, 60),
    50878: ("ast", 0, 20000), 51244: ("lymph", 0, 100),
    51200: ("eos", 0, 100), 50915: ("ddimer", 0, 50000),
    50931: ("gluc", 0, 2000), 50983: ("sodium", 100, 180),
    50971: ("potass", 0, 10), 50882: ("bicarb", 0, 60),
    51222: ("hb", 0, 25), 51265: ("plt", 0, 2000),
    50868: ("agap", -10, 50),
}


def histlabs_sql():
    conds = " OR ".join(
        f"(l.itemid = {i} AND l.valuenum BETWEEN {lo} AND {hi})"
        for i, (_, lo, hi) in TESTS.items())
    ids = ", ".join(str(i) for i in TESTS)
    return f"""
SELECT f.stay_id, l.itemid,
  arg_max(l.valuenum, l.charttime) AS last,
  REGR_SLOPE(l.valuenum, date_diff('day', l.charttime, f.admittime)) AS slope,
  AVG(CASE WHEN l.flag = 'abnormal' THEN 1.0 ELSE 0.0 END) AS abn,
  MAX(l.valuenum) AS maxv, COUNT(*) AS n
FROM (SELECT stay_id, subject_id, admittime FROM (
        SELECT s.stay_id, s.subject_id, a.admittime, s.los,
               row_number() OVER (PARTITION BY s.hadm_id ORDER BY s.intime) AS rn
        FROM mimiciv_icu.icustays s
        JOIN mimiciv_hosp.admissions a USING (hadm_id))
      WHERE rn = 1 AND los >= 0.25) f
JOIN mimiciv_hosp.labevents l
  ON l.subject_id = f.subject_id
 AND l.charttime < f.admittime AND l.charttime >= f.admittime - INTERVAL 365 DAY
 AND l.itemid IN ({ids}) AND l.valuenum IS NOT NULL
 AND ({conds})
GROUP BY 1, 2
"""

DB = "/srv/mimic-iv/db/mimic4-v31.db"

COHORT_SQL = """
WITH ranked AS (
  SELECT s.stay_id, s.subject_id, s.intime, s.first_careunit, s.los,
         p.anchor_age, p.gender, a.admission_type, a.hospital_expire_flag AS y,
         row_number() OVER (PARTITION BY s.hadm_id ORDER BY s.intime) AS rn
  FROM mimiciv_icu.icustays s
  JOIN mimiciv_hosp.patients p USING (subject_id)
  JOIN mimiciv_hosp.admissions a USING (hadm_id)
),
first_stay AS (
  SELECT stay_id, subject_id, intime, first_careunit,
         anchor_age, gender, admission_type, y
  FROM ranked WHERE rn = 1 AND los >= 0.25
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
    hist = con.execute(histlabs_sql()).fetchdf()
    con.close()
    print(f"cohort: {len(df)} stays, events: {int(df.y.sum())} ({df.y.mean():.3f})")
    print(f"history cells: {len(hist)} stay-tests", flush=True)
    hist["test"] = hist["itemid"].map({i: n for i, (n, _, _) in TESTS.items()})
    wide = hist.pivot_table(index="stay_id",
                            columns="test",
                            values=["last", "slope", "abn", "maxv", "n"],
                            aggfunc="first")
    wide.columns = [f"h_{t}_{s}" for s, t in wide.columns]
    df = df.merge(wide, on="stay_id", how="left")
    hist_cols = []
    for _, (t, _, _) in TESTS.items():
        df[f"h_{t}_miss"] = df[f"h_{t}_last"].isna().astype(int)
        hist_cols += [f"h_{t}_last", f"h_{t}_slope", f"h_{t}_abn",
                      f"h_{t}_maxv", f"h_{t}_n", f"h_{t}_miss"]
    hist_cols = [c for c in hist_cols
                 if c in df.columns and not df[c].isna().all()]
    print(f"history features: {len(hist_cols)}", flush=True)

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

    base_cols = list(num_cols)
    full_cols = list(num_cols) + hist_cols
    y = df["y"].to_numpy()
    idx_tr, idx_te = train_test_split(
        np.arange(len(df)), test_size=0.2, random_state=42, stratify=y)
    ytr, yte = y[idx_tr], y[idx_te]
    print(f"train: {len(idx_tr)} (events {ytr.sum()}), "
          f"test: {len(idx_te)} (events {yte.sum()})")

    def fit_predict(cols):
        num = [c for c in cols if c not in cat_cols]
        pre = ColumnTransformer([
            ("num", Pipeline([("imp", SimpleImputer(strategy="median")),
                              ("sc", StandardScaler())]), num),
            ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
        ])
        clf = Pipeline([("pre", pre),
                        ("lr", LogisticRegression(C=1.0, max_iter=5000))])
        clf.fit(df[cols].iloc[idx_tr], ytr)
        p = clf.predict_proba(df[cols].iloc[idx_te])[:, 1]
        return clf, p

    _, p_base = fit_predict(base_cols + cat_cols)
    print(f"[base] AUC: {roc_auc_score(yte, p_base):.4f} | "
          f"AP: {average_precision_score(yte, p_base):.4f} | "
          f"Brier: {brier_score_loss(yte, p_base):.4f}")
    clf_full, p_full = fit_predict(full_cols + cat_cols)
    print(f"[base+history] AUC: {roc_auc_score(yte, p_full):.4f} | "
          f"AP: {average_precision_score(yte, p_full):.4f} | "
          f"Brier: {brier_score_loss(yte, p_full):.4f}")
    print(f"(base rate {yte.mean():.4f})")

    q = pd.qcut(p_full, 10, labels=False, duplicates="drop")
    print("calibration[full]: decile,n,mean_pred,observed")
    for d in sorted(set(q)):
        m = q == d
        print(f"  {d},{m.sum()},{p_full[m].mean():.4f},{yte[m].mean():.4f}")

    names = list(full_cols) + list(
        clf_full.named_steps["pre"].named_transformers_["cat"]
        .get_feature_names_out(cat_cols))
    coefs = clf_full.named_steps["lr"].coef_[0]
    order = np.argsort(coefs)
    print("most negative coef:")
    for i in order[:8]:
        print(f"  {names[i]}: {coefs[i]:+.3f}")
    print("most positive coef:")
    for i in order[-8:][::-1]:
        print(f"  {names[i]}: {coefs[i]:+.3f}")
    print("top history-lab coefs by |coef|:")
    h_idx = [i for i in range(len(names)) if names[i].startswith("h_")]
    for i in sorted(h_idx, key=lambda j: -abs(coefs[j]))[:12]:
        print(f"  {names[i]}: {coefs[i]:+.3f}")


if __name__ == "__main__":
    main()
