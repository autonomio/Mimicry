"""Constipation in the prior year vs hospital survival (MIMIC-IV v3.1, s0 only).

Exposure (structured only, window [admittime-365d, admittime)):
  coded: ICD 564.0x/K59.0x in prior admissions
  lax_any: laxative prescription start in window (formulary match)
  either/both; dose (distinct laxative classes 0/1/2+); recency 30d
  (none/remote/recent) + 180d sensitivity; full-caliper 1:1 PS matching
Outcome: hospital_expire_flag (same admission).
Methods: crude 2x2; adjusted logistic (OR+95% CI); 1:1 propensity matching with
caliper + balance + McNemar; dose-response; recency; subgroups; E-value.
Aggregates only leave s0.

Run on s0: /srv/mimic-iv/.venv/bin/python constipation.py
"""
import math
import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

DB = "/srv/mimic-iv/db/mimic4-v31.db"
OUT = "/tmp/"

LAX = """(UPPER(drug) LIKE '%SENNA%' OR UPPER(drug) LIKE '%DOCUSATE%'
 OR UPPER(drug) LIKE '%BISACODYL%' OR UPPER(drug) LIKE '%POLYETHYLENE%'
 OR UPPER(drug) LIKE '%MIRALAX%' OR UPPER(drug) LIKE '%LACTULOSE%'
 OR UPPER(drug) LIKE '%MILK OF MAGNESIA%' OR UPPER(drug) LIKE '%MAGNESIUM HYDROXIDE%'
 OR UPPER(drug) LIKE 'MAG HYDROX%' OR UPPER(drug) LIKE '%METHYLNALTREXONE%'
 OR UPPER(drug) LIKE '%PSYLLIUM%' OR UPPER(drug) LIKE 'GLYCERIN%'
 OR UPPER(drug) LIKE '%LUBIPROSTONE%' OR UPPER(drug) LIKE '%FLEET%')"""

LAXCLASS = """CASE
 WHEN UPPER(drug) LIKE '%SENNA%' THEN 'senna'
 WHEN UPPER(drug) LIKE '%DOCUSATE%' THEN 'docusate'
 WHEN UPPER(drug) LIKE '%BISACODYL%' THEN 'bisacodyl'
 WHEN UPPER(drug) LIKE '%POLYETHYLENE%' OR UPPER(drug) LIKE '%MIRALAX%' THEN 'peg'
 WHEN UPPER(drug) LIKE '%LACTULOSE%' THEN 'lactulose'
 WHEN UPPER(drug) LIKE '%MILK OF MAGNESIA%' OR UPPER(drug) LIKE '%MAGNESIUM HYDROXIDE%'
   OR UPPER(drug) LIKE 'MAG HYDROX%' THEN 'mom'
 WHEN UPPER(drug) LIKE '%METHYLNALTREXONE%' THEN 'methylnalt'
 WHEN UPPER(drug) LIKE '%PSYLLIUM%' THEN 'psyllium'
 WHEN UPPER(drug) LIKE 'GLYCERIN%' THEN 'glycerin'
 WHEN UPPER(drug) LIKE '%LUBIPROSTONE%' THEN 'lubip'
 WHEN UPPER(drug) LIKE '%FLEET%' THEN 'fleet' END"""

