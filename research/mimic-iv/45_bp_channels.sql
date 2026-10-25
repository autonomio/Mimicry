-- Source-channel specificity from MIMIC-IV v3.1 raw chart events.
-- art=220052/225312; cuff=220181; blood pressure plausibility 0..300.
-- Count distinct valid timestamp records, not duplicate row counts.
SET threads=6;
SET memory_limit='16GB';
SET preserve_insertion_order=false;
CREATE OR REPLACE TEMP TABLE bp_times AS
SELECT stay_id, charttime,
 max(CASE WHEN itemid IN (220052,225312) THEN 1 ELSE 0 END) art,
 max(CASE WHEN itemid=220181 THEN 1 ELSE 0 END) cuff
FROM mimiciv_icu.chartevents
WHERE itemid IN (220052,225312,220181)
 AND valuenum>0 AND valuenum<300 AND stay_id IS NOT NULL
GROUP BY stay_id,charttime;
SELECT 'bp_timestamps' AS metric,count(*) n FROM bp_times
UNION ALL SELECT 'art_arterial_timestamps',count(*) FROM bp_times WHERE art=1
UNION ALL SELECT 'cuff_timestamps',count(*) FROM bp_times WHERE cuff=1
UNION ALL SELECT 'concurrent_art_and_cuff',count(*) FROM bp_times WHERE art=1 AND cuff=1;
CREATE OR REPLACE TEMP TABLE at_risk_bins AS
SELECT b.anchor_id,b.treated_id,b.stay_id,b.subject_id,b.arm,
 b.weight,b.bin,b.observed_h,
 a.anchor_time+b.bin*INTERVAL '4 hours' AS start_time,
 least(a.outtime,coalesce(a.deathtime,a.outtime),
       a.anchor_time+(b.bin+1)*INTERVAL '4 hours') AS end_time
FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/risk_event_bins.parquet') b
JOIN read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/risk_weighted.parquet') a
 USING(anchor_id);
COPY (
 SELECT b.anchor_id,b.treated_id,b.stay_id,b.subject_id,b.arm,
 b.weight,b.bin,b.observed_h,
 count(x.charttime) FILTER (WHERE x.art=1) AS n_art,
 count(x.charttime) FILTER (WHERE x.cuff=1) AS n_cuff,
 count(x.charttime) FILTER (WHERE x.art=1 AND x.cuff=1) AS n_both,
 count(x.charttime) FILTER (WHERE x.art=1 OR x.cuff=1) AS n_any
 FROM at_risk_bins b LEFT JOIN bp_times x
 ON x.stay_id=b.stay_id AND x.charttime>=b.start_time
 AND x.charttime<b.end_time
 GROUP BY ALL
) TO '/srv/mimic-iv/studies/decision_feedback_20261025/risk_bp_channel_bins.parquet'
(FORMAT PARQUET,COMPRESSION ZSTD);
SELECT arm,bin,
round(sum(weight*n_art)/sum(weight*observed_h),4) art_per_hour,
round(sum(weight*n_cuff)/sum(weight*observed_h),4) cuff_per_hour,
round(sum(weight*n_both)/sum(weight*observed_h),4) both_per_hour,
round(sum(weight*n_any)/sum(weight*observed_h),4) any_map_per_hour
FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/risk_bp_channel_bins.parquet')
GROUP BY arm,bin ORDER BY arm,bin;
