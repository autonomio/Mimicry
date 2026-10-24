-- Step 1 sensitivity: trajectories for (a) all died, (b) died with monitoring
-- within 2h of death, (c) hash-matched survivors. Deterministic controls via
-- hash(stay_id) so every committed output shares one control sample.
WITH cases AS (
  SELECT s.stay_id, s.outtime AS anchor, s.first_careunit
  FROM mimiciv_icu.icustays s
  JOIN mimiciv_hosp.patients p USING (subject_id)
  WHERE p.dod BETWEEN s.intime AND s.outtime
),
case_n AS (
  SELECT first_careunit, COUNT(*) AS n FROM cases GROUP BY 1
),
controls AS (
  SELECT stay_id, outtime AS anchor FROM (
    SELECT s.stay_id, s.outtime, s.first_careunit,
           row_number() OVER (PARTITION BY s.first_careunit ORDER BY hash(s.stay_id)) AS rn
    FROM mimiciv_icu.icustays s
    JOIN mimiciv_hosp.admissions a USING (hadm_id)
    WHERE a.hospital_expire_flag = 0
  ) t JOIN case_n USING (first_careunit)
  WHERE rn <= case_n.n
),
gap AS (
  SELECT c.stay_id,
    date_diff('second', MAX(e.charttime), ANY_VALUE(c.anchor)) / 3600.0 AS gap_h
  FROM cases c JOIN mimiciv_icu.chartevents e USING (stay_id)
  GROUP BY 1
),
cohort AS (
  SELECT stay_id, anchor, 'died_all' AS cohort FROM cases
  UNION ALL
  SELECT c.stay_id, c.anchor, 'died_gap2h' AS cohort FROM cases c JOIN gap g USING (stay_id) WHERE g.gap_h <= 2
  UNION ALL
  SELECT stay_id, anchor, 'survived' AS cohort FROM controls
),
events AS (
  SELECT c.cohort, c.stay_id,
         CAST(date_diff('hour', e.charttime, c.anchor) AS INTEGER) AS h,
         e.itemid, e.valuenum
  FROM cohort c
  JOIN mimiciv_icu.chartevents e USING (stay_id)
  WHERE e.charttime >= c.anchor - INTERVAL 24 HOUR
    AND e.charttime < c.anchor
    AND e.valuenum IS NOT NULL
    AND e.itemid IN (220045, 220210, 220277, 220181, 220052, 223761)
),
per_stay_hour AS (
  SELECT cohort, stay_id, h,
    MEDIAN(CASE WHEN itemid = 220045 AND valuenum BETWEEN 10 AND 300 THEN valuenum END) AS hr,
    MEDIAN(CASE WHEN itemid = 220210 AND valuenum BETWEEN 0 AND 80 THEN valuenum END) AS rr,
    MEDIAN(CASE WHEN itemid = 220277 AND valuenum BETWEEN 50 AND 100 THEN valuenum END) AS spo2,
    MEDIAN(CASE WHEN itemid = 220181 AND valuenum BETWEEN 10 AND 200 THEN valuenum END) AS nbpm,
    MEDIAN(CASE WHEN itemid = 220052 AND valuenum BETWEEN 10 AND 200 THEN valuenum END) AS abpm,
    MEDIAN(CASE WHEN itemid = 223761 THEN (valuenum - 32) * 5 / 9 END) AS tempc
  FROM events GROUP BY 1, 2, 3
),
hourly AS (
  SELECT cohort, stay_id, h, hr, rr, spo2,
    COALESCE(nbpm, abpm) AS map,
    CASE WHEN tempc BETWEEN 30 AND 43 THEN tempc END AS tempc
  FROM per_stay_hour
),
long AS (
  SELECT cohort, stay_id, h, vital, v FROM hourly
  UNPIVOT (v FOR vital IN (hr, rr, spo2, map, tempc))
  WHERE v IS NOT NULL AND h <= 23
)
SELECT cohort, h AS hours_before, vital,
  ROUND(MEDIAN(v), 2) AS median,
  ROUND(QUANTILE_CONT(v, 0.25), 2) AS p25,
  ROUND(QUANTILE_CONT(v, 0.75), 2) AS p75,
  COUNT(DISTINCT stay_id) AS n_stays
FROM long GROUP BY 1, 2, 3 ORDER BY 1, 3, 2;
