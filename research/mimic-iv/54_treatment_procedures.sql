-- MIMIC-IV: explicit treatment procedure and subsequent comfort-status timing.
-- Event-level findings are descriptive; never condition on future status.
SET threads=5;
SET memory_limit='12GB';
CREATE OR REPLACE TEMP TABLE a AS
SELECT anchor_id,treated_id,stay_id,subject_id,arm,weight,anchor_time,
 least(outtime,coalesce(deathtime,outtime),anchor_time+INTERVAL '12 hours') end12,
 outtime,deathtime,first_nonfull
FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/risk_weighted.parquet');
CREATE OR REPLACE TEMP TABLE procedures AS
SELECT a.anchor_id,
 count(p.stay_id) FILTER (
  WHERE p.itemid=227194 AND p.starttime<a.anchor_time-INTERVAL '4 hours'
 ) n_extub_pre_12to4,
 count(p.stay_id) FILTER (
  WHERE p.itemid=227194 AND p.starttime>=a.anchor_time-INTERVAL '4 hours'
    AND p.starttime<a.anchor_time
 ) n_extub_pre_4to0,
 count(p.stay_id) FILTER (
  WHERE p.itemid=227194 AND p.starttime>=a.anchor_time
    AND p.starttime<a.anchor_time+INTERVAL '4 hours'
 ) n_extub_post_0to4,
 count(p.stay_id) FILTER (
  WHERE p.itemid=227194 AND p.starttime>=a.anchor_time
 ) n_extub_post_0to12,
 count(p.stay_id) FILTER (
  WHERE p.itemid=224385 AND p.starttime<a.anchor_time
 ) n_intub_pre_12h,
 count(p.stay_id) FILTER (
  WHERE p.itemid=224385 AND p.starttime>=a.anchor_time
 ) n_intub_post_12h
FROM a LEFT JOIN mimiciv_icu.procedureevents p
 ON p.stay_id=a.stay_id
 AND p.itemid IN (227194,224385)
 AND p.starttime>=a.anchor_time-INTERVAL '12 hours'
 AND p.starttime<a.end12
GROUP BY 1;
CREATE OR REPLACE TEMP TABLE comfort AS
SELECT a.anchor_id,
 count(c.stay_id) FILTER(WHERE c.charttime>=a.anchor_time
   AND c.charttime<a.anchor_time+INTERVAL '4 hours') n_cmo_4h,
 count(c.stay_id) FILTER(WHERE c.charttime>=a.anchor_time) n_cmo_12h
FROM a LEFT JOIN mimiciv_icu.chartevents c
 ON c.stay_id=a.stay_id AND c.itemid=223758
 AND c.value='Comfort measures only'
 AND c.charttime>=a.anchor_time
 AND c.charttime<a.end12 GROUP BY 1;
COPY(
 SELECT a.anchor_id,a.treated_id,a.stay_id,a.subject_id,a.arm,a.weight,
 a.deathtime,a.anchor_time,a.outtime,
 p.* EXCLUDE(anchor_id),c.* EXCLUDE(anchor_id)
 FROM a JOIN procedures p USING(anchor_id) JOIN comfort c USING(anchor_id)
) TO '/srv/mimic-iv/studies/decision_feedback_20261025/risk_support_procedures.parquet'
(FORMAT PARQUET,COMPRESSION ZSTD);
SELECT arm, count(*) n_anchors,round(sum(weight),1) weighted_n,
 round(100*sum(weight*(n_extub_pre_12to4>0)::INT)/sum(weight),2) extub_12to4h_pre_pct,
 round(100*sum(weight*(n_extub_pre_4to0>0)::INT)/sum(weight),2) extub_4h_pre_pct,
 round(100*sum(weight*(n_extub_post_0to4>0)::INT)/sum(weight),2) extub_4h_post_pct,
 round(100*sum(weight*(n_extub_post_0to12>0)::INT)/sum(weight),2) extub_12h_post_pct,
 round(100*sum(weight*(n_intub_post_12h>0)::INT)/sum(weight),2) intub_12h_post_pct,
 round(100*sum(weight*(n_cmo_12h>0)::INT)/sum(weight),2) cmo_12h_pct
FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/risk_support_procedures.parquet')
GROUP BY arm ORDER BY arm;
