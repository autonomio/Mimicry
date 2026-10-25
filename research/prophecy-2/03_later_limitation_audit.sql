-- Prophecy 2: DNR-only vs DNR/DNI and future limitation documentation.
-- Aggregate-only 12h windows after new POE status orders. No record-level export.
-- Missing subsequent DNI/CMO does not prove comfort goals were absent.
SET threads=4;
SET memory_limit='8GB';
WITH t AS (
 SELECT w.anchor_id,w.treated_id,w.anchor_time,w.outtime,w.deathtime,
 s.hadm_id,ty.first_nonfull_state subtype,
 least(w.outtime,coalesce(w.deathtime,w.outtime),
 w.anchor_time+INTERVAL '12 hours') AS end_t
 FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/risk_weighted_severityhistory.parquet') w
 JOIN read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/risk_treated.parquet') ty
 ON ty.stay_id=w.treated_id
 JOIN mimiciv_icu.icustays s ON s.stay_id=w.stay_id
 WHERE w.arm='DNR'
),
future AS (
 SELECT t.anchor_id,
 coalesce(max((c.dni=1)::INT),0) any_new_dni12,
 coalesce(max((c.cmo=1)::INT),0) any_new_cmo12
 FROM t LEFT JOIN mimiciv_derived.code_status c ON c.hadm_id=t.hadm_id
 AND c.charttime>t.anchor_time AND c.charttime<t.end_t
 GROUP BY t.anchor_id
),
extubations AS (
 SELECT t.anchor_id,min(p.starttime) first_extubation
 FROM t LEFT JOIN mimiciv_icu.procedureevents p
 ON p.stay_id=t.treated_id AND p.itemid=227194
 AND p.starttime>=t.anchor_time AND p.starttime<t.end_t
 GROUP BY t.anchor_id
)
SELECT subtype,count(*) n_cases,
 count(*) FILTER(WHERE f.any_new_dni12=1) later_dni_recorded,
 count(*) FILTER(WHERE f.any_new_cmo12=1) later_cmo_recorded,
 count(*) FILTER(WHERE e.first_extubation IS NOT NULL) extubation12,
 count(*) FILTER(WHERE e.first_extubation IS NOT NULL AND
 f.any_new_dni12=0 AND f.any_new_cmo12=0) extubation_no_later_documented_dni_cmo,
 count(*) FILTER(WHERE e.first_extubation IS NOT NULL AND
 t.deathtime BETWEEN e.first_extubation AND
 e.first_extubation+INTERVAL '2 hours') extubation_then_death_within2h
FROM t JOIN future f USING(anchor_id) JOIN extubations e USING(anchor_id)
GROUP BY subtype ORDER BY subtype;
