.read /srv/mimic-iv/studies/decision_feedback_20261025/10_definitions.sql
-- Exploratory event-time measurement contrasts, complete 12h windows.
WITH m AS (
 SELECT t.stay_id,t.arm,t.state,t.sofa,
 count(v.charttime) FILTER(WHERE v.charttime<t.charttime AND v.heart_rate IS NOT NULL) hr0,
 count(v.charttime) FILTER(WHERE v.charttime>=t.charttime AND v.heart_rate IS NOT NULL) hr1,
 count(v.charttime) FILTER(WHERE v.charttime<t.charttime AND coalesce(v.mbp,v.mbp_ni) IS NOT NULL) map0,
 count(v.charttime) FILTER(WHERE v.charttime>=t.charttime AND coalesce(v.mbp,v.mbp_ni) IS NOT NULL) map1
 FROM event_landmarks t LEFT JOIN mimiciv_derived.vitalsign v
 ON v.stay_id=t.stay_id AND v.charttime>=t.charttime-INTERVAL '12 hours'
 AND v.charttime<t.charttime+INTERVAL '12 hours'
 GROUP BY ALL
)
SELECT state,count(*) n,round(avg(sofa),2) mean_sofa,
round(avg(hr0),3) pre_hr_recordings,
round(avg(hr1-hr0),3) delta_hr_recordings,
round(avg(map0),3) pre_map_recordings,
round(avg(map1-map0),3) delta_map_recordings
FROM m GROUP BY state ORDER BY state;
