"""Adversarial tests of the prophecy findings (MIMIC-IV v3.1, s0 only).

B-robust: DNR<48h -> death with rich adjustment (SOFA subs, supports,
  lactate/creatinine), DNR->death lag stratification, SOFA-tertile
  stratification, E-value, 1:1 PS matching, unit-rate IV (2SLS).
Discont-robust: regression-adjusted post-slope, off-center placebo
  cuts, survivor-with-DNR falsification.
C-robust: 5-fold CV AUCs (FC + ALL), paired bootstrap gap CIs,
  cause-mix FC vs DNR decedents.
Aggregates only leave s0.
"""
import math
import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

DB = "/srv/mimic-iv/db/mimic4-v31.db"
OUT = "/tmp/"


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


def main():
    con = duckdb.connect(DB, read_only=True)
    print("loading stays + landmarks + supports + labs...", flush=True)
    stays = con.execute("""
SELECT i.stay_id, i.intime, i.outtime, i.first_careunit AS unit,
  a.hospital_expire_flag AS y, a.deathtime, p.anchor_age AS age,
  p.gender,
  CASE WHEN s.stay_id IS NOT NULL THEN 1 ELSE 0 END AS sepsis
FROM mimiciv_icu.icustays i
JOIN mimiciv_hosp.admissions a ON a.hadm_id = i.hadm_id
JOIN mimiciv_hosp.patients p ON p.subject_id = i.subject_id
LEFT JOIN (SELECT DISTINCT stay_id FROM mimiciv_derived.sepsis3) s
  USING (stay_id)""").fetchdf()
    stays["los_h"] = (pd.to_datetime(stays["outtime"]) -
                      pd.to_datetime(stays["intime"])).dt.total_seconds() / 3600
    sofa = con.execute("""
SELECT stay_id, respiration_24hours AS s_resp, coagulation_24hours AS s_coag,
  liver_24hours AS s_liver, cardiovascular_24hours AS s_cv,
  cns_24hours AS s_cns, renal_24hours AS s_renal, sofa_24hours AS sofa48
FROM mimiciv_derived.sofa WHERE hr = 48""").fetchdf()
    stays = stays.merge(sofa, on="stay_id", how="left")
    code = con.execute("""
SELECT stay_id, MIN(CASE WHEN dnr = 1 OR cmo = 1 THEN charttime END) AS dnr_t
FROM mimiciv_derived.code_status GROUP BY 1""").fetchdf()
    stays = stays.merge(code, on="stay_id", how="left")
    stays["dnr_h"] = (pd.to_datetime(stays["dnr_t"]) -
                      pd.to_datetime(stays["intime"])).dt.total_seconds() / 3600
    stays["death_h"] = (pd.to_datetime(stays["deathtime"]) -
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
                              AND i.intime + INTERVAL 60 HOUR
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
    print(f"stays: {len(stays)}", flush=True)

    b = stays[(stays["los_h"] >= 48) & (stays["sofa48"].notna())].copy()
    b["exp"] = ((b["dnr_h"].notna()) & (b["dnr_h"] < 48)).astype(int)
    b["lac"] = b["lac"].clip(upper=20)
    b["crea"] = b["crea"].clip(upper=15)
    base = ["s_resp", "s_coag", "s_liver", "s_cv", "s_cns", "s_renal",
            "age", "sepsis", "vent48", "vaso48", "rrt48", "lac", "crea"]

    def design(df, cols):
        X = pd.get_dummies(df[cols + ["cause", "gender"]],
                           columns=["cause", "gender"], drop_first=True,
                           dtype=float)
        return X.fillna(X.median())

    # ---- B-rich ----
    Xr = design(b, base)
    Xr["exp"] = b["exp"].values
    lr = LogisticRegression(C=1.0, max_iter=5000).fit(Xr.values, b["y"])
    k = list(Xr.columns).index("exp")
    or_rich = math.exp(lr.coef_[0][k])
    ev = or_rich + math.sqrt(or_rich * (or_rich - 1))
    print(f"[B-rich] n={len(b)} adjOR_dnr={or_rich:.2f} E-value={ev:.2f}",
          flush=True)

    # ---- B timing-before-landmark stratification ----
    # (DNR->death lag would condition on the outcome; instead split by
    #  DNR clock time, all fixed before the 48h landmark)
    timdef = [("none", b["exp"] == 0),
              ("dnr<24h", (b["exp"] == 1) & (b["dnr_h"] < 24)),
              ("dnr24-48h", (b["exp"] == 1) & (b["dnr_h"] >= 24))]
    Xl = design(b, base)
    for name, m in timdef[1:]:
        Xl[f"tim_{name}"] = m.astype(int).values
    lrl = LogisticRegression(C=1.0, max_iter=5000).fit(Xl.values, b["y"])
    for name, m in timdef:
        r = b[m]["y"].mean() if m.sum() else float("nan")
        if name == "none":
            print(f"  tim {name}: n={int(m.sum())} death={r:.3f} (ref)",
                  flush=True)
        else:
            j = list(Xl.columns).index(f"tim_{name}")
            print(f"  tim {name}: n={int(m.sum())} death={r:.3f} "
                  f"adjOR={math.exp(lrl.coef_[0][j]):.2f}", flush=True)

    # ---- B SOFA-tertile stratification ----
    b["tert"] = pd.qcut(b["sofa48"], 3, labels=["lo", "mid", "hi"])
    for t, g in b.groupby("tert", observed=True):
        Xg = design(g, base)
        Xg["exp"] = g["exp"].values
        if g["exp"].sum() < 20 or len(g) < 100:
            continue
        ll = LogisticRegression(C=1.0, max_iter=5000).fit(Xg.values, g["y"])
        j = list(Xg.columns).index("exp")
        print(f"  tert {t} (sofa {g['sofa48'].min():.0f}-"
              f"{g['sofa48'].max():.0f}): n={len(g)} "
              f"adjOR={math.exp(ll.coef_[0][j]):.2f}", flush=True)

    # ---- B PS matching (rich covariates) ----
    Xp = StandardScaler().fit_transform(design(b, base))
    ps = LogisticRegression(C=1.0, max_iter=5000).fit(Xp, b["exp"]
                                                     ).predict_proba(Xp)[:, 1]
    b = b.assign(ps=ps).reset_index(drop=True)
    cal = 0.2 * ps.std()
    exp_idx = np.where(b["exp"].to_numpy() == 1)[0]
    ctl_idx = np.where(b["exp"].to_numpy() == 0)[0]
    order = np.argsort(ps[ctl_idx])
    cs, used = ctl_idx[order], np.zeros(len(ctl_idx), bool)
    pss = ps[cs]
    rng = np.random.default_rng(5)
    pairs = []
    for i in rng.permutation(exp_idx):
        j = int(np.searchsorted(pss, ps[i]))
        best, bd = -1, cal
        for kk in range(max(0, j - 200), min(len(cs), j + 200)):
            if used[kk]:
                continue
            dd = abs(pss[kk] - ps[i])
            if dd <= cal and dd < bd:
                best, bd = kk, dd
        if best >= 0:
            used[best] = True
            pairs.append((i, cs[best]))
    pairs = np.array(pairs)
    ye = b["y"].to_numpy()[pairs[:, 0]]
    yc = b["y"].to_numpy()[pairs[:, 1]]
    bb = int(((ye == 1) & (yc == 0)).sum())
    cc = int(((ye == 0) & (yc == 1)).sum())
    mor = bb / cc
    se = math.sqrt(1 / bb + 1 / cc)
    print(f"[B-match] pairs={len(pairs)} death exp={ye.mean():.3f} "
          f"ctl={yc.mean():.3f} OR={mor:.2f} "
          f"[{math.exp(math.log(mor) - 1.96 * se):.2f}-"
          f"{math.exp(math.log(mor) + 1.96 * se):.2f}]", flush=True)
    print("  balance |SMD| max before/after:", flush=True)
    sms = []
    for col in base:
        x = b[col].fillna(b[col].median()).to_numpy()
        e, u = x[b["exp"].to_numpy() == 1], x[b["exp"].to_numpy() == 0]
        s0 = math.sqrt((e.var() + u.var()) / 2)
        sb = abs(e.mean() - u.mean()) / s0 if s0 else 0
        xm, cm = x[pairs[:, 0]], x[pairs[:, 1]]
        s1 = math.sqrt((xm.var() + cm.var()) / 2)
        sa = abs(xm.mean() - cm.mean()) / s1 if s1 else 0
        sms.append((col, round(sb, 3), round(sa, 3)))
    mxb = max(s[1] for s in sms)
    mxa = max(s[2] for s in sms)
    print(f"    max|SMD| {mxb:.3f} -> {mxa:.3f}", flush=True)

    # ---- B IV: unit leave-one-out DNR rate ----
    u = b.groupby("unit")["exp"].agg(["sum", "count"])
    b = b.merge(u, left_on="unit", right_index=True)
    b["iv"] = (b["sum"] - b["exp"]) / (b["count"] - 1)
    b = b[np.isfinite(b["iv"])].copy()
    print(f"  IV sample (units with 2+ stays): n={len(b)}", flush=True)
    Xi = design(b, base)
    Xi["iv"] = b["iv"].values
    Xim = sm.add_constant(Xi.values)
    fs = sm.OLS(b["exp"].values, Xim).fit()
    ji = list(Xi.columns).index("iv")
    F = (fs.params[ji + 1] / fs.bse[ji + 1]) ** 2
    b["exp_hat"] = fs.fittedvalues
    Xr2 = design(b, base)
    Xr2["exp_hat"] = b["exp_hat"].values
    iv2 = sm.OLS(b["y"].values, sm.add_constant(Xr2.values)).fit()
    jh = list(Xr2.columns).index("exp_hat")
    ci = np.asarray(iv2.conf_int())
    print(f"[B-IV] first-stage F={F:.1f} units={b['unit'].nunique()} "
          f"IV risk-diff={iv2.params[jh + 1]:.3f} "
          f"[{ci[jh + 1, 0]:.3f}-{ci[jh + 1, 1]:.3f}]", flush=True)
    ols = sm.OLS(b["y"].values, sm.add_constant(
        design(b, base).assign(exp=b["exp"].values).values)).fit()
    print(f"  OLS risk-diff for scale: {ols.params[-1]:.3f}", flush=True)

    # ---- discontinuity: regression-adjusted + placebos ----
    print("pulling peri-DNR vitals...", flush=True)
    peri = con.execute("""
SELECT c.stay_id, c.charttime, c.itemid, c.valuenum
FROM mimiciv_icu.chartevents c
JOIN (SELECT stay_id,
        MIN(CASE WHEN dnr = 1 OR cmo = 1 THEN charttime END) AS dnr_t
      FROM mimiciv_derived.code_status GROUP BY 1) k USING (stay_id)
WHERE c.itemid IN (220045, 220052, 220181)
  AND c.valuenum IS NOT NULL
  AND c.charttime BETWEEN k.dnr_t - INTERVAL 12 HOUR
                      AND k.dnr_t + INTERVAL 12 HOUR""").fetchdf()
    imap = stays.set_index("stay_id")["intime"].to_dict()
    dmap = stays.set_index("stay_id")["dnr_h"].to_dict()
    ymap = stays.set_index("stay_id")["y"].to_dict()
    peri["h"] = (pd.to_datetime(peri["charttime"]) -
                 peri["stay_id"].map(
                     lambda s: pd.to_datetime(imap[s]))).dt.total_seconds() / 3600 \
        - peri["stay_id"].map(dmap)
    peri["sig"] = peri["itemid"].map({220045: "hr", 220052: "map",
                                      220181: "map"})
    peri["y"] = peri["stay_id"].map(ymap)
    peri = peri[((peri["sig"] == "hr") & peri["valuenum"].between(20, 300)) |
                ((peri["sig"] == "map") & peri["valuenum"].between(20, 200))]
    # matched full-code controls (elapsed/age/sepsis)
    fc = stays[(stays["dnr_h"].isna()) & (stays["los_h"] >= 48)]
    dnr_stays = stays[(stays["dnr_h"].notna()) & (stays["dnr_h"] >= 12)]
    rng = np.random.default_rng(3)
    pairs = []
    used = set()
    for _, r in dnr_stays.sample(frac=1, random_state=3).iterrows():
        c = fc[(~fc["stay_id"].isin(used)) &
               (fc["sepsis"] == r["sepsis"]) &
               ((fc["age"] - r["age"]).abs() <= 10) &
               (fc["los_h"] >= r["dnr_h"] + 12)]
        if len(c) == 0:
            continue
        m = c.iloc[rng.integers(len(c))]
        used.add(m["stay_id"])
        pairs.append((r["stay_id"], m["stay_id"], r["dnr_h"]))
    mstays = ",".join(map(str, {p[1] for p in pairs}))
    mperi = con.execute(f"""
SELECT stay_id, charttime, itemid, valuenum
FROM mimiciv_icu.chartevents
WHERE stay_id IN ({mstays})
  AND itemid IN (220045, 220052, 220181) AND valuenum IS NOT NULL""").fetchdf()
    pmap = {p[1]: p[2] for p in pairs}
    mperi["h"] = (pd.to_datetime(mperi["charttime"]) -
                  mperi["stay_id"].map(
                      lambda s: pd.to_datetime(imap[s]))).dt.total_seconds() / 3600 \
        - mperi["stay_id"].map(pmap)
    mperi = mperi[mperi["h"].between(-12, 12)]
    mperi["sig"] = mperi["itemid"].map({220045: "hr", 220052: "map",
                                        220181: "map"})
    mperi = mperi[((mperi["sig"] == "hr") &
                   mperi["valuenum"].between(20, 300)) |
                  ((mperi["sig"] == "map") &
                   mperi["valuenum"].between(20, 200))]
    con.close()

    def slope_rows(df, lo1, hi1, lo2, hi2):
        out = {}
        for sig in ["hr", "map"]:
            s = df[df["sig"] == sig]
            g1 = s[(s["h"] >= lo1) & (s["h"] < hi1)].groupby("stay_id")
            g2 = s[(s["h"] > lo2) & (s["h"] <= hi2)].groupby("stay_id")
            rows = []
            for sid in set(g1.groups) & set(g2.groups):
                a, bb = g1.get_group(sid), g2.get_group(sid)
                if len(a) >= 3 and len(bb) >= 3:
                    rows.append((sid, np.polyfit(a["h"], a["valuenum"], 1)[0],
                                 np.polyfit(bb["h"], bb["valuenum"], 1)[0],
                                 a["valuenum"].median()))
            out[sig] = pd.DataFrame(rows, columns=["stay_id", "pre",
                                                   "post", "lvl"])
        return out

    s_dnr = slope_rows(peri[peri["y"] == 1], -12, -2, 2, 12)
    s_ctl = slope_rows(mperi, -12, -2, 2, 12)
    s_surv = slope_rows(peri[peri["y"] == 0], -12, -2, 2, 12)
    smap = stays.set_index("stay_id")
    for sig in ["hr", "map"]:
        d = s_dnr[sig].assign(dnr=1)
        c = s_ctl[sig].assign(dnr=0)
        p = pd.concat([d, c])
        p["sofa"] = p["stay_id"].map(smap["sofa48"].fillna(
            smap["sofa48"].median()))
        p["age"] = p["stay_id"].map(smap["age"])
        p["sepsis"] = p["stay_id"].map(smap["sepsis"])
        X = sm.add_constant(p[["dnr", "pre", "lvl", "sofa", "age",
                               "sepsis"]].fillna(p.median(numeric_only=True)))
        fit = sm.OLS(p["post"].values, X.values).fit(cov_type="HC1")
        print(f"[reg {sig}] dnr coef={fit.params[1]:.4f} "
              f"p={fit.pvalues[1]:.2g} n={len(p)}", flush=True)
        # off-center placebo cuts (narrow, avoid h=0)
        for cut, a1, b1, a2, b2 in [(-6, -12, -7, -5, 0), (6, 0, 5, 7, 12)]:
            pdn = slope_rows(peri[peri["y"] == 1], a1, b1, a2,
                             b2)[sig]
            if len(pdn) > 50:
                w = stats.wilcoxon(pdn["post"] - pdn["pre"]).pvalue
                print(f"  placebo cut {cut:+d}h: n={len(pdn)} medianΔ="
                      f"{(pdn['post'] - pdn['pre']).median():+.3f} p={w:.2g}",
                      flush=True)
        # survivor-with-DNR falsification
        sv = s_surv[sig]
        if len(sv) > 50:
            w = stats.wilcoxon(sv["post"] - sv["pre"]).pvalue
            print(f"  survivor-DNR: n={len(sv)} medianΔ="
                  f"{(sv['post'] - sv['pre']).median():+.3f} p={w:.2g}",
                  flush=True)

    # ---- C-robust: CV AUCs + paired bootstrap + cause mix ----
    con = duckdb.connect(DB, read_only=True)
    all_dec = stays[(stays["y"] == 1) & (stays["deathtime"].notna())]
    fc_ids = set(stays[(stays["y"] == 1) &
                       (stays["dnr_h"].isna())]["stay_id"])
    ct = pd.crosstab(all_dec["cause"].fillna("missing"),
                     all_dec["stay_id"].isin(fc_ids).map(
                         {True: "full", False: "dnr"}))
    print("cause mix (rows) x code status:\n", ct.to_string(), flush=True)
    print("median death_h full vs dnr:",
          round(float(all_dec[all_dec['stay_id'].isin(
              fc_ids)]["death_h"].median()), 1),
          round(float(all_dec[~all_dec['stay_id'].isin(
              fc_ids)]["death_h"].median()), 1), flush=True)
    dids = ",".join(map(str, all_dec["stay_id"].tolist()))
    surv = stays[(stays["y"] == 0) & (stays["los_h"] >= 72)].sample(
        15000, random_state=11)
    sids = ",".join(map(str, surv["stay_id"].tolist()))
    ITEMS = "220045,220052,220181,220210,224690,220277,223762,223761"
    vitd = con.execute(f"""
SELECT c.stay_id,
  CAST(date_diff('hour', c.charttime, a.deathtime) AS INTEGER) AS hbd,
  c.itemid, AVG(c.valuenum) AS m, STDDEV(c.valuenum) AS s,
  COUNT(*) AS n
FROM mimiciv_icu.chartevents c
JOIN mimiciv_hosp.admissions a ON a.hadm_id = c.hadm_id
WHERE c.stay_id IN ({dids}) AND c.itemid IN ({ITEMS})
  AND c.valuenum IS NOT NULL
  AND c.charttime >= a.deathtime - INTERVAL 72 HOUR
  AND c.charttime <= a.deathtime
GROUP BY 1, 2, 3""").fetchdf()
    vits = con.execute(f"""
SELECT c.stay_id,
  CAST(date_diff('hour', c.charttime, i.outtime) AS INTEGER) AS hbd,
  c.itemid, AVG(c.valuenum) AS m, STDDEV(c.valuenum) AS s,
  COUNT(*) AS n
FROM mimiciv_icu.chartevents c
JOIN mimiciv_icu.icustays i USING (stay_id)
WHERE c.stay_id IN ({sids}) AND c.itemid IN ({ITEMS})
  AND c.valuenum IS NOT NULL
  AND c.charttime >= i.outtime - INTERVAL 72 HOUR
  AND c.charttime <= i.outtime
GROUP BY 1, 2, 3""").fetchdf()
    con.close()
    IMAP = {220045: "hr", 220052: "map", 220181: "map", 220210: "rr",
            224690: "rr", 220277: "spo2", 223762: "temp", 223761: "temp"}
    RANGES = {"hr": (20, 300), "map": (20, 200), "rr": (0, 80),
              "spo2": (50, 100), "temp": (30, 43)}

    def tidy(v):
        v = v.copy()
        v["sig"] = v["itemid"].map(IMAP)
        f = v["itemid"] == 223761
        v.loc[f, "m"] = (v.loc[f, "m"] - 32) * 5 / 9
        lo = v["sig"].map({s: b[0] for s, b in RANGES.items()})
        hi = v["sig"].map({s: b[1] for s, b in RANGES.items()})
        v = v[(v["m"] >= lo) & (v["m"] <= hi)]
        v["mn"] = v["m"] * v["n"]
        v["s2n"] = v["s"].fillna(0) ** 2 * v["n"]
        g = v.groupby(["stay_id", "hbd", "sig"])
        n = g["n"].sum()
        return pd.DataFrame({"m": g["mn"].sum() / n,
                             "s": np.sqrt(g["s2n"].sum() / n),
                             "n": n}).reset_index()

    vd, vs = tidy(vitd), tidy(vits)
    dhmap = all_dec.set_index("stay_id")["death_h"].to_dict()
    agemap = stays.set_index("stay_id")["age"].to_dict()
    sepmap = stays.set_index("stay_id")["sepsis"].to_dict()
    svmap = surv.set_index("stay_id")[["los_h", "age",
                                       "sepsis"]].to_dict("index")
    vd_by = dict(tuple(vd.groupby("stay_id")))
    vs_by = dict(tuple(vs.groupby("stay_id")))
    sv_ids = surv["stay_id"].tolist()

    def feat_row(w, age, sepsis):
        g = w.groupby("sig")["m"].mean()
        h = w[w["sig"] == "hr"]
        out = {"hr": g.get("hr"), "map": g.get("map"), "rr": g.get("rr"),
               "spo2": g.get("spo2"), "temp": g.get("temp"),
               "hr_sd": np.sqrt(np.average(h["s"].fillna(0) ** 2,
                                           weights=h["n"]))
               if h["n"].sum() > 0 else np.nan,
               "age": age, "sepsis": sepsis}
        if out["hr"] is None or out["map"] is None or (
                isinstance(out["hr"], float) and np.isnan(out["hr"])):
            return None
        return out

    rng = np.random.default_rng(7)
    for H in [6, 12, 24]:
        cases, ctrls = [], []
        for sid, dh in dhmap.items():
            if dh - H - 6 < 0 or sid not in vd_by:
                continue
            w = vd_by[sid]
            w = w[(w["hbd"] >= H) & (w["hbd"] < H + 6)]
            if w.empty:
                continue
            f = feat_row(w, agemap[sid], sepmap[sid])
            if f is not None:
                cases.append((sid, f))
        for _ in range(len(cases)):
            sid = sv_ids[rng.integers(len(sv_ids))]
            if sid not in vs_by:
                continue
            sv = svmap[sid]
            s0 = rng.uniform(6, max(7, sv["los_h"] - H - 6))
            w = vs_by[sid]
            w = w[(w["hbd"] >= sv["los_h"] - s0 - 6) &
                  (w["hbd"] < sv["los_h"] - s0)]
            if w.empty:
                continue
            f = feat_row(w, sv["age"], sv["sepsis"])
            if f is not None:
                ctrls.append(f)
        Xa = pd.DataFrame([f for _, f in cases] + ctrls)
        ya = np.array([1] * len(cases) + [0] * len(ctrls))
        fc_idx = [i for i, (sid, _) in enumerate(cases) if sid in fc_ids]
        Xf = pd.DataFrame([cases[i][1] for i in fc_idx] +
                          ctrls[:len(fc_idx)])
        yf = np.array([1] * len(fc_idx) + [0] * len(fc_idx))
        for tag, XX, yy in [("ALL", Xa, ya), ("FC", Xf, yf)]:
            Xs = StandardScaler().fit_transform(XX.fillna(XX.median()))
            aucs = []
            skf = StratifiedKFold(n_splits=5, shuffle=True,
                                  random_state=9)
            for tr, te in skf.split(Xs, yy):
                lr = LogisticRegression(C=1.0,
                                        max_iter=5000).fit(Xs[tr], yy[tr])
                aucs.append(roc_auc_score(yy[te],
                                          lr.predict_proba(Xs[te])[:, 1]))
            print(f"[CV {tag} H={H}h] n={len(yy)} "
                  f"AUC={np.mean(aucs):.3f} sd={np.std(aucs):.3f}",
                  flush=True)
        # paired bootstrap gap (same controls)
        Xas = StandardScaler().fit_transform(Xa.fillna(Xa.median()))
        Xfs = StandardScaler().fit_transform(Xf.fillna(Xf.median()))
        gaps = []
        brng = np.random.default_rng(13)
        na, nf = len(ya), len(yf)
        for _ in range(200):
            ia = brng.integers(0, na, na)
            iff = brng.integers(0, nf, nf)
            try:
                aa = roc_auc_score(
                    ya[ia], LogisticRegression(C=1.0, max_iter=2000).fit(
                        Xas[ia], ya[ia]).predict_proba(Xas[ia])[:, 1])
                af = roc_auc_score(
                    yf[iff], LogisticRegression(C=1.0, max_iter=2000).fit(
                        Xfs[iff], yf[iff]).predict_proba(Xfs[iff])[:, 1])
                gaps.append(aa - af)
            except ValueError:
                pass
        print(f"  ALL-FC gap: {np.mean(gaps):.3f} "
              f"95%CI [{np.percentile(gaps, 2.5):.3f}-"
              f"{np.percentile(gaps, 97.5):.3f}]", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
