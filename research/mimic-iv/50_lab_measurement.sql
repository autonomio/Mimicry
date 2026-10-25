-- MIMIC-IV 3.1 laboratory ordering/measurement as an alternative process.
-- Unique chemistry/CBC specimen timestamps, within ICU person-time.
SET threads=6;
SET memory_limit='14GB';
CREATE OR REPLACE TEMP TABLE a AS
SELECT w.anchor_id,w.subject_id,w.stay_id,w.arm,w.weight,w.anchor_time,
 i.hadm_id,
 least(w.outtime,coalesce(w.deathtime,w.outtime),
  w.anchor_time+INTERVAL '12 hours') AS post_end
FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/risk_weighted.parquet') w
JOIN mimiciv_icu.icustays i USING(stay_id);
CREATE OR REPLACE TEMP TABLE chemistry AS
SELECT a.anchor_id,
 count(DISTINCT c.specimen_id) FILTER(WHERE c.charttime<a.anchor_time) pre_chem,
 count(DISTINCT c.specimen_id) FILTER(WHERE c.charttime>=a.anchor_time) post_chem
FROM a LEFT JOIN mimiciv_derived.chemistry c
ON c.hadm_id=a.hadm_id AND c.charttime>=a.anchor_time-INTERVAL '12 hours'
AND c.charttime<a.post_end GROUP BY 1;
CREATE OR REPLACE TEMP TABLE cbc AS
SELECT a.anchor_id,
 count(DISTINCT c.specimen_id) FILTER(WHERE c.charttime<a.anchor_time) pre_cbc,
 count(DISTINCT c.specimen_id) FILTER(WHERE c.charttime>=a.anchor_time) post_cbc
FROM a LEFT JOIN mimiciv_derived.complete_blood_count c
ON c.hadm_id=a.hadm_id AND c.charttime>=a.anchor_time-INTERVAL '12 hours'
AND c.charttime<a.post_end GROUP BY 1;
COPY(
 SELECT a.anchor_id,a.subject_id,a.arm,a.weight,
 12.0 AS pre_h,
 greatest(0.,datediff('second',a.anchor_time,a.post_end)/3600.) AS post_h,
 c.pre_chem,c.post_chem,b.pre_cbc,b.post_cbc
 FROM a JOIN chemistry c USING(anchor_id) JOIN cbc b USING(anchor_id)
) TO '/srv/mimic-iv/studies/decision_feedback_20261025/risk_lab_anchor.parquet'
(FORMAT PARQUET,COMPRESSION ZSTD);
SELECT arm,round(sum(weight),1) n_weighted,
round(sum(weight*pre_chem)/(12*sum(weight)),4) chem_pre_per_h,
round(sum(weight*post_chem)/sum(weight*post_h),4) chem_post_per_h,
round(sum(weight*pre_cbc)/(12*sum(weight)),4) cbc_pre_per_h,
round(sum(weight*post_cbc)/sum(weight*post_h),4) cbc_post_per_h
FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/risk_lab_anchor.parquet')
GROUP BY 1 ORDER BY 1;
