-- Prior-year labs sweep (MIMIC-IV v3.1, s0, read-only).
-- For every hospital admission: labs drawn in [admittime-365d, admittime).
-- Aggregates only. Labels from d_labitems are dictionary interpretation, not features.
CREATE TEMP TABLE py AS
SELECT a.hadm_id, a.hospital_expire_flag AS died,
       CASE WHEN s.hadm_id IS NOT NULL THEN 1 ELSE 0 END AS icu,
       l.itemid, l.valuenum, l.flag, l.charttime
FROM mimiciv_hosp.admissions a
LEFT JOIN (SELECT DISTINCT hadm_id FROM mimiciv_icu.icustays) s USING (hadm_id)
JOIN mimiciv_hosp.labevents l
  ON l.subject_id = a.subject_id
 AND l.charttime < a.admittime AND l.charttime >= a.admittime - INTERVAL 365 DAY;
SELECT 'Q1_coverage' AS q, COUNT(DISTINCT hadm_id) AS adm_with_pylab,
       (SELECT COUNT(*) FROM mimiciv_hosp.admissions) AS adm_total FROM py;
SELECT 'Q2_peradm' AS q,
       MEDIAN(cnt) AS med_tests, QUANTILE_CONT(cnt, 0.9) AS p90_tests,
       MEDIAN(ntests) AS med_distinct_tests
FROM (SELECT hadm_id, COUNT(*) AS cnt, COUNT(DISTINCT itemid) AS ntests
      FROM py GROUP BY 1);
SELECT 'Q3_top' AS q, p.itemid, d.label, d.fluid, d.category,
       COUNT(DISTINCT p.hadm_id) AS nadm, COUNT(*) AS nrows
FROM py p JOIN mimiciv_hosp.d_labitems d USING (itemid)
GROUP BY 1, 2, 3, 4, 5 ORDER BY nadm DESC LIMIT 40;
SELECT 'Q4_flags' AS q, flag, COUNT(*) AS n FROM py GROUP BY 1, 2 ORDER BY n DESC LIMIT 10;
CREATE TEMP TABLE lastv AS
SELECT hadm_id, died, icu, itemid, arg_max(valuenum, charttime) AS last_val,
       arg_max(flag, charttime) AS last_flag, COUNT(*) AS n_meas
FROM py WHERE valuenum IS NOT NULL GROUP BY 1, 2, 3, 4;
SELECT 'Q5_by_death' AS q, itemid, died, COUNT(*) AS n_adm,
       ROUND(MEDIAN(last_val), 3) AS med,
       ROUND(QUANTILE_CONT(last_val, 0.25), 3) AS p25,
       ROUND(QUANTILE_CONT(last_val, 0.75), 3) AS p75
FROM lastv GROUP BY 1, 2, 3 ORDER BY 2, 3;
SELECT 'Q6_by_icu' AS q, itemid, icu, COUNT(*) AS n_adm,
       ROUND(MEDIAN(last_val), 3) AS med,
       ROUND(QUANTILE_CONT(last_val, 0.25), 3) AS p25,
       ROUND(QUANTILE_CONT(last_val, 0.75), 3) AS p75
FROM lastv GROUP BY 1, 2, 3 ORDER BY 2, 3;
