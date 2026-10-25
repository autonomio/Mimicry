-- Specificity: respiratory rate and oxygen saturation charting, alongside MAP/HR.
SET threads=6;
SET memory_limit='14GB';
CREATE OR REPLACE TEMP TABLE b AS
SELECT x.anchor_id,x.treated_id,x.stay_id,x.subject_id,x.arm,x.weight,x.bin,
 x.observed_h,
 a.anchor_time+x.bin*INTERVAL '4 hours' AS begin_time,
 least(a.outtime,coalesce(a.deathtime,a.outtime),
  a.anchor_time+(x.bin+1)*INTERVAL '4 hours') AS end_time
FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/risk_event_bins.parquet') x
JOIN read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/risk_weighted.parquet') a USING(anchor_id);
COPY (
 SELECT b.anchor_id,b.subject_id,b.arm,b.weight,b.bin,b.observed_h,
 count(v.charttime) FILTER(WHERE v.spo2 IS NOT NULL) n_spo2,
 count(v.charttime) FILTER(WHERE v.resp_rate IS NOT NULL) n_rr,
 count(v.charttime) FILTER(WHERE v.temperature IS NOT NULL) n_temp
 FROM b LEFT JOIN mimiciv_derived.vitalsign v
 ON v.stay_id=b.stay_id AND v.charttime>=b.begin_time AND v.charttime<b.end_time
 GROUP BY ALL
) TO '/srv/mimic-iv/studies/decision_feedback_20261025/risk_other_vital_bins.parquet'
(FORMAT PARQUET,COMPRESSION ZSTD);
WITH x AS (
 SELECT arm,
 sum(weight*n_spo2) FILTER(WHERE bin BETWEEN -3 AND -1) pre_spo2,
 sum(weight*n_spo2) FILTER(WHERE bin BETWEEN 0 AND 2) post_spo2,
 sum(weight*n_rr) FILTER(WHERE bin BETWEEN -3 AND -1) pre_rr,
 sum(weight*n_rr) FILTER(WHERE bin BETWEEN 0 AND 2) post_rr,
 sum(weight*n_temp) FILTER(WHERE bin BETWEEN -3 AND -1) pre_temp,
 sum(weight*n_temp) FILTER(WHERE bin BETWEEN 0 AND 2) post_temp,
 sum(weight*observed_h) FILTER(WHERE bin BETWEEN -3 AND -1) pre_hours,
 sum(weight*observed_h) FILTER(WHERE bin BETWEEN 0 AND 2) post_hours
 FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/risk_other_vital_bins.parquet') GROUP BY arm
)
SELECT arm,
round(pre_spo2/pre_hours,4) spo2_pre,round(post_spo2/post_hours,4) spo2_post,
round(pre_rr/pre_hours,4) rr_pre,round(post_rr/post_hours,4) rr_post,
round(pre_temp/pre_hours,4) temp_pre,round(post_temp/post_hours,4) temp_post
FROM x ORDER BY arm;
