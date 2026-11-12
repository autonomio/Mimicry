"""Signs of death: gap-driven analyses (MIMIC-IV v3.1, s0 only).

Gaps vs literature: (1) continuous physiology of dying at scale
(Hui et al. used intermittent bedside signs in small cancer cohorts);
(2) autonomic collapse beyond trauma HRV studies; (3) cause-specific
modes of dying; (4) withdrawal-vs-natural confounding quantified;
(5) circadian death timing (hospice lore vs hospital data) +
rhythmicity loss; (6) hour-scale imminent-death prediction
(clinicians wrong 1/3 at 72h; PaP AUC 0.82 at days-weeks scale).
Also validates Hui late signs (oliguria) instrumentally.

Cohort: 9,438 terminal-ICU hospital decedents + 15k survivor sample.
Aggregates only leave s0.

Run on s0: /srv/mimic-iv/.venv/bin/python signs_of_death.py
"""
import math
import duckdb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

DB = "/srv/mimic-iv/db/mimic4-v31.db"
OUT = "/tmp/"

# signal -> [(itemid, lo, hi, f_to_c)]
SIG = {
    "hr": [(220045, 20, 300, False)],
    "map": [(220052, 20, 200, False), (220181, 20, 200, False)],
    "rr": [(220210, 0, 80, False), (224690, 0, 80, False)],
    "spo2": [(220277, 50, 100, False)],
    "temp": [(223762, 30, 43, False), (223761, 86, 110, True)],
}
ALLITEMS = sorted({i for v in SIG.values() for i, _, _, _ in v})
ITEM2SIG = {i: s for s, v in SIG.items() for i, _, _, _ in v}


