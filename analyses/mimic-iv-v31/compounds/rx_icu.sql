-- In-ICU intake (MIMIC-IV v3.1, s0, read-only).
-- First ICU stays: eMAR Administered drugs within the stay window +
-- ingredient-level and input-level IV items by stay. Aggregates only.
CREATE TEMP TABLE fst AS
SELECT s.stay_id, s.hadm_id, s.subject_id, s.intime, s.outtime,
       CASE WHEN p.dod BETWEEN s.intime AND s.outtime THEN 1 ELSE 0 END AS died_icu,
       a.hospital_expire_flag AS died_hosp
FROM mimiciv_icu.icustays s
JOIN mimiciv_hosp.patients p USING (subject_id)
JOIN mimiciv_hosp.admissions a USING (hadm_id)
QUALIFY row_number() OVER (PARTITION BY s.hadm_id ORDER BY s.intime) = 1;
CREATE TEMP TABLE emrx AS
SELECT f.stay_id, f.died_icu, f.died_hosp, e.medication AS drug
FROM fst f
JOIN mimiciv_hosp.emar e
  ON e.subject_id = f.subject_id
 AND e.charttime >= f.intime AND e.charttime < f.outtime
WHERE e.event_txt = 'Administered';
CREATE TEMP TABLE ingx AS
SELECT f.stay_id, f.died_icu, f.died_hosp, i.itemid
FROM fst f JOIN mimiciv_icu.ingredientevents i USING (stay_id);
CREATE TEMP TABLE inpx AS
SELECT f.stay_id, f.died_icu, f.died_hosp, i.itemid
FROM fst f JOIN mimiciv_icu.inputevents i USING (stay_id);
SELECT 'Q1_cov' AS q,
  (SELECT COUNT(DISTINCT stay_id) FROM emrx) AS stays_emar,
  (SELECT COUNT(DISTINCT stay_id) FROM ingx) AS stays_ing,
  (SELECT COUNT(DISTINCT stay_id) FROM inpx) AS stays_inp,
  (SELECT COUNT(*) FROM fst) AS stays_total;
SELECT 'Q2_emar' AS q, drug, died_icu, died_hosp, COUNT(DISTINCT stay_id) AS n
FROM emrx GROUP BY 1, 2, 3, 4;
SELECT 'Q3_ing' AS q, itemid, died_icu, died_hosp, COUNT(DISTINCT stay_id) AS n
FROM ingx GROUP BY 1, 2, 3, 4;
SELECT 'Q4_inp' AS q, itemid, died_icu, died_hosp, COUNT(DISTINCT stay_id) AS n
FROM inpx GROUP BY 1, 2, 3, 4;
SELECT 'Q5_denom' AS q, died_icu, died_hosp, COUNT(*) AS n FROM fst GROUP BY 1, 2, 3;
