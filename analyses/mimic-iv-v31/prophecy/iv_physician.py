"""Physician-leniency IV for the DNR -> death effect (MIMIC-IV v3.1, s0 only).

Judge-leniency design: the admitting provider's leave-one-out DNR<48h
rate instruments the DNR decision, conditional on unit fixed effects +
rich patient controls (night admission checked as a second instrument:
no first stage, discarded). Sample: B-rich population (ICU los>=48h,
sofa48 known), providers with 50+ stays (robustness: 20+). 2SLS with
structural-residual SEs + SOFA-tertile heterogeneity.
Aggregates only leave s0.

Run on s0: /srv/mimic-iv/.venv/bin/python iv_physician.py
"""
import math
import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

DB = "/srv/mimic-iv/db/mimic4-v31.db"


def cause_of(row, sepmap):
    if sepmap.get(row["stay_id"], 0) == 1:
        return "sepsis"
    v, c = str(row["icd_version"]), str(row["icd_code"])
    if v == "10":
        if c[:1] == "G" or c[:3] in ("I60", "I61", "I62", "I63", "I64",
                                     "I65", "I66", "I67", "I68", "I69"):
            return "neuro"
        if c[:1] == "I":
            return "cardiac"
        if c[:1] == "J":
            return "respiratory"
        return "other"
    try:
        n = int(c[:3])
    except ValueError:
        return "other"
    if 410 <= n <= 429:
        return "cardiac"
    if 430 <= n <= 438 or 320 <= n <= 359:
        return "neuro"
    if 460 <= n <= 519:
        return "respiratory"
    return "other"


def design(df, cols, extra=()):
    X = pd.get_dummies(df[cols + ["cause", "gender", "unit"] + list(extra)],
                       columns=["cause", "gender", "unit"], drop_first=True,
                       dtype=float).fillna(df[cols].median(numeric_only=True))
    zv = [c for c in X.columns if X[c].std() == 0]
    if zv:
        X = X.drop(columns=zv)
    return X


def tsls(y, X_exog, d, z, label):
    """2SLS with correct structural-residual SEs. X_exog: DataFrame (no const).
    Returns (est, se, F_first)."""
    X1 = sm.add_constant(pd.concat([X_exog, z], axis=1).values)
    fs = sm.OLS(d.values, X1).fit()
    k = X_exog.shape[1]
    F = float((fs.params[-1] / fs.bse[-1]) ** 2)
    dhat = fs.fittedvalues
    Xh = sm.add_constant(
        pd.concat([X_exog, pd.Series(dhat, index=X_exog.index)], axis=1).values)
    s2 = sm.OLS(y.values, Xh).fit()
    beta = np.asarray(s2.params)
    Xs = sm.add_constant(
        pd.concat([X_exog, d], axis=1).values)
    resid = y.values - Xs @ beta
    s2v = float(resid @ resid) / (len(y) - Xh.shape[1])
    V = s2v * np.linalg.pinv(Xh.T @ Xh)
    se = math.sqrt(max(float(V[-1, -1]), 0.0))
    print(f"  [{label}] first-stage F={F:.1f} IV={float(beta[-1]):.3f} "
          f"[{float(beta[-1]) - 1.96 * se:.3f}-"
          f"{float(beta[-1]) + 1.96 * se:.3f}]", flush=True)
    return float(beta[-1]), se, F


