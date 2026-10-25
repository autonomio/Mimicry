-- MIMIC-IV 3.1, descriptive treatment delivery around risk-set landmarks.
-- IMPORTANT: Derived drug doses are chart-derived intervals; do not equate
-- with bedside infusion pump traces. No causal inference.
-- All patient-level outputs remain in restricted study directory on s0.
SET threads=6;
SET memory_limit='16GB';
SET preserve_insertion_order=false;

CREATE OR REPLACE TEMP TABLE b AS
SELECT x.anchor_id,x.treated_id,x.stay_id,x.subject_id,x.arm,x.weight,x.bin,
  x.observed_h,x.censored_h,
  a.anchor_time + x.bin*INTERVAL '4 hours' AS window_start,
  least(a.outtime,coalesce(a.deathtime,a.outtime),
        a.anchor_time + (x.bin+1)*INTERVAL '4 hours') AS window_end,
  least(a.outtime,coalesce(a.deathtime,a.outtime),
        a.anchor_time + (x.bin+1)*INTERVAL '4 hours',
        CASE WHEN a.arm='RISKSET' AND a.first_nonfull>a.anchor_time
             THEN a.first_nonfull ELSE a.outtime END) AS window_end_censored
FROM read_parquet(
 '/srv/mimic-iv/studies/decision_feedback_20261025/risk_event_bins.parquet') x
JOIN read_parquet(
 '/srv/mimic-iv/studies/decision_feedback_20261025/risk_weighted.parquet') a
USING(anchor_id);

-- De-duplicate identical infusion intervals rather than summing conflicting
-- dose assignments. Average and maximum dose are both retained for sensitivity.
-- The rare non-identical overlapping intervals may still overcount time;
-- exposure hours are capped at available ICU time and audited.
CREATE OR REPLACE TEMP TABLE pressor_clean AS
SELECT stay_id,starttime,endtime,
  avg(norepinephrine_equivalent_dose::DOUBLE) AS dose_mean,
  max(norepinephrine_equivalent_dose::DOUBLE) AS dose_max,
  count(*) AS n_source_rows,
  count(DISTINCT norepinephrine_equivalent_dose) AS n_distinct_doses
FROM mimiciv_derived.norepinephrine_equivalent_dose
WHERE endtime>starttime
GROUP BY stay_id,starttime,endtime;

CREATE OR REPLACE TEMP TABLE press_bin AS
SELECT b.anchor_id,b.bin,
  count(p.stay_id) AS overlapping_pressor_intervals,
  coalesce(sum(CASE WHEN p.stay_id IS NULL THEN 0 ELSE
    greatest(0,datediff('second',greatest(p.starttime,b.window_start),
                                 least(p.endtime,b.window_end))/3600.0)
    END),0) AS pressor_raw_h,
  coalesce(sum(CASE WHEN p.stay_id IS NULL THEN 0 ELSE
    greatest(0,datediff('second',greatest(p.starttime,b.window_start),
                                 least(p.endtime,b.window_end))/3600.0)
       *least(5.0,greatest(0.0,p.dose_mean))
    END),0) AS ne_mean_dose_hours,
  coalesce(sum(CASE WHEN p.stay_id IS NULL THEN 0 ELSE
    greatest(0,datediff('second',greatest(p.starttime,b.window_start),
                                 least(p.endtime,b.window_end))/3600.0)
       *least(5.0,greatest(0.0,p.dose_max))
    END),0) AS ne_max_dose_hours
FROM b LEFT JOIN pressor_clean p
  ON p.stay_id=b.stay_id AND p.starttime<b.window_end
  AND p.endtime>b.window_start
GROUP BY b.anchor_id,b.bin;

CREATE OR REPLACE TEMP TABLE vent_bin AS
SELECT b.anchor_id,b.bin,
 coalesce(sum(CASE WHEN v.ventilation_status='InvasiveVent' THEN
   greatest(0,datediff('second',greatest(v.starttime,b.window_start),
                                least(v.endtime,b.window_end))/3600.0)
   ELSE 0 END),0) AS invasive_raw_h,
 coalesce(sum(CASE WHEN v.ventilation_status='Tracheostomy' THEN
   greatest(0,datediff('second',greatest(v.starttime,b.window_start),
                                least(v.endtime,b.window_end))/3600.0)
   ELSE 0 END),0) AS trach_raw_h,
 coalesce(sum(CASE WHEN v.ventilation_status IN ('NonInvasiveVent','HFNC') THEN
   greatest(0,datediff('second',greatest(v.starttime,b.window_start),
                                least(v.endtime,b.window_end))/3600.0)
   ELSE 0 END),0) AS noninvasive_raw_h,
 coalesce(sum(CASE WHEN v.ventilation_status='SupplementalOxygen' THEN
   greatest(0,datediff('second',greatest(v.starttime,b.window_start),
                                least(v.endtime,b.window_end))/3600.0)
   ELSE 0 END),0) AS oxygen_raw_h,
 coalesce(count(v.stay_id),0) AS ventilation_overlap_intervals
FROM b LEFT JOIN mimiciv_derived.ventilation v
 ON v.stay_id=b.stay_id AND v.starttime<b.window_end
 AND v.endtime>b.window_start
GROUP BY b.anchor_id,b.bin;

COPY(
 SELECT b.anchor_id,b.treated_id,b.stay_id,b.subject_id,b.arm,b.weight,b.bin,
 b.observed_h,b.censored_h,
 least(b.observed_h,p.pressor_raw_h) AS pressor_h,
 least(b.observed_h,v.invasive_raw_h) AS invasive_h,
 least(b.observed_h,v.trach_raw_h) AS trach_h,
 least(b.observed_h,v.noninvasive_raw_h) AS noninvasive_h,
 least(b.observed_h,v.oxygen_raw_h) AS oxygen_h,
 -- Dose intensity averaged over ICU hours, including off-support hours
 p.ne_mean_dose_hours AS ne_mean_dose_hours,
 p.ne_max_dose_hours AS ne_max_dose_hours,
 p.pressor_raw_h,v.invasive_raw_h,v.ventilation_overlap_intervals,
 p.overlapping_pressor_intervals
 FROM b JOIN press_bin p USING(anchor_id,bin)
 JOIN vent_bin v USING(anchor_id,bin)
) TO '/srv/mimic-iv/studies/decision_feedback_20261025/risk_support_bins.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);

SELECT arm,bin,round(sum(weight*observed_h),1) n_patient_hours,
 round(sum(weight*pressor_h)/sum(weight*observed_h),4) pressor_fraction,
 round(sum(weight*invasive_h)/sum(weight*observed_h),4) invasive_vent_fraction,
 round(sum(weight*(invasive_h+trach_h))/sum(weight*observed_h),4) invasive_plus_trach_fraction,
 round(sum(weight*noninvasive_h)/sum(weight*observed_h),4) hfnc_niv_fraction,
 round(sum(weight*ne_mean_dose_hours)/sum(weight*observed_h),4) ne_eq_dose_per_patient_hour
FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/risk_support_bins.parquet')
GROUP BY arm,bin ORDER BY arm,bin;

SELECT arm,
 count(*) n_event_bins,
 count(*) FILTER (WHERE pressor_raw_h>observed_h+0.01) n_overlapping_pressor_bins,
 count(*) FILTER (WHERE invasive_raw_h>observed_h+0.01) n_overlapping_invasive_bins,
 round(max(ne_mean_dose_hours),3) maximum_dose_hours_in_bin,
 round(sum(weight*observed_h),1) observed_weighted_hours
FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/risk_support_bins.parquet')
GROUP BY arm ORDER BY arm;