COV_SQL = """
SELECT a.subject_id, a.hadm_id, a.admittime, a.hospital_expire_flag AS y,
  p.anchor_age, p.gender, a.race, a.insurance, a.admission_type,
  a.admission_location, p.anchor_year_group,
  CASE WHEN s.hadm_id IS NOT NULL THEN 1 ELSE 0 END AS icu,
  COALESCE(u.n_prior, 0) AS n_prior,
  COALESCE(u.los_total, 0) AS prior_los_total,
  ch.charlson_max AS prior_charlson,
  COALESCE(u.year_n, 0) AS prior_year_n,
  COALESCE(x.px_cardiac,0) AS px_cardiac, COALESCE(x.px_hf,0) AS px_hf,
  COALESCE(x.px_stroke,0) AS px_stroke, COALESCE(x.px_renal,0) AS px_renal,
  COALESCE(x.px_copd,0) AS px_copd, COALESCE(x.px_diab,0) AS px_diab,
  COALESCE(x.px_onc,0) AS px_onc, COALESCE(x.px_sepsis,0) AS px_sepsis,
  COALESCE(x.px_liver,0) AS px_liver
FROM mimiciv_hosp.admissions a
JOIN mimiciv_hosp.patients p USING (subject_id)
LEFT JOIN (SELECT DISTINCT hadm_id FROM mimiciv_icu.icustays) s USING (hadm_id)
LEFT JOIN (
  SELECT b.hadm_id, COUNT(*) AS n_prior,
    COALESCE(SUM(date_diff('day', p.admittime, p.dischtime)), 0) AS los_total,
    SUM(CASE WHEN p.admittime >= b.admittime - INTERVAL 1 YEAR THEN 1 ELSE 0 END) AS year_n
  FROM mimiciv_hosp.admissions b
  JOIN mimiciv_hosp.admissions p
    ON p.subject_id = b.subject_id AND p.admittime < b.admittime
  GROUP BY 1
) u USING (hadm_id)
LEFT JOIN (
  SELECT b.hadm_id, MAX(c.charlson_comorbidity_index) AS charlson_max
  FROM mimiciv_hosp.admissions b
  JOIN mimiciv_hosp.admissions p
    ON p.subject_id = b.subject_id AND p.admittime < b.admittime
  LEFT JOIN mimiciv_derived.charlson c ON c.hadm_id = p.hadm_id
  GROUP BY 1
) ch USING (hadm_id)
LEFT JOIN (
  SELECT b.hadm_id,
    MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code,3) BETWEEN '410' AND '414'
                    OR d.icd_version = 10 AND LEFT(d.icd_code,3) BETWEEN 'I20' AND 'I25')
             THEN 1 ELSE 0 END) AS px_cardiac,
    MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code,3) = '428'
                    OR d.icd_version = 10 AND LEFT(d.icd_code,3) = 'I50')
             THEN 1 ELSE 0 END) AS px_hf,
    MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code,3) BETWEEN '430' AND '438'
                    OR d.icd_version = 10 AND LEFT(d.icd_code,3) BETWEEN 'I60' AND 'I69')
             THEN 1 ELSE 0 END) AS px_stroke,
    MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code,3) BETWEEN '584' AND '586'
                    OR d.icd_version = 10 AND LEFT(d.icd_code,3) BETWEEN 'N17' AND 'N19')
             THEN 1 ELSE 0 END) AS px_renal,
    MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code,3) BETWEEN '490' AND '496'
                    OR d.icd_version = 10 AND LEFT(d.icd_code,3) BETWEEN 'J40' AND 'J47')
             THEN 1 ELSE 0 END) AS px_copd,
    MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code,3) = '250'
                    OR d.icd_version = 10 AND LEFT(d.icd_code,3) BETWEEN 'E10' AND 'E14')
             THEN 1 ELSE 0 END) AS px_diab,
    MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code,3) BETWEEN '140' AND '239'
                    OR d.icd_version = 10 AND LEFT(d.icd_code,3) BETWEEN 'C00' AND 'D49')
             THEN 1 ELSE 0 END) AS px_onc,
    MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code,3) = '038'
                    OR d.icd_version = 10 AND LEFT(d.icd_code,3) BETWEEN 'A40' AND 'A41')
             THEN 1 ELSE 0 END) AS px_sepsis,
    MAX(CASE WHEN (d.icd_version = 9 AND LEFT(d.icd_code,3) BETWEEN '570' AND '573'
                    OR d.icd_version = 10 AND LEFT(d.icd_code,3) BETWEEN 'K70' AND 'K77')
             THEN 1 ELSE 0 END) AS px_liver
  FROM mimiciv_hosp.admissions b
  JOIN mimiciv_hosp.admissions p
    ON p.subject_id = b.subject_id AND p.admittime < b.admittime
  LEFT JOIN mimiciv_hosp.diagnoses_icd d ON d.hadm_id = p.hadm_id
  GROUP BY 1
) x USING (hadm_id)
ORDER BY hadm_id
"""

