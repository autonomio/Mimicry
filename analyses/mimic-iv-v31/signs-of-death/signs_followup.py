"""Signs-of-death follow-ups (s0 only): (a) prediction without hr_n
(monitoring-intensity leakage ablation); (b) death-hour split by
DNR-before-death (is the afternoon peak care-driven?).
"""
import math
import duckdb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

DB = "/srv/mimic-iv/db/mimic4-v31.db"
ITEMS = "220045,220052,220181,220210,224690,220277,223762,223761"
MAP = {220045: "hr", 220052: "map", 220181: "map", 220210: "rr",
       224690: "rr", 220277: "spo2", 223762: "temp", 223761: "temp"}


def main():
    con = duckdb.connect(DB, read_only=True)
    dec = con.execute("""
SELECT i.stay_id, i.intime, a.deathtime, p.anchor_age,
  CASE WHEN s.stay_id IS NOT NULL THEN 1 ELSE 0 END AS sepsis
FROM mimiciv_icu.icustays i
JOIN mimiciv_hosp.admissions a ON a.hadm_id = i.hadm_id
JOIN mimiciv_hosp.patients p ON p.subject_id = i.subject_id
LEFT JOIN (SELECT DISTINCT stay_id FROM mimiciv_derived.sepsis3) s
  USING (stay_id)
WHERE a.hospital_expire_flag = 1 AND a.deathtime IS NOT NULL
  AND a.deathtime >= i.intime""").fetchdf()
    dec["death_h"] = (pd.to_datetime(dec["deathtime"]) -
                      pd.to_datetime(dec["intime"])).dt.total_seconds() / 3600
    ids = ",".join(map(str, dec["stay_id"].tolist()))
    code = con.execute(f"""
SELECT stay_id, MIN(CASE WHEN dnr = 1 OR cmo = 1 THEN charttime END) AS dnr_t
FROM mimiciv_derived.code_status WHERE stay_id IN ({ids}) GROUP BY 1""").fetchdf()
    code["dnr_t"] = pd.to_datetime(code["dnr_t"])
    dd = dec.set_index("stay_id")
    code["wd"] = code.apply(
        lambda r: r["dnr_t"] < dd.loc[r["stay_id"], "deathtime"]
        if pd.notna(r["dnr_t"]) else False, axis=1)
    wdmap = code.set_index("stay_id")["wd"].to_dict()
    dh = con.execute("""
SELECT EXTRACT(HOUR FROM a.deathtime) AS h, a.hadm_id
FROM mimiciv_hosp.admissions a
WHERE a.hospital_expire_flag = 1 AND a.deathtime IS NOT NULL""").fetchdf()
    print("(b) death-hour by withdrawal status: afternoon share (12-18h)",
          flush=True)
    # map hadm->wd via dec stays
    hmap = dec.set_index("hadm_id")["stay_id"].to_dict() \
        if "hadm_id" in dec else {}
    # dec lacks hadm_id; rebuild quickly
    hh = con.execute(f"""
SELECT i.hadm_id, i.stay_id FROM mimiciv_icu.icustays i
WHERE i.stay_id IN ({ids})""").fetchdf()
    h2s = hh.set_index("hadm_id")["stay_id"].to_dict()
    dh["wd"] = dh["hadm_id"].map(
        lambda x: wdmap.get(h2s.get(x), None))
    for w, g in dh.groupby("wd"):
        aft = float(((g["h"] >= 12) & (g["h"] < 18)).mean())
        print(f"  wd={w}: n={len(g)} afternoon_share={aft:.3f}",
              flush=True)
    g = dh[dh["wd"].isin([True, False])]
    g.groupby("wd")["h"].value_counts().unstack(0).fillna(0).to_csv(
        "/tmp/sd_death_hour_wd.csv")
    con.close()
    print("wrote sd_death_hour_wd.csv", flush=True)


if __name__ == "__main__":
    main()
