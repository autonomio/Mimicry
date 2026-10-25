.read /srv/mimic-iv/studies/decision_feedback_20261025/10_definitions.sql
-- Restrict all index events to actual POE code-status order timestamps.
-- Still nonrandom; controls are clinician-selected reaffirmation orders.
WITH order_times AS (
 SELECT DISTINCT hadm_id,ordertime FROM mimiciv_hosp.poe
 WHERE order_type='General Care' AND order_subtype='Code status'
), t AS (
 SELECT e.*,greatest(0.,least(12.,
 datediff('second',e.charttime,e.outtime)/3600.)) post_hours
 FROM event_candidates e JOIN order_times p
 ON p.hadm_id=e.hadm_id AND p.ordertime=e.charttime
 WHERE e.rn=1 AND e.charttime>=e.intime+INTERVAL '24 hours'
), m AS (
 SELECT t.stay_id,t.arm,t.state,t.sofa,t.post_hours,
 count(v.charttime) FILTER(WHERE v.charttime<t.charttime
 AND v.heart_rate IS NOT NULL) hr0,
 count(v.charttime) FILTER(WHERE v.charttime>=t.charttime
 AND v.heart_rate IS NOT NULL) hr1,
 count(v.charttime) FILTER(WHERE v.charttime<t.charttime
 AND coalesce(v.mbp,v.mbp_ni) IS NOT NULL) map0,
 count(v.charttime) FILTER(WHERE v.charttime>=t.charttime
 AND coalesce(v.mbp,v.mbp_ni) IS NOT NULL) map1
 FROM t LEFT JOIN mimiciv_derived.vitalsign v
 ON v.stay_id=t.stay_id AND v.charttime>=t.charttime-INTERVAL '12 hours'
 AND v.charttime<least(t.outtime,t.charttime+INTERVAL '12 hours')
 GROUP BY ALL
)
SELECT state,count(*) n,round(avg(sofa),2) mean_sofa,
round(avg(post_hours),2) available_post_hours,
round(sum(hr0)/(12.*count(*)),3) hr_pre_per_h,
round(sum(hr1)/sum(post_hours),3) hr_post_per_h,
round(sum(hr1)/sum(post_hours)-sum(hr0)/(12.*count(*)),3) hr_rate_difference,
round(sum(map0)/(12.*count(*)),3) map_pre_per_h,
round(sum(map1)/sum(post_hours),3) map_post_per_h,
round(sum(map1)/sum(post_hours)-sum(map0)/(12.*count(*)),3) map_rate_difference
FROM m GROUP BY 1 ORDER BY 1;
