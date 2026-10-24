-- Pre-admission prescriptions (MIMIC-IV v3.1, s0, read-only).
-- Per admission: distinct drug GSNs prescribed during PRIOR admissions.
-- Aggregates only. Drug strings used only as dictionary labels.
CREATE TEMP TABLE priorx AS
SELECT a.hadm_id, a.hospital_expire_flag AS died,
       CASE WHEN s.hadm_id IS NOT NULL THEN 1 ELSE 0 END AS icu, TRIM(r.gsn) AS gsn
FROM mimiciv_hosp.admissions a
LEFT JOIN (SELECT DISTINCT hadm_id FROM mimiciv_icu.icustays) s USING (hadm_id)
JOIN mimiciv_hosp.admissions p
  ON p.subject_id = a.subject_id AND p.admittime < a.admittime
JOIN mimiciv_hosp.prescriptions r ON r.hadm_id = p.hadm_id
WHERE r.gsn IS NOT NULL;
SELECT 'Q1_cov' AS q, COUNT(DISTINCT hadm_id) AS adm_with_priorx,
       (SELECT COUNT(*) FROM mimiciv_hosp.admissions) AS adm_total FROM priorx;
SELECT 'Q2_peradm' AS q, MEDIAN(cnt) AS med_drugs,
       QUANTILE_CONT(cnt, 0.9) AS p90_drugs
FROM (SELECT hadm_id, COUNT(DISTINCT gsn) AS cnt FROM priorx GROUP BY 1);
SELECT 'Q3_gsn' AS q, gsn, COUNT(DISTINCT hadm_id) AS nadm
FROM priorx GROUP BY 1, 2 ORDER BY nadm DESC, gsn;
WITH label_ct AS (
  SELECT TRIM(gsn) AS gsn, TRIM(LOWER(drug)) AS d, COUNT(*) AS c
  FROM mimiciv_hosp.prescriptions
  WHERE TRIM(gsn) IN (SELECT DISTINCT gsn FROM priorx)
  GROUP BY 1, 2
)
SELECT 'Q3b_labels' AS q, gsn, d AS label FROM (
  SELECT gsn, d, row_number() OVER (PARTITION BY gsn ORDER BY c DESC, d) AS rn
  FROM label_ct) WHERE rn = 1 ORDER BY 2;
SELECT 'Q4_gap' AS q, gsn, died, COUNT(DISTINCT hadm_id) AS n_exp
FROM priorx GROUP BY 1, 2, 3 ORDER BY 2, 3;
SELECT 'Q5_gapicu' AS q, gsn, icu, COUNT(DISTINCT hadm_id) AS n_exp
FROM priorx GROUP BY 1, 2, 3 ORDER BY 2, 3;
SELECT 'Q6_denom' AS q, died, icu, COUNT(*) AS n
FROM (SELECT DISTINCT hadm_id, died, icu FROM priorx) GROUP BY 1, 2, 3 ORDER BY 2, 3;
