-- Read-only MIMIC-IV v3.1 analysis definitions.
-- Do not interpret the order timestamp as random treatment assignment.
SET threads=4;
SET memory_limit='8GB';
CREATE OR REPLACE TEMP VIEW code_history AS
WITH distinct_codes AS (
 SELECT DISTINCT hadm_id,charttime,
 CASE WHEN cmo=1 THEN 'CMO'
 WHEN dnr=1 AND dni=1 THEN 'DNR_DNI'
 WHEN dnr=1 THEN 'DNR_ONLY'
 WHEN dni=1 THEN 'DNI_ONLY'
 WHEN fullcode=1 THEN 'FULL' ELSE 'OTHER' END AS state
 FROM mimiciv_derived.code_status
)
SELECT s.subject_id,s.hadm_id,s.stay_id,s.intime,s.outtime,
 s.first_careunit,c.charttime,c.state
FROM mimiciv_icu.icustays s
JOIN mimiciv_hosp.admissions a ON a.hadm_id=s.hadm_id
JOIN distinct_codes c ON c.hadm_id=s.hadm_id
 AND c.charttime>=a.admittime AND c.charttime<=s.outtime;
CREATE OR REPLACE TEMP VIEW code_sequence AS
SELECT *,lag(state) OVER(
 PARTITION BY stay_id ORDER BY charttime,state) prev_state
FROM code_history;
CREATE OR REPLACE TEMP VIEW event_candidates AS
SELECT q.*,f.sofa,
 CASE WHEN state='FULL' THEN 'CONTROL'
 ELSE 'DNR' END AS arm,
 row_number() OVER(
 PARTITION BY q.stay_id,CASE WHEN state='FULL' THEN 'CONTROL'
 ELSE 'DNR' END ORDER BY q.charttime,state) AS rn
FROM code_sequence q
JOIN mimiciv_derived.first_day_sofa f ON q.stay_id=f.stay_id
WHERE prev_state='FULL' AND state IN ('FULL','DNR_ONLY','DNR_DNI')
 AND charttime>=intime;
CREATE OR REPLACE TEMP VIEW event_landmarks AS
SELECT * FROM event_candidates
WHERE rn=1 AND charttime>=intime+INTERVAL '24 hours'
 AND charttime+INTERVAL '12 hours'<=outtime;
