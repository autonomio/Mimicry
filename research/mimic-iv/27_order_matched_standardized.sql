.read /srv/mimic-iv/studies/decision_feedback_20261025/10_definitions.sql
-- POE-order-only at-risk rate study; descriptive, not causal.
-- Patient-clustered influence-function SE conditional on strata/support.
WITH orders AS (SELECT DISTINCT hadm_id,ordertime FROM mimiciv_hosp.poe
WHERE order_type='General Care' AND order_subtype='Code status'),
t AS (SELECT e.*,greatest(0.,least(12.,
datediff('second',e.charttime,e.outtime)/3600.)) post_h
FROM event_candidates e JOIN orders p ON p.hadm_id=e.hadm_id
AND p.ordertime=e.charttime WHERE e.rn=1
AND e.charttime>=e.intime+INTERVAL '24 hours'),
m AS (SELECT t.subject_id,t.arm,t.first_careunit,t.sofa,
datediff('hour',t.intime,t.charttime) h,t.post_h,
count(v.charttime) FILTER(WHERE v.charttime<t.charttime
AND v.heart_rate IS NOT NULL) hr0,
count(v.charttime) FILTER(WHERE v.charttime>=t.charttime
AND v.heart_rate IS NOT NULL) hr1,
count(v.charttime) FILTER(WHERE v.charttime<t.charttime
AND coalesce(v.mbp,v.mbp_ni) IS NOT NULL) mp0,
count(v.charttime) FILTER(WHERE v.charttime>=t.charttime
AND coalesce(v.mbp,v.mbp_ni) IS NOT NULL) mp1
FROM t LEFT JOIN mimiciv_derived.vitalsign v ON v.stay_id=t.stay_id
AND v.charttime>=t.charttime-INTERVAL '12 hours'
AND v.charttime<least(t.outtime,t.charttime+INTERVAL '12 hours')
GROUP BY ALL),
b AS (SELECT subject_id,arm,
CASE WHEN first_careunit LIKE '%Neuro%' THEN 'NEURO'
WHEN first_careunit LIKE '%MICU%' THEN 'MICU'
WHEN first_careunit LIKE '%CVICU%' THEN 'CVICU'
WHEN first_careunit LIKE '%CCU%' THEN 'CCU'
WHEN first_careunit LIKE '%TSICU%' THEN 'TSICU'
WHEN first_careunit LIKE '%SICU%' THEN 'SICU' ELSE 'OTHER' END unit,
CASE WHEN sofa<4 THEN 0 WHEN sofa<8 THEN 1
WHEN sofa<12 THEN 2 ELSE 3 END sb,
CASE WHEN h<48 THEN 0 WHEN h<96 THEN 1
WHEN h<192 THEN 2 ELSE 3 END tb,
post_h,hr0,hr1,mp0,mp1 FROM m),
cells AS (SELECT arm,unit,sb,tb,count(*) n,
avg(post_h) avgh,
avg(hr0) hrpre,avg(mp0) mppre,
sum(hr1)/sum(post_h) hrpost,
sum(mp1)/sum(post_h) mppost,
sum(hr1)/sum(post_h)-avg(hr0)/12. dhr,
sum(mp1)/sum(post_h)-avg(mp0)/12. dmp,
sum(post_h) exposure
FROM b GROUP BY ALL),
pairs AS (SELECT a.unit,a.sb,a.tb,
a.n nt,c.n nc,
a.avgh a_h,c.avgh c_h,
a.hrpre a_hrpre,c.hrpre c_hrpre,
a.mppre a_mppre,c.mppre c_mppre,
a.hrpost a_hrpost,c.hrpost c_hrpost,
a.mppost a_mppost,c.mppost c_mppost,
a.dhr-c.dhr dif_hr,a.dmp-c.dmp dif_mp
FROM cells a JOIN cells c USING(unit,sb,tb)
WHERE a.arm='DNR' AND c.arm='CONTROL' AND a.n>=5 AND c.n>=5
AND a.exposure>10 AND c.exposure>10),
e AS (SELECT count(*) n_cells,sum(nt) n_t,sum(nc) n_c,
sum(nt*dif_hr)/sum(nt) dh,sum(nt*dif_mp)/sum(nt) dm FROM pairs),
u AS (SELECT b.subject_id,
sum(CASE WHEN arm='DNR'
THEN p.dif_hr-e.dh+(hr1-p.a_hrpost*post_h)/p.a_h-(hr0-p.a_hrpre)/12.
ELSE -(p.nt::DOUBLE/p.nc)*((hr1-p.c_hrpost*post_h)/p.c_h-(hr0-p.c_hrpre)/12.) END) uh,
sum(CASE WHEN arm='DNR'
THEN p.dif_mp-e.dm+(mp1-p.a_mppost*post_h)/p.a_h-(mp0-p.a_mppre)/12.
ELSE -(p.nt::DOUBLE/p.nc)*((mp1-p.c_mppost*post_h)/p.c_h-(mp0-p.c_mppre)/12.) END) um
FROM b JOIN pairs p USING(unit,sb,tb) CROSS JOIN e GROUP BY b.subject_id),
v AS (SELECT count(*) clusters,sum(uh*uh) sh,sum(um*um) sm FROM u)
SELECT e.n_cells,e.n_t,e.n_c,v.clusters,
round(e.dh,4) hr_rate_contrast,
round(sqrt(v.sh)/e.n_t,4) hr_cluster_se,
round(e.dh-1.96*sqrt(v.sh)/e.n_t,4) hr_ci_lo,
round(e.dh+1.96*sqrt(v.sh)/e.n_t,4) hr_ci_hi,
round(e.dm,4) map_rate_contrast,
round(sqrt(v.sm)/e.n_t,4) map_cluster_se,
round(e.dm-1.96*sqrt(v.sm)/e.n_t,4) map_ci_lo,
round(e.dm+1.96*sqrt(v.sm)/e.n_t,4) map_ci_hi
FROM e CROSS JOIN v;
