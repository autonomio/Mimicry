-- MIMIC-IV 3.1 risk-set candidate construction. RUN ONLY on a read-only DB.
-- Distinct known full-code periods: first recorded FULL through first
-- subsequently recorded non-FULL, with no earlier treatment limitation.
-- Restrict to first ICU stay per hospital admission. All identifiers remain on s0.
SET threads=6;
SET memory_limit='14GB';
SET preserve_insertion_order=false;
CREATE OR REPLACE TEMP TABLE status_times AS
WITH v AS (
 SELECT hadm_id,charttime,
 CASE WHEN cmo=1 THEN 'CMO'
 WHEN dnr=1 AND dni=1 THEN 'DNR_DNI'
 WHEN dnr=1 THEN 'DNR_ONLY'
 WHEN dni=1 THEN 'DNI_ONLY'
 WHEN fullcode=1 THEN 'FULL' ELSE 'OTHER' END AS status
 FROM mimiciv_derived.code_status
)
SELECT hadm_id,charttime,min(status) status,count(DISTINCT status) n_states
FROM v GROUP BY 1,2;
CREATE OR REPLACE TEMP TABLE bad_hadm AS
SELECT DISTINCT hadm_id FROM status_times WHERE n_states>1;
CREATE OR REPLACE TEMP TABLE stay_base AS
WITH first_stay AS (
 SELECT *,row_number() OVER(PARTITION BY hadm_id ORDER BY intime,stay_id) rn
 FROM mimiciv_icu.icustays
), visits AS (
 SELECT s.subject_id,s.hadm_id,s.stay_id,s.intime,s.outtime,
 s.first_careunit AS careunit,
 CASE WHEN s.first_careunit LIKE '%Neuro%' THEN 'NEURO'
 WHEN s.first_careunit LIKE '%MICU%' THEN 'MICU'
 WHEN s.first_careunit LIKE '%CVICU%' THEN 'CVICU'
 WHEN s.first_careunit LIKE '%CCU%' THEN 'CCU'
 WHEN s.first_careunit LIKE '%TSICU%' THEN 'TSICU'
 WHEN s.first_careunit LIKE '%SICU%' THEN 'SICU'
 ELSE 'OTHER' END AS unit_group,
 f.sofa, a.age, p.anchor_year_group AS era, ad.deathtime,ad.dischtime
 FROM first_stay s
 JOIN mimiciv_derived.first_day_sofa f ON f.stay_id=s.stay_id
 JOIN mimiciv_derived.age a ON a.hadm_id=s.hadm_id
 JOIN mimiciv_hosp.patients p ON p.subject_id=s.subject_id
 JOIN mimiciv_hosp.admissions ad ON ad.hadm_id=s.hadm_id
 WHERE s.rn=1 AND s.hadm_id NOT IN (SELECT hadm_id FROM bad_hadm)
)
SELECT v.*,
 min(st.charttime) FILTER(WHERE st.status='FULL') AS first_full,
 min(st.charttime) FILTER(WHERE st.status<>'FULL') AS first_nonfull,
 arg_min(st.status,st.charttime) FILTER(WHERE st.status<>'FULL') AS first_nonfull_state
FROM visits v
JOIN mimiciv_hosp.admissions ad ON v.hadm_id=ad.hadm_id
LEFT JOIN status_times st ON st.hadm_id=v.hadm_id
 AND st.charttime>=ad.admittime AND st.charttime<=v.outtime
GROUP BY ALL;
CREATE OR REPLACE TEMP TABLE treated AS
WITH dnr_poe AS (
 SELECT DISTINCT hadm_id,ordertime FROM mimiciv_hosp.poe
 WHERE order_type='General Care' AND order_subtype='Code status'
)
SELECT s.*,
 s.first_nonfull AS index_time,
 datediff('second',s.intime,s.first_nonfull) AS elapsed_seconds
FROM stay_base s JOIN dnr_poe p ON p.hadm_id=s.hadm_id
 AND p.ordertime=s.first_nonfull
WHERE s.first_nonfull_state IN ('DNR_ONLY','DNR_DNI')
 AND s.first_full<s.first_nonfull
 AND s.first_nonfull>=s.intime+INTERVAL '24 hours'
 AND s.first_nonfull<s.intime+INTERVAL '14 days'
 AND s.first_nonfull<s.outtime
 AND (s.deathtime IS NULL OR s.deathtime>s.first_nonfull)
 AND s.sofa IS NOT NULL AND s.age IS NOT NULL
 AND s.unit_group<>'OTHER';
CREATE OR REPLACE TEMP TABLE eligible_control_stays AS
SELECT * FROM stay_base
WHERE first_full IS NOT NULL AND sofa IS NOT NULL AND age IS NOT NULL
 AND unit_group<>'OTHER'
 AND outtime>=intime+INTERVAL '24 hours';
CREATE OR REPLACE TEMP TABLE risk_candidates AS
SELECT t.stay_id treated_stay_id,t.subject_id treated_subject_id,
 c.stay_id control_stay_id,c.subject_id control_subject_id,
 c.intime+t.elapsed_seconds*INTERVAL '1 second' AS pseudo_time,
 t.elapsed_seconds,t.unit_group,t.era,
 t.sofa treated_sofa,c.sofa control_sofa,
 t.age treated_age,c.age control_age,
 c.first_nonfull AS control_first_nonfull
FROM treated t JOIN eligible_control_stays c
 ON c.unit_group=t.unit_group AND c.era=t.era
 AND abs(c.sofa-t.sofa)<=3 AND abs(c.age-t.age)<=20
 AND c.subject_id<>t.subject_id
 AND c.intime+t.elapsed_seconds*INTERVAL '1 second'<c.outtime
 AND (c.deathtime IS NULL OR c.deathtime>c.intime+t.elapsed_seconds*INTERVAL '1 second')
 AND c.first_full<=c.intime+t.elapsed_seconds*INTERVAL '1 second'
 AND (c.first_nonfull IS NULL
      OR c.first_nonfull>c.intime+t.elapsed_seconds*INTERVAL '1 second')
 AND floor(extract(hour from t.index_time)/6)
 =floor(extract(hour from (c.intime+t.elapsed_seconds*INTERVAL '1 second'))/6)
QUALIFY row_number() OVER(
 PARTITION BY t.stay_id
 ORDER BY hash(20261025,t.stay_id,c.stay_id))<=160;
SELECT 'treated' metric,count(*) n FROM treated
UNION ALL SELECT 'eligible_control_stays',count(*) FROM eligible_control_stays
UNION ALL SELECT 'candidate_pairs',count(*) FROM risk_candidates
UNION ALL SELECT 'treated_with_candidates',count(DISTINCT treated_stay_id) FROM risk_candidates
UNION ALL SELECT 'distinct_candidate_control_stays',count(DISTINCT control_stay_id) FROM risk_candidates;

-- Persist restricted patient-level intermediates only on s0.
COPY (SELECT * FROM treated)
TO '/srv/mimic-iv/studies/decision_feedback_20261025/risk_treated.parquet'
(FORMAT PARQUET,COMPRESSION ZSTD);
COPY (SELECT * FROM risk_candidates)
TO '/srv/mimic-iv/studies/decision_feedback_20261025/risk_candidates.parquet'
(FORMAT PARQUET,COMPRESSION ZSTD);
