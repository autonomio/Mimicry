-- MIMIC-IV v3.1 code-status data provenance, exploratory audit.
-- All tables read-only; aggregate results only.
SET threads=4;
SET memory_limit='8GB';
SELECT
  count(*) AS n_icu_stays,
  count(DISTINCT subject_id) AS n_icu_patients,
  count(DISTINCT hadm_id) AS n_admissions
FROM mimiciv_icu.icustays;
SELECT
  count(*) AS n_code_records,
  count(*) FILTER (WHERE stay_id IS NULL) AS outside_icu
FROM mimiciv_derived.code_status;
