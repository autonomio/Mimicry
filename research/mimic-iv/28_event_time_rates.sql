.read /srv/mimic-iv/studies/decision_feedback_20261025/10_definitions.sql
-- Four-hour event-time risk-set charting rates. Bin 0 begins at order time.
WITH orders AS (SELECT DISTINCT hadm_id,ordertime FROM mimiciv_hosp.poe
 WHERE order_type='General Care' AND order_subtype='Code status'),
t AS (SELECT e.* FROM event_candidates e JOIN orders p
 ON p.hadm_id=e.hadm_id AND p.ordertime=e.charttime
 WHERE e.rn=1 AND e.charttime>=e.intime+INTERVAL '24 hours'),
windows AS (
 SELECT t.stay_id,t.arm,k.i AS bin,
 greatest(t.intime,t.charttime+k.i*INTERVAL '4 hours') start_t,
 least(t.outtime,t.charttime+(k.i+1)*INTERVAL '4 hours') end_t
 FROM t CROSS JOIN range(-6,3) k(i)
), m AS (
 SELECT w.stay_id,w.arm,w.bin,
 greatest(0.,datediff('second',w.start_t,w.end_t)/3600.) exposed_h,
 count(v.charttime) FILTER(WHERE v.heart_rate IS NOT NULL) n_hr,
 count(v.charttime) FILTER(WHERE coalesce(v.mbp,v.mbp_ni) IS NOT NULL) n_map
 FROM windows w LEFT JOIN mimiciv_derived.vitalsign v
 ON v.stay_id=w.stay_id AND v.charttime>=w.start_t AND v.charttime<w.end_t
 GROUP BY ALL
)
SELECT arm,4*bin AS hours_from_order,count(*) n_stays,
round(sum(exposed_h),1) observed_icu_hours,
round(sum(n_hr)/nullif(sum(exposed_h),0),3) hr_records_per_icu_hour,
round(sum(n_map)/nullif(sum(exposed_h),0),3) map_records_per_icu_hour
FROM m GROUP BY arm,bin ORDER BY arm,bin;