def main():
    con = duckdb.connect(DB, read_only=True)
    print("loading B sample + provider + night...", flush=True)
    stays = con.execute("""
SELECT i.stay_id, i.intime, i.outtime, i.first_careunit AS unit,
  a.hospital_expire_flag AS y, a.deathtime, a.admittime,
  a.admit_provider_id AS prov, p.anchor_age AS age, p.gender,
  CASE WHEN s.stay_id IS NOT NULL THEN 1 ELSE 0 END AS sepsis
FROM mimiciv_icu.icustays i
JOIN mimiciv_hosp.admissions a ON a.hadm_id = i.hadm_id
JOIN mimiciv_hosp.patients p ON p.subject_id = i.subject_id
LEFT JOIN (SELECT DISTINCT stay_id FROM mimiciv_derived.sepsis3) s
  USING (stay_id)""").fetchdf()
    stays["los_h"] = (pd.to_datetime(stays["outtime"]) -
                      pd.to_datetime(stays["intime"])).dt.total_seconds() / 3600
    stays["night"] = pd.to_datetime(
        stays["admittime"]).dt.hour.map(lambda h: 1 if h >= 19 or h < 7 else 0)
    sofa = con.execute("""
SELECT stay_id, respiration_24hours AS s_resp, coagulation_24hours AS s_coag,
  liver_24hours AS s_liver, cardiovascular_24hours AS s_cv,
  cns_24hours AS s_cns, renal_24hours AS s_renal, sofa_24hours AS sofa48
FROM mimiciv_derived.sofa WHERE hr = 48""").fetchdf()
    stays = stays.merge(sofa, on="stay_id", how="left")
    so24 = con.execute("""
SELECT stay_id, sofa_24hours AS sofa24 FROM mimiciv_derived.sofa
WHERE hr = 24""").fetchdf()
    stays = stays.merge(so24, on="stay_id", how="left")
    code = con.execute("""
SELECT stay_id, MIN(CASE WHEN dnr = 1 OR cmo = 1 THEN charttime END) AS dnr_t
FROM mimiciv_derived.code_status GROUP BY 1""").fetchdf()
    stays = stays.merge(code, on="stay_id", how="left")
    stays["dnr_h"] = (pd.to_datetime(stays["dnr_t"]) -
                      pd.to_datetime(stays["intime"])).dt.total_seconds() / 3600
    dx = con.execute("""
SELECT i.stay_id, d.icd_version, d.icd_code
FROM mimiciv_hosp.diagnoses_icd d
JOIN mimiciv_icu.icustays i ON i.hadm_id = d.hadm_id
WHERE d.seq_num = 1""").fetchdf().drop_duplicates("stay_id")
    sepmap = stays.set_index("stay_id")["sepsis"].to_dict()
    dx["cause"] = dx.apply(lambda r: cause_of(r, sepmap), axis=1)
    stays = stays.merge(dx[["stay_id", "cause"]], on="stay_id", how="left")
    supp = con.execute("""
SELECT i.stay_id,
  MAX(CASE WHEN v.starttime <= i.intime + INTERVAL 48 HOUR
            AND (v.endtime IS NULL OR v.endtime > i.intime + INTERVAL 48 HOUR)
            AND v.ventilation_status IN ('InvasiveVent', 'Tracheostomy')
           THEN 1 ELSE 0 END) AS vent48,
  MAX(CASE WHEN x.starttime <= i.intime + INTERVAL 48 HOUR
            AND (x.endtime IS NULL OR x.endtime > i.intime + INTERVAL 48 HOUR)
           THEN 1 ELSE 0 END) AS vaso48,
  MAX(CASE WHEN r.charttime BETWEEN i.intime + INTERVAL 36 HOUR
                              AND i.intime + INTERVAL 48 HOUR
            AND r.dialysis_active = 1 THEN 1 ELSE 0 END) AS rrt48
FROM mimiciv_icu.icustays i
LEFT JOIN mimiciv_derived.ventilation v USING (stay_id)
LEFT JOIN mimiciv_derived.vasoactive_agent x USING (stay_id)
LEFT JOIN mimiciv_derived.rrt r USING (stay_id)
WHERE date_diff('hour', i.intime, i.outtime) >= 48
GROUP BY 1""").fetchdf()
    stays = stays.merge(supp, on="stay_id", how="left")
    labs = con.execute("""
SELECT i.stay_id,
  MAX(CASE WHEN l.itemid IN (50813, 52442, 53154) THEN l.valuenum END) AS lac,
  MAX(CASE WHEN l.itemid IN (50912, 52024, 52546) THEN l.valuenum END) AS crea
FROM mimiciv_hosp.labevents l
JOIN mimiciv_icu.icustays i ON i.hadm_id = l.hadm_id
WHERE l.charttime BETWEEN i.intime + INTERVAL 24 HOUR
                      AND i.intime + INTERVAL 48 HOUR
  AND l.valuenum > 0
GROUP BY 1""").fetchdf()
    stays = stays.merge(labs, on="stay_id", how="left")
    con.close()
    print(f"stays: {len(stays)}", flush=True)

    b = stays[(stays["los_h"] >= 48) & (stays["sofa48"].notna()) &
              (stays["prov"].notna())].copy()
    b["exp"] = ((b["dnr_h"].notna()) & (b["dnr_h"] < 48)).astype(int)
    b["lac"] = b["lac"].clip(upper=20)
    b["crea"] = b["crea"].clip(upper=15)
    base = ["s_resp", "s_coag", "s_liver", "s_cv", "s_cns", "s_renal",
            "age", "sepsis", "vent48", "vaso48", "rrt48", "lac", "crea"]

    for min_n in [50, 20]:
        vc = b["prov"].value_counts()
        keep = set(vc[vc >= min_n].index)
        d = b[b["prov"].isin(keep)].copy().reset_index(drop=True)
        # leave-one-out provider DNR rate
        g = d.groupby("prov")["exp"].agg(["sum", "count"])
        d = d.merge(g, left_on="prov", right_index=True)
        d["iv"] = (d["sum"] - d["exp"]) / (d["count"] - 1)
        d["prov_n"] = d["count"]
        print(f"===== providers with {min_n}+ stays: {len(keep)} providers, "
              f"n={len(d)} =====", flush=True)
        print(f"  IV spread: p10={d['iv'].quantile(0.1):.3f} "
              f"med={d['iv'].median():.3f} "
              f"p90={d['iv'].quantile(0.9):.3f}", flush=True)

        # balance: instrument vs pre-determined covariates, WITHIN unit
        # (raw IV correlates with unit case-mix; identification is
        # within-unit, so balance must be too)
        U = pd.get_dummies(d["unit"], dtype=float).values
        ivr = sm.OLS(d["iv"].values, U).fit().resid
        d["iv_hi"] = (ivr > np.median(ivr)).astype(int)
        print("  balance within-unit (IV resid above/below median):",
              flush=True)
        for c in ["age", "sofa24", "sofa48", "sepsis", "lac", "crea"]:
            x = d[c].fillna(d[c].median())
            xr = sm.OLS(x.values, U).fit().resid
            a, e = xr[d["iv_hi"] == 1], xr[d["iv_hi"] == 0]
            t = stats.ttest_ind(a, e).pvalue
            s = x.std()
            print(f"    {c}: Δ={a.mean() - e.mean():.3f} "
                  f"({(a.mean() - e.mean()) / s:+.3f} SD) p={t:.2g}",
                  flush=True)
        X = design(d, base + ["prov_n"])

        # OLS benchmark
        Xo = sm.add_constant(
            pd.concat([X, d["exp"]], axis=1).values)
        ols = sm.OLS(d["y"].values, Xo).fit(cov_type="HC1")
        print(f"  OLS risk-diff: {ols.params[-1]:.3f} "
              f"[{ols.conf_int()[-1, 0]:.3f}-{ols.conf_int()[-1, 1]:.3f}]",
              flush=True)
        # reduced form
        Xr = sm.add_constant(
            pd.concat([X, d["iv"]], axis=1).values)
        rf = sm.OLS(d["y"].values, Xr).fit(cov_type="HC1")
        print(f"  reduced form (death ~ IV): {rf.params[-1]:.3f} "
              f"p={rf.pvalues[-1]:.2g}", flush=True)
        # 2SLS, provider IV
        tsls(d["y"], X, d["exp"], d[["iv"]], f"provider-IV{min_n}")
        # first stage detail: compliance gradient
        d["iv_q"] = pd.qcut(d["iv"], 5, labels=False, duplicates="drop")
        qtab = d.groupby("iv_q")["exp"].agg(["mean", "count"])
        print("  first-stage gradient (IV quintile -> DNR rate):",
              qtab["mean"].round(3).tolist(), flush=True)
        if min_n == 50:
            # night admission as candidate second instrument: check
            # first stage (too weak to use: F~5, reported and discarded)
            Xn = sm.add_constant(
                pd.concat([X, d["night"]], axis=1).values)
            fsn = sm.OLS(d["exp"].values, Xn).fit()
            Fn = float((fsn.params[-1] / fsn.bse[-1]) ** 2)
            print(f"  night first-stage F={Fn:.1f} "
                  f"(DNR|night={d[d['night'] == 1]['exp'].mean():.3f} vs "
                  f"day={d[d['night'] == 0]['exp'].mean():.3f}) — too weak, "
                  f"provider IV only", flush=True)
            # heterogeneity: 2SLS by SOFA tertile (is the causal effect
            # concentrated where physiology says "fine"?)
            d["tert"] = pd.qcut(d["sofa48"], 3,
                                labels=["lo", "mid", "hi"])
            for t, g in d.groupby("tert", observed=True):
                Xg = design(g, base + ["prov_n"])
                print(f"    tert {t}: n={len(g)} "
                      f"DNR rate={g['exp'].mean():.3f} "
                      f"death={g['y'].mean():.3f}", flush=True)
                tsls(g["y"], Xg, g["exp"], g[["iv"]], f"tert-{t}")
    print("done", flush=True)


if __name__ == "__main__":
    main()
