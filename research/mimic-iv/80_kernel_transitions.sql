-- Observational stochastic transition kernel: six-hour ICU grid.
-- Requires audited, read-only MIMIC-IV v3.1 70_multistate_panel.sql output.
-- A state is the observed/documented history at a landmark, not latent truth.
-- Terminal DEATH/EXIT absorb; otherwise next code, support, recording,
-- and observed physiology form a sequential conditional joint law.
-- The true next code and future measurements are OUTCOMES only.
SET threads=6;
SET memory_limit='14GB';
SET preserve_insertion_order=false;
COPY (
 WITH p AS (
 SELECT *,
  LEAD(step) OVER(PARTITION BY stay_id ORDER BY step) next_step,
  LEAD(code_state) OVER(PARTITION BY stay_id ORDER BY step) next_status_at_landmark,
  LEAD(code_age_h) OVER(PARTITION BY stay_id ORDER BY step) next_code_age_h,
  LEAD(hr) OVER(PARTITION BY stay_id ORDER BY step) next_hr_check,
  LEAD(map) OVER(PARTITION BY stay_id ORDER BY step) next_map_check,
  LEAD(rr) OVER(PARTITION BY stay_id ORDER BY step) next_rr,
  LEAD(spo2) OVER(PARTITION BY stay_id ORDER BY step) next_spo2,
  LEAD(n_hr) OVER(PARTITION BY stay_id ORDER BY step) next_hr_count_check,
  LEAD(n_map) OVER(PARTITION BY stay_id ORDER BY step) next_map_count_check,
  LEAD(n_spo2) OVER(PARTITION BY stay_id ORDER BY step) next_spo2_count_check,
  LEAD(n_rr) OVER(PARTITION BY stay_id ORDER BY step) next_rr_count_check,
  LEAD(prior_invasive_h) OVER(PARTITION BY stay_id ORDER BY step) next_invasive_check,
  LEAD(prior_pressor_h) OVER(PARTITION BY stay_id ORDER BY step) next_pressor_check
 FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/multistate_6h_panel.parquet')
 )
 SELECT subject_id,stay_id,era,unit_group,step,age,sofa,
  code_state,code_age_h,hr,map,rr,spo2,n_hr,n_map,n_spo2,n_rr,
  prior_invasive_h,prior_pressor_h,
  CASE WHEN death_within6h THEN 'DEATH'
       WHEN exit_within6h THEN 'EXIT'
       ELSE 'STAY' END AS terminal_outcome,
  CASE WHEN NOT death_within6h AND NOT exit_within6h
       THEN next_status_at_landmark ELSE NULL END next_code,
  CASE WHEN NOT death_within6h AND NOT exit_within6h
       THEN next_code_age_h ELSE NULL END next_code_age_h,
  next_icu_hours,next_invasive_h,next_pressor_h,
  next_n_hr,next_n_map,next_spo2_count_check AS next_n_spo2,next_n_rr,next_mean_hr,next_mean_map,
  next_rr,next_spo2,
  next_step,next_hr_check,next_map_check,
  next_hr_count_check,next_map_count_check,next_spo2_count_check,next_rr_count_check,
  next_invasive_check,next_pressor_check,
  within_bin_collision,code_document_change_within6h
 FROM p
 WHERE step<27
) TO '/srv/mimic-iv/studies/decision_feedback_20261025/kernel_6h_transitions.parquet'
(FORMAT PARQUET,COMPRESSION ZSTD);
SELECT era,terminal_outcome,count(*) n
FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/kernel_6h_transitions.parquet')
GROUP BY 1,2 ORDER BY 1,2;
SELECT count(*) n_rows,
 count(*) FILTER(WHERE terminal_outcome='STAY' AND next_step IS NULL) missing_next_step,
 count(*) FILTER(WHERE terminal_outcome='STAY' AND next_step<>step+1) missing_immediate_next,
 count(*) FILTER(WHERE terminal_outcome='STAY' AND next_code IS NULL) missing_next_code,
 count(*) FILTER(WHERE terminal_outcome='STAY' AND next_icu_hours<5.9999) short_nonterminal_exposure,
 count(*) FILTER(WHERE terminal_outcome='DEATH' AND next_step IS NOT NULL) death_with_next_row,
 count(*) FILTER(WHERE terminal_outcome='EXIT' AND next_step IS NOT NULL) exit_with_next_row,
 count(*) FILTER(WHERE terminal_outcome='STAY' AND next_n_hr<>next_hr_count_check) count_mismatch,
 count(*) FILTER(WHERE terminal_outcome='STAY' AND next_n_spo2<>next_spo2_count_check) spo2_count_mismatch,
 count(*) FILTER(WHERE terminal_outcome='STAY' AND next_n_rr<>next_rr_count_check) rr_count_mismatch,
 count(*) FILTER(WHERE terminal_outcome='STAY' AND abs(next_invasive_h-next_invasive_check)>.01) vent_mismatch,
 count(*) FILTER(WHERE terminal_outcome='STAY' AND abs(next_pressor_h-next_pressor_check)>.01) press_mismatch
FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/kernel_6h_transitions.parquet');
