-- Prior-year labs, pure-history cut (MIMIC-IV v3.1, s0, read-only).
-- Same as pylab_sweep.sql but last value must be OLDER than 24h before
-- admission, excluding ED presentation workup. Aggregates only.
CREATE TEMP TABLE py AS
SELECT a.hadm_id, a.admittime, a.hospital_expire_flag AS died,
       CASE WHEN s.hadm_id IS NOT NULL THEN 1 ELSE 0 END AS icu,
       l.itemid, l.valuenum, l.charttime
FROM mimiciv_hosp.admissions a
LEFT JOIN (SELECT DISTINCT hadm_id FROM mimiciv_icu.icustays) s USING (hadm_id)
JOIN mimiciv_hosp.labevents l
  ON l.subject_id = a.subject_id
 AND l.charttime < a.admittime - INTERVAL 24 HOUR
 AND l.charttime >= a.admittime - INTERVAL 365 DAY;
SELECT 'Q1_cov' AS q, COUNT(DISTINCT hadm_id) AS adm_with_histlab,
       (SELECT COUNT(*) FROM mimiciv_hosp.admissions) AS adm_total FROM py;
CREATE TEMP TABLE lastv AS
SELECT hadm_id, died, icu, itemid, arg_max(valuenum, charttime) AS last_val
FROM py WHERE valuenum IS NOT NULL GROUP BY 1, 2, 3, 4;
SELECT 'Q5_death' AS q, itemid, died, COUNT(*) AS n_adm,
       ROUND(MEDIAN(last_val), 3) AS med
FROM lastv GROUP BY 1, 2, 3 ORDER BY 2, 3;
SELECT 'Q6_icu' AS q, itemid, icu, COUNT(*) AS n_adm,
       ROUND(MEDIAN(last_val), 3) AS med
FROM lastv GROUP BY 1, 2, 3 ORDER BY 2, 3;
