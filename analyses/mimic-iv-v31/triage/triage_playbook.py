"""Triage reverse-engineering (MIMIC-IV v3.1, s0 only).

Reconstruct the triage moment for every first ICU stay and model the
hospital's de-facto triage decisions from structured fields ONLY
(no free text anywhere: no notes, no descriptions, no value text;
diagnoses via ICD prefixes, DRG via code, nothing else).

Feature blocks (all structured):
  PRESENT: age/gender/race/insurance/language/marital, admission type/location,
    provider experience, current-admission dx buckets + Charlson
    + HCFA-DRG(top30) + APR severity/mortality (retrospective descriptors).
  HISTORY: prior admissions/ICU counts, prior LOS, days since discharge,
    prior-year utilization, prior Charlson max, 9 prior-dx bucket flags,
    prior procedure count, prior max lactate/creatinine.
  SYSTEM ("gov situation"): hour of day + night flag.
    Bed census, weekday and season are UNRECOVERABLE: per-patient whole-day
    date offsets destroy cross-patient simultaneity (verified empirically).
    Anchor year group is used for era cross-tabs only, never as a feature.
Outcomes: first_careunit (multiclass), direct ICU <6h (binary).
Plus: presentation-only vs full ablation, hour/night/year cross-tabs.

Run on s0: /srv/mimic-iv/.venv/bin/python triage_playbook.py
Outputs (aggregates only) to /tmp/triage_*.csv + printed metrics.
"""
import duckdb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score,
                             brier_score_loss, roc_auc_score)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

DB = "/srv/mimic-iv/db/mimic4-v31.db"
OUT = "/tmp/"

BASE_SQL = """
SELECT s.stay_id, s.subject_id, s.hadm_id, s.intime, s.outtime, s.los,
       s.first_careunit, a.admittime,
       p.anchor_age, p.gender, p.anchor_year_group, a.admission_type, a.admission_location,
       a.insurance, a.language, a.marital_status, a.race,
       a.admit_provider_id, p.anchor_year_group,
       CASE WHEN s.intime < a.admittime + INTERVAL 6 HOUR THEN 1 ELSE 0 END AS direct6h,
       date_diff('hour', a.admittime, s.intime) AS hours_to_icu
FROM mimiciv_icu.icustays s
JOIN mimiciv_hosp.patients p USING (subject_id)
JOIN mimiciv_hosp.admissions a USING (hadm_id)
QUALIFY row_number() OVER (PARTITION BY s.hadm_id ORDER BY s.intime) = 1
ORDER BY s.stay_id
"""

