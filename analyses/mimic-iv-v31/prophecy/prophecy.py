"""Self-fulfilling prophecy dissection (MIMIC-IV v3.1, s0 only).

(A) Does early risk predict DNR? Landmark 24h: day-1 SOFA -> DNR
    within (24,72]h (stays with los>=24h, no DNR before 24h).
(B) Does DNR predict death beyond physiology? Landmark 48h (and 24h):
    DNR-before-landmark -> hospital death, adjusted for SOFA at
    landmark + age + sepsis + cause. Plus within-stay slope
    discontinuity: MAP/HR slopes [-12,-2]h vs [+2,+12]h around DNR
    time, with matched full-code controls at same elapsed hour.
(C) Honest estimand: 6/12/24h prediction on FULL-CODE decedents only
    vs all-decedent AUCs (0.816/0.783/0.777).
(D) Model vs chart: AUC of "DNR already written at landmark" alone
    and combined with physiology.
Aggregates only leave s0.
"""
import duckdb
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
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
    print("loading stays + sofa landmarks + dnr + dx...", flush=True)
    stays = con.execute("""
SELECT i.stay_id, i.intime, i.outtime, i.hadm_id, a.hospital_expire_flag AS y,
  a.deathtime, p.anchor_age AS age, p.gender,
  CASE WHEN s.stay_id IS NOT NULL THEN 1 ELSE 0 END AS sepsis
FROM mimiciv_icu.icustays i
JOIN mimiciv_hosp.admissions a ON a.hadm_id = i.hadm_id
JOIN mimiciv_hosp.patients p ON p.subject_id = i.subject_id
LEFT JOIN (SELECT DISTINCT stay_id FROM mimiciv_derived.sepsis3) s
  USING (stay_id)""").fetchdf()
    stays["los_h"] = (pd.to_datetime(stays["outtime"]) -
                      pd.to_datetime(stays["intime"])).dt.total_seconds() / 3600
    sofa = con.execute("""
SELECT stay_id, hr, sofa_24hours AS sofa FROM mimiciv_derived.sofa
WHERE hr IN (24, 48)""").fetchdf()
    so = sofa.pivot_table(index="stay_id", columns="hr",
                          values="sofa").rename(columns={24: "sofa24",
                                                         48: "sofa48"})
    stays = stays.merge(so, on="stay_id", how="left")
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
    print(f"stays: {len(stays)}", flush=True)

    def design(df, cols):
        X = pd.get_dummies(df[cols], columns=["cause", "gender"],
                           drop_first=True, dtype=float)
        return X.fillna(X.median())

    # ---- A. day-1 SOFA -> DNR in (24,72] ----
    a = stays[(stays["los_h"] >= 24) & (stays["sofa24"].notna()) &
              ((stays["dnr_h"].isna()) | (stays["dnr_h"] >= 24))].copy()
    a["dnr72"] = ((a["dnr_h"].notna()) & (a["dnr_h"] <= 72)).astype(int)
    Xa = design(a, ["sofa24", "age", "sepsis", "cause", "gender"])
    Xas = StandardScaler().fit_transform(Xa)
    lra = LogisticRegression(C=1.0, max_iter=5000).fit(Xas, a["dnr72"])
    auca = roc_auc_score(a["dnr72"], lra.predict_proba(Xas)[:, 1])
    lra_raw = LogisticRegression(C=1.0, max_iter=5000).fit(
        Xa.values, a["dnr72"])
    j = list(Xa.columns).index("sofa24")
    print(f"[A] n={len(a)} dnr72_rate={a['dnr72'].mean():.3f} "
          f"AUC={auca:.3f} OR_per_SOFApt="
          f"{np.exp(lra_raw.coef_[0][j]):.3f}", flush=True)

    # ---- B. DNR-before-landmark -> death ----
    for LM, SC in [(48, "sofa48"), (24, "sofa24")]:
        b = stays[(stays["los_h"] >= LM) & (stays[SC].notna())].copy()
        b["exp"] = ((b["dnr_h"].notna()) & (b["dnr_h"] < LM)).astype(int)
        Xb = design(b, [SC, "age", "sepsis", "cause", "gender"])
        Xb["exp"] = b["exp"].values
        Xbs = StandardScaler().fit_transform(Xb)
        lr = LogisticRegression(C=1.0, max_iter=5000).fit(Xbs, b["y"])
        auc = roc_auc_score(b["y"], lr.predict_proba(Xbs)[:, 1])
        lr_raw = LogisticRegression(C=1.0, max_iter=5000).fit(
            Xb.values, b["y"])
        k = list(Xb.columns).index("exp")
        r1 = b[b["exp"] == 1]["y"].mean()
        r0 = b[b["exp"] == 0]["y"].mean()
        print(f"[B{LM}] n={len(b)} exp_rate={b['exp'].mean():.3f} "
              f"death|dnr={r1:.3f} death|full={r0:.3f} "
              f"adjOR_dnr={np.exp(lr_raw.coef_[0][k]):.2f} AUC={auc:.3f}",
              flush=True)

    # ---- B2. slope discontinuity around DNR ----
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
    print(f"  peri rows: {len(peri)}", flush=True)
    dmap = stays.set_index("stay_id")["dnr_h"].to_dict()
    imap = stays.set_index("stay_id")["intime"].to_dict()
    peri["h"] = (pd.to_datetime(peri["charttime"]) -
                 peri["stay_id"].map(
                     lambda s: pd.to_datetime(imap[s]))).dt.total_seconds() / 3600 \
        - peri["stay_id"].map(dmap)
    peri["sig"] = peri["itemid"].map({220045: "hr", 220052: "map",
                                      220181: "map"})
    peri = peri[((peri["sig"] == "hr") & peri["valuenum"].between(20, 300)) |
                ((peri["sig"] == "map") & peri["valuenum"].between(20, 200))]
    # matched full-code controls at same elapsed hour
    fc = stays[(stays["dnr_h"].isna()) & (stays["los_h"] >= 48)]
    dnr_stays = stays[(stays["dnr_h"].notna()) & (stays["dnr_h"] >= 12) &
                      (stays["dnr_h"] <= stays["los_h"])]
    rng = np.random.default_rng(3)
    pairs = []
    used = set()
    for _, r in dnr_stays.sample(frac=1, random_state=3).iterrows():
        c = fc[(~fc["stay_id"].isin(used)) &
               (fc["sepsis"] == r["sepsis"]) &
               ((fc["age"] - r["age"]).abs() <= 10) &
               ((fc["los_h"] - r["dnr_h"]).abs() <= 48) &
               (fc["los_h"] >= r["dnr_h"] + 12)]
        if len(c) == 0:
            continue
        m = c.iloc[rng.integers(len(c))]
        used.add(m["stay_id"])
        pairs.append((r["stay_id"], m["stay_id"], r["dnr_h"]))
    print(f"  matched pairs: {len(pairs)}", flush=True)
    mstays = ",".join(map(str, {p[1] for p in pairs}))
    mperi = con.execute(f"""
SELECT stay_id, charttime, itemid, valuenum
FROM mimiciv_icu.chartevents
WHERE stay_id IN ({mstays})
  AND itemid IN (220045, 220052, 220181) AND valuenum IS NOT NULL""").fetchdf()
    con.close()
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

    def slopes(df):
        out = {}
        for sig in ["hr", "map"]:
            s = df[df["sig"] == sig]
            mh = s[(s["h"] >= -12) & (s["h"] < -2)].groupby("stay_id")
            ph = s[(s["h"] > 2) & (s["h"] <= 12)].groupby("stay_id")
            rows = []
            for sid in set(mh.groups) & set(ph.groups):
                a, b = mh.get_group(sid), ph.get_group(sid)
                if len(a) >= 3 and len(b) >= 3:
                    sa = np.polyfit(a["h"], a["valuenum"], 1)[0]
                    sb = np.polyfit(b["h"], b["valuenum"], 1)[0]
                    rows.append((sid, sa, sb, a["valuenum"].median(),
                                 b["valuenum"].median()))
            out[sig] = pd.DataFrame(rows, columns=["stay_id", "pre",
                                                   "post", "lvl_pre",
                                                   "lvl_post"])
        return out

    s_dnr, s_ctl = slopes(peri), slopes(mperi)
    for sig in ["hr", "map"]:
        d, c = s_dnr[sig], s_ctl[sig]
        dd = (d["post"] - d["pre"]).median()
        cc = (c["post"] - c["pre"]).median()
        w = stats.wilcoxon(d["post"] - d["pre"]).pvalue if len(d) > 10 else 1
        dl = (d["lvl_post"] - d["lvl_pre"]).median()
        cl = (c["lvl_post"] - c["lvl_pre"]).median()
        print(f"[discont {sig}] dnr n={len(d)} slope {d['pre'].median():.3f}"
              f"->{d['post'].median():.3f} p={w:.2g} levelΔ={dl:.2f} | "
              f"ctl n={len(c)} slopeΔ={cc:.3f} levelΔ={cl:.2f}", flush=True)
        d.drop(columns=["stay_id"]).to_csv(f"{OUT}pr_slope_dnr_{sig}.csv", index=False)
        c.drop(columns=["stay_id"]).to_csv(f"{OUT}pr_slope_ctl_{sig}.csv", index=False)

    # ---- C+D. full-code prediction + chart baseline ----
    con = duckdb.connect(DB, read_only=True)
    all_dec = stays[(stays["y"] == 1) & (stays["deathtime"].notna())]
    fc_ids = set(stays[(stays["y"] == 1) &
                       (stays["dnr_h"].isna())]["stay_id"])
    print(f"all decedents: {len(all_dec)}, full-code: {len(fc_ids)}",
          flush=True)
    fids = ",".join(map(str, all_dec["stay_id"].tolist()))
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
WHERE c.stay_id IN ({fids}) AND c.itemid IN ({ITEMS})
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
    print(f"  vit rows fc/surv: {len(vitd)}/{len(vits)}", flush=True)
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
    dhmap = all_dec.set_index("stay_id").apply(
        lambda r: (pd.to_datetime(r["deathtime"]) -
                   pd.to_datetime(r["intime"])).total_seconds() / 3600,
        axis=1).to_dict()
    agemap = stays.set_index("stay_id")["age"].to_dict()
    sepmap = stays.set_index("stay_id")["sepsis"].to_dict()
    dnrmap = stays.set_index("stay_id")["dnr_h"].to_dict()
    svmap = surv.set_index("stay_id")[["los_h", "age",
                                       "sepsis"]].to_dict("index")
    vd_by = dict(tuple(vd.groupby("stay_id")))
    vs_by = dict(tuple(vs.groupby("stay_id")))
    rng = np.random.default_rng(7)
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

    def run_pred(tag, case_ids):
        for H in [6, 12, 24]:
            Xy, Ch = [], []
            for sid in case_ids:
                dh = dhmap[sid]
                if dh - H - 6 < 0 or sid not in vd_by:
                    continue
                w = vd_by[sid]
                w = w[(w["hbd"] >= H) & (w["hbd"] < H + 6)]
                if w.empty:
                    continue
                f = feat_row(w, agemap[sid], sepmap[sid])
                if f is not None:
                    Xy.append((f, 1))
                    dn = dnrmap.get(sid)
                    Ch.append(1 if dn is not None and not np.isnan(dn)
                              and dn < dh - H else 0)
            ncase = len(Xy)
            for _ in range(ncase):
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
                    Xy.append((f, 0))
                    dn = dnrmap.get(sid)
                    Ch.append(1 if dn is not None and not np.isnan(dn)
                              and dn < s0 + 6 else 0)
            X = pd.DataFrame([f for f, _ in Xy])
            y = np.array([v for _, v in Xy])
            Ch = np.array(Ch)
            Xs = StandardScaler().fit_transform(X.fillna(X.median()))
            auc = roc_auc_score(y, LogisticRegression(
                C=1.0, max_iter=5000).fit(Xs, y).predict_proba(Xs)[:, 1])
            aucc = roc_auc_score(y, Ch)
            Xc = np.column_stack([Xs, Ch])
            aucb = roc_auc_score(y, LogisticRegression(
                C=1.0, max_iter=5000).fit(Xc, y).predict_proba(Xc)[:, 1])
            print(f"[{tag} H={H}h] n={len(y)} pos={int(y.sum())} "
                  f"AUCphys={auc:.3f} AUCchart={aucc:.3f} "
                  f"AUCboth={aucb:.3f}", flush=True)

    run_pred("FC", [s for s in dhmap if s in fc_ids])
    run_pred("ALL", list(dhmap))
    print("done", flush=True)


if __name__ == "__main__":
    main()
