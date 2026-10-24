-- Step 3a: lactate (50813) + creatinine (50912) in 6h bins over the last 24h.
-- Labs are sparse; bins keep n reportable. Aggregates only.
WITH cases AS (
  SELECT s.stay_id, s.subject_id, s.outtime AS anchor, s.first_careunit
  FROM mimiciv_icu.icustays s
  JOIN mimiciv_hosp.patients p USING (subject_id)
  WHERE p.dod BETWEEN s.intime AND s.outtime
),
case_n AS (
  SELECT first_careunit, COUNT(*) AS n FROM cases GROUP BY 1
),
controls AS (
  SELECT stay_id, subject_id, outtime AS anchor FROM (
    SELECT s.stay_id, s.subject_id, s.outtime, s.first_careunit,
           row_number() OVER (PARTITION BY s.first_careunit ORDER BY hash(s.stay_id)) AS rn
    FROM mimiciv_icu.icustays s
    JOIN mimiciv_hosp.admissions a USING (hadm_id)
    WHERE a.hospital_expire_flag = 0
  ) t JOIN case_n USING (first_careunit)
  WHERE rn <= case_n.n
),
cohort AS (
  SELECT stay_id, subject_id, anchor, 'died' AS cohort FROM cases
  UNION ALL
  SELECT stay_id, subject_id, anchor, 'survived' AS cohort FROM controls
),
labs AS (
  SELECT c.cohort, c.stay_id,
         CAST(date_diff('hour', l.charttime, c.anchor) AS INTEGER) // 6 AS b,
         l.itemid, l.valuenum
  FROM cohort c
  JOIN mimiciv_hosp.labevents l
    ON l.subject_id = c.subject_id
   AND l.charttime >= c.anchor - INTERVAL 24 HOUR
   AND l.charttime < c.anchor
  WHERE l.valuenum IS NOT NULL AND l.itemid IN (50813, 50912)
),
per_stay_bin AS (
  SELECT cohort, stay_id, b,
    MEDIAN(CASE WHEN itemid = 50813 AND valuenum BETWEEN 0 AND 30 THEN valuenum END) AS lactate,
    MEDIAN(CASE WHEN itemid = 50912 AND valuenum BETWEEN 0 AND 20 THEN valuenum END) AS creat
  FROM labs GROUP BY 1, 2, 3
),
long AS (
  SELECT cohort, stay_id, b, vital, v FROM per_stay_bin
  UNPIVOT (v FOR vital IN (lactate, creat))
  WHERE v IS NOT NULL
)
SELECT cohort, b AS bin6, vital,
  ROUND(MEDIAN(v), 3) AS median,
  ROUND(QUANTILE_CONT(v, 0.25), 3) AS p25,
  ROUND(QUANTILE_CONT(v, 0.75), 3) AS p75,
  COUNT(DISTINCT stay_id) AS n_stays
FROM long GROUP BY 1, 2, 3 ORDER BY 1, 3, 2;