HIST_SQL = """
WITH base AS (
  SELECT s.stay_id, s.subject_id, s.hadm_id, a.admittime, a.admit_provider_id
  FROM mimiciv_icu.icustays s
  JOIN mimiciv_hosp.admissions a USING (hadm_id)
  QUALIFY row_number() OVER (PARTITION BY s.hadm_id ORDER BY s.intime) = 1
),
priors AS (
  SELECT b.stay_id, p.hadm_id AS phadm, p.admittime AS padm, p.dischtime AS pdisch
  FROM base b
  JOIN mimiciv_hosp.admissions p
    ON p.subject_id = b.subject_id AND p.admittime < b.admittime
),
util AS (
  SELECT stay_id, COUNT(*) AS n_prior_adm,
    COALESCE(SUM(date_diff('day', padm, pdisch)), 0) AS prior_los_total,
    MAX(date_diff('day', padm, pdisch)) AS prior_los_max
  FROM priors GROUP BY 1
),
yr AS (
  SELECT b.stay_id, COUNT(*) AS prior_year_n
  FROM base b
  JOIN mimiciv_hosp.admissions p
    ON p.subject_id = b.subject_id
   AND p.admittime < b.admittime
   AND p.admittime >= b.admittime - INTERVAL 1 YEAR
  GROUP BY 1
),
since AS (
  SELECT b.stay_id, date_diff('day', MAX(p.dischtime), b.admittime) AS days_since_last
  FROM base b
  JOIN mimiciv_hosp.admissions p
    ON p.subject_id = b.subject_id AND p.admittime < b.admittime
  GROUP BY 1, b.admittime
),
picu AS (
  SELECT b.stay_id, COUNT(DISTINCT q.stay_id) AS n_prior_icu
  FROM base b
  JOIN mimiciv_hosp.admissions p
    ON p.subject_id = b.subject_id AND p.admittime < b.admittime
  JOIN mimiciv_icu.icustays q ON q.hadm_id = p.hadm_id
  GROUP BY 1
),
pcharl AS (
  SELECT b.stay_id, MAX(c.charlson_comorbidity_index) AS prior_charlson_max
  FROM base b
  JOIN mimiciv_hosp.admissions p
    ON p.subject_id = b.subject_id AND p.admittime < b.admittime
  JOIN mimiciv_derived.charlson c ON c.hadm_id = p.hadm_id
  GROUP BY 1
),
pdx AS (
  SELECT b.stay_id,
    MAX(CASE WHEN (d.icd_version = 9 AND d.icd_code BETWEEN '410' AND '41499'
                    OR d.icd_version = 10 AND LEFT(d.icd_code, 3) BETWEEN 'I20' AND 'I25')
             THEN 1 ELSE 0 END) AS px_cardiac,
    MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code, 3) = '428'
                    OR d.icd_version = 10 AND LEFT(d.icd_code, 3) = 'I50')
             THEN 1 ELSE 0 END) AS px_hf,
    MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code, 3) BETWEEN '430' AND '438'
                    OR d.icd_version = 10 AND LEFT(d.icd_code, 3) BETWEEN 'I60' AND 'I69')
             THEN 1 ELSE 0 END) AS px_stroke,
    MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code, 3) BETWEEN '584' AND '586'
                    OR d.icd_version = 10 AND LEFT(d.icd_code, 3) BETWEEN 'N17' AND 'N19')
             THEN 1 ELSE 0 END) AS px_renal,
    MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code, 3) BETWEEN '490' AND '496'
                    OR d.icd_version = 10 AND LEFT(d.icd_code, 3) BETWEEN 'J40' AND 'J47')
             THEN 1 ELSE 0 END) AS px_copd,
    MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code, 3) = '250'
                    OR d.icd_version = 10 AND LEFT(d.icd_code, 3) BETWEEN 'E10' AND 'E14')
             THEN 1 ELSE 0 END) AS px_diab,
    MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code, 3) BETWEEN '140' AND '239'
                    OR d.icd_version = 10 AND LEFT(d.icd_code, 3) BETWEEN 'C00' AND 'D49')
             THEN 1 ELSE 0 END) AS px_onc,
    MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code, 3) = '038'
                    OR d.icd_version = 10 AND LEFT(d.icd_code, 3) BETWEEN 'A40' AND 'A41')
             THEN 1 ELSE 0 END) AS px_sepsis,
    MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code, 3) BETWEEN '570' AND '573'
                    OR d.icd_version = 10 AND LEFT(d.icd_code, 3) BETWEEN 'K70' AND 'K77')
             THEN 1 ELSE 0 END) AS px_liver
  FROM base b
  JOIN mimiciv_hosp.admissions p
    ON p.subject_id = b.subject_id AND p.admittime < b.admittime
  JOIN mimiciv_hosp.diagnoses_icd d ON d.hadm_id = p.hadm_id
  GROUP BY 1
),
pproc AS (
  SELECT b.stay_id, COUNT(*) AS n_prior_proc
  FROM base b
  JOIN mimiciv_hosp.admissions p
    ON p.subject_id = b.subject_id AND p.admittime < b.admittime
  JOIN mimiciv_hosp.procedures_icd r ON r.hadm_id = p.hadm_id
  GROUP BY 1
),
plabs AS (
  SELECT b.stay_id,
    MAX(CASE WHEN l.itemid = 50813 AND l.valuenum BETWEEN 0 AND 30 THEN l.valuenum END) AS prior_lact_max,
    MAX(CASE WHEN l.itemid = 50912 AND l.valuenum BETWEEN 0 AND 20 THEN l.valuenum END) AS prior_creat_max
  FROM base b
  JOIN mimiciv_hosp.labevents l
    ON l.subject_id = b.subject_id AND l.charttime < b.admittime
   AND l.itemid IN (50813, 50912)
  GROUP BY 1
),
prov AS (
  SELECT b.stay_id,
    CASE WHEN ANY_VALUE(b.admit_provider_id) IS NULL THEN NULL
         ELSE COUNT(p2.hadm_id) END AS prov_n_prior,
    MAX(CASE WHEN b.admit_provider_id IS NULL THEN 1 ELSE 0 END) AS prov_null
  FROM base b
  LEFT JOIN mimiciv_hosp.admissions p2
    ON b.admit_provider_id IS NOT NULL
   AND p2.admit_provider_id = b.admit_provider_id AND p2.admittime < b.admittime
  GROUP BY 1
)
SELECT b.stay_id, COALESCE(u.n_prior_adm, 0) AS n_prior_adm,
  COALESCE(i.n_prior_icu, 0) AS n_prior_icu,
  COALESCE(u.prior_los_total, 0) AS prior_los_total,
  u.prior_los_max, s.days_since_last, COALESCE(y.prior_year_n, 0) AS prior_year_n,
  c.prior_charlson_max,
  COALESCE(d.px_cardiac, 0) AS px_cardiac, COALESCE(d.px_hf, 0) AS px_hf,
  COALESCE(d.px_stroke, 0) AS px_stroke, COALESCE(d.px_renal, 0) AS px_renal,
  COALESCE(d.px_copd, 0) AS px_copd, COALESCE(d.px_diab, 0) AS px_diab,
  COALESCE(d.px_onc, 0) AS px_onc, COALESCE(d.px_sepsis, 0) AS px_sepsis,
  COALESCE(d.px_liver, 0) AS px_liver,
  COALESCE(r.n_prior_proc, 0) AS n_prior_proc,
  l.prior_lact_max, l.prior_creat_max, v.prov_n_prior, v.prov_null
FROM base b
LEFT JOIN util u USING (stay_id)
LEFT JOIN since s USING (stay_id)
LEFT JOIN yr y USING (stay_id)
LEFT JOIN picu i USING (stay_id)
LEFT JOIN pcharl c USING (stay_id)
LEFT JOIN pdx d USING (stay_id)
LEFT JOIN pproc r USING (stay_id)
LEFT JOIN plabs l USING (stay_id)
LEFT JOIN prov v USING (stay_id)
ORDER BY b.stay_id
"""

