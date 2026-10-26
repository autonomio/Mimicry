-- Prophecy 2: DNR phenotype and physician-instrument provenance audit.
-- MIMIC-IV v3.1, source DB READ ONLY, aggregate-only results.
-- This audits feasibility; does NOT validate IV exclusion or LATE.
SET threads=4;
SET memory_limit='8GB';
SELECT 'all_icustays' measure,count(*) n
FROM mimiciv_icu.icustays
UNION ALL SELECT 'all_derived_code_status_rows',count(*) FROM mimiciv_derived.code_status
UNION ALL SELECT 'unassigned_icu_stay_code_status_rows',count(*)
 FROM mimiciv_derived.code_status WHERE stay_id IS NULL;

WITH entry AS (
 SELECT s.stay_id,
 arg_max(CASE WHEN c.cmo=1 THEN 'CMO'
 WHEN c.dnr=1 AND c.dni=1 THEN 'DNR_DNI'
 WHEN c.dnr=1 THEN 'DNR_ONLY'
 WHEN c.dni=1 THEN 'DNI_ONLY'
 WHEN c.fullcode=1 THEN 'FULL'
 ELSE 'OTHER' END,c.charttime) AS state
 FROM mimiciv_icu.icustays s
 LEFT JOIN mimiciv_derived.code_status c ON s.hadm_id=c.hadm_id
 AND c.charttime<=s.intime
 GROUP BY 1
)
SELECT coalesce(state,'UNKNOWN_PRIOR') status_on_icu_entry,count(*) n
FROM entry GROUP BY 1 ORDER BY n DESC;

WITH events AS (
 SELECT hadm_id,charttime,
 count(DISTINCT concat_ws(':',fullcode,dnr,dni,cmo)) n_distinct_status
 FROM mimiciv_derived.code_status GROUP BY 1,2
)
SELECT count(*) FILTER(WHERE n_distinct_status>1) contradictory_timestamp_groups,
 count(DISTINCT hadm_id) FILTER(WHERE n_distinct_status>1) admissions_with_ties
FROM events;

WITH orders AS (
 SELECT s.hadm_id,s.stay_id,p.order_provider_id,a.admit_provider_id,
 p.ordertime
 FROM mimiciv_hosp.poe p JOIN mimiciv_icu.icustays s
 ON s.hadm_id=p.hadm_id AND p.ordertime>=s.intime AND p.ordertime<=s.outtime
 JOIN mimiciv_hosp.admissions a ON a.hadm_id=s.hadm_id
 WHERE p.order_type='General Care' AND p.order_subtype='Code status'
)
SELECT count(*) n_icu_code_orders,
 count(*) FILTER(WHERE order_provider_id=admit_provider_id) n_same_as_admitting_provider,
 count(*) FILTER(WHERE order_provider_id IS NULL) n_missing_order_provider,
 count(*) FILTER(WHERE admit_provider_id IS NULL) n_missing_admitting_provider,
 count(DISTINCT order_provider_id) n_distinct_ordering_providers,
 count(DISTINCT admit_provider_id) n_distinct_admitting_providers
FROM orders;

-- A strong leave-one-out physician preference association is merely
-- instrument RELEVANCE. "order_provider_id" is recorded at the DNR
-- event and cannot be assumed pre-assigned. "admit_provider_id"
-- is hospital admitting provider, not automatically the ICU attending.
-- Patient preferences, physician co-interventions and case selection
-- are unobserved; therefore this script does not estimate DNR LATE.
