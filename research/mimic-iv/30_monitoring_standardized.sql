.read /srv/mimic-iv/studies/decision_feedback_20261025/10_definitions.sql
-- Case-mix standardization, not causal treatment effect.
-- Unit x day-1 SOFA bin x ICU elapsed-time bin, >=5 events per arm per cell.
WITH measurements AS (
 SELECT t.subject_id,t.arm,t.first_careunit,t.sofa,
 datediff('hour',t.intime,t.charttime) hours_in_icu,
 count(v.charttime) FILTER(WHERE v.charttime<t.charttime AND v.heart_rate IS NOT NULL) hr0,
 count(v.charttime) FILTER(WHERE v.charttime>=t.charttime AND v.heart_rate IS NOT NULL) hr1,
 count(v.charttime) FILTER(WHERE v.charttime<t.charttime AND coalesce(v.mbp,v.mbp_ni) IS NOT NULL) map0,
 count(v.charttime) FILTER(WHERE v.charttime>=t.charttime AND coalesce(v.mbp,v.mbp_ni) IS NOT NULL) map1
 FROM event_landmarks t LEFT JOIN mimiciv_derived.vitalsign v
 ON v.stay_id=t.stay_id AND v.charttime>=t.charttime-INTERVAL '12 hours'
 AND v.charttime<t.charttime+INTERVAL '12 hours'
 GROUP BY ALL
), b AS (
 SELECT subject_id,arm,
 CASE WHEN first_careunit LIKE '%Neuro%' THEN 'NEURO'
 WHEN first_careunit LIKE '%MICU%' THEN 'MICU'
 WHEN first_careunit LIKE '%CVICU%' THEN 'CVICU'
 WHEN first_careunit LIKE '%CCU%' THEN 'CCU'
 WHEN first_careunit LIKE '%TSICU%' THEN 'TSICU'
 WHEN first_careunit LIKE '%SICU%' THEN 'SICU' ELSE 'OTHER' END unit,
 CASE WHEN sofa<4 THEN 0 WHEN sofa<8 THEN 1 WHEN sofa<12 THEN 2 ELSE 3 END sb,
 CASE WHEN hours_in_icu<48 THEN 0 WHEN hours_in_icu<96 THEN 1
 WHEN hours_in_icu<192 THEN 2 ELSE 3 END tb,
 hr1-hr0 dh,map1-map0 dm FROM measurements
), cells AS (
 SELECT arm,unit,sb,tb,count(*) n,avg(dh) mh,avg(dm) mm
 FROM b GROUP BY ALL
), pairs AS (
 SELECT t.unit,t.sb,t.tb,t.n nt,c.n nc,c.mh ch,c.mm cm,t.mh th,t.mm tm
 FROM cells t JOIN cells c USING(unit,sb,tb)
 WHERE t.arm='DNR' AND c.arm='CONTROL' AND t.n>=5 AND c.n>=5
), effect AS (
 SELECT count(*) n_cells,sum(nt) n_dnr,sum(nc) n_control,
 sum(nt*(th-ch))/sum(nt) dh,sum(nt*(tm-cm))/sum(nt) dm FROM pairs
), u AS (
 SELECT b.subject_id,
 sum(CASE WHEN b.arm='DNR' THEN b.dh-p.ch-e.dh
 ELSE -(p.nt::DOUBLE/p.nc)*(b.dh-p.ch) END) uh,
 sum(CASE WHEN b.arm='DNR' THEN b.dm-p.cm-e.dm
 ELSE -(p.nt::DOUBLE/p.nc)*(b.dm-p.cm) END) um
 FROM b JOIN pairs p USING(unit,sb,tb) CROSS JOIN effect e
 GROUP BY b.subject_id
), v AS (
 SELECT count(*) n_patient_clusters,sum(uh*uh) vh,sum(um*um) vm FROM u
)
SELECT e.n_cells,e.n_dnr,e.n_control,v.n_patient_clusters,
round(e.dh,3) hr_delta,round(sqrt(v.vh)/e.n_dnr,3) hr_se,
round(e.dh-1.96*sqrt(v.vh)/e.n_dnr,3) hr_ci_lo,
round(e.dh+1.96*sqrt(v.vh)/e.n_dnr,3) hr_ci_hi,
round(e.dm,3) map_delta,round(sqrt(v.vm)/e.n_dnr,3) map_se,
round(e.dm-1.96*sqrt(v.vm)/e.n_dnr,3) map_ci_lo,
round(e.dm+1.96*sqrt(v.vm)/e.n_dnr,3) map_ci_hi
FROM effect e CROSS JOIN v;