EXP_SQL = f"""
WITH lax AS (
  SELECT a.hadm_id, {LAXCLASS} AS cls, MAX(r.starttime) AS last_rx
  FROM mimiciv_hosp.admissions a
  JOIN mimiciv_hosp.prescriptions r
    ON r.subject_id = a.subject_id
   AND r.starttime IS NOT NULL
   AND r.starttime < a.admittime AND r.starttime >= a.admittime - INTERVAL 365 DAY
  WHERE {LAX}
  GROUP BY 1, 2
),
coded AS (
  SELECT DISTINCT a.hadm_id, MAX(p.admittime) AS last_dx
  FROM mimiciv_hosp.admissions a
  JOIN mimiciv_hosp.admissions p
    ON p.subject_id = a.subject_id
   AND p.admittime < a.admittime AND p.admittime >= a.admittime - INTERVAL 365 DAY
  JOIN mimiciv_hosp.diagnoses_icd d ON d.hadm_id = p.hadm_id
  WHERE (d.icd_version = 9 AND LEFT(d.icd_code, 4) = '5640')
     OR (d.icd_version = 10 AND LEFT(d.icd_code, 4) = 'K590')
  GROUP BY 1
)
SELECT a.hadm_id,
  CASE WHEN c.hadm_id IS NOT NULL THEN 1 ELSE 0 END AS coded,
  CASE WHEN l.hadm_id IS NOT NULL THEN 1 ELSE 0 END AS lax_any,
  COALESCE(l.ncls, 0) AS lax_ncls,
  LEAST(COALESCE(date_diff('day', l.last_rx, a.admittime), 9999),
        COALESCE(date_diff('day', c.last_dx, a.admittime), 9999)) AS days_since
FROM mimiciv_hosp.admissions a
LEFT JOIN coded c USING (hadm_id)
LEFT JOIN (SELECT hadm_id, COUNT(DISTINCT cls) AS ncls,
                  MAX(last_rx) AS last_rx FROM lax GROUP BY 1) l USING (hadm_id)
ORDER BY 1
"""


def mcnemar_p(b, c):
    n = b + c
    if n == 0:
        return 1.0
    if n <= 1000:
        k = min(b, c)
        p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
        return min(1.0, 2 * p)
    z = (abs(b - c) - 1) / math.sqrt(n)
    return math.erfc(z / math.sqrt(2))