def main():
    con = duckdb.connect(DB, read_only=True)
    print("loading decedent stays...", flush=True)
    dec = con.execute("""
SELECT i.stay_id, i.intime, i.outtime, a.deathtime, a.hadm_id,
  p.anchor_age, p.gender,
  CASE WHEN s.stay_id IS NOT NULL THEN 1 ELSE 0 END AS sepsis
FROM mimiciv_icu.icustays i
JOIN mimiciv_hosp.admissions a ON a.hadm_id = i.hadm_id
JOIN mimiciv_hosp.patients p ON p.subject_id = i.subject_id
LEFT JOIN (SELECT DISTINCT stay_id FROM mimiciv_derived.sepsis3) s
  USING (stay_id)
WHERE a.hospital_expire_flag = 1 AND a.deathtime IS NOT NULL
  AND a.deathtime >= i.intime
  AND i.stay_id IN (SELECT stay_id FROM (
    SELECT stay_id, ROW_NUMBER() OVER (
      PARTITION BY hadm_id ORDER BY intime DESC) AS rn
    FROM mimiciv_icu.icustays) t WHERE rn = 1)""").fetchdf()
    dec["death_h"] = (pd.to_datetime(dec["deathtime"]) -
                      pd.to_datetime(dec["intime"])).dt.total_seconds() / 3600
    print(f"decedents: {len(dec)}", flush=True)
    ids = ",".join(map(str, dec["stay_id"].tolist()))

    print("hourly vitals decedents...", flush=True)
    vitd = con.execute(f"""
SELECT c.stay_id,
  CAST(date_diff('hour', c.charttime, a.deathtime) AS INTEGER) AS hbd,
  c.itemid, AVG(c.valuenum) AS m, STDDEV(c.valuenum) AS s,
  COUNT(*) AS n
FROM mimiciv_icu.chartevents c
JOIN mimiciv_hosp.admissions a ON a.hadm_id = c.hadm_id
WHERE c.stay_id IN ({ids}) AND c.itemid IN ({','.join(map(str, ALLITEMS))})
  AND c.valuenum IS NOT NULL
  AND c.charttime >= a.deathtime - INTERVAL 72 HOUR
  AND c.charttime <= a.deathtime
GROUP BY 1, 2, 3""").fetchdf()
    print(f"  rows: {len(vitd)}", flush=True)

    print("survivor sample + hourly vitals...", flush=True)
    surv = con.execute("""
SELECT i.stay_id, i.intime, i.outtime, a.hadm_id, p.anchor_age, p.gender,
  CASE WHEN s.stay_id IS NOT NULL THEN 1 ELSE 0 END AS sepsis
FROM mimiciv_icu.icustays i
JOIN mimiciv_hosp.admissions a ON a.hadm_id = i.hadm_id
JOIN mimiciv_hosp.patients p ON p.subject_id = i.subject_id
LEFT JOIN (SELECT DISTINCT stay_id FROM mimiciv_derived.sepsis3) s
  USING (stay_id)
WHERE a.hospital_expire_flag = 0
  AND date_diff('hour', i.intime, i.outtime) >= 72
ORDER BY RANDOM() LIMIT 15000""").fetchdf()
    sids = ",".join(map(str, surv["stay_id"].tolist()))
    vits = con.execute(f"""
SELECT c.stay_id,
  CAST(date_diff('hour', c.charttime, i.outtime) AS INTEGER) AS hbd,
  c.itemid, AVG(c.valuenum) AS m, STDDEV(c.valuenum) AS s,
  COUNT(*) AS n
FROM mimiciv_icu.chartevents c
JOIN mimiciv_icu.icustays i USING (stay_id)
WHERE c.stay_id IN ({sids}) AND c.itemid IN ({','.join(map(str, ALLITEMS))})
  AND c.valuenum IS NOT NULL
  AND c.charttime >= i.outtime - INTERVAL 72 HOUR
  AND c.charttime <= i.outtime
GROUP BY 1, 2, 3""").fetchdf()
    print(f"  rows: {len(vits)}", flush=True)

    print("urine output...", flush=True)
    uo = con.execute(f"""
SELECT u.stay_id,
  CAST(date_diff('hour', u.charttime, a.deathtime) AS INTEGER) AS hbd,
  AVG(u.uo_mlkghr_6hr) AS rate
FROM mimiciv_derived.urine_output_rate u
JOIN mimiciv_icu.icustays i USING (stay_id)
JOIN mimiciv_hosp.admissions a ON a.hadm_id = i.hadm_id
WHERE u.stay_id IN ({ids})
  AND u.charttime >= a.deathtime - INTERVAL 72 HOUR
  AND u.charttime <= a.deathtime
GROUP BY 1, 2""").fetchdf()
    uos = con.execute(f"""
SELECT u.stay_id,
  CAST(date_diff('hour', u.charttime, i.outtime) AS INTEGER) AS hbd,
  AVG(u.uo_mlkghr_6hr) AS rate
FROM mimiciv_derived.urine_output_rate u
JOIN mimiciv_icu.icustays i USING (stay_id)
WHERE u.stay_id IN ({sids})
  AND u.charttime >= i.outtime - INTERVAL 72 HOUR
  AND u.charttime <= i.outtime
GROUP BY 1, 2""").fetchdf()

    print("clock hours + code status + dx + onsets...", flush=True)
    clk = con.execute("""
SELECT EXTRACT(HOUR FROM deathtime) AS h, COUNT(*) AS n
FROM mimiciv_hosp.admissions WHERE hospital_expire_flag = 1
GROUP BY 1 ORDER BY 1""").fetchdf()
    admh = con.execute("""
SELECT EXTRACT(HOUR FROM admittime) AS h, COUNT(*) AS n
FROM mimiciv_hosp.admissions GROUP BY 1 ORDER BY 1""").fetchdf()
    dnrh = con.execute(f"""
SELECT EXTRACT(HOUR FROM MIN(charttime)) AS h, COUNT(*) AS n
FROM mimiciv_derived.code_status WHERE stay_id IN ({ids})
  AND (dnr = 1 OR cmo = 1) GROUP BY stay_id""").fetchdf()
    code = con.execute(f"""
SELECT stay_id, MIN(CASE WHEN dnr = 1 OR cmo = 1 THEN charttime END) AS dnr_t
FROM mimiciv_derived.code_status WHERE stay_id IN ({ids}) GROUP BY 1""").fetchdf()
    dx = con.execute(f"""
SELECT i.stay_id, d.icd_version, d.icd_code
FROM mimiciv_hosp.diagnoses_icd d
JOIN mimiciv_icu.icustays i ON i.hadm_id = d.hadm_id
WHERE i.stay_id IN ({ids}) AND d.seq_num = 1""").fetchdf()
    ons = con.execute(f"""
SELECT stay_id,
  MIN(CASE WHEN respiration_24hours >= 3 THEN hr END) AS o_resp,
  MIN(CASE WHEN coagulation_24hours >= 3 THEN hr END) AS o_coag,
  MIN(CASE WHEN liver_24hours >= 3 THEN hr END) AS o_liver,
  MIN(CASE WHEN cardiovascular_24hours >= 3 THEN hr END) AS o_cv,
  MIN(CASE WHEN cns_24hours >= 3 THEN hr END) AS o_cns,
  MIN(CASE WHEN renal_24hours >= 3 THEN hr END) AS o_renal
FROM mimiciv_derived.sofa WHERE stay_id IN ({ids}) GROUP BY 1""").fetchdf()
    con.close()

    # ---- tidy vitals: plausibility filter, F->C, pool sources ----
    def tidy(v):
        v = v.copy()
        v["sig"] = v["itemid"].map(ITEM2SIG)
        keep = pd.Series(False, index=v.index)
        for s, specs in SIG.items():
            for iid, lo, hi, _ in specs:
                m = (v["itemid"] == iid) & (v["m"] >= lo) & (v["m"] <= hi)
                keep |= m
        v = v[keep].copy()
        f = v["itemid"] == 223761
        v.loc[f, "m"] = (v.loc[f, "m"] - 32) * 5 / 9
        v.loc[f, "s"] = v.loc[f, "s"] * 5 / 9
        # pool sources: n-weighted mean per stay/hour/signal
        # (vectorized; groupby.apply is prohibitive at 6M rows)
        v = v.copy()
        v["mn"] = v["m"] * v["n"]
        v["s2n"] = v["s"].fillna(0) ** 2 * v["n"]
        g = v.groupby(["stay_id", "hbd", "sig"])
        n = g["n"].sum()
        w = pd.DataFrame({"m": g["mn"].sum() / n,
                          "s": np.sqrt(g["s2n"].sum() / n),
                          "n": n}).reset_index()
        return w

    vd, vs = tidy(vitd), tidy(vits)
    print(f"tidy rows dec/surv: {len(vd)}/{len(vs)}", flush=True)

    # ---- A. trajectories + divergence onset ----
    traj = []
    for sig in SIG:
        a = vd[vd["sig"] == sig].groupby("hbd")["m"].agg(["mean", "sem",
                                                          "count"])
        b = vs[vs["sig"] == sig].groupby("hbd")["m"].agg(["mean", "sem",
                                                          "count"])
        j = a.join(b, lsuffix="_d", rsuffix="_s", how="inner")
        j["sig"] = sig
        traj.append(j.reset_index())
        # divergence: first hbd (from 0 upward) where CIs separate,
        # sustained 3h
        div = None
        sep = ((j["mean_d"] - 1.96 * j["sem_d"] >
                j["mean_s"] + 1.96 * j["sem_s"]) |
               (j["mean_s"] - 1.96 * j["sem_s"] >
                j["mean_d"] + 1.96 * j["sem_d"]))
        for h in range(0, 70):
            if sep.loc[h:h + 2].all() if h + 2 in sep.index else False:
                div = h
                break
        d0 = j.loc[0, "mean_d"] if 0 in j.index else float("nan")
        d72 = j["mean_d"].iloc[-1]
        print(f"[{sig}] hbd0={d0:.2f} hbd71={d72:.2f} "
              f"divergence_h={div}", flush=True)
    pd.concat(traj).to_csv(OUT + "sd_traj.csv", index=False)

    # ---- B. HRV proxies: within-hour HR sd + successive-hour |d| ----
    hrv = []
    for name, w in [("dec", vd), ("surv", vs)]:
        h = w[w["sig"] == "hr"].copy()
        g = h.groupby("hbd").agg(wsd=("s", "mean"), n=("m", "count"))
        # successive-hour absolute change of hourly mean per stay
        hp = h.pivot_table(index="stay_id", columns="hbd", values="m")
        rm = pd.Series({c: hp[c].sub(hp[c + 1]).abs().mean()
                        for c in range(0, 71) if c in hp and c + 1 in hp})
        g["succ_d"] = rm
        g["grp"] = name
        hrv.append(g.reset_index())
        print(f"[hrv {name}] wsd hbd0={g.loc[0, 'wsd']:.2f} "
              f"hbd71={g['wsd'].iloc[-1]:.2f} | "
              f"succ hbd0={g.loc[0, 'succ_d']:.2f} "
              f"hbd71={g['succ_d'].iloc[-1]:.2f}", flush=True)
    pd.concat(hrv).to_csv(OUT + "sd_hrv.csv", index=False)

    # ---- C. circadian ----
    clk.to_csv(OUT + "sd_death_hour.csv", index=False)
    admh.to_csv(OUT + "sd_admit_hour.csv", index=False)
    dh = dnrh["h"].value_counts().sort_index()
    dh.to_csv(OUT + "sd_dnr_hour.csv", header=["n"])
    from scipy import stats
    for nm, t in [("death", clk), ("admit", admh)]:
        chi2, p = stats.chisquare(t["n"])
        pk = t.loc[t["n"].idxmax(), "h"]
        print(f"[{nm} hour] chi2={chi2:.0f} p={p:.2g} peak_h={int(pk)} "
              f"max/min={t['n'].max() / t['n'].min():.2f}", flush=True)
    # cosinor amplitude by day before death (temp + hr)
    for sig in ["temp", "hr"]:
        amps = []
        for name, w in [("dec", vd), ("surv", vs)]:
            h = w[w["sig"] == sig].copy()
            h["day"] = h["hbd"] // 24  # 0,1,2 days before event
            for dd_ in [2, 1, 0]:
                s = h[h["day"] == dd_].groupby("hbd")["m"].mean()
                if len(s) < 12:
                    continue
                t = 2 * math.pi * (s.index % 24) / 24
                X = np.column_stack([np.ones(len(s)), np.sin(t),
                                     np.cos(t)])
                beta, *_ = np.linalg.lstsq(X, s.values, rcond=None)
                amp = math.hypot(beta[1], beta[2])
                amps.append([name, dd_, round(amp, 4), len(s)])
        print(f"[cosinor {sig}]",
              {f"{n}d{d}": a for n, d, a, _ in amps}, flush=True)
        pd.DataFrame(amps, columns=["grp", "day", "amp",
                                    "nbins"]).to_csv(
            OUT + f"sd_cos_{sig}.csv", index=False)

    # ---- cause groups ----
    dx = dx.drop_duplicates("stay_id")
    sepmap = dec.set_index("stay_id")["sepsis"].to_dict()

    def cause(r):
        if sepmap.get(r["stay_id"], 0) == 1:
            return "sepsis"
        v, c = str(r["icd_version"]), str(r["icd_code"])
        if v == "10":
            if c[:1] == "G" or c[:3] in ("I60", "I61", "I62", "I63",
                                         "I64", "I65", "I66", "I67",
                                         "I68", "I69"):
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

    dx["cause"] = dx.apply(cause, axis=1)
    print("cause mix:", dx["cause"].value_counts().to_dict(), flush=True)
    cmap = dx.set_index("stay_id")["cause"].to_dict()
    vd = vd.copy()
    vd["cause"] = vd["stay_id"].map(cmap)
    # early vs late death by cause (<=72h vs >72h after ICU admission)
    dhmap = dec.set_index("stay_id")["death_h"].to_dict()
    early = []
    for c, g in dx.groupby("cause"):
        hh = g["stay_id"].map(dhmap)
        e = float((hh <= 72).mean())
        early.append([c, len(g), round(e, 3),
                      round(float(hh.median()), 1)])
        print(f"[cause {c}] n={len(g)} early72={e:.3f} "
              f"median_death_h={float(hh.median()):.0f}", flush=True)
    pd.DataFrame(early, columns=["cause", "n", "early72",
                                 "median_death_h"]).to_csv(
        OUT + "sd_cause_timing.csv", index=False)
    # trajectory shape by cause (hr/map/sofa-ish via temp? just vitals)
    for sig in ["hr", "map", "rr"]:
        ct = vd[vd["sig"] == sig].groupby(["cause", "hbd"])["m"].mean()
        ct.unstack(0).to_csv(OUT + f"sd_cause_{sig}.csv")
    # first-organ by cause
    orgs = ["o_resp", "o_coag", "o_liver", "o_cv", "o_cns", "o_renal"]
    ons["cause"] = ons["stay_id"].map(cmap)
    fo = []
    for c, g in ons.groupby("cause"):
        shares = {}
        for _, r in g.iterrows():
            v = r[orgs].dropna()
            if len(v) == 0:
                continue
            m = v.min()
            first = [o for o in v.index if v[o] <= m + 24]
            for o in first:
                shares[o] = shares.get(o, 0) + 1 / len(first)
        tot = sum(shares.values())
        row = {"cause": c, "n": len(g)}
        row.update({o: round(shares.get(o, 0) / tot, 4) if tot else 0
                    for o in orgs})
        fo.append(row)
    pd.DataFrame(fo).to_csv(OUT + "sd_cause_first.csv", index=False)
    print(pd.DataFrame(fo).to_string(), flush=True)

    # ---- E. withdrawal split ----
    code["dnr_t"] = pd.to_datetime(code["dnr_t"])
    into = dec.set_index("stay_id")
    code = code.merge(dec[["stay_id", "intime", "deathtime"]], on="stay_id")
    code["dnr_h"] = (pd.to_datetime(code["dnr_t"]) -
                     pd.to_datetime(code["intime"])).dt.total_seconds() / 3600
    code["dd_h"] = (pd.to_datetime(code["deathtime"]) -
                    pd.to_datetime(code["intime"])).dt.total_seconds() / 3600
    code["d2d"] = code["dd_h"] - code["dnr_h"]
    print(f"DNR/CMO before death: {(code['d2d'] > 0).sum()} / {len(dec)} "
          f"= {(code['d2d'] > 0).mean():.3f}", flush=True)
    print(f"  DNR->death median h: "
          f"{float(code.loc[code['d2d'] > 0, 'd2d'].median()):.1f}",
          flush=True)
    wdraw = set(code.loc[code["d2d"] > 0, "stay_id"])
    vd = vd.copy()
    vd["wd"] = vd["stay_id"].isin(wdraw).map({True: "dnr", False: "full"})
    for sig in SIG:
        wt = vd[vd["sig"] == sig].groupby(["wd", "hbd"])["m"].mean()
        wt.unstack(0).to_csv(OUT + f"sd_wd_{sig}.csv")
    # last-6h slope by withdrawal status (MAP + HR)
    for sig in ["hr", "map"]:
        sl = []
        for w, g in vd[vd["sig"] == sig].groupby("wd"):
            piv = g.pivot_table(index="stay_id", columns="hbd", values="m")
            use = piv[[c for c in range(0, 6) if c in piv.columns]]
            b = use.apply(lambda r: np.polyfit(
                sorted(use.columns), r.reindex(sorted(use.columns)).values,
                1)[0] if r.notna().sum() >= 3 else np.nan, axis=1)
            sl.append([w, int(b.notna().sum()), round(float(b.median()), 4)])
        print(f"[slope6 {sig}]", sl, flush=True)

    # ---- F. Hui oliguria validation ----
    uo["grp"] = "dec"
    uos["grp"] = "surv"
    uu = pd.concat([uo, uos])
    olig = uu.assign(olig05=(uu["rate"] < 0.5).astype(int),
                     olig03=(uu["rate"] < 0.3).astype(int))
    og = olig.groupby(["grp", "hbd"])[["olig05",
                                       "olig03"]].mean().reset_index()
    og.to_csv(OUT + "sd_oliguria.csv", index=False)
    for grp in ["dec", "surv"]:
        g = og[og["grp"] == grp].set_index("hbd")
        print(f"[oliguria {grp}] <0.5mL/kg/h hbd0={g.loc[0, 'olig05']:.3f} "
              f"hbd23={g.loc[23, 'olig05']:.3f} hbd71="
              f"{g['olig05'].iloc[-1]:.3f}", flush=True)

    # ---- G. imminent-death prediction ----
    dhmap = dec.set_index("stay_id")["death_h"].to_dict()
    agemap = dec.set_index("stay_id")["anchor_age"].to_dict()
    sepmap2 = dec.set_index("stay_id")["sepsis"].to_dict()
    # survivor landmarks need elapsed-hour info: recompute los
    surv["los_h"] = (pd.to_datetime(surv["outtime"]) -
                     pd.to_datetime(surv["intime"])).dt.total_seconds() / 3600
    svmap = surv.set_index("stay_id")[["los_h", "anchor_age",
                                       "sepsis"]].to_dict("index")
    rng = np.random.default_rng(7)
    sv_ids = surv["stay_id"].tolist()
    vd_by = dict(tuple(vd.groupby("stay_id")))
    vs_by = dict(tuple(vs.groupby("stay_id")))
    for H in [6, 12, 24]:
        Xy = []
        for sid, dh in dhmap.items():
            if dh - H - 6 < 0 or sid not in vd_by:
                continue
            w = vd_by[sid]
            w = w[(w["hbd"] >= H) & (w["hbd"] < H + 6)]
            if w.empty:
                continue
            f = feat_row(w, agemap[sid], sepmap2[sid])
            if f is not None:
                Xy.append((f, 1))
        ncase = len(Xy)
        # controls: survivors still in ICU at matched elapsed time
        for _ in range(ncase):
            sid = sv_ids[rng.integers(len(sv_ids))]
            if sid not in vs_by:
                continue
            sv = svmap[sid]
            s0 = rng.uniform(6, max(7, sv["los_h"] - H - 6))
            hbd_lo = sv["los_h"] - s0 - 6
            hbd_hi = sv["los_h"] - s0
            w = vs_by[sid]
            w = w[(w["hbd"] >= hbd_lo) & (w["hbd"] < hbd_hi)]
            if w.empty:
                continue
            f = feat_row(w, sv["anchor_age"], sv["sepsis"])
            if f is not None:
                Xy.append((f, 0))
        X = pd.DataFrame([f for f, _ in Xy])
        y = np.array([v for _, v in Xy])
        Xs = StandardScaler().fit_transform(X.fillna(X.median()))
        lr = LogisticRegression(C=1.0, max_iter=5000).fit(Xs, y)
        auc = roc_auc_score(y, lr.predict_proba(Xs)[:, 1])
        Xn = X.drop(columns=["hr_n"])
        Xns = StandardScaler().fit_transform(Xn.fillna(Xn.median()))
        lrn = LogisticRegression(C=1.0, max_iter=5000).fit(Xns, y)
        aucn = roc_auc_score(y, lrn.predict_proba(Xns)[:, 1])
        print(f"[predict H={H}h] n={len(y)} "
              f"pos={int(y.sum())} AUC={auc:.3f} "
              f"AUC_no_hrn={aucn:.3f}", flush=True)
        co = sorted(zip(X.columns, lr.coef_[0]), key=lambda x: -abs(x[1]))
        print(f"  top coefs: {[(c, round(float(v), 3)) for c, v in co[:6]]}",
              flush=True)
    print("done", flush=True)


def feat_row(w, age, sepsis):
    g = w.groupby("sig")["m"].mean()
    h = w[w["sig"] == "hr"]
    out = {"hr": g.get("hr"), "map": g.get("map"), "rr": g.get("rr"),
           "spo2": g.get("spo2"), "temp": g.get("temp"),
           "hr_n": h["n"].sum() if len(h) else 0,
           "hr_sd": np.sqrt(np.average(h["s"].fillna(0) ** 2,
                                       weights=h["n"])) if h["n"].sum() > 0
           else np.nan,
           "age": age, "sepsis": sepsis}
    if sum(v is None or (isinstance(v, float) and math.isnan(v))
           for v in [out["hr"], out["map"]]) > 0:
        return None
    return out


if __name__ == "__main__":
    main()
