-- As-of available ICU vital signs for existing MIMIC-IV multistate pilot.
-- ONLY charted observations with storetime<=landmark. Patient-level results
-- restricted to s0; source DB opened READ ONLY.
SET threads=6;
SET memory_limit='18GB';
SET preserve_insertion_order=false;
CREATE OR REPLACE TEMP TABLE times AS
SELECT p.stay_id,p.step,
 i.intime+(p.step*6)*INTERVAL '1 hour' t
FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/multistate_6h_pilot_checked.parquet') p
JOIN mimiciv_icu.icustays i ON i.stay_id=p.stay_id;
CREATE OR REPLACE TEMP TABLE observed_at_t AS
SELECT t.stay_id,t.step,c.charttime,
 avg(CASE WHEN c.itemid=220045 AND c.valuenum>0 AND c.valuenum<300
 THEN c.valuenum END) hr,
 avg(CASE WHEN c.itemid IN (220052,220181,225312)
 AND c.valuenum>0 AND c.valuenum<300 THEN c.valuenum END) map_val,
 avg(CASE WHEN c.itemid IN (220210,224690)
 AND c.valuenum>0 AND c.valuenum<70 THEN c.valuenum END) rr,
 avg(CASE WHEN c.itemid=220277 AND c.valuenum>0 AND c.valuenum<=100
 THEN c.valuenum END) spo2
FROM times t LEFT JOIN mimiciv_icu.chartevents c
 ON c.stay_id=t.stay_id
 AND c.charttime>=t.t-INTERVAL '6 hours' AND c.charttime<t.t
 AND c.storetime IS NOT NULL AND c.storetime<=t.t
 AND c.itemid IN (220045,220052,220181,225312,220210,224690,220277)
GROUP BY t.stay_id,t.step,c.charttime;
COPY(
 SELECT stay_id,step,
 avg(hr) hr_asof,avg(map_val) map_asof,avg(rr) rr_asof,avg(spo2) spo2_asof,
 count(*) FILTER(WHERE hr IS NOT NULL) n_hr_asof,
 count(*) FILTER(WHERE map_val IS NOT NULL) n_map_asof,
 count(*) FILTER(WHERE spo2 IS NOT NULL) n_spo2_asof
 FROM observed_at_t GROUP BY stay_id,step
) TO '/srv/mimic-iv/studies/decision_feedback_20261025/multistate_6h_pilot_asof_vitals.parquet'
(FORMAT PARQUET,COMPRESSION ZSTD);
SELECT p.era,count(*) n_landmarks,
 round(avg((p.n_hr>a.n_hr_asof)::INT),4) share_hr_asof_deficit,
 round(avg((p.n_map>a.n_map_asof)::INT),4) share_map_asof_deficit,
 round(avg(p.n_hr-a.n_hr_asof),4) mean_missing_hr_reports,
 round(avg(p.n_map-a.n_map_asof),4) mean_missing_map_reports,
 round(avg((a.n_hr_asof=0)::INT),4) share_with_no_ontime_hr
FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/multistate_6h_pilot_checked.parquet') p
JOIN read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/multistate_6h_pilot_asof_vitals.parquet') a
USING(stay_id,step)
GROUP BY 1 ORDER BY 1;
