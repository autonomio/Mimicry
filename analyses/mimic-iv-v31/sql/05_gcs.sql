-- Step 3c: hourly median GCS total (eye 220739 + verbal 223900 + motor 223901)
-- over the last 24h. Complete triplets only. Aggregates only.
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
cohort AS (
  SELECT stay_id, anchor, 'died' AS cohort FROM cases
  UNION ALL
  SELECT stay_id, anchor, 'survived' AS cohort FROM controls
),
gcs_events AS (
  SELECT c.cohort, c.stay_id,
         CAST(date_diff('hour', e.charttime, c.anchor) AS INTEGER) AS h,
         MAX(CASE WHEN e.itemid = 220739 AND e.valuenum BETWEEN 1 AND 4 THEN e.valuenum END) AS eye,
         MAX(CASE WHEN e.itemid = 223900 AND e.valuenum BETWEEN 1 AND 5 THEN e.valuenum END) AS verbal,
         MAX(CASE WHEN e.itemid = 223901 AND e.valuenum BETWEEN 1 AND 6 THEN e.valuenum END) AS motor
  FROM cohort c
  JOIN mimiciv_icu.chartevents e USING (stay_id)
  WHERE e.charttime >= c.anchor - INTERVAL 24 HOUR
    AND e.charttime < c.anchor
    AND e.itemid IN (220739, 223900, 223901)
  GROUP BY 1, 2, 3, e.charttime
),
totals AS (
  SELECT cohort, stay_id, h, (eye + verbal + motor) AS gcs
  FROM gcs_events WHERE eye IS NOT NULL AND verbal IS NOT NULL AND motor IS NOT NULL
)
SELECT cohort, h AS hours_before,
  ROUND(MEDIAN(gcs), 1) AS median_gcs,
  ROUND(QUANTILE_CONT(gcs, 0.25), 1) AS p25,
  ROUND(QUANTILE_CONT(gcs, 0.75), 1) AS p75,
  COUNT(DISTINCT stay_id) AS n_stays
FROM totals WHERE h <= 23 GROUP BY 1, 2 ORDER BY 1, 2;
