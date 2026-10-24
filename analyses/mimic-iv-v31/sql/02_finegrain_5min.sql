-- Step 2: 5-minute vital medians over the last 6h, still-monitored subset
-- (monitoring gap <= 1h). MAP/SpO2/HR. Aggregates only.
WITH cases AS (
  SELECT s.stay_id, s.outtime AS anchor, s.first_careunit
  FROM mimiciv_icu.icustays s
  JOIN mimiciv_hosp.patients p USING (subject_id)
  WHERE p.dod BETWEEN s.intime AND s.outtime
),
survivors AS (
  SELECT s.stay_id, s.outtime AS anchor, s.first_careunit
  FROM mimiciv_icu.icustays s
  JOIN mimiciv_hosp.admissions a USING (hadm_id)
  WHERE a.hospital_expire_flag = 0
),
allstays AS (
  SELECT stay_id, anchor, first_careunit, 'died' AS cohort FROM cases
  UNION ALL
  SELECT stay_id, anchor, first_careunit, 'survived' AS cohort FROM survivors
),
gap AS (
  SELECT c.cohort, c.stay_id, c.anchor, c.first_careunit,
    date_diff('second', MAX(e.charttime), ANY_VALUE(c.anchor)) / 3600.0 AS gap_h
  FROM allstays c JOIN mimiciv_icu.chartevents e USING (stay_id)
  GROUP BY 1, 2, 3, 4
),
cases1h AS (
  SELECT stay_id, anchor, first_careunit FROM gap
  WHERE cohort = 'died' AND gap_h <= 1
),
case_n AS (
  SELECT first_careunit, COUNT(*) AS n FROM cases1h GROUP BY 1
),
controls1h AS (
  SELECT stay_id, anchor FROM (
    SELECT g.stay_id, g.anchor, g.first_careunit,
           row_number() OVER (PARTITION BY g.first_careunit ORDER BY hash(g.stay_id)) AS rn
    FROM gap g WHERE g.cohort = 'survived' AND g.gap_h <= 1
  ) t JOIN case_n USING (first_careunit)
  WHERE rn <= case_n.n
),
cohort AS (
  SELECT stay_id, anchor, 'died' AS cohort FROM cases1h
  UNION ALL
  SELECT stay_id, anchor, 'survived' AS cohort FROM controls1h
),
events AS (
  SELECT c.cohort, c.stay_id,
         CAST(date_diff('minute', e.charttime, c.anchor) AS INTEGER) // 5 AS b,
         e.itemid, e.valuenum
  FROM cohort c
  JOIN mimiciv_icu.chartevents e USING (stay_id)
  WHERE e.charttime >= c.anchor - INTERVAL 6 HOUR
    AND e.charttime < c.anchor
    AND e.valuenum IS NOT NULL
    AND e.itemid IN (220045, 220277, 220181, 220052)
),
per_stay_bin AS (
  SELECT cohort, stay_id, b,
    MEDIAN(CASE WHEN itemid = 220045 AND valuenum BETWEEN 10 AND 300 THEN valuenum END) AS hr,
    MEDIAN(CASE WHEN itemid = 220277 AND valuenum BETWEEN 50 AND 100 THEN valuenum END) AS spo2,
    MEDIAN(CASE WHEN itemid = 220181 AND valuenum BETWEEN 10 AND 200 THEN valuenum END) AS nbpm,
    MEDIAN(CASE WHEN itemid = 220052 AND valuenum BETWEEN 10 AND 200 THEN valuenum END) AS abpm
  FROM events GROUP BY 1, 2, 3
),
binned AS (
  SELECT cohort, stay_id, b, hr, spo2, COALESCE(nbpm, abpm) AS map
  FROM per_stay_bin
),
long AS (
  SELECT cohort, stay_id, b, vital, v FROM binned
  UNPIVOT (v FOR vital IN (hr, spo2, map))
  WHERE v IS NOT NULL AND b <= 71
)
SELECT cohort, b AS bin5, vital,
  ROUND(MEDIAN(v), 2) AS median,
  ROUND(QUANTILE_CONT(v, 0.25), 2) AS p25,
  ROUND(QUANTILE_CONT(v, 0.75), 2) AS p75,
  COUNT(DISTINCT stay_id) AS n_stays
FROM long GROUP BY 1, 2, 3 ORDER BY 1, 3, 2;
