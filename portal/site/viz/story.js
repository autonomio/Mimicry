import {COLORS,STATUS_LABELS,nfmt,esc,validateVizData} from "./core.js";
import {mountCohortSpace} from "./cohort-space.js";
import {mountEventTime} from "./event-time.js";
import {mountEvidenceMatrix} from "./evidence-matrix.js";
import {mountClaimAudit} from "./claim-audit.js";

/**
 * A field guide is an ordered scientific argument: define -> select ->
 * observe -> challenge -> conclude. Charts are reusable independently.
 */
export async function mountDnrStory(root,release){
 const response=await fetch("/data/viz/prophecy2-observations-v1.json",{cache:"no-cache"});
 if(!response.ok)throw new Error("The verified aggregate visual dataset could not be loaded.");
 const data=await response.json();
 validateVizData(data,release);
 let subtype="DNR_ONLY",stageTimer=null;
 const archive="/tracks/prophecy-2/releases/"+encodeURIComponent(release.id)+"/";
 const template=[
 '<section class="mv-hero" id="mv-start"><div class="mv-wrap mv-hero-grid"><div>',
 '<div class="mv-meta">MIMICRY <span>/</span> PROPHECY 2 <span>/</span> A VISUAL INVESTIGATION</div>',
 '<h1>A small order.<br><em>A very big inference.</em></h1>',
 '<p class="mv-lead">When clinicians record <strong>do not resuscitate</strong> in intensive care, what changes next? And how much can the medical record actually tell us about why?</p>',
 '<div class="mv-hero-actions"><a class="mv-action" href="#mv-scene-definition">Follow the evidence <span aria-hidden="true">↓</span></a>',
 '<a class="mv-quiet-link" href="'+archive+'">Examine source estimates ↗</a></div>',
 '<div class="mv-hero-footnote">MIMIC-IV v3.1 · '+nfmt(release.cohort.eligible_first_dnr)+' eligible first DNR orders · Observational research · Not clinical advice</div>',
 '</div><div class="mv-hero-symbol" aria-hidden="true"><div class="mv-orbit mv-orbit-1"></div><div class="mv-orbit mv-orbit-2"></div><div class="mv-orbit mv-orbit-3"></div><span class="mv-letter">DNR</span><span class="mv-symbol-note">A CLINICAL DIRECTIVE ≠ A CAUSAL EFFECT</span></div></div></section>',
 '<nav class="mv-chapters" aria-label="Story chapters"><div class="mv-wrap mv-chapter-inner">',
 '<span class="mv-chapter-brand">PROPHECY <b>2</b></span>',
 '<a href="#mv-scene-definition" data-mv-chapter="1"><span>01</span> The meaning</a>',
 '<a href="#mv-scene-selection" data-mv-chapter="2"><span>02</span> The selection</a>',
 '<a href="#mv-scene-timing" data-mv-chapter="3"><span>03</span> The moment</a>',
  '<a href="#mv-scene-sensitivity" data-mv-chapter="4"><span>04</span> The evidence</a>',
 '<a href="#mv-scene-causality" data-mv-chapter="5"><span>05</span> The limit</a>',
 '<span class="mv-chapter-serial">M / 02</span>',
 '</div></nav>',
 '<section class="mv-scene mv-definition" id="mv-scene-definition" data-mv-scene="1"><div class="mv-wrap">',
 '<div class="mv-scene-lead"><span class="mv-kicker">01 — DEFINE THE EXPOSURE</span><h2>First, name the <em>decision.</em></h2>',
 '<p>The words on the order matter. DNR applies to CPR at cardiac arrest. It does not, by itself, direct staff to withdraw ventilation, stop medications, or provide comfort-only care.</p></div>',
 '<div class="mv-directive-grid">',
 '<article class="mv-directive mv-directive-full"><span>DOCUMENTED BASELINE</span><h3>Full code</h3><p>No documented CPR limitation in this recorded state. Missing documentation is <b>not</b> assumed to mean full code.</p><div class="mv-directive-foot">Known documented comparator</div></article>',
 '<article class="mv-directive mv-directive-dnr"><span>PRIMARY RESEARCH QUESTION</span><h3>DNR only</h3><p>Do not attempt CPR at arrest. Other decisions about treatment need separate evidence.</p><div class="mv-directive-foot">CPR limitation</div></article>',
 '<article class="mv-directive mv-directive-dni"><span>DIFFERENT CLINICAL EXPOSURE</span><h3>DNR + DNI</h3><p>CPR and intubation limitations recorded together. It must not be pooled with isolated DNR.</p><div class="mv-directive-foot">CPR + intubation limitations</div></article>',
 '</div><p class="mv-definition-note">Comfort-measures-only is a separate treatment-goals state, not a synonym for DNR. These are recorded directives, not a complete picture of the patient’s wishes.</p>',
 '</div></section>',
 '<section class="mv-scene mv-selection" id="mv-scene-selection" data-mv-scene="2"><div class="mv-wrap">',
 '<div class="mv-scene-lead"><span class="mv-kicker">02 — WHERE THE COMPARISON BEGINS TO BREAK</span>',
 '<h2>Watch the study <em>shrink.</em></h2>',
 '<p>Each circle represents an aggregated ICU group, never an individual. Its position shows mean recorded illness severity and the fraction of ICU time spent on invasive ventilation just before the order. Its area represents the number of orders.</p></div>',
 '<div class="mv-story-control-head"><div><span class="mv-mono">ANALYTIC STAGE — NOT PATIENT TIME</span><div class="mv-stage-buttons" role="group" aria-label="Study selection stage">',
 data.cohort_bubbles.stages.map((s,i)=>'<button type="button" data-mv-stage="'+esc(s.id)+'" aria-pressed="'+(i===0?'true':'false')+'" class="'+(i===0?'active':'')+'"><span>0'+(i+1)+'</span>'+esc(s.label)+'</button>').join(""),
 '</div></div><button id="mv-stage-play" type="button" class="mv-play" aria-pressed="false">▶ Play study selection</button></div>',
 '<div class="mv-chart-frame mv-chart-frame-bubble"><div id="mv-space-plot" class="mv-space-plot"></div>',
 '<aside class="mv-space-aside"><div id="mv-stage-summary" class="mv-stage-summary" aria-live="polite"></div>',
 '<div class="mv-legend"><span><i class="mv-dot mv-dnr"></i>DNR only</span><span><i class="mv-dot mv-dni"></i>DNR + DNI</span></div>',
 '<div id="mv-space-detail" class="mv-space-detail" aria-live="polite"></div>',
 '<p id="mv-space-censor" class="mv-chart-caution"></p></aside></div>',
 '<div class="mv-under-plot"><p>The circles move because <strong>we change the eligibility rules</strong>, not because individual patients travel along these axes. Stricter overlap can make a subgroup disappear.</p>',
 '<details><summary>Read the plotted aggregate table</summary><div class="mv-table-scroll"><table id="mv-space-table"></table></div></details></div>',
 '</div></section>',
 '<section class="mv-scene mv-timing" id="mv-scene-timing" data-mv-scene="3"><div class="mv-wrap">',
 '<div class="mv-scene-lead"><span class="mv-kicker">03 — TIME ZERO IS NOT RANDOM</span><h2>The order is written. <em>What moves?</em></h2>',
 '<p>Two aggregate clinical histories are aligned to the order—or an equivalent ICU elapsed time for eligible full-code controls. Explore four-hour observed bins. Rates can change before the order, because clinicians respond to evolving illness.</p></div>',
 '<div class="mv-subtype-shell"><div><span class="mv-mono">DOCUMENTED ORDER</span><div class="mv-subtype-controls" role="group" aria-label="Compare documented code status">',
 '<button type="button" data-mv-subtype="DNR_ONLY" class="active" aria-pressed="true"><i class="mv-dot mv-dnr"></i> DNR only</button>',
 '<button type="button" data-mv-subtype="DNR_DNI" aria-pressed="false"><i class="mv-dot mv-dni"></i> DNR + DNI</button>',
 '</div></div><p id="mv-subtype-deck">Start with isolated DNR to avoid pooling different clinical directives.</p></div>',
 '<div class="mv-metric-controls" id="mv-metric-controls" role="group" aria-label="Treatment or monitoring variable">',
 '<button type="button" data-mv-metric="invasive_ventilation" aria-pressed="true" class="active">Invasive ventilation</button>',
 '<button type="button" data-mv-metric="vasopressor_exposure" aria-pressed="false">Vasopressors</button>',
 '<button type="button" data-mv-metric="map_recording" aria-pressed="false">Blood-pressure recording</button>',
 '</div>',
 '<div class="mv-chart-frame mv-chart-frame-time"><div id="mv-time-plot" class="mv-time-plot"></div>',
 '<div class="mv-time-tools"><div class="mv-time-tools-head"><span class="mv-mono">RECORDED FOUR-HOUR WINDOW</span><strong id="mv-bin-time"></strong></div>',
 '<div class="mv-slider-row"><button id="mv-time-play" type="button" class="mv-play" aria-pressed="false">▶ Play the recorded bins</button>',
 '<input type="range" id="mv-timeline" min="0" max="8" value="5" step="1" aria-label="Four-hour event-time window" /></div>',
 '<div class="mv-timeline-ends"><span>−24h before</span><b>0 · ORDER</b><span>+12h after</span></div>',
 '<div id="mv-time-readout" class="mv-time-readout" aria-live="polite"></div>',
 '<p id="mv-time-caution" class="mv-chart-caution"></p>',
 '</div></div>',
 '<div class="mv-under-plot"><p>These are clinical <strong>recording and treatment rates</strong> among patients still observed in ICU—not causal responses to the order. The individual four-hour bins have no published pointwise confidence intervals.</p>',
 '<details><summary>Inspect every recorded time bin</summary><div class="mv-table-scroll"><table id="mv-time-table"></table></div></details></div>',
 '</div></section>',
 '<section class="mv-scene mv-inference" id="mv-scene-sensitivity" data-mv-scene="4"><div class="mv-wrap">',
 '<div class="mv-scene-lead"><span class="mv-kicker">04 — THE CLAIM IS THE DIFFICULT PART</span>',
 '<h2>Now try to <em>break the finding.</em></h2>',
 '<p>Pick an estimate. Compare earlier negative-control timing, the window around the order, the primary analysis and stricter control overlap. The figures change because <strong>the analysis design changes</strong>.</p></div>',
 '<div id="mv-evidence-matrix" class="mv-matrix-mount"></div>',
 '</div></section>',
 '<section class="mv-scene mv-causality" id="mv-scene-causality" data-mv-scene="5"><div class="mv-wrap">',
 '<div class="mv-scene-lead"><span class="mv-kicker">05 — THE CAUSAL QUESTION</span><h2>Did the order <em>cause</em> the deaths?</h2>'+
 '<p>The mortality difference is striking. It cannot answer the causal question. Follow four stages of inference and see why the conclusion stops short of attributing deaths to a CPR limitation.</p></div>',
 '<div id="mv-claim-audit"></div>',
 '<div class="mv-inference-finish"><div><span class="mv-kicker">THE IDENTIFICATION BOUNDARY</span><h3>We observe decisions.<br>We do not observe every reason.</h3></div>',
 '<div class="mv-claims"><article><span>SUPPORTED OBSERVATION</span><p>Non-CPR treatment and physiological monitoring change around documented DNR decisions.</p></article>',
 '<article><span>FRAGILE ASSUMPTION</span><p>Measured case-mix similarity cannot remove unrecorded prognosis, patient wishes or clinical intentions.</p></article>',
 '<article><span>NOT IDENTIFIED</span><p>The records do not establish how many deaths, if any, were caused by the isolated DNR order.</p></article></div></div>',
 '<div class="mv-provenance"><span>DATA: MIMIC-IV v3.1 · AGGREGATED STATISTICS ONLY</span>',
 '<p>Data extracted from the existing secure ICU cohort. Aggregates below groups of 30 are suppressed from the cohort map. Conditional intervals do not include all model-selection or weight-estimation uncertainty.</p>',
 '<a href="'+archive+'">Read the full DNR research release ↗</a> <a href="/tracks/prophecy-2/methods/">Research design and limitations ↗</a>',
 '</div></div></section>'
 ].join("");
 root.innerHTML=template;
 const getSubtype=()=>subtype;
 function setSubtype(next){
  subtype=next;
  document.querySelectorAll("[data-mv-subtype]").forEach(b=>{
   const on=b.dataset.mvSubtype===next;b.classList.toggle("active",on);
   b.setAttribute("aria-pressed",String(on));
  });
  const s=release.states.find(x=>x.id===next);
  document.querySelector("#mv-subtype-deck").textContent=
   nfmt(s.n_dnr)+" orders on measured common support · "+
   s.meaning+". These are selected decisions, not randomized exposures.";
  cohort.setSubtype(next);timing.setSubtype();matrix.setSubtype();claims.setSubtype();
 }
 const cohort=mountCohortSpace(document.querySelector("#mv-space-plot"),
   data,{getSubtype,onSubtypeChange:setSubtype});
 const timing=mountEventTime(document.querySelector("#mv-time-plot"),
   data,release,{getSubtype});
 const matrix=mountEvidenceMatrix(document.querySelector("#mv-evidence-matrix"),
   release,{getSubtype});
 const claims=mountClaimAudit(document.querySelector("#mv-claim-audit"),release,{getSubtype});
 document.querySelectorAll("[data-mv-stage]").forEach(b=>
   b.addEventListener("click",()=>{stopStage();cohort.setStage(b.dataset.mvStage);}));
 document.querySelectorAll("[data-mv-subtype]").forEach(b=>
   b.addEventListener("click",()=>setSubtype(b.dataset.mvSubtype)));
 const stagePlay=document.querySelector("#mv-stage-play");
 const order=["eligible","supported","strict"];
 function stopStage(){
  if(stageTimer)clearInterval(stageTimer);stageTimer=null;
  stagePlay.textContent="▶ Play study selection";stagePlay.setAttribute("aria-pressed","false");
 }
 stagePlay.addEventListener("click",()=>{
  if(stageTimer){stopStage();return;}
  const idx=order.indexOf(cohort.getStage());
  if(idx===order.length-1)cohort.setStage("eligible");
  stagePlay.textContent="Ⅱ Pause";stagePlay.setAttribute("aria-pressed","true");
  stageTimer=setInterval(()=>{
   const current=order.indexOf(cohort.getStage());
   if(current>=order.length-1){stopStage();return;}
   cohort.setStage(order[current+1]);
  },1500);
 });
 setSubtype(subtype);
 const storyNav=[...document.querySelectorAll("[data-mv-chapter]")];
 const chapters=[...document.querySelectorAll("[data-mv-scene]")];
 let observer=null;
 if(typeof IntersectionObserver!=="undefined"){
  observer=new IntersectionObserver(entries=>{
   const active=entries.filter(e=>e.isIntersecting)
     .sort((a,b)=>b.intersectionRatio-a.intersectionRatio)[0];
   if(!active)return;
   const index=active.target.dataset.mvScene;
   storyNav.forEach(link=>{
    if(link.dataset.mvChapter===index)link.setAttribute("aria-current","location");
    else link.removeAttribute("aria-current");
   });
  },{rootMargin:"-16% 0px -62% 0px",threshold:[0,.1,.4]});
  chapters.forEach(x=>observer.observe(x));
 }
 // Navigation and UI are purposefully user-controlled; no automatic scroll.
 return {destroy:()=>{stopStage();cohort.destroy();timing.destroy();matrix.destroy();claims.destroy();observer?.disconnect();}};
}
