-- Retrospectively observed pre-index neurologic/metabolic severity.
-- Assay/chart time is before index. Availability of results to physicians
-- at the index time is NOT established by charttime.
SET threads=5;
SET memory_limit='12GB';
CREATE OR REPLACE TEMP TABLE a AS
SELECT w.anchor_id,w.treated_id,w.stay_id,w.subject_id,w.arm,w.weight,
 w.anchor_time,s.hadm_id
FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/risk_weighted_supporthistory.parquet') w
JOIN mimiciv_icu.icustays s USING(stay_id);
CREATE OR REPLACE TEMP TABLE gs AS
SELECT a.anchor_id,
 count(g.gcs) FILTER(WHERE g.gcs BETWEEN 3 AND 15) n_gcs24,
 arg_max(g.gcs,g.charttime) FILTER(
   WHERE g.gcs BETWEEN 3 AND 15 AND
   g.charttime>=a.anchor_time-INTERVAL '12 hours') gcs_latest12,
 arg_max(g.gcs,g.charttime) FILTER(
   WHERE g.gcs BETWEEN 3 AND 15) gcs_latest24,
 min(g.gcs) FILTER(WHERE g.gcs BETWEEN 3 AND 15) gcs_min24,
 max(g.gcs_unable) gcs_any_unable
FROM a LEFT JOIN mimiciv_derived.gcs g
 ON g.stay_id=a.stay_id AND
 g.charttime>=a.anchor_time-INTERVAL '24 hours'
 AND g.charttime<a.anchor_time
GROUP BY a.anchor_id;
CREATE OR REPLACE TEMP TABLE lact AS
SELECT a.anchor_id,
 count(bg.lactate) FILTER(WHERE bg.lactate BETWEEN 0.1 AND 30) n_lact24,
 arg_max(bg.lactate,bg.charttime) FILTER(
   WHERE bg.lactate BETWEEN 0.1 AND 30) lact_latest24,
 max(bg.lactate) FILTER(WHERE bg.lactate BETWEEN 0.1 AND 30) lact_max24,
 count(bg.lactate) FILTER(
   WHERE bg.lactate BETWEEN 0.1 AND 30 AND
   bg.charttime>=a.anchor_time-INTERVAL '12 hours') n_lact12
FROM a LEFT JOIN mimiciv_derived.bg bg
 ON bg.hadm_id=a.hadm_id
 AND bg.charttime>=a.anchor_time-INTERVAL '24 hours'
 AND bg.charttime<a.anchor_time
GROUP BY a.anchor_id;
CREATE OR REPLACE TEMP TABLE renal AS
SELECT a.anchor_id,
 arg_max(c.creatinine,c.charttime) FILTER(
   WHERE c.creatinine BETWEEN 0.1 AND 30) creat_latest24,
 arg_max(c.bun,c.charttime) FILTER(
   WHERE c.bun BETWEEN 0.1 AND 250) bun_latest24
FROM a LEFT JOIN mimiciv_derived.chemistry c
 ON c.hadm_id=a.hadm_id
 AND c.charttime>=a.anchor_time-INTERVAL '24 hours'
 AND c.charttime<a.anchor_time
GROUP BY a.anchor_id;
COPY(
 SELECT a.anchor_id,a.treated_id,a.stay_id,a.subject_id,a.arm,a.weight,
 g.* EXCLUDE(anchor_id),l.* EXCLUDE(anchor_id),r.* EXCLUDE(anchor_id)
 FROM a JOIN gs g USING(anchor_id) JOIN lact l USING(anchor_id)
 JOIN renal r USING(anchor_id)
) TO '/srv/mimic-iv/studies/decision_feedback_20261025/risk_pre_severity.parquet'
(FORMAT PARQUET,COMPRESSION ZSTD);
SELECT arm,count(*) n,round(sum(weight),1) weighted_n,
round(100.0*sum(weight*(gcs_latest12 IS NOT NULL)::INT)/sum(weight),2) pct_gcs_recent,
round(sum(weight*gcs_latest12) FILTER(WHERE gcs_latest12 IS NOT NULL)/
 sum(weight) FILTER(WHERE gcs_latest12 IS NOT NULL),2) weighted_mean_latest_gcs,
round(100.0*sum(weight*(lact_latest24 IS NOT NULL)::INT)/sum(weight),2) pct_lactate_last24,
round(sum(weight*lact_latest24) FILTER(WHERE lact_latest24 IS NOT NULL)/
 sum(weight) FILTER(WHERE lact_latest24 IS NOT NULL),2) weighted_mean_lactate,
round(100.0*sum(weight*(creat_latest24 IS NOT NULL)::INT)/sum(weight),2) pct_creatinine_recent
FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/risk_pre_severity.parquet')
GROUP BY 1 ORDER BY 1;
