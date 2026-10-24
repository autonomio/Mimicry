"""Prior-year common ailments vs serious illness (MIMIC-IV v3.1, s0 only).

Screen: 16 ailments x 3 outcomes (hospital death, any ICU stay,
elective admission -> late (>=24h) ICU transfer). Stage 1: crude +
adjusted logistic + E-value + BH-FDR. Stage 2 (FDR hits with |OR-1|>0.1
only): adjusted dx/rx
decomposition, 1:1 PS matching + balance, dose-response, recency.
Structured fields only. Aggregates only leave s0.

Run on s0: /srv/mimic-iv/.venv/bin/python ailment_sweep.py
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

# rx class -> UPPER(drug) LIKE stems
RX = {
    "lax": ["%SENNA%", "%DOCUSATE%", "%BISACODYL%", "%POLYETHYLENE%",
            "%MIRALAX%", "%LACTULOSE%", "%MILK OF MAGNESIA%",
            "%MAGNESIUM HYDROXIDE%", "MAG HYDROX%", "%METHYLNALTREXONE%",
            "%PSYLLIUM%", "GLYCERIN%", "%LUBIPROSTONE%", "%FLEET%"],
    "ppi": ["%PRAZOLE%"],
    "h2": ["%FAMOTIDINE%", "%RANITIDINE%", "%CIMETIDINE%", "%NIZATIDINE%"],
    "statin": ["%STATIN%"],
    "ssri": ["%SERTRALINE%", "%FLUOXETINE%", "%PAROXETINE%", "%CITALOPRAM%",
             "%ESCITALOPRAM%", "%VENLAFAXINE%", "%DULOXETINE%", "%BUPROPION%",
             "%MIRTAZAPINE%", "%TRAZODONE%"],
    "benzo": ["%LORAZEPAM%", "%ALPRAZOLAM%", "%CLONAZEPAM%", "%DIAZEPAM%",
              "%OXAZEPAM%", "%TEMAZEPAM%", "%BUSPIRONE%", "%HYDROXYZINE%"],
    "hypnotic": ["%ZOLPIDEM%", "%ESZOPICLONE%", "%ZALEPLON%"],
    "antihist": ["%LORATADINE%", "%CETIRIZINE%", "%FEXOFENADINE%",
                 "%DIPHENHYDRAMINE%", "%CHLORPHENIRAMINE%"],
    "nsaid": ["%IBUPROFEN%", "%NAPROXEN%", "%CELECOXIB%", "%DICLOFENAC%",
              "%MELOXICAM%", "%KETOROLAC%", "%INDOMETHACIN%"],
    "opioid": ["%OXYCODONE%", "%HYDROCODONE%", "%MORPHINE%", "%CODEINE%",
               "%TRAMADOL%", "%FENTANYL%", "%HYDROMORPHONE%", "%METHADONE%",
               "%OXYMORPHONE%"],
    "levo": ["%LEVOTHYROXINE%", "%THYROXINE%"],
    "triptan": ["%TRIPTAN%"],
    "gaba": ["%GABAPENTIN%", "%PREGABALIN%"],
    "metformin": ["%METFORMIN%"],
    "insulin": ["%INSULIN%"],
    "antihyp": ["%LISINOPRIL%", "%ENALAPRIL%", "%LOSARTAN%", "%VALSARTAN%",
                "%AMLODIPINE%", "%DILTIAZEM%", "%METOPROLOL%", "%ATENOLOL%",
                "%HYDROCHLOROTHIAZIDE%", "%FUROSEMIDE%"],
    "albuterol": ["%ALBUTEROL%"],
    "ironb12": ["%FERROUS%", "%IRON%", "%CYANOCOBALAMIN%", "%VITAMIN B12%",
                "%FOLATE%", "%FOLIC ACID%"],
    "utiabx": ["%NITROFURANTOIN%", "%CIPROFLOXACIN%", "%SULFAMETHOXAZOLE%",
               "%TRIMETHOPRIM%"],
}

# ailment -> (icd9 prefixes, icd10 prefixes, rx classes)
AIL = {
    "constip": (["5640"], ["K590"], ["lax"]),
    "gerd": (["53081", "53011"], ["K21"], ["ppi", "h2"]),
    "sleep": (["7805", "3074"], ["G47", "F51"], ["hypnotic"]),
    "anxiety": (["3000"], ["F41"], ["benzo"]),
    "depress": (["2962", "2963", "311"], ["F32", "F33"], ["ssri"]),
    "backpain": (["724"], ["M54"], ["nsaid", "opioid", "gaba"]),
    "headache": (["346", "7840"], ["G43", "G44"], ["triptan"]),
    "allergy": (["477"], ["J30"], ["antihist"]),
    "hyperlip": (["272"], ["E78"], ["statin"]),
    "hypothy": (["244"], ["E03"], ["levo"]),
    "hyperten": (["401", "402", "403", "404", "405"],
                 ["I10", "I11", "I12", "I13", "I14", "I15"], ["antihyp"]),
    "diabetes": (["250"], ["E10", "E11"], ["metformin", "insulin"]),
    "asthma_copd": (["493", "496"], ["J45", "J44"], ["albuterol"]),
    "anemia": (["280", "281"], ["D50", "D51"], ["ironb12"]),
    "uti": (["5990"], ["N390"], ["utiabx"]),
    "obesity": (["2780"], ["E66"], []),
}


# stems that would otherwise contaminate a class (nystatin is not a statin,
# aripiprazole is not a PPI, spironolactone is not iron)
RX_EXCL = {"statin": ["%NYSTATIN%"], "ppi": ["%ARIPIPRAZOLE%"],
           "ironb12": ["%SPIRONOLACTONE%"]}


def rx_cond(cls):
    base = "(" + " OR ".join(f"UPPER(r.drug) LIKE '{s}'" for s in RX[cls]) + ")"
    for x in RX_EXCL.get(cls, []):
        base += f" AND UPPER(r.drug) NOT LIKE '{x}'"
    return f"({base})"


def dx_cond(ail):
    p9, p10, _ = AIL[ail]
    c9 = " OR ".join(f"d.icd_code LIKE '{p}%'" for p in p9)
    c10 = " OR ".join(f"d.icd_code LIKE '{p}%'" for p in p10)
    return (f"((d.icd_version = 9 AND ({c9})) "
            f"OR (d.icd_version = 10 AND ({c10})))")


RX_SQL = ("SELECT a.hadm_id,\n" + ",\n".join(
    f"  SUM(CASE WHEN {rx_cond(c)} THEN 1 ELSE 0 END) AS rx_{c}_n,\n"
    f"  MAX(CASE WHEN {rx_cond(c)} THEN r.starttime END) AS rx_{c}_last"
    for c in RX)
    + "\nFROM mimiciv_hosp.admissions a\n"
    "JOIN mimiciv_hosp.prescriptions r ON r.subject_id = a.subject_id\n"
    " AND r.starttime IS NOT NULL AND r.starttime < a.admittime\n"
    " AND r.starttime >= a.admittime - INTERVAL 365 DAY\nGROUP BY 1")

DX_SQL = ("SELECT a.hadm_id,\n" + ",\n".join(
    f"  MAX(CASE WHEN {dx_cond(a_)} THEN 1 ELSE 0 END) AS dx_{a_},\n"
    f"  MAX(CASE WHEN {dx_cond(a_)} THEN p.admittime END) AS dx_{a_}_last"
    for a_ in AIL)
    + "\nFROM mimiciv_hosp.admissions a\n"
    "JOIN mimiciv_hosp.admissions p ON p.subject_id = a.subject_id\n"
    " AND p.admittime < a.admittime\n"
    " AND p.admittime >= a.admittime - INTERVAL 365 DAY\n"
    "LEFT JOIN mimiciv_hosp.diagnoses_icd d ON d.hadm_id = p.hadm_id\n"
    "GROUP BY 1")

COV_SQL = """
SELECT a.subject_id, a.hadm_id, a.admittime, a.hospital_expire_flag AS death,
  p.anchor_age, p.gender, a.race, a.insurance, a.admission_type,
  a.admission_location, p.anchor_year_group,
  CASE WHEN s.hadm_id IS NOT NULL THEN 1 ELSE 0 END AS icu,
  s.icu_first AS icu_first,
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
LEFT JOIN (SELECT hadm_id, MIN(intime) AS icu_first
           FROM mimiciv_icu.icustays GROUP BY 1) s USING (hadm_id)
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

