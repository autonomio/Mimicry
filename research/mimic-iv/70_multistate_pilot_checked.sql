-- Multistate longitudinal landmark panel. Exploratory MIMIC-IV 3.1.
-- First ICU stay per patient, 6h landmarks over first seven ICU days.
-- At each landmark: latest previously documented code status (UNKNOWN
-- separately), six-hour measured physiology, monitoring intensity,
-- prior support delivered. Labels are NEXT-six-hour competing exits.
-- All data stay on s0; source DuckDB read-only.
SET threads=6;
SET memory_limit='18GB';
SET preserve_insertion_order=false;
CREATE OR REPLACE TEMP TABLE stays AS
WITH ordered AS (
 SELECT s.*,row_number() OVER(PARTITION BY s.subject_id
   ORDER BY s.intime,s.stay_id) AS rn
 FROM mimiciv_icu.icustays s
)
SELECT s.subject_id,s.hadm_id,s.stay_id,s.first_careunit,
 CASE WHEN s.first_careunit LIKE '%Neuro%' THEN 'NEURO'
 WHEN s.first_careunit LIKE '%MICU%' THEN 'MICU'
 WHEN s.first_careunit LIKE '%CVICU%' THEN 'CVICU'
 WHEN s.first_careunit LIKE '%CCU%' THEN 'CCU'
 WHEN s.first_careunit LIKE '%TSICU%' THEN 'TSICU'
 WHEN s.first_careunit LIKE '%SICU%' THEN 'SICU'
 ELSE 'OTHER' END unit_group,
 s.intime,s.outtime,a.admittime,a.deathtime,p.anchor_year_group AS era,
 age.age,sofa.sofa
FROM ordered s
JOIN mimiciv_hosp.admissions a ON a.hadm_id=s.hadm_id
JOIN mimiciv_hosp.patients p ON p.subject_id=s.subject_id
LEFT JOIN mimiciv_derived.age age ON age.hadm_id=s.hadm_id
LEFT JOIN mimiciv_derived.first_day_sofa sofa ON sofa.stay_id=s.stay_id
WHERE s.rn=1 AND s.outtime>s.intime AND s.first_careunit IS NOT NULL;
CREATE OR REPLACE TEMP TABLE status_events AS
SELECT hadm_id,charttime,
 CASE WHEN max(cmo)=1 THEN 'CMO'
 WHEN max(dnr)=1 AND max(dni)=1 THEN 'DNR_DNI'
 WHEN max(dnr)=1 THEN 'DNR_ONLY'
 WHEN max(dni)=1 THEN 'DNI_ONLY'
 WHEN max(fullcode)=1 THEN 'FULL'
 ELSE 'UNKNOWN' END status,
 count(DISTINCT concat_ws(':',fullcode,dnr,dni,cmo)) n_states
FROM mimiciv_derived.code_status
GROUP BY hadm_id,charttime;
-- Exclude entire admissions with contradictory timestamps rather than
-- silently imposing priority at the same timestamp.
CREATE OR REPLACE TEMP TABLE bad_admissions AS
SELECT DISTINCT hadm_id FROM status_events WHERE n_states>1;
CREATE OR REPLACE TEMP TABLE landmarks AS
SELECT s.*,
 k.i AS step,
 s.intime+(k.i*6)*INTERVAL '1 hour' AS t,
 least(s.outtime,coalesce(s.deathtime,s.outtime),
 s.intime+((k.i+1)*6)*INTERVAL '1 hour') AS end_t
FROM stays s CROSS JOIN range(4,28) k(i)
WHERE s.hadm_id NOT IN (SELECT hadm_id FROM bad_admissions)
 AND s.intime+(k.i*6)*INTERVAL '1 hour'<s.outtime
 AND (s.deathtime IS NULL OR s.intime+(k.i*6)*INTERVAL '1 hour'<s.deathtime);
CREATE OR REPLACE TEMP TABLE code_at_landmark AS
SELECT l.stay_id,l.step,
 arg_max(e.status,e.charttime) AS code_state,
 max(e.charttime) AS latest_code_time
FROM landmarks l LEFT JOIN status_events e ON e.hadm_id=l.hadm_id
 AND e.charttime>=l.admittime
 AND e.charttime<=l.t
GROUP BY l.stay_id,l.step;
CREATE OR REPLACE TEMP TABLE code_next AS
SELECT l.stay_id,l.step,
 min(e.charttime) AS first_change_time,
 arg_min(e.status,e.charttime) AS first_change_state
FROM landmarks l JOIN code_at_landmark x USING(stay_id,step)
 LEFT JOIN status_events e ON e.hadm_id=l.hadm_id
 AND e.charttime>l.t
 AND e.charttime<=l.t+INTERVAL '6 hours'
 AND e.charttime<=l.outtime
 AND (l.deathtime IS NULL OR e.charttime<=l.deathtime)
 AND e.status IS DISTINCT FROM coalesce(x.code_state,'UNKNOWN')
GROUP BY l.stay_id,l.step;
CREATE OR REPLACE TEMP TABLE measured AS
SELECT l.stay_id,l.step,
 avg(v.heart_rate) AS hr,
 avg(coalesce(v.mbp,v.mbp_ni)) AS map,
 avg(v.resp_rate) AS rr,
 avg(v.spo2) AS spo2,
 count(v.charttime) FILTER(WHERE v.heart_rate IS NOT NULL) n_hr,
 count(v.charttime) FILTER(WHERE coalesce(v.mbp,v.mbp_ni) IS NOT NULL) n_map,
 count(v.charttime) FILTER(WHERE v.spo2 IS NOT NULL) n_spo2