CURR_SQL = """
WITH base AS (
  SELECT s.stay_id, s.hadm_id
  FROM mimiciv_icu.icustays s
  QUALIFY row_number() OVER (PARTITION BY s.hadm_id ORDER BY s.intime) = 1
)
SELECT b.stay_id,
  MAX(CASE WHEN (d.icd_version = 9 AND d.icd_code BETWEEN '410' AND '41499'
                  OR d.icd_version = 10 AND LEFT(d.icd_code, 3) BETWEEN 'I20' AND 'I25')
           THEN 1 ELSE 0 END) AS dx_cardiac,
  MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code, 3) = '428'
                  OR d.icd_version = 10 AND LEFT(d.icd_code, 3) = 'I50')
           THEN 1 ELSE 0 END) AS dx_hf,
  MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code, 3) BETWEEN '430' AND '438'
                  OR d.icd_version = 10 AND LEFT(d.icd_code, 3) BETWEEN 'I60' AND 'I69')
           THEN 1 ELSE 0 END) AS dx_stroke,
  MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code, 3) BETWEEN '584' AND '586'
                  OR d.icd_version = 10 AND LEFT(d.icd_code, 3) BETWEEN 'N17' AND 'N19')
           THEN 1 ELSE 0 END) AS dx_renal,
  MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code, 3) BETWEEN '490' AND '496'
                  OR d.icd_version = 10 AND LEFT(d.icd_code, 3) BETWEEN 'J40' AND 'J47')
           THEN 1 ELSE 0 END) AS dx_copd,
  MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code, 3) = '250'
                  OR d.icd_version = 10 AND LEFT(d.icd_code, 3) BETWEEN 'E10' AND 'E14')
           THEN 1 ELSE 0 END) AS dx_diab,
  MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code, 3) BETWEEN '140' AND '239'
                  OR d.icd_version = 10 AND LEFT(d.icd_code, 3) BETWEEN 'C00' AND 'D49')
           THEN 1 ELSE 0 END) AS dx_onc,
  MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code, 3) = '038'
                  OR d.icd_version = 10 AND LEFT(d.icd_code, 3) BETWEEN 'A40' AND 'A41')
           THEN 1 ELSE 0 END) AS dx_sepsis,
  MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code, 3) BETWEEN '570' AND '573'
                  OR d.icd_version = 10 AND LEFT(d.icd_code, 3) BETWEEN 'K70' AND 'K77')
           THEN 1 ELSE 0 END) AS dx_liver,
  MAX(c.charlson_comorbidity_index) AS charlson_now,
  MAX(CASE WHEN g.drg_type = 'HCFA' THEN g.drg_code END) AS drg_hcfa,
  MAX(CASE WHEN g.drg_type = 'APR' THEN g.drg_severity END) AS apr_sev,
  MAX(CASE WHEN g.drg_type = 'APR' THEN g.drg_mortality END) AS apr_mort
FROM base b
LEFT JOIN mimiciv_hosp.diagnoses_icd d ON d.hadm_id = b.hadm_id
LEFT JOIN mimiciv_derived.charlson c ON c.hadm_id = b.hadm_id
LEFT JOIN mimiciv_hosp.drgcodes g ON g.hadm_id = b.hadm_id
GROUP BY 1
ORDER BY 1
"""

