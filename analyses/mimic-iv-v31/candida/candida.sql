-- Candida: fungus vs host (MIMIC-IV v3.1, s0, read-only).
-- First ICU stays: candidemia (candida in blood culture during the stay)
-- crossed with micafungin prescribed during the hospitalization.
-- Outcomes: died in ICU, died in hospital. Aggregates only.
WITH fst AS (
  SELECT s.stay_id, s.hadm_id, s.subject_id, s.intime, s.outtime, s.los,
         p.anchor_age,
         CASE WHEN p.dod BETWEEN s.intime AND s.outtime THEN 1 ELSE 0 END AS died_icu,
         a.hospital_expire_flag AS died_hosp
  FROM mimiciv_icu.icustays s
  JOIN mimiciv_hosp.patients p USING (subject_id)
  JOIN mimiciv_hosp.admissions a USING (hadm_id)
  QUALIFY row_number() OVER (PARTITION BY s.hadm_id ORDER BY s.intime) = 1
),
cand AS (
  SELECT DISTINCT f.stay_id
  FROM fst f
  JOIN mimiciv_hosp.microbiologyevents m
    ON m.subject_id = f.subject_id
   AND m.charttime >= f.intime AND m.charttime < f.outtime
   AND m.spec_type_desc IN ('BLOOD CULTURE', 'BLOOD CULTURE ( MYCO/F LYTIC BOTTLE)')
   AND UPPER(m.org_name) LIKE '%CANDIDA%'
),
mica AS (
  SELECT DISTINCT f.stay_id
  FROM fst f
  JOIN mimiciv_hosp.prescriptions r ON r.hadm_id = f.hadm_id
  WHERE UPPER(r.drug) LIKE '%MICAFUNGIN%'
)
SELECT 'Q1_2x2' AS q,
  CASE WHEN c.stay_id IS NOT NULL THEN 1 ELSE 0 END AS candidemia,
  CASE WHEN m.stay_id IS NOT NULL THEN 1 ELSE 0 END AS micafungin,
  COUNT(*) AS n,
  ROUND(100.0*AVG(f.died_icu), 1) AS pct_died_icu,
  ROUND(100.0*AVG(f.died_hosp), 1) AS pct_died_hosp,
  ROUND(MEDIAN(f.anchor_age), 1) AS med_age,
  ROUND(MEDIAN(f.los), 2) AS med_los_days
FROM fst f
LEFT JOIN cand c USING (stay_id)
LEFT JOIN mica m USING (stay_id)
GROUP BY 1, 2, 3 ORDER BY 2, 3;
