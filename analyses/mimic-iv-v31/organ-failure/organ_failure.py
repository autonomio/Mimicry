"""Order of organ failure leading to death (MIMIC-IV v3.1, s0 only).

Cohort: terminal ICU stays of hospital decedents (deathtime known).
Organ failure = SOFA subscore (trailing-24h) first reaching >=3
(sensitivity >=2). Hourly resolution; ties within 24h = simultaneous.
Outputs: failure prevalence at death, first-organ distribution, pairwise
precedence + lead times, common sequences, death-aligned trajectories
(decedents vs survivor sample), sepsis/age/DNR subgroups, support-therapy
validation lags, Vincent-2011 replication (dSOFA last 4 days).
Aggregates only leave s0.

Run on s0: /srv/mimic-iv/.venv/bin/python organ_failure.py
"""
import duckdb
import numpy as np
import pandas as pd

DB = "/srv/mimic-iv/db/mimic4-v31.db"
OUT = "/tmp/"
ORGANS = ["respiration", "coagulation", "liver", "cardiovascular", "cns",
          "renal"]
SHORT = {"respiration": "RESP", "coagulation": "COAG", "liver": "LIVER",
         "cardiovascular": "CV", "cns": "CNS", "renal": "RENAL"}


def main():
    con = duckdb.connect(DB, read_only=True)
    print("loading terminal stays...", flush=True)
    stays = con.execute("""
SELECT i.stay_id, i.intime, i.outtime, a.deathtime,
  a.hospital_expire_flag AS died, p.anchor_age, p.gender,
  CASE WHEN s.stay_id IS NOT NULL THEN 1 ELSE 0 END AS sepsis
FROM mimiciv_icu.icustays i
JOIN mimiciv_hosp.admissions a USING (hadm_id)
JOIN mimiciv_hosp.patients p ON p.subject_id = i.subject_id
LEFT JOIN (SELECT DISTINCT stay_id FROM mimiciv_derived.sepsis3) s
  USING (stay_id)
WHERE i.stay_id IN (
  SELECT stay_id FROM (
    SELECT stay_id, ROW_NUMBER() OVER (
      PARTITION BY hadm_id ORDER BY intime DESC) AS rn
    FROM mimiciv_icu.icustays) t WHERE rn = 1)
""").fetchdf()
    stays["los_h"] = (pd.to_datetime(stays["outtime"]) -
                      pd.to_datetime(stays["intime"])).dt.total_seconds() / 3600
    stays["death_h"] = (pd.to_datetime(stays["deathtime"]) -
                        pd.to_datetime(stays["intime"])).dt.total_seconds() / 3600
    stays["disch_death_h"] = (
        pd.to_datetime(stays["deathtime"]) -
        pd.to_datetime(stays["outtime"])).dt.total_seconds() / 3600
    dec = stays[(stays["died"] == 1) & stays["death_h"].notna() &
                (stays["death_h"] >= 0) &
                (stays["disch_death_h"] <= 72)].copy()
    print(f"terminal stays: {len(stays)}, decedents: {len(dec)}, "
          f"los>=48h: {int((dec['los_h'] >= 48).sum())}", flush=True)

    print("loading sofa rows...", flush=True)
    ids = ",".join(map(str, dec["stay_id"].tolist()))
    sofa = con.execute(f"""
SELECT stay_id, hr, starttime, respiration_24hours AS respiration,
  coagulation_24hours AS coagulation, liver_24hours AS liver,
  cardiovascular_24hours AS cardiovascular, cns_24hours AS cns,
  renal_24hours AS renal, sofa_24hours AS sofa
FROM mimiciv_derived.sofa WHERE stay_id IN ({ids})""").fetchdf()
    print(f"sofa rows: {len(sofa)}", flush=True)

    print("loading supports + code status...", flush=True)
    supp = con.execute(f"""
SELECT COALESCE(v.stay_id, x.stay_id) AS stay_id, v.vent_t, x.vaso_t
FROM (SELECT stay_id, MIN(starttime) AS vent_t
      FROM mimiciv_derived.ventilation
      WHERE stay_id IN ({ids})
        AND ventilation_status IN ('InvasiveVent', 'Tracheostomy')
      GROUP BY 1) v
FULL OUTER JOIN (SELECT stay_id, MIN(starttime) AS vaso_t
      FROM mimiciv_derived.vasoactive_agent
      WHERE stay_id IN ({ids})
      GROUP BY 1) x USING (stay_id)""").fetchdf()
    rrt = con.execute(f"""
SELECT stay_id, MIN(charttime) AS rrt_t
FROM mimiciv_derived.rrt
WHERE stay_id IN ({ids}) AND dialysis_active = 1 GROUP BY 1""").fetchdf()
    code = con.execute(f"""
SELECT stay_id, MIN(CASE WHEN dnr = 1 OR cmo = 1 THEN charttime END) AS dnr_t,
  COUNT(*) AS code_n
FROM mimiciv_derived.code_status WHERE stay_id IN ({ids}) GROUP BY 1""").fetchdf()
    # survivor sample for trajectory control
    surv_ids = con.execute("""
SELECT stay_id FROM mimiciv_icu.icustays i
JOIN mimiciv_hosp.admissions a USING (hadm_id)
WHERE a.hospital_expire_flag = 0
  AND date_diff('hour', i.intime, i.outtime) >= 48
ORDER BY RANDOM() LIMIT 15000""").fetchdf()["stay_id"].tolist()
    sids = ",".join(map(str, surv_ids))
    surv_sofa = con.execute(f"""
SELECT s.stay_id, s.hr, s.respiration_24hours AS respiration,
  s.coagulation_24hours AS coagulation, s.liver_24hours AS liver,
  s.cardiovascular_24hours AS cardiovascular, s.cns_24hours AS cns,
  s.renal_24hours AS renal, s.sofa_24hours AS sofa,
  date_diff('hour', i.intime, i.outtime) AS los
FROM mimiciv_derived.sofa s
JOIN mimiciv_icu.icustays i USING (stay_id)
WHERE s.stay_id IN ({sids})""").fetchdf()
    con.close()
    print(f"survivor rows: {len(surv_sofa)}", flush=True)

    d = dec.merge(supp, on="stay_id", how="left").merge(
        rrt, on="stay_id", how="left").merge(code, on="stay_id", how="left")
    for c in ["vent_t", "vaso_t", "rrt_t", "dnr_t", "intime", "deathtime"]:
        d[c] = pd.to_datetime(d[c])
    into = d.set_index("stay_id")["intime"]
    dd = d.set_index("stay_id")["deathtime"]
    for c in ["vent_t", "vaso_t", "rrt_t", "dnr_t"]:
        d[c + "_h"] = (d[c] - d["intime"]).dt.total_seconds() / 3600
    # early-DNR flag: dnr/cmo >24h before death
    d["early_dnr"] = ((d["dnr_t_h"].notna()) &
                      (d["dnr_t_h"] < d["death_h"] - 24)).astype(int)
    # strict full-code: code-status charted AND never DNR/CMO (missing
    # code-status stays are unknown, not full-code)
    d["fullcode"] = (d["dnr_t_h"].isna() &
                     d["code_n"].fillna(0).gt(0)).astype(int)
    print(f"early-DNR stays: {int(d['early_dnr'].sum())} "
          f"({d['early_dnr'].mean():.3f}), strict full-code: "
          f"{int(d['fullcode'].sum())} ({d['fullcode'].mean():.3f}), "
          f"missing code-status: "
          f"{int(d['code_n'].isna().sum())}", flush=True)
    prim = d[d["los_h"] >= 48].copy()
    print(f"PRIMARY cohort (los>=48h): {len(prim)}, sepsis="
          f"{int(prim['sepsis'].sum())}, age65+="
          f"{int((prim['anchor_age'] >= 65).sum())}", flush=True)

    for thr in [3, 2]:
        tag = f"thr{thr}"
        print(f"===== threshold >={thr} =====", flush=True)
        # onset hour per organ per stay (PRIMARY los>=48h cohort, so
        # prevalence, first-organ, precedence and sequences share one
        # population)
        so = sofa.merge(prim[["stay_id", "death_h"]], on="stay_id")
        so = so[so["hr"] <= so["death_h"]]
        onsets = {}
        for o in ORGANS:
            f = so[so[o] >= thr].groupby("stay_id")["hr"].min()
            onsets[o] = f
        on = pd.DataFrame(onsets)
        # last-24h max per organ (failure at death)
        last = so[so["hr"] > so["death_h"] - 24].groupby("stay_id")[ORGANS].max()
        prev = (last >= thr).mean().round(4)
        print("prevalence failed in last 24h before death:",
              flush=True)
        for o in ORGANS:
            print(f"  {o}: {prev[o]:.4f} "
                  f"(n={(last[o] >= thr).sum()})", flush=True)
        nfail = (last >= thr).sum(axis=1)
        print("n organs failed distribution:",
              nfail.value_counts().sort_index().to_dict(), flush=True)
        prev.to_csv(f"{OUT}of_prev_{tag}.csv", header=["prev"])

        # first-failing organ (ties split)
        fo = {}
        for sid, row in on.dropna(how="all").iterrows():
            r = row.dropna()
            if len(r) == 0:
                continue
            m = r.min()
            first = [o for o in r.index if r[o] <= m + 24]
            for o in first:
                fo[o] = fo.get(o, 0) + 1 / len(first)
        tot = sum(fo.values())
        print("first-failing organ (tie-split):", flush=True)
        for o in sorted(fo, key=fo.get, reverse=True):
            print(f"  {o}: {fo[o] / tot:.4f} ({fo[o]:.0f})", flush=True)
        pd.Series({o: fo.get(o, 0) / tot for o in ORGANS}).to_csv(
            f"{OUT}of_first_{tag}.csv", header=["share"])

        # pairwise precedence + lead times (primary cohort)
        onp = on.loc[on.index.intersection(prim["stay_id"])]
        prec = []
        for i, a in enumerate(ORGANS):
            for b in ORGANS[i + 1:]:
                both = onp[[a, b]].dropna()
                n = len(both)
                if n == 0:
                    continue
                dlt = both[a] - both[b]
                pab = float((dlt < -24).mean())
                pba = float((dlt > 24).mean())
                tie = float((dlt.abs() <= 24).mean())
                lead = dlt[dlt.abs() > 24]
                med = float(lead.median()) if len(lead) else float("nan")
                print(f"  {SHORT[a]} vs {SHORT[b]}: n={n} "
                      f"P({SHORT[a]} first)={pab:.3f} "
                      f"P({SHORT[b]} first)={pba:.3f} tie24={tie:.3f} "
                      f"median_lead_h={med:.1f}", flush=True)
                denom = pab + pba
                na = round(pab / denom, 4) if denom else None
                nb = round(pba / denom, 4) if denom else None
                prec.append([a, b, n, round(pab, 4), round(pba, 4),
                             round(tie, 4), na, nb,
                             round(med, 1) if med == med else None])
        pd.DataFrame(prec, columns=["a", "b", "n_both", "p_a_first",
                                    "p_b_first", "tie24",
                                    "p_a_first_notie", "p_b_first_notie",
                                    "median_lead_h"]).to_csv(
            f"{OUT}of_precedence_{tag}.csv", index=False)

        # common sequences (>=2 failures, primary cohort)
        seqs = {}
        for sid, row in onp.iterrows():
            r = row.dropna().sort_values()
            if len(r) < 2:
                continue
            groups, cur, t0 = [], [SHORT[r.index[0]]], r.iloc[0]
            for o, t in zip(r.index[1:], r.values[1:]):
                if t - t0 <= 24:
                    cur.append(SHORT[o])
                else:
                    groups.append("=".join(sorted(cur)))
                    cur, t0 = [SHORT[o]], t
            groups.append("=".join(sorted(cur)))
            s = "<".join(groups)
            seqs[s] = seqs.get(s, 0) + 1
        top = sorted(seqs.items(), key=lambda x: -x[1])[:20]
        print(f"sequences (n={sum(seqs.values())} stays, "
              f"{len(seqs)} distinct), top 20:", flush=True)
        for s, c in top:
            print(f"  {c}: {s}", flush=True)
        pd.Series(seqs).sort_values(ascending=False).to_csv(
            f"{OUT}of_sequences_{tag}.csv", header=["n"])

        # median hours from k-th failure to death (primary)
        dh_map = d.set_index("stay_id")["death_h"].to_dict()
        for k in [1, 2, 3]:
            vals = []
            for sid, row in onp.iterrows():
                r = row.dropna().sort_values()
                if len(r) >= k:
                    vals.append(dh_map[sid] - r.iloc[k - 1])
            if vals:
                print(f"  failure #{k} -> death: median "
                      f"{float(np.median(vals)):.1f}h "
                      f"IQR [{float(np.percentile(vals, 25)):.0f}-"
                      f"{float(np.percentile(vals, 75)):.0f}] n={len(vals)}",
                      flush=True)

    # ---- death-aligned trajectories (6h bins, -168..0) ----
    so = sofa.merge(d[["stay_id", "death_h", "sepsis", "anchor_age",
                       "early_dnr", "fullcode"]], on="stay_id")
    so = so[so["hr"] <= so["death_h"]]
    so["hbd"] = so["death_h"] - so["hr"]
    so = so[so["hbd"] <= 168]
    so["bin"] = (so["hbd"] // 6 * 6).astype(int)
    tra = so.groupby("bin")[ORGANS + ["sofa"]].mean().round(3)
    tra["n"] = so.groupby("bin")["stay_id"].nunique()
    tra.to_csv(f"{OUT}of_traj_dec.csv")
    for grp, mask in [("sepsis", so["sepsis"] == 1),
                      ("nonsepsis", so["sepsis"] == 0),
                      ("age65p", so["anchor_age"] >= 65),
                      ("ageu65", so["anchor_age"] < 65),
                      ("fullcode", so["fullcode"] == 1)]:
        g = so[mask].groupby("bin")[ORGANS + ["sofa"]].mean().round(3)
        g["n"] = so[mask].groupby("bin")["stay_id"].nunique()
        g.to_csv(f"{OUT}of_traj_{grp}.csv")
    sv = surv_sofa.copy()
    sv["hbd"] = sv["los"] - sv["hr"]
    sv = sv[(sv["hbd"] >= 0) & (sv["hbd"] <= 168)]
    sv["bin"] = (sv["hbd"] // 6 * 6).astype(int)
    svt = sv.groupby("bin")[ORGANS + ["sofa"]].mean().round(3)
    svt["n"] = sv.groupby("bin")["stay_id"].nunique()
    svt.to_csv(f"{OUT}of_traj_surv.csv")
    print("trajectories written; decedent total SOFA at -168h vs -6h:",
          flush=True)
    print(f"  {tra['sofa'].iloc[-1]:.2f} -> {tra['sofa'].iloc[0]:.2f}",
          flush=True)

    # ---- support validation lags ----
    so_all = sofa.merge(d[["stay_id", "vent_t_h", "vaso_t_h", "rrt_t_h"]],
                        on="stay_id")
    for o, col in [("cardiovascular", "vaso_t_h"),
                   ("renal", "rrt_t_h"), ("respiration", "vent_t_h")]:
        f = so_all[so_all[o] >= 3].groupby("stay_id")["hr"].min()
        m = pd.DataFrame({"onset": f}).merge(
            d.set_index("stay_id")[col], left_index=True, right_index=True)
        m = m[m[col].notna()]
        lag = (m[col] - m["onset"]).dropna()
        print(f"  {o}: support-after-onset median "
              f"{float(lag.median()):.1f}h "
              f"IQR [{float(lag.quantile(0.25)):.0f}-"
              f"{float(lag.quantile(0.75)):.0f}] n={len(lag)}", flush=True)

    # ---- Vincent 2011 replication: dSOFA over last 4 days ----
    vv = []
    dh_map = d.set_index("stay_id")["death_h"].to_dict()
    for sid, grp in sofa.groupby("stay_id"):
        dh = dh_map[sid]
        if dh < 96:
            continue
        g = grp[grp["hr"] <= dh].sort_values("hr")
        g96 = g[g["hr"] <= dh - 96]
        g24 = g[g["hr"] <= dh - 24]
        if len(g96) == 0 or len(g24) == 0:
            continue
        r96, r24 = g96.iloc[-1], g24.iloc[-1]
        # require fresh rows near both cutoffs (no stale discharge score
        # reused at -96h and -24h)
        if r24["hr"] < dh - 48 or r96["hr"] < dh - 120:
            continue
        any_inc = int(any(r24[o] > r96[o] for o in ORGANS))
        vv.append((sid, r96["sofa"], r24["sofa"], any_inc))
    vv = pd.DataFrame(vv, columns=["stay_id", "s96", "s24", "any_inc"])
    if len(vv):
        delta = vv["s24"] - vv["s96"]
        print(f"Vincent replication (n={len(vv)}, los>=4d decedents): "
              f"mean dSOFA(-96h->-24h)={delta.mean():.2f}, "
              f"increased={(delta > 0).mean():.3f}, "
              f"stable={(delta == 0).mean():.3f}, "
              f"decreased={(delta < 0).mean():.3f}", flush=True)
        print(f"  mean SOFA -96h={vv['s96'].mean():.2f}, "
              f"-24h={vv['s24'].mean():.2f}, "
              f"any-organ-increase={vv['any_inc'].mean():.3f} "
              f"(INDEPTH: 0.80)", flush=True)

    # ---- lethality ranking: P(hospital death | organ ever >=3) ----
    con = duckdb.connect(DB, read_only=True)
    leth = con.execute("""
SELECT MAX(CASE WHEN s.respiration_24hours >= 3 THEN 1 ELSE 0 END) AS f_resp,
  MAX(CASE WHEN s.coagulation_24hours >= 3 THEN 1 ELSE 0 END) AS f_coag,
  MAX(CASE WHEN s.liver_24hours >= 3 THEN 1 ELSE 0 END) AS f_liver,
  MAX(CASE WHEN s.cardiovascular_24hours >= 3 THEN 1 ELSE 0 END) AS f_cv,
  MAX(CASE WHEN s.cns_24hours >= 3 THEN 1 ELSE 0 END) AS f_cns,
  MAX(CASE WHEN s.renal_24hours >= 3 THEN 1 ELSE 0 END) AS f_renal,
  MAX(a.hospital_expire_flag) AS died
FROM mimiciv_derived.sofa s
JOIN mimiciv_icu.icustays i USING (stay_id)
JOIN mimiciv_hosp.admissions a USING (hadm_id)
GROUP BY s.stay_id""").fetchdf()
    con.close()
    print("lethality P(death | organ ever SOFA>=3):", flush=True)
    for c, o in [("f_resp", "respiration"), ("f_coag", "coagulation"),
                 ("f_liver", "liver"), ("f_cv", "cardiovascular"),
                 ("f_cns", "cns"), ("f_renal", "renal")]:
        sub = leth[leth[c] == 1]
        print(f"  {o}: {sub['died'].mean():.4f} (n={len(sub)})",
              flush=True)
    print(f"  baseline ICU-stay death rate: {leth['died'].mean():.4f}",
          flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