def main():
    con = duckdb.connect(DB, read_only=True)
    df = con.execute(COV_SQL).fetchdf()
    ex = con.execute(EXP_SQL).fetchdf()
    con.close()
    df = df.merge(ex, on="hadm_id")
    df["either"] = ((df["coded"] == 1) | (df["lax_any"] == 1)).astype(int)
    df["both"] = ((df["coded"] == 1) & (df["lax_any"] == 1)).astype(int)
    df["recency"] = np.select(
        [df["either"] == 0, df["days_since"] <= 30],
        ["none", "recent"], default="remote")
    df["recency180"] = np.select(
        [df["either"] == 0, df["days_since"] <= 180],
        ["none", "recent"], default="remote")
    df["dose"] = np.select(
        [df["either"] == 0, df["lax_ncls"] == 1, df["lax_ncls"] >= 2],
        ["0", "1class", "2+class"], default="coded_only")
    print(f"admissions: {len(df)}, deaths: {int(df.y.sum())} ({df.y.mean():.4f})",
          flush=True)
    print("exposure prevalence:",
          {c: round(float(df[c].mean()), 4)
           for c in ["coded", "lax_any", "either", "both"]}, flush=True)

    num = ["anchor_age", "n_prior", "prior_los_total", "prior_charlson",
           "prior_year_n", "px_cardiac", "px_hf", "px_stroke", "px_renal",
           "px_copd", "px_diab", "px_onc", "px_sepsis", "px_liver"]
    cat = ["gender", "race", "insurance", "admission_type",
           "admission_location", "anchor_year_group"]
    for c in ["prior_charlson"]:
        df[f"miss_{c}"] = df[c].isna().astype(int)
    num = list(num) + ["miss_prior_charlson"]
    for c in cat:
        vc = df[c].value_counts()
        rare = set(vc[vc < 1000].index)
        if rare:
            df[c] = df[c].where(~df[c].isin(rare), "OTHER")
    Xc = pd.get_dummies(df[num + cat].copy(), columns=cat, dummy_na=False,
                        dtype=float, drop_first=True).fillna(
                            df[num].median(numeric_only=True))
    # Scale numerics (z-score) so Newton converges; binary exposure
    # coefficients are unaffected by rescaling of other covariates.
    mu, sd = Xc[num].mean(), Xc[num].std().replace(0, 1.0)
    Xc[num] = (Xc[num] - mu) / sd
    # Drop zero-variance columns (separation risk)
    zv = [c for c in Xc.columns if Xc[c].std() == 0]
    if zv:
        print(f"dropping zero-variance cols: {zv}", flush=True)
        Xc = Xc.drop(columns=zv)
    Xc = sm.add_constant(Xc, has_constant="add")

    forest = []

    # crude + adjusted per definition
    for col in ["coded", "lax_any", "either", "both"]:
        e1 = df[col] == 1
        a, b = int((e1 & (df.y == 1)).sum()), int((e1 & (df.y == 0)).sum())
        c, d = int((~e1 & (df.y == 1)).sum()), int((~e1 & (df.y == 0)).sum())
        crude = (a / b) / (c / d)
        print(f"[{col}] exposed n={a + b} death rate exp={a / (a + b):.4f} "
              f"unexp={c / (c + d):.4f} crude OR={crude:.3f}", flush=True)
        Xe = Xc.copy()
        Xe[col] = df[col].to_numpy(dtype=float)
        fit = sm.Logit(df["y"], Xe).fit(disp=0, method="lbfgs", maxiter=1000)
        est = fit.params[col]
        lo, hi = fit.conf_int().loc[col]
        p = fit.pvalues[col]
        print(f"  adjusted OR={math.exp(est):.3f} "
              f"[{math.exp(lo):.3f}-{math.exp(hi):.3f}] p={p:.2g}", flush=True)
        forest.append((f"adjusted:{col}", math.exp(est), math.exp(lo),
                       math.exp(hi)))

    # adjusted + ICU mediator sensitivity for main definition
    Xe = Xc.copy()
    Xe["either"] = df["either"].to_numpy(dtype=float)
    Xe["icu"] = df["icu"].to_numpy(dtype=float)
    fit = sm.Logit(df["y"], Xe).fit(disp=0, method="lbfgs", maxiter=1000)
    est = fit.params["either"]
    lo, hi = fit.conf_int().loc["either"]
    print(f"[either+icu] adjusted OR={math.exp(est):.3f} "
          f"[{math.exp(lo):.3f}-{math.exp(hi):.3f}] p={fit.pvalues['either']:.2g}",
          flush=True)
    forest.append(("adjusted+ICU:either", math.exp(est), math.exp(lo),
                   math.exp(hi)))

    # propensity 1:1 matching on 'either' and on 'coded'
    bal_all = []
    for ecol in ["either", "coded"]:
        ps_pipe = Pipeline([("sc", StandardScaler()),
                            ("lr", LogisticRegression(C=1.0, max_iter=5000))])
        ps = ps_pipe.fit(Xc.fillna(0.0), df[ecol]).predict_proba(
            Xc.fillna(0.0))[:, 1]
        cal = 0.2 * ps.std()
        exp_idx = np.where(df[ecol].to_numpy() == 1)[0]
        ctl_idx = np.where(df[ecol].to_numpy() == 0)[0]
        order = np.argsort(ps[ctl_idx])
        ctl_sorted, used = ctl_idx[order], np.zeros(len(ctl_idx), bool)
        ps_sorted = ps[ctl_sorted]
        rng = np.random.default_rng(42)
        pairs = []
        for i in rng.permutation(exp_idx):
            lo = np.searchsorted(ps_sorted, ps[i] - cal)
            hi = np.searchsorted(ps_sorted, ps[i] + cal, side="right")
            best, best_d = -1, cal
            for k in range(lo, hi):
                if used[k]:
                    continue
                dd = abs(ps_sorted[k] - ps[i])
                if dd < best_d:
                    best, best_d = k, dd
            if best >= 0:
                used[best] = True
                pairs.append((i, ctl_sorted[best]))
        pairs = np.array(pairs)
        ye, yc = df["y"].to_numpy()[pairs[:, 0]], df["y"].to_numpy()[pairs[:, 1]]
        b = int(((ye == 1) & (yc == 0)).sum())
        c = int(((ye == 0) & (yc == 1)).sum())
        mor = b / c if c else float("inf")
        ci = (math.exp(math.log(mor) - 1.96 * math.sqrt(1 / b + 1 / c)),
              math.exp(math.log(mor) + 1.96 * math.sqrt(1 / b + 1 / c))) if min(b, c) > 0 else (mor, mor)
        print(f"[matched:{ecol}] pairs={len(pairs)} exp death={ye.mean():.4f} "
              f"ctl death={yc.mean():.4f} OR={mor:.3f} [{ci[0]:.3f}-{ci[1]:.3f}] "
              f"mcnemar p={mcnemar_p(b, c):.2g}", flush=True)
        forest.append((f"matched:{ecol}", mor, ci[0], ci[1]))
        print(f"balance {ecol} (SMD before -> after):")
        for col in ["anchor_age", "n_prior", "prior_los_total", "prior_year_n",
                    "prior_charlson"]:
            x = df[col].fillna(df[col].median()).to_numpy()
            e, u = x[df[ecol].to_numpy() == 1], x[df[ecol].to_numpy() == 0]
            m = x[pairs[:, 1]]
            s0 = np.sqrt((e.var() + u.var()) / 2)
            smd0 = (e.mean() - u.mean()) / s0 if s0 else 0
            s1 = np.sqrt((x[pairs[:, 0]].var() + m.var()) / 2)
            smd1 = (x[pairs[:, 0]].mean() - m.mean()) / s1 if s1 else 0
            bal_all.append((ecol, col, round(float(smd0), 3),
                            round(float(smd1), 3)))
            print(f"  {col}: {smd0:.3f} -> {smd1:.3f}", flush=True)
    pd.DataFrame(bal_all, columns=["exposure", "covariate", "smd_before",
                                   "smd_after"]).to_csv(
        OUT + "const_balance.csv", index=False)

    # dose-response + recency (adjusted, same covariates)
    for col, vals in (("dose", ["1class", "2+class", "coded_only"]),
                        ("recency", ["remote", "recent"]),
                        ("recency180", ["remote", "recent"])):
        dum = pd.get_dummies(df[col], prefix=col, dtype=float).drop(
            columns=[f"{col}_0" if col == "dose" else f"{col}_none"])
        Xe = pd.concat([Xc, dum], axis=1)
        fit = sm.Logit(df["y"], Xe).fit(disp=0, method="lbfgs", maxiter=1000)
        for v in vals:
            k = f"{col}_{v}"
            est = fit.params[k]
            lo, hi = fit.conf_int().loc[k]
            print(f"[{k} vs ref] OR={math.exp(est):.3f} "
                  f"[{math.exp(lo):.3f}-{math.exp(hi):.3f}] p={fit.pvalues[k]:.2g}",
                  flush=True)
            forest.append((k, math.exp(est), math.exp(lo), math.exp(hi)))

    # subgroups (adjusted, either)
    df["age65"] = (df["anchor_age"] >= 65).astype(int)
    for tag, m in (("age<65", df["age65"] == 0), ("age65+", df["age65"] == 1),
                   ("noICU", df["icu"] == 0), ("ICU", df["icu"] == 1)):
        sub = df[m]
        Xe = Xc.loc[m].copy()
        Xe["either"] = sub["either"].to_numpy(dtype=float)
        fit = sm.Logit(sub["y"], Xe).fit(disp=0, method="lbfgs", maxiter=1000)
        est = fit.params["either"]
        lo, hi = fit.conf_int().loc["either"]
        print(f"[subgroup {tag} n={len(sub)}] OR={math.exp(est):.3f} "
              f"[{math.exp(lo):.3f}-{math.exp(hi):.3f}] p={fit.pvalues['either']:.2g}",
              flush=True)
        forest.append((f"subgroup:{tag}", math.exp(est), math.exp(lo),
                       math.exp(hi)))

    # E-values for estimates with OR meaningfully above 1
    for tag, o, _, _ in forest:
        if o > 1.1:
            ev = o + math.sqrt(o * (o - 1))
            print(f"E-value for {tag} OR={o:.3f}: {ev:.3f}", flush=True)
    pd.DataFrame(forest, columns=["model", "or", "lo", "hi"]).to_csv(
        OUT + "const_forest.csv", index=False)
    print("wrote const_forest.csv, const_balance.csv", flush=True)


if __name__ == "__main__":
    main()