# NOTE: bed census is NOT computable in MIMIC-IV. Dates carry per-patient
# random whole-day offsets (shifted span covers 63+ years vs 14 real years),
# so cross-patient simultaneity is destroyed. Verified: lab-draw hours show
# the real clinical pattern (time-of-day preserved) while admission weekdays
# are uniform (weekday/season destroyed). System-state features = hour of
# day + night flag only; anchor_year_group is era stratification for the
# by-year cross-tab, not a model feature (era is not knowable prospectively
# in a usable way and leaks secular drift). No census, weekday, or month.

CATS = ["gender", "admission_type", "admission_location", "insurance",
        "language", "marital_status", "race", "drg_top30"]
NUM = ["anchor_age", "prov_n_prior", "prov_null",
       "n_prior_adm", "n_prior_icu", "prior_los_total", "prior_los_max",
       "days_since_last", "prior_year_n", "prior_charlson_max",
       "px_cardiac", "px_hf", "px_stroke", "px_renal", "px_copd", "px_diab",
       "px_onc", "px_sepsis", "px_liver", "n_prior_proc",
       "prior_lact_max", "prior_creat_max",
       "dx_cardiac", "dx_hf", "dx_stroke", "dx_renal", "dx_copd", "dx_diab",
       "dx_onc", "dx_sepsis", "dx_liver", "charlson_now", "apr_sev", "apr_mort",
       "hour", "night"]
MISS = ["days_since_last", "prior_charlson_max", "prior_lact_max",
        "prior_creat_max", "prov_n_prior", "apr_sev", "apr_mort"]
PRESENT = ["anchor_age", "prov_null", "gender", "admission_type",
           "admission_location", "insurance", "language", "marital_status",
           "race", "prov_n_prior", "dx_cardiac", "dx_hf", "dx_stroke",
           "dx_renal", "dx_copd", "dx_diab", "dx_onc", "dx_sepsis", "dx_liver",
           "charlson_now", "drg_top30", "apr_sev", "apr_mort"]


