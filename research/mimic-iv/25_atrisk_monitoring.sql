.read /srv/mimic-iv/studies/decision_feedback_20261025/10_definitions.sql
-- At-risk observed person-time: death/discharge truncate post-event monitoring.
-- This is a descriptive rate, not an outcome under forced 12h survival.
WITH t AS (
 SELECT *,greatest(0.,least(12.,
 datediff('second',charttime,outtime)/3600.)) post_hours
 FROM event_candidates
 WHERE rn=1 AND charttime>=intime+INTERVAL '24 hours'
), counts AS (
 SELECT t.stay_id,t.arm,t.state,t.post_hours,
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
SELECT state,count(*) n,round(avg(post_hours),2) mean_observed_post_hours,
round(sum(hr0)/(12.*count(*)),3) hr_records_per_hour_pre,
round(sum(hr1)/sum(post_hours),3) hr_records_per_hour_post,
round(sum(hr1)/sum(post_hours)-sum(hr0)/(12.*count(*)),3) hr_rate_difference,
round(sum(map0)/(12.*count(*)),3) map_records_per_hour_pre,
round(sum(map1)/sum(post_hours),3) map_records_per_hour_post,
round(sum(map1)/sum(post_hours)-sum(map0)/(12.*count(*)),3) map_rate_difference
FROM counts GROUP BY 1 ORDER BY 1;
