-- Prior 18-hour observed-history augmentation of the six-hour Markov state.
-- Only previous landmarks are used; no post-index leakage.
-- The resulting augmented state is sufficient to simulate a finite-order
-- stochastic process if the matching lags are updated at every rollout step.
SET threads=4;
SET memory_limit='8GB';
SET preserve_insertion_order=false;
COPY (
 SELECT *,
 lag(hr,1) OVER w AS lag1_hr,
 lag(map,1) OVER w AS lag1_map,
 lag(rr,1) OVER w AS lag1_rr,
 lag(spo2,1) OVER w AS lag1_spo2,
 lag(n_hr,1) OVER w AS lag1_n_hr,
 lag(n_map,1) OVER w AS lag1_n_map,
 lag(prior_invasive_h,1) OVER w AS lag1_invasive,
 lag(prior_pressor_h,1) OVER w AS lag1_pressor,
 lag(hr,2) OVER w AS lag2_hr,
 lag(map,2) OVER w AS lag2_map,
 lag(prior_invasive_h,2) OVER w AS lag2_invasive,
 lag(prior_pressor_h,2) OVER w AS lag2_pressor,
 lag(prior_invasive_h,3) OVER w AS lag3_invasive,
 lag(prior_pressor_h,3) OVER w AS lag3_pressor
 FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/kernel_6h_transitions.parquet')
 WINDOW w AS (PARTITION BY stay_id ORDER BY step)
) TO '/srv/mimic-iv/studies/decision_feedback_20261025/kernel_history_6h.parquet'
(FORMAT PARQUET,COMPRESSION ZSTD);
SELECT count(*) n,
count(*) FILTER(WHERE step=4 AND lag1_hr IS NOT NULL) initial_leak_count,
count(*) FILTER(WHERE step>4 AND lag1_invasive IS NULL) unexpected_missing_lag1_support,
count(*) FILTER(WHERE step>5 AND lag2_pressor IS NULL) unexpected_missing_lag2_support
FROM read_parquet('/srv/mimic-iv/studies/decision_feedback_20261025/kernel_history_6h.parquet');