def main():
    con = duckdb.connect(DB, read_only=True)
    base = con.execute(BASE_SQL).fetchdf()
    hist = con.execute(HIST_SQL).fetchdf()
    curr = con.execute(CURR_SQL).fetchdf()
    con.close()
    print(f"stays: {len(base)}", flush=True)

    df = base.merge(hist, on="stay_id").merge(curr, on="stay_id")
    ts = pd.to_datetime(df["admittime"])
    df["hour"] = ts.dt.hour
    df["night"] = ((ts.dt.hour >= 19) | (ts.dt.hour < 7)).astype(int)
    # Group rare units so stratification works
    vc = df["first_careunit"].value_counts()
    rare = set(vc[vc < 100].index)
    df["unit"] = df["first_careunit"].where(~df["first_careunit"].isin(rare),
                                            "OTHER_UNIT")
    print(f"units: {df['unit'].nunique()} "
          f"({len(rare)} rare grouped)", flush=True)
    top30 = set(df["drg_hcfa"].value_counts().head(30).index)
    df["drg_top30"] = df["drg_hcfa"].where(df["drg_hcfa"].isin(top30), "OTHER")
    df.loc[df["prov_null"] == 1, "prov_n_prior"] = np.nan
    for c in MISS:
        df[f"miss_{c}"] = df[c].isna().astype(int)
    num_cols = list(NUM) + [f"miss_{c}" for c in MISS]
    print(f"features: {len(num_cols)} numeric + {len(CATS)} categorical", flush=True)

    def fit_predict(X, y):
        Xtr, Xte, ytr, yte = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y)
        pre = ColumnTransformer([
            ("num", Pipeline([("imp", SimpleImputer(strategy="median")),
                              ("sc", StandardScaler())]),
             [c for c in num_cols if c in X.columns]),
            ("cat", OneHotEncoder(handle_unknown="ignore"),
             [c for c in CATS if c in X.columns]),
        ])
        clf = Pipeline([("pre", pre),
                        ("lr", LogisticRegression(C=1.0, max_iter=5000))])
        clf.fit(Xtr, ytr)
        return clf, Xte, yte, clf.predict_proba(Xte)

    # ---- M1: unit multiclass ----
    X, y = df[num_cols + CATS], df["unit"]
    clf, Xte, yte, P = fit_predict(X, y)
    pred = clf.classes_[P.argmax(axis=1)]
    print(f"[unit] acc: {accuracy_score(yte, pred):.4f}", flush=True)
    perclass = []
    for i, cls in enumerate(clf.classes_):
        b = (yte == cls).to_numpy()
        auc = roc_auc_score(b, P[:, i]) if b.sum() > 0 else float("nan")
        perclass.append((cls, int(b.sum()), round(float(auc), 4)))
        print(f"  {cls}: n={int(b.sum())} ovr_auc={auc:.4f}", flush=True)
    pd.DataFrame(perclass, columns=["unit", "n_test", "ovr_auc"]).to_csv(
        OUT + "triage_unit_perclass.csv", index=False)
    names = list(num_cols) + list(
        clf.named_steps["pre"].named_transformers_["cat"].get_feature_names_out(
            [c for c in CATS if c in X.columns]))
    rows = []
    for i, cls in enumerate(clf.classes_):
        for j in np.argsort(np.abs(clf.named_steps["lr"].coef_[i]))[::-1][:8]:
            rows.append((cls, names[j], round(float(clf.named_steps["lr"].coef_[i][j]), 3)))
    pd.DataFrame(rows, columns=["unit", "feature", "coef"]).to_csv(
        OUT + "triage_unit_topcoefs.csv", index=False)

    # ---- M2: direct6h binary, full vs presentation-only ----
    yb = df["direct6h"].to_numpy()
    for tag, cols in (("full", num_cols + CATS),
                      ("present_only", [c for c in PRESENT if c in df.columns])):
        Xb = df[cols]
        _, Xte, yte, P = fit_predict(Xb, yb)
        p = P[:, 1]
        print(f"[direct:{tag}] AUC: {roc_auc_score(yte, p):.4f} | "
              f"AP: {average_precision_score(yte, p):.4f} | "
              f"Brier: {brier_score_loss(yte, p):.4f}", flush=True)
    # calibration for full model
    _, Xte, yte, P = fit_predict(df[num_cols + CATS], yb)
    p = P[:, 1]
    q = pd.qcut(p, 10, labels=False, duplicates="drop")
    cal = []
    for d in sorted(set(q)):
        m = q == d
        cal.append((int(d), int(m.sum()), round(float(p[m].mean()), 4),
                    round(float(yte[m].mean()), 4)))
    pd.DataFrame(cal, columns=["decile", "n", "mean_pred", "observed"]).to_csv(
        OUT + "triage_direct_calibration.csv", index=False)

    # ---- system-state cross-tabs (hour/night/year; census impossible) ----
    by_hour = df.groupby("hour")["direct6h"].agg(["mean", "count"]).reset_index()
    by_hour.columns = ["hour", "direct_rate", "n"]
    by_hour.to_csv(OUT + "triage_direct_by_hour.csv", index=False)
    by_night = df.groupby("night")["direct6h"].agg(["mean", "count"]).reset_index()
    by_night.columns = ["night", "direct_rate", "n"]
    by_night.to_csv(OUT + "triage_direct_by_night.csv", index=False)
    by_year = df.groupby("anchor_year_group")["direct6h"].agg(["mean", "count"]).reset_index()
    by_year.columns = ["anchor_year_group", "direct_rate", "n"]
    by_year.to_csv(OUT + "triage_direct_by_year.csv", index=False)
    mix = df.groupby(["night", "unit"], observed=True).size().unstack(fill_value=0)
    mix = (mix.T / mix.sum(axis=1)).T
    mix.reset_index().to_csv(OUT + "triage_unitmix_night.csv", index=False)
    print("wrote triage_*.csv", flush=True)


if __name__ == "__main__":
    main()
