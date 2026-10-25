-- MIMIC-IV v3.1 outcome construction; matching/weights already frozen.
-- All patient-level outputs remain in the restricted server study directory.
SET threads=6;
SET memory_limit='16GB';
SET preserve_insertion_order=false;
CREATE OR REPLACE TEMP TABLE anchors AS
SELECT * FROM read_parquet(
 '/srv/mimic-iv/studies/decision_feedback_20261025/risk_weighted.parquet');
CREATE OR REPLACE TEMP TABLE observation_bins AS
WITH event_bins AS (
 SELECT a.anchor_id,a.treated_id,a.stay_id,a.subject_id,a.arm,
 a.weight,a.anchor_time,a.first_nonfull,
 k.i AS bin,
 a.anchor_time+k.i*INTERVAL '4 hours' AS start_time,
 a.anchor_time+(k.i+1)*INTERVAL '4 hours' AS nominal_end,
 a.outtime,a.deathtime
 FROM anchors a CROSS JOIN range(-6,3) k(i)
), limits AS (
 SELECT *,
 least(nominal_end,outtime,coalesce(deathtime,outtime)) AS end_time,
 CASE WHEN arm='RISKSET' AND first_nonfull>anchor_time
 THEN least(nominal_end,outtime,coalesce(deathtime,outtime),first_nonfull)
 ELSE least(nominal_end,outtime,coalesce(deathtime,outtime)) END
 AS censor_at_control_transition
 FROM event_bins
)
SELECT *,
 greatest(0.,datediff('second',start_time,end_time)/3600.) observed_h,
 greatest(0.,datediff('second',start_time,censor_at_control_transition)/3600.) censored_h
FROM limits;
COPY (
 SELECT b.anchor_id,b.treated_id,b.stay_id,b.subject_id,b.arm,
 b.weight,b.bin,b.observed_h,b.censored_h,
 count(v.charttime) FILTER(WHERE v.heart_rate IS NOT NULL) n_hr,
 count(v.charttime) FILTER(WHERE coalesce(v.mbp,v.mbp_ni) IS NOT NULL) n_map,
 count(v.charttime) FILTER(WHERE v.heart_rate IS NOT NULL AND
 v.charttime<b.censor_at_control_transition) n_hr_censored,
 count(v.charttime) FILTER(WHERE coalesce(v.mbp,v.mbp_ni) IS NOT NULL AND
 v.charttime<b.censor_at_control_transition) n_map_censored
 FROM observation_bins b LEFT JOIN mimiciv_derived.vitalsign v
 ON v.stay_id=b.stay_id AND v.charttime>=b.start_time
 AND v.charttime<b.end_time
 GROUP BY ALL
) TO '/srv/mimic-iv/studies/decision_feedback_20261025/risk_event_bins.parquet'
(FORMAT PARQUET,COMPRESSION ZSTD);
SELECT arm,bin,count(*) n_anchors,
round(sum(weight),1) weighted_n,
round(sum(weight*observed_h),1) weighted_person_hours,
round(sum(weight*n_hr)/nullif(sum(weight*observed_h),0),3) hr_per_icu_hour,
round(sum(weight*n_map)/nullif(sum(weight*observed_h),0),3) map_per_icu_hour
FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/risk_event_bins.parquet')
GROUP BY arm,bin ORDER BY arm,bin;
