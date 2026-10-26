import {COLORS,STATUS_LABELS,nfmt,asPercent} from "./core.js";

/**
 * ClaimAudit: observed outcome contrast + failures of identification.
 * All probabilities are genuine reported conditional subgroup estimates.
 * No counterfactual "lives saved" visualization or implied causal effect.
 */
export function mountClaimAudit(root,release,{getSubtype}){
 function redraw(){
  const s=release.states.find(x=>x.id===getSubtype());
  const mortality=s.events.death_within_12h;
  const scale=.3; // FIXED shared 0–30% absolute risk scale across both states
  const strict=s.positivity;
  const fragility=strict.strict_max_smd>=.10;
  const n=s.n_dnr;
  root.innerHTML=
  '<div class="mv-causal-head"><div><span class="mv-kicker">OBSERVED 12-HOUR MORTALITY</span>'+
  '<h3>Different mortality. <em>Different underlying prognosis?</em></h3>'+
  '<p>Mortality after a new '+STATUS_LABELS[getSubtype()]+' order is much higher than in weighted eligible full-code risk sets. These people were not randomized to code status.</p></div>'+
  '<div class="mv-causal-arm-meta">Among '+nfmt(n)+' DNR events on measured common support</div></div>'+
  '<div class="mv-risk-scale"><span>0%</span><span>10%</span><span>20%</span><span>30%</span></div>'+
  '<div class="mv-risk-bars"><div class="mv-risk-line"><div class="mv-risk-name">'+STATUS_LABELS[getSubtype()]+'</div>'+
  '<div class="mv-risk-track"><span class="mv-risk-bar mv-risk-dnr" id="mv-claim-dnr-bar"></span></div>'+
  '<strong>'+asPercent(mortality.dnr,2)+'</strong></div>'+
  '<div class="mv-risk-line"><div class="mv-risk-name">Eligible full code</div>'+
  '<div class="mv-risk-track"><span class="mv-risk-bar mv-risk-control" id="mv-claim-control-bar"></span></div>'+
  '<strong>'+asPercent(mortality.full_code_control,2)+'</strong></div></div>'+
  '<p class="mv-causal-footnote">Observed 12-hour risk difference: '+nfmt(mortality.difference*100,2)+
  ' percentage points (fixed-weight approximate 95% interval '+nfmt(mortality.ci95[0]*100,2)+'–'+
  nfmt(mortality.ci95[1]*100,2)+'). <strong>This is an association, not an estimate of DNR-caused mortality.</strong>'+
  ' This figure uses a fixed 0–30% zero-based axis for both subtypes.</p>'+
  '<div class="mv-claim-ladder"><div class="mv-claim-step"><span class="mv-claim-step-num">01</span><div>'+
  '<strong>Recorded differences are real.</strong><p>The two observed groups have very different rates of death and treatment changes around the index. That is a description of the data.</p></div><span class="mv-claim-status mv-claim-status-known">Observed</span></div>'+
  '<div class="mv-claim-step"><span class="mv-claim-step-num">02</span><div>'+
  '<strong>Measured controls do not make patients exchangeable.</strong><p>'+
  nfmt(strict.risk_sets_under_two_effective_controls)+' of '+nfmt(n)+
  ' case-specific risk sets have fewer than two effective controls. The stricter comparison leaves '+
  nfmt(strict.strict_n)+' cases and reaches measured balance |SMD| = '+nfmt(strict.strict_max_smd,3)+
  (fragility?', above the 0.10 diagnostic.':' . Unobserved prognosis remains unresolved.')+
  '</p></div><span class="mv-claim-status mv-claim-status-fragile">'+(fragility?'Balance failed':'Uncertain')+'</span></div>'+
  '<div class="mv-claim-step"><span class="mv-claim-step-num">03</span><div>'+
  '<strong>Provider practice variation is not automatically an instrument.</strong><p>Only '+
  nfmt(release.provenance.ordering_provider_matches_hospital_admitting)+' of '+
  nfmt(release.provenance.icu_code_orders)+' ICU-time code-status orders were entered by the recorded hospital admitting provider. Neither identifier proves quasi-random assignment of the ICU decision-maker.</p></div>'+
  '<span class="mv-claim-status mv-claim-status-no">IV not validated</span></div>'+
  '<div class="mv-claim-step mv-claim-last"><span class="mv-claim-step-num">04</span><div>'+
  '<strong>We cannot attribute deaths to the DNR order.</strong><p>Unknown neurological prognosis, treatment intentions, patient preferences and simultaneous clinical decisions may explain large parts of the contrast. A DNR-only directive concerns CPR at arrest, not blanket withdrawal of life support.</p></div>'+
  '<span class="mv-claim-status mv-claim-status-no">Not identified</span></div></div>';
  const dnrBar=root.querySelector("#mv-claim-dnr-bar");
  const ctrlBar=root.querySelector("#mv-claim-control-bar");
  // Widths are absolute observed probabilities on ONE fixed axis, not
  // standardized coefficients or inferred counterfactual survival.
  dnrBar.style.width=(Math.min(mortality.dnr,scale)/scale*100)+"%";
  ctrlBar.style.width=(Math.min(mortality.full_code_control,scale)/scale*100)+"%";
  dnrBar.style.background=COLORS[getSubtype()];
 }
 redraw();
 return {setSubtype:redraw,destroy:()=>{}};
}
