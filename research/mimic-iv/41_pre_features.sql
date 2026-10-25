-- Eligible risk-set anchors and PRE-index covariates only.
-- MIMIC-IV 3.1. Source database readonly. Outputs stay on s0.
SET threads=6;
SET memory_limit='14GB';
SET preserve_insertion_order=false;
CREATE OR REPLACE TEMP TABLE treated AS
SELECT * FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/risk_treated.parquet');
CREATE OR REPLACE TEMP TABLE candidates AS
SELECT * FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/risk_candidates.parquet');
CREATE OR REPLACE TEMP TABLE anchors AS
WITH all_rows AS (
 SELECT t.stay_id treated_id,t.stay_id stay_id,t.subject_id,
 t.index_time anchor_time,t.intime,t.outtime,t.deathtime,
 t.sofa,t.age,t.era,t.unit_group, t.first_nonfull,
 'DNR' AS arm
 FROM treated t
 WHERE t.stay_id IN (SELECT treated_stay_id FROM candidates)
 UNION ALL
 SELECT c.treated_stay_id AS treated_id,c.control_stay_id AS stay_id,
 c.control_subject_id AS subject_id,c.pseudo_time anchor_time,
 s.intime,s.outtime,ad.deathtime,c.control_sofa sofa,c.control_age age,
 c.era,c.unit_group,c.control_first_nonfull AS first_nonfull,
 'RISKSET' AS arm
 FROM candidates c JOIN mimiciv_icu.icustays s ON s.stay_id=c.control_stay_id
 JOIN mimiciv_hosp.admissions ad ON ad.hadm_id=s.hadm_id
)
SELECT row_number() OVER(ORDER BY treated_id,arm,stay_id) anchor_id,*
FROM all_rows;
CREATE OR REPLACE TEMP TABLE previtals AS
SELECT a.anchor_id,
 count(v.charttime) FILTER (
  WHERE v.charttime<a.anchor_time-INTERVAL '12 hours'
  AND v.heart_rate IS NOT NULL) hr_n_early,
 count(v.charttime) FILTER (
  WHERE v.charttime>=a.anchor_time-INTERVAL '12 hours'
  AND v.heart_rate IS NOT NULL) hr_n_recent,
 count(v.charttime) FILTER (
  WHERE v.charttime<a.anchor_time-INTERVAL '12 hours'
  AND coalesce(v.mbp,v.mbp_ni) IS NOT NULL) map_n_early,
 count(v.charttime) FILTER (
  WHERE v.charttime>=a.anchor_time-INTERVAL '12 hours'
  AND coalesce(v.mbp,v.mbp_ni) IS NOT NULL) map_n_recent,
 count(v.charttime) FILTER (
  WHERE v.charttime>=a.anchor_time-INTERVAL '4 hours'
  AND v.heart_rate IS NOT NULL) hr_n_last4,
 count(v.charttime) FILTER (
  WHERE v.charttime>=a.anchor_time-INTERVAL '4 hours'
  AND coalesce(v.mbp,v.mbp_ni) IS NOT NULL) map_n_last4,
 avg(v.heart_rate) FILTER(
  WHERE v.charttime>=a.anchor_time-INTERVAL '12 hours') mean_hr,
 avg(coalesce(v.mbp,v.mbp_ni)) FILTER(
  WHERE v.charttime>=a.anchor_time-INTERVAL '12 hours') mean_map,
 avg(v.resp_rate) FILTER(
  WHERE v.charttime>=a.anchor_time-INTERVAL '12 hours') mean_rr,
 avg(v.spo2) FILTER(
  WHERE v.charttime>=a.anchor_time-INTERVAL '12 hours') mean_spo2,
 avg(v.heart_rate) FILTER(
  WHERE v.charttime>=a.anchor_time-INTERVAL '12 hours'
  AND v.charttime<a.anchor_time-INTERVAL '6 hours') hr_prev6,
 avg(v.heart_rate) FILTER(
  WHERE v.charttime>=a.anchor_time-INTERVAL '6 hours') hr_last6,
 avg(coalesce(v.mbp,v.mbp_ni)) FILTER(
  WHERE v.charttime>=a.anchor_time-INTERVAL '12 hours'
  AND v.charttime<a.anchor_time-INTERVAL '6 hours') map_prev6,
 avg(coalesce(v.mbp,v.mbp_ni)) FILTER(
  WHERE v.charttime>=a.anchor_time-INTERVAL '6 hours') map_last6
FROM anchors a LEFT JOIN mimiciv_derived.vitalsign v
 ON v.stay_id=a.stay_id
 AND v.charttime>=a.anchor_time-INTERVAL '24 hours'
 AND v.charttime<a.anchor_time
GROUP BY a.anchor_id;
CREATE OR REPLACE TEMP TABLE pre_vent AS
SELECT a.anchor_id,
 max(CASE WHEN v.ventilation_status IN ('InvasiveVent','Tracheostomy')
 THEN 1 ELSE 0 END) AS vent_recent
FROM anchors a LEFT JOIN mimiciv_derived.ventilation v
 ON v.stay_id=a.stay_id
 AND v.starttime<a.anchor_time
 AND v.endtime>a.anchor_time-INTERVAL '6 hours'
GROUP BY 1;
CREATE OR REPLACE TEMP TABLE pre_press AS
SELECT a.anchor_id,
 max(CASE WHEN p.stay_id IS NOT NULL THEN 1 ELSE 0 END) press_recent
FROM anchors a LEFT JOIN mimiciv_derived.norepinephrine_equivalent_dose p
 ON p.stay_id=a.stay_id
 AND p.starttime<a.anchor_time
 AND p.endtime>a.anchor_time-INTERVAL '6 hours'
GROUP BY 1;
COPY (
 SELECT a.*,
 v.hr_n_early,v.hr_n_recent,v.map_n_early,v.map_n_recent,
 v.hr_n_last4,v.map_n_last4,v.mean_hr,v.mean_map,v.mean_rr,v.mean_spo2,
 v.hr_last6-v.hr_prev6 AS hr_6h_change,
 v.map_last6-v.map_prev6 AS map_6h_change,
 coalesce(p.press_recent,0) press_recent,
 coalesce(e.vent_recent,0) vent_recent
 FROM anchors a JOIN previtals v USING(anchor_id)
 JOIN pre_press p USING(anchor_id)
 JOIN pre_vent e USING(anchor_id)
) TO '/srv/mimic-iv/studies/decision_feedback_20261025/risk_pre_features.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);
SELECT arm,count(*) n,round(avg(sofa),2) sofa,
round(avg(age),1) age,
round(avg(hr_n_early),2) hr_early,
round(avg(hr_n_recent),2) hr_recent,
round(avg(map_n_recent),2) map_recent,
round(avg(mean_map),1) mean_map,
round(avg(mean_hr),1) mean_hr,
round(avg(press_recent),3) press_recent
FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/risk_pre_features.parquet')
GROUP BY 1 ORDER BY 1;