FROM landmarks l LEFT JOIN mimiciv_derived.vitalsign v
 ON v.stay_id=l.stay_id
 AND v.charttime>=l.t-INTERVAL '6 hours' AND v.charttime<l.t
GROUP BY l.stay_id,l.step;
CREATE OR REPLACE TEMP TABLE prior_support AS
SELECT l.stay_id,l.step,
 coalesce(sum(greatest(0,datediff('second',
  greatest(v.starttime,l.t-INTERVAL '6 hours'),
  least(v.endtime,l.t))/3600.0))
  FILTER(WHERE v.ventilation_status='InvasiveVent'),0) AS invasive_h
FROM landmarks l LEFT JOIN mimiciv_derived.ventilation v
 ON v.stay_id=l.stay_id AND v.starttime<l.t
 AND v.endtime>l.t-INTERVAL '6 hours'
GROUP BY l.stay_id,l.step;
CREATE OR REPLACE TEMP TABLE prior_press AS
SELECT l.stay_id,l.step,
 coalesce(sum(greatest(0,datediff('second',
  greatest(p.starttime,l.t-INTERVAL '6 hours'),
  least(p.endtime,l.t))/3600.0)),0) AS pressor_raw_h
FROM landmarks l LEFT JOIN (
 SELECT DISTINCT stay_id,starttime,endtime
 FROM mimiciv_derived.norepinephrine_equivalent_dose
) p ON p.stay_id=l.stay_id
 AND p.starttime<l.t AND p.endtime>l.t-INTERVAL '6 hours'
GROUP BY l.stay_id,l.step;
COPY(
 SELECT l.subject_id,l.hadm_id,l.stay_id,l.era,l.unit_group,
 l.step,l.age,l.sofa,
 coalesce(c.code_state,'UNKNOWN') AS code_state,
 datediff('hour',coalesce(c.latest_code_time,l.intime),l.t) AS code_age_h,
 m.hr,m.map,m.rr,m.spo2,
 m.n_hr,m.n_map,m.n_spo2,
 least(6,ps.invasive_h) AS prior_invasive_h,
 least(6,pp.pressor_raw_h) AS prior_pressor_h,
 greatest(0,datediff('second',l.t,l.end_t)/3600.0) AS next_icu_hours,
 CASE
 WHEN l.deathtime IS NOT NULL AND l.deathtime>l.t
  AND l.deathtime<=l.outtime AND l.deathtime<=l.t+INTERVAL '6 hours'
  AND (n.first_change_time IS NULL OR l.deathtime<=n.first_change_time)
 THEN 'DEATH'
 WHEN l.outtime>l.t AND l.outtime<=l.t+INTERVAL '6 hours'
  AND (n.first_change_time IS NULL OR l.outtime<=n.first_change_time)
 THEN 'ICU_EXIT'
 WHEN n.first_change_time IS NOT NULL AND c.code_state IS NULL THEN 'FIRST_DOCUMENTATION'
 WHEN n.first_change_time IS NOT NULL THEN 'CODE_CHANGE'
 ELSE 'NO_EVENT'
 END AS next_event,
 coalesce(n.first_change_state,'NONE') AS next_code_state,
 (l.deathtime>l.t AND l.deathtime<=l.outtime
  AND l.deathtime<=l.t+INTERVAL '6 hours') AS death_within6h,
 (l.outtime>l.t AND l.outtime<=l.t+INTERVAL '6 hours') AS icu_exit_within6h,
 (n.first_change_time IS NOT NULL AND c.code_state IS NOT NULL) AS code_change_within6h,
 (n.first_change_time IS NOT NULL AND c.code_state IS NULL) AS first_documentation_within6h,
 (n.first_change_time IS NOT NULL AND (
  (l.deathtime>l.t AND l.deathtime<=l.t+INTERVAL '6 hours' AND l.deathtime<=l.outtime)
  OR l.outtime<=l.t+INTERVAL '6 hours')) AS within_bin_collision,
 CASE WHEN n.first_change_time IS NOT NULL THEN datediff('second',l.t,n.first_change_time)/3600. ELSE NULL END AS code_offset_h,
 CASE WHEN l.deathtime>l.t AND l.deathtime<=l.outtime
  AND l.deathtime<=l.t+INTERVAL '6 hours' THEN datediff('second',l.t,l.deathtime)/3600. ELSE NULL END AS death_offset_h,
 CASE WHEN l.outtime>l.t AND l.outtime<=l.t+INTERVAL '6 hours' THEN datediff('second',l.t,l.outtime)/3600. ELSE NULL END AS exit_offset_h

 FROM landmarks l
 JOIN code_at_landmark c USING(stay_id,step)
 JOIN code_next n USING(stay_id,step)
 JOIN measured m USING(stay_id,step)
 JOIN prior_support ps USING(stay_id,step)
 JOIN prior_press pp USING(stay_id,step)
) TO '/srv/mimic-iv/studies/decision_feedback_20261025/multistate_6h_pilot_checked.parquet'
(FORMAT PARQUET,COMPRESSION ZSTD);
SELECT era,next_event,count(*) n
FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/multistate_6h_pilot_checked.parquet')
GROUP BY 1,2 ORDER BY 1,2;
