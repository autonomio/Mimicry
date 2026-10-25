-- Prophecy: terminal endpoint sensitivity to ICU return in same admission.
-- MIMIC-IV 3.1, first ICU stay per subject at hour24; no downloads.
-- WARNING: Defining permanent ICU exit using future readmission is a
-- retrospective diagnostic, NOT a prospectively known outcome at time0.
-- Output only aggregate counts. Never export stay-/subject-level data.
SET threads=4;
SET memory_limit='8GB';
WITH firsts AS (
 SELECT x.subject_id,s.hadm_id,x.stay_id,x.era,s.intime,s.outtime
 FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/kernel_6h_transitions.parquet') x
 JOIN mimiciv_icu.icustays s ON s.stay_id=x.stay_id
 WHERE x.step=4 AND x.era IN ('2017 - 2019','2020 - 2022')
), seq AS (
 SELECT subject_id,arg_min(terminal_outcome,step) AS state
 FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/kernel_6h_transitions.parquet')
 WHERE step BETWEEN 4 AND 23 AND terminal_outcome IN ('EXIT','DEATH')
 GROUP BY subject_id
), readmit AS (
 SELECT f.*,min(s2.intime) AS next_icu_in
 FROM firsts f LEFT JOIN mimiciv_icu.icustays s2
 ON s2.subject_id=f.subject_id AND s2.stay_id<>f.stay_id
 AND s2.hadm_id=f.hadm_id AND s2.intime>f.outtime
 GROUP BY ALL
), cohort AS (
 SELECT f.era,coalesce(q.state,'STAY') AS outcome,
 (f.next_icu_in IS NOT NULL AND f.next_icu_in<f.outtime+INTERVAL '24 hours') AS returned24,
 (f.next_icu_in IS NOT NULL AND f.next_icu_in<f.outtime+INTERVAL '7 days') AS returned7
 FROM readmit f LEFT JOIN seq q USING(subject_id)
)
SELECT era,count(*) n_hour24_patients,
 count(*) FILTER(WHERE outcome='EXIT') original_icu_exit_count,
 round(100.0*count(*) FILTER(WHERE outcome='EXIT')/count(*),4) original_exit_pct,
 count(*) FILTER(WHERE outcome='EXIT' AND returned24) reenter24_after_earlier_exit,
 round(100.0*count(*) FILTER(WHERE outcome='EXIT' AND NOT returned24)/count(*),4) exit_not_reentered24_pct,
 round(100.0*count(*) FILTER(WHERE outcome='EXIT' AND NOT returned7)/count(*),4) exit_not_reentered7d_pct,
 count(*) FILTER(WHERE outcome='DEATH') first_icu_deaths
FROM cohort
GROUP BY era ORDER BY era;