NUM = ["anchor_age", "n_prior", "prior_los_total", "prior_charlson",
       "prior_year_n", "px_cardiac", "px_hf", "px_stroke", "px_renal",
       "px_copd", "px_diab", "px_onc", "px_sepsis", "px_liver",
       "miss_prior_charlson"]
CAT = ["gender", "race", "insurance", "admission_type",
       "admission_location", "anchor_year_group"]
BALCOLS = ["anchor_age", "n_prior", "prior_los_total", "prior_year_n",
           "prior_charlson"]


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


def design(df):
    """Covariate design matrix (own dummies/collapse/scale per population)."""
    d = df.copy().reset_index(drop=True)
    d["miss_prior_charlson"] = d["prior_charlson"].isna().astype(int)
    thr = max(30, len(d) // 500)
    for c in CAT:
        vc = d[c].value_counts()
        rare = set(vc[vc < thr].index)
        if rare:
            d[c] = d[c].where(~d[c].isin(rare), "OTHER")
    Xc = pd.get_dummies(d[NUM + CAT].copy(), columns=CAT, dummy_na=False,
                        dtype=float, drop_first=True).fillna(
                            d[NUM].median(numeric_only=True))
    mu, sd = Xc[NUM].mean(), Xc[NUM].std().replace(0, 1.0)
    Xc[NUM] = (Xc[NUM] - mu) / sd
    zv = [c for c in Xc.columns if Xc[c].std() == 0]
    if zv:
        Xc = Xc.drop(columns=zv)
    return d, sm.add_constant(Xc, has_constant="add")


def crude_or(e, y):
    a, b = int(((e == 1) & (y == 1)).sum()), int(((e == 1) & (y == 0)).sum())
    c, d = int(((e == 0) & (y == 1)).sum()), int(((e == 0) & (y == 0)).sum())
    if min(a, b, c, d) == 0:
        return float("nan")
    return (a / b) / (c / d)


def adj_fit(d, Xc, ycol, ecol):
    Xe = Xc.copy()
    Xe[ecol] = d[ecol].to_numpy(dtype=float)
    fit = sm.Logit(d[ycol], Xe).fit(disp=0, method="lbfgs", maxiter=1000)
    est = fit.params[ecol]
    lo, hi = fit.conf_int().loc[ecol]
    return math.exp(est), math.exp(lo), math.exp(hi), float(fit.pvalues[ecol])


def ps_match(d, Xc, ycol, ecol):
    ps = Pipeline([("sc", StandardScaler()),
                   ("lr", LogisticRegression(C=1.0,
                                             max_iter=5000))]).fit(
        Xc.fillna(0.0), d[ecol]).predict_proba(Xc.fillna(0.0))[:, 1]
    cal = 0.2 * ps.std()
    ev = d[ecol].to_numpy()
    exp_idx = np.where(ev == 1)[0]
    ctl_idx = np.where(ev == 0)[0]
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
    yv = d[ycol].to_numpy()
    ye, yc = yv[pairs[:, 0]], yv[pairs[:, 1]]
    b = int(((ye == 1) & (yc == 0)).sum())
    c = int(((ye == 0) & (yc == 1)).sum())
    mor = b / c if c else float("inf")
    if min(b, c) > 0:
        se = math.sqrt(1 / b + 1 / c)
        ci = (math.exp(math.log(mor) - 1.96 * se),
              math.exp(math.log(mor) + 1.96 * se))
    else:
        ci = (mor, mor)
    bal = []
    for col in BALCOLS:
        x = d[col].fillna(d[col].median()).to_numpy()
        e, u = x[ev == 1], x[ev == 0]
        s0 = np.sqrt((e.var() + u.var()) / 2)
        smd0 = (e.mean() - u.mean()) / s0 if s0 else 0
        xm, cm = x[pairs[:, 0]], x[pairs[:, 1]]
        s1 = np.sqrt((xm.var() + cm.var()) / 2)
        smd1 = (xm.mean() - cm.mean()) / s1 if s1 else 0
        bal.append((col, round(float(smd0), 3), round(float(smd1), 3)))
    return len(pairs), float(ye.mean()), float(yc.mean()), mor, ci, \
        mcnemar_p(b, c), bal


def main():
    con = duckdb.connect(DB, read_only=True)
    print("loading covariates...", flush=True)
    df = con.execute(COV_SQL).fetchdf()
    print("loading rx exposures...", flush=True)
    rx = con.execute(RX_SQL).fetchdf()
    print("loading dx exposures...", flush=True)
    dx = con.execute(DX_SQL).fetchdf()
    con.close()
    df = df.merge(rx, on="hadm_id", how="left").merge(dx, on="hadm_id",
                                                      how="left")
    df["admittime"] = pd.to_datetime(df["admittime"])
    df["icu_first"] = pd.to_datetime(df["icu_first"])
    # Unexpected ICU transfer: elective admission whose FIRST ICU stay starts
    # >=24h after admission (excludes planned post-op and direct ICU).
    df["late_icu"] = ((df["icu"] == 1) &
                      (df["icu_first"] >= df["admittime"] +
                       pd.Timedelta(hours=24))).astype(int)

    # per-ailment flags: dx / rx fills / either / days_since
    for ail, (_, _, classes) in AIL.items():
        df[f"dx_{ail}"] = df[f"dx_{ail}"].fillna(0).astype(int)
        nfill = np.zeros(len(df))
        flist = [pd.to_datetime(df[f"dx_{ail}_last"])]
        for c in classes:
            nfill = nfill + df[f"rx_{c}_n"].fillna(0).to_numpy()
            flist.append(pd.to_datetime(df[f"rx_{c}_last"]))
        df[f"rxn_{ail}"] = nfill
        df[f"rx_{ail}"] = (nfill > 0).astype(int)
        anyf = pd.concat(flist, axis=1).max(axis=1)
        df[f"either_{ail}"] = ((df[f"dx_{ail}"] == 1) |
                               (df[f"rx_{ail}"] == 1)).astype(int)
        ds = (df["admittime"] - pd.to_datetime(anyf)).dt.days
        df[f"ds_{ail}"] = ds.where(df[f"either_{ail}"] == 1, 9999)
    print(f"admissions: {len(df)}, deaths: {int(df.death.sum())}, "
          f"icu: {int(df.icu.sum())}, elective: "
          f"{int((df.admission_type == 'ELECTIVE').sum())}, late_icu: "
          f"{int(df.late_icu.sum())}", flush=True)
    for ail in AIL:
        e = df[f"either_{ail}"]
        print(f"  {ail}: prev={e.mean():.4f} "
              f"(dx={df[f'dx_{ail}'].mean():.4f} "
              f"rx={df[f'rx_{ail}'].mean():.4f})", flush=True)

    pops = {
        "death": (df, "death"),
        "icu": (df, "icu"),
        "unexpected_icu": (df[df["admission_type"] == "ELECTIVE"], "late_icu"),
    }
    popdat = {}
    for oname, (pdf, ycol) in pops.items():
        d, Xc = design(pdf)
        popdat[oname] = (d, Xc, ycol)
        print(f"[{oname}] n={len(d)} events={int(d[ycol].sum())} "
              f"({d[ycol].mean():.4f}) cols={Xc.shape[1]}", flush=True)

    # ---- Stage 1: screen ----
    screen = []
    for oname, (d, Xc, ycol) in popdat.items():
        y = d[ycol]
        for ail in AIL:
            ecol = f"either_{ail}"
            e = d[ecol]
            n_exp = int(e.sum())
            c_dx = crude_or(d[f"dx_{ail}"], y)
            c_rx = crude_or(d[f"rx_{ail}"], y)
            c_e = crude_or(e, y)
            o, lo, hi, p = adj_fit(d, Xc, ycol, ecol)
            ev = o + math.sqrt(o * (o - 1)) if o > 1 else float("nan")
            screen.append([oname, ail, n_exp, round(float(e.mean()), 4),
                           round(c_dx, 3), round(c_rx, 3), round(c_e, 3),
                           round(o, 4), round(lo, 4), round(hi, 4), p, ev])
            print(f"[{oname}|{ail}] n_exp={n_exp} crude dx/rx/either="
                  f"{c_dx:.3f}/{c_rx:.3f}/{c_e:.3f} adj OR={o:.3f} "
                  f"[{lo:.3f}-{hi:.3f}] p={p:.2g}", flush=True)
    scr = pd.DataFrame(
        screen, columns=["outcome", "ailment", "n_exp", "prev", "crude_dx",
                         "crude_rx", "crude_either", "adj_or", "adj_lo",
                         "adj_hi", "adj_p", "evalue"])
    # BH-FDR over all screen cells
    scr = scr.sort_values("adj_p").reset_index(drop=True)
    m = len(scr)
    q = scr["adj_p"] * m / (np.arange(m) + 1)
    scr["q"] = np.minimum.accumulate(q[::-1])[::-1].clip(upper=1.0)
    scr.to_csv(OUT + "ail_screen.csv", index=False)
    print(scr[["outcome", "ailment", "adj_or", "adj_p", "q"]].to_string(),
          flush=True)

    hits = scr[(scr["q"] < 0.05) & ((scr["adj_or"] > 1.1) |
                                    (scr["adj_or"] < 0.9))]
    print(f"HITS for stage 2: {len(hits)}", flush=True)

    # ---- Stage 2: full battery for hits ----
    forest = [(r["outcome"], f"adjusted:{r['ailment']}", r["adj_or"],
               r["adj_lo"], r["adj_hi"]) for _, r in scr.iterrows()]
    bal_all = []
    for _, h in hits.iterrows():
        oname, ail = h["outcome"], h["ailment"]
        d, Xc, ycol = popdat[oname]
        print(f"=== stage2 {oname}|{ail} ===", flush=True)
        for ecol, lab in [(f"dx_{ail}", "dx"), (f"rx_{ail}", "rx")]:
            if lab == "rx" and not AIL[ail][2]:
                continue
            if d[ecol].sum() < 50:
                print(f"  {lab}: n too small, skipped", flush=True)
                continue
            o, lo, hi, p = adj_fit(d, Xc, ycol, ecol)
            print(f"  adjusted {lab} OR={o:.3f} [{lo:.3f}-{hi:.3f}] p={p:.2g}",
                  flush=True)
            forest.append((oname, f"adjusted-{lab}:{ail}", o, lo, hi))
        ecol = f"either_{ail}"
        np_, ye, yc, mor, ci, pmcn, bal = ps_match(d, Xc, ycol, ecol)
        print(f"  matched pairs={np_} exp={ye:.4f} ctl={yc:.4f} OR={mor:.3f} "
              f"[{ci[0]:.3f}-{ci[1]:.3f}] mcnemar p={pmcn:.2g}", flush=True)
        forest.append((oname, f"matched:{ail}", mor, ci[0], ci[1]))
        for col, sb, sa in bal:
            bal_all.append((oname, ail, col, sb, sa))
            print(f"    {col}: {sb:.3f} -> {sa:.3f}", flush=True)
        # dose + recency (adjusted)
        d = d.copy()
        d["dose"] = np.select(
            [d[ecol] == 0, d[f"rxn_{ail}"] == 1, d[f"rxn_{ail}"] >= 2],
            ["0", "1", "2+"], default="coded_only")
        d["rec"] = np.select(
            [d[ecol] == 0, d[f"ds_{ail}"] <= 183],
            ["none", "recent"], default="remote")
        for col, ref, vals in (("dose", "0", ["1", "2+", "coded_only"]),
                               ("rec", "none", ["remote", "recent"])):
            levels = [v for v in vals if (d[col] == v).sum() >= 50]
            if not levels:
                continue
            dum = pd.get_dummies(d[col], prefix=col,
                                 dtype=float).drop(columns=[f"{col}_{ref}"])
            dum = dum[[f"{col}_{v}" for v in levels]]
            Xe = pd.concat([Xc, dum], axis=1)
            fit = sm.Logit(d[ycol], Xe).fit(disp=0, method="lbfgs",
                                            maxiter=1000)
            for v in levels:
                k = f"{col}_{v}"
                est = fit.params[k]
                lo, hi = fit.conf_int().loc[k]
                print(f"  [{k} vs ref] OR={math.exp(est):.3f} "
                      f"[{math.exp(lo):.3f}-{math.exp(hi):.3f}] "
                      f"p={fit.pvalues[k]:.2g}", flush=True)
                forest.append((oname, f"{k}:{ail}", math.exp(est),
                               math.exp(lo), math.exp(hi)))
    pd.DataFrame(forest, columns=["outcome", "model", "or", "lo",
                                  "hi"]).to_csv(OUT + "ail_forest.csv",
                                                index=False)
    pd.DataFrame(bal_all, columns=["outcome", "ailment", "covariate",
                                   "smd_before", "smd_after"]).to_csv(
        OUT + "ail_balance.csv", index=False)
    print("wrote ail_screen.csv, ail_forest.csv, ail_balance.csv", flush=True)


if __name__ == "__main__":
    main()
