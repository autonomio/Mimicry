-- Step 0/1: cohort definitions + monitoring-withdrawal gap analysis.
-- gap_h = hours between a stay's last chart event and its anchor (death/discharge).
-- Produces 00_withdrawal_gaps.csv (run part 1) and 00_withdrawal_2x2.csv (part 2).
-- Aggregates only.
WITH cases AS (
  SELECT s.stay_id, s.outtime AS anchor FROM mimiciv_icu.icustays s
  JOIN mimiciv_hosp.patients p USING (subject_id)
  WHERE p.dod BETWEEN s.intime AND s.outtime
),
controls AS (
  SELECT s.stay_id, s.outtime AS anchor FROM mimiciv_icu.icustays s
  JOIN mimiciv_hosp.admissions a USING (hadm_id)
  WHERE a.hospital_expire_flag = 0
),
cohort AS (
  SELECT stay_id, anchor, 'died' AS cohort FROM cases
  UNION ALL
  SELECT stay_id, anchor, 'survived' AS cohort FROM controls
),
lastchart AS (
  SELECT c.cohort, c.stay_id,
    date_diff('second', MAX(e.charttime), ANY_VALUE(c.anchor)) / 3600.0 AS gap_h
  FROM cohort c JOIN mimiciv_icu.chartevents e USING (stay_id)
  GROUP BY 1, 2
)
-- Part 1: gap distribution by cohort
SELECT cohort, COUNT(*) n,
  ROUND(QUANTILE_CONT(gap_h, 0.1), 2) p10,
  ROUND(QUANTILE_CONT(gap_h, 0.25), 2) p25,
  ROUND(MEDIAN(gap_h), 2) p50,
  ROUND(QUANTILE_CONT(gap_h, 0.75), 2) p75,
  ROUND(QUANTILE_CONT(gap_h, 0.9), 2) p90,
  ROUND(100.0 * SUM(CASE WHEN gap_h <= 1 THEN 1 ELSE 0 END) / COUNT(*), 1) pct_within_1h,
  ROUND(100.0 * SUM(CASE WHEN gap_h <= 6 THEN 1 ELSE 0 END) / COUNT(*), 1) pct_within_6h,
  ROUND(100.0 * SUM(CASE WHEN gap_h > 24 THEN 1 ELSE 0 END) / COUNT(*), 1) pct_over_24h
FROM lastchart GROUP BY 1;
-- Part 2: 2x2 table at the 2h threshold (run separately against the same CTEs)
-- SELECT cohort, COUNT(*) n,
--   SUM(CASE WHEN gap_h > 2 THEN 1 ELSE 0 END) AS gap_over_2h,
--   ROUND(100.0 * SUM(CASE WHEN gap_h > 2 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_over_2h
-- FROM lastchart GROUP BY 1;
