-- Step 3b: pressor exposure per hour over the last 24h.
-- A stay is covered in hour h if any pressor infusion overlaps that hour.
-- Itemids: norepinephrine 221906, epi 221289/229617, vaso 222315,
-- phenyl 221749/229630/229631/229632, dopamine 221662, dobutamine 221653.
-- Aggregates only.
WITH cases AS (
  SELECT s.stay_id, s.intime, a.deathtime AS anchor, s.first_careunit
  FROM mimiciv_icu.icustays s
  JOIN mimiciv_hosp.admissions a USING (hadm_id)
  WHERE a.deathtime BETWEEN s.intime AND s.outtime
),
case_n AS (
  SELECT first_careunit, COUNT(*) AS n FROM cases GROUP BY 1
),
controls AS (
  SELECT stay_id, intime, outtime AS anchor FROM (
    SELECT s.stay_id, s.intime, s.outtime, s.first_careunit,
           row_number() OVER (PARTITION BY s.first_careunit ORDER BY hash(s.stay_id)) AS rn
    FROM mimiciv_icu.icustays s
    JOIN mimiciv_hosp.admissions a USING (hadm_id)
    WHERE a.hospital_expire_flag = 0
  ) t JOIN case_n USING (first_careunit)
  WHERE rn <= case_n.n
),
cohort AS (
  SELECT stay_id, intime, anchor, 'died' AS cohort FROM cases
  UNION ALL
  SELECT stay_id, intime, anchor, 'survived' AS cohort FROM controls
),
inf AS (
  SELECT DISTINCT c.cohort, c.stay_id, c.anchor, i.starttime,
    COALESCE(i.endtime, i.starttime + INTERVAL 1 HOUR) AS endtime
  FROM cohort c
  JOIN mimiciv_icu.inputevents i USING (stay_id)
  WHERE i.itemid IN (221906, 221289, 229617, 222315, 221749, 229630, 229631, 229632, 221662, 221653)
    AND i.starttime < c.anchor
    AND COALESCE(i.endtime, i.starttime + INTERVAL 1 HOUR) >= c.anchor - INTERVAL 24 HOUR
),
hours AS (
  SELECT range(0, 24) AS hs
),
covered AS (
  SELECT c.cohort, c.stay_id, h AS hour_before,
    MAX(CASE WHEN i.stay_id IS NOT NULL
              AND i.starttime < c.anchor - (h * INTERVAL 1 HOUR)
              AND i.endtime > c.anchor - ((h + 1) * INTERVAL 1 HOUR)
             THEN 1 ELSE 0 END) AS on_pressor
  FROM cohort c
  CROSS JOIN (SELECT UNNEST(range(0, 24)) AS h) hh
  LEFT JOIN inf i ON i.stay_id = c.stay_id AND i.cohort = c.cohort
  WHERE c.intime < c.anchor - (h * INTERVAL 1 HOUR)
  GROUP BY 1, 2, 3
)
SELECT cohort, hour_before,
  COUNT(*) AS n_stays,
  SUM(on_pressor) AS n_on_pressor,
  ROUND(100.0 * SUM(on_pressor) / COUNT(*), 1) AS pct_on_pressor
FROM covered GROUP BY 1, 2 ORDER BY 1, 2;
