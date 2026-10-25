/* Mimicry: live research, transparent evidence. No runtime dependencies. */
const $ = (selector, root=document) => root.querySelector(selector);
const $$ = (selector, root=document) => Array.from(root.querySelectorAll(selector));
const esc = value => String(value == null ? "" : value).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;");
const fmt = (n,d=0) => Number(n).toLocaleString("en-US",{minimumFractionDigits:d,maximumFractionDigits:d});
const pct = (v,d=1) => fmt(v*100,d)+"%";
const dateFmt = s => new Date(s+"T12:00:00Z").toLocaleDateString("en-GB",{day:"numeric",month:"long",year:"numeric",timeZone:"UTC"});
const clamp=(n,a,b)=>Math.min(b,Math.max(a,n));
const ICON={
 arrow:'<path d="M4 12h16M14 6l6 6-6 6"/>',
 up:'<path d="M12 19V5m-7 7 7-7 7 7"/>',
 eye:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
 check:'<path d="m4 12 5 5L20 6"/>',
 alert:'<path d="M12 3 2 21h20L12 3zm0 6v5m0 4h.01"/>',
 book:'<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
 nodes:'<circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="12" cy="19" r="2"/><path d="m7 7 4 10m6-10-4 10M7 6h10"/>',
 route:'<path d="M6 3v12a3 3 0 0 0 6 0V9a3 3 0 0 1 6 0v12"/><circle cx="6" cy="3" r="2"/><circle cx="18" cy="21" r="2"/>',
 download:'<path d="M12 3v12m-4-4 4 4 4-4M5 19h14"/>'
};
const ico=(name,size=18)=>'<svg aria-hidden="true" width="'+size+'" height="'+size+'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'+(ICON[name]||ICON.arrow)+'</svg>';
const renderTo=html=>{ $("#main").innerHTML=html; };
const pathFor=track=>"/tracks/"+encodeURIComponent(track.slug)+"/";
const currentPath=location.pathname;
const label=(s,cls="")=>'<span class="eyebrow '+cls+'">'+esc(s)+'</span>';
const frame=(eyebrow,title,desc)=>'<div class="page-intro container"><p class="eyebrow">'+esc(eyebrow)+'</p><h1>'+esc(title)+'</h1><p class="page-description">'+esc(desc)+'</p></div>';
const statusPill=(txt,cls="")=>'<span class="status-pill '+cls+'"><span class="status-dot"></span>'+esc(txt)+'</span>';
function header(catalog){
  const activeTrack=currentPath.split("/")[2]||"";
  $("#site-header").innerHTML=[
   '<header class="site-header"><div class="header-in container">',
   '<a class="wordmark" href="/" aria-label="Mimicry research observatory home"><span class="mark" aria-hidden="true"><span></span><span></span><span></span></span>Mimicry<span class="wordmark-period">.</span></a>',
   '<a class="header-note" href="/research/">Independent research / live evidence</a>',
   '<button class="mobile-menu" aria-label="Open navigation" aria-expanded="false" aria-controls="primary-nav"><span></span><span></span></button>',
   '<nav id="primary-nav" class="primary-nav" aria-label="Primary navigation">',
   '<a href="/research/" '+(currentPath.startsWith("/research")?'aria-current="page"':"")+'>Research tracks</a>',
   ...catalog.tracks.map(t=>'<a href="'+pathFor(t)+'" '+(activeTrack===t.slug?'aria-current="page"':"")+'>'+esc(t.name)+'</a>'),
   '<a href="/about/" '+(currentPath.startsWith("/about")?'aria-current="page"':"")+'>About</a>',
   '</nav></div></header>'
  ].join("");
  const menu=$(".mobile-menu"); menu.addEventListener("click",()=>{
    const open=menu.getAttribute("aria-expanded")!=="true";
    menu.setAttribute("aria-expanded",String(open));
    menu.setAttribute("aria-label",open?"Close navigation":"Open navigation");
    $("#primary-nav").classList.toggle("open",open);
  });
}
function footer(catalog){
 $("#site-footer").innerHTML=[
  '<footer class="footer"><div class="container"><div class="footer-top"><div>',
  '<span class="footer-mark">M<span class="mint-dot">.</span></span>',
  '<p>Research, with the uncertainty left in.</p></div>',
  '<div class="footer-links"><a href="/research/">Research</a><a href="/tracks/prophecy/methods/">Methods</a><a href="https://github.com/autonomio/Mimicry" target="_blank" rel="noopener noreferrer">Source code '+ico("arrow",15)+'</a></div>',
  '</div><div class="footer-bottom"><span>Open methods · Aggregate evidence only</span><span>Mimicry research observatory · '+new Date().getUTCFullYear()+'</span></div></div></footer>'
 ].join("");
}
const heroGraphic=()=>[
 '<div class="hero-art" aria-hidden="true"><div class="hero-orb hero-orb-a"></div><div class="hero-orb hero-orb-b"></div>',
 '<svg class="hero-lines" viewBox="0 0 680 550" preserveAspectRatio="xMidYMid slice" fill="none">',
 '<g stroke="#a3d8cf" stroke-opacity=".20" stroke-width="1">',
 '<path d="M-60 380 C150 90 310 480 730 90"/><path d="M-60 410 C150 120 310 510 730 120"/><path d="M-60 440 C150 150 310 540 730 150"/>',
 '<path d="M-60 470 C150 180 310 570 730 180"/><path d="M-60 500 C150 210 310 600 730 210"/>',
 '</g><path d="M-60 380 C150 90 310 480 730 90" stroke="#98e5d2" stroke-width="2.2" stroke-opacity=".85"/>',
 '<circle cx="340" cy="276" r="5" fill="#9ce5d2"/><circle cx="340" cy="276" r="18" stroke="#9ce5d2" stroke-opacity=".40"/>',
 '</svg><span class="hero-art-label">OBSERVED OUTCOME  ≠  BIOLOGICAL DESTINY</span></div>'
].join("");
function home(catalog){
 const latest=catalog.releases[0], t=latest?catalog.tracks.find(x=>x.id===latest.track):catalog.tracks[0];
 renderTo([
  '<section class="home-hero"><div class="container home-hero-grid"><div class="home-hero-copy">',
  label("MIMICRY / RESEARCH OBSERVATORY","mint"),
  '<h1>What the data <em>remembers.</em></h1>',
  '<p class="home-lead">Illness is not the only force shaping a health outcome. Care, decisions and what we measure shape the record too. Mimicry is where we study that relationship—with evidence you can explore and methods you can examine.</p>',
  '<div class="hero-actions"><a class="button button-primary" href="/research/">Explore the research '+ico("arrow")+'</a><a class="text-link light-link" href="/about/">Our approach '+ico("arrow",16)+'</a></div>',
  '<div class="hero-footnote"><span class="foot-rule"></span>Evidence, not certainty. Every claim has a boundary.</div>',
  '</div>',heroGraphic(),'</div></section>',
  '<section class="section section-tracks"><div class="container"><div class="section-heading"><div>'+label("01 / The observatory")+'<h2>Research tracks</h2></div><p>Distinct scientific programs, one shared standard: show the evidence, the methods and where the models fail.</p></div>',
  catalog.tracks.map(trackCard).join(""),
  '</div></section>',
  '<section class="section dark-band"><div class="container split-statement"><div>'+label("A PUBLIC COMMITMENT","mint")+'<h2>The finding matters.<br><em>So does the failure.</em></h2></div><div><p>Research advances by discovering where our explanations break. Mimicry publishes results alongside their assumptions, validation criteria and unsuccessful tests.</p><a href="/about/" class="text-link light-link">Read our research principles '+ico("arrow",16)+'</a></div></div></section>',
  latest?'<section class="section"><div class="container"><div class="section-heading"><div>'+label("LATEST RELEASE")+'<h2>From the research desk</h2></div></div>'+releaseCard(latest,t)+'</div></section>':"",
  '<section class="section end-cap"><div class="container"><span class="section-index">M / 01</span><p>Not a forecast of fate.<br><strong>A clearer account of what happened.</strong></p></div></section>'
 ].join(""));
}
function trackCard(t){
 return [
 '<a class="track-card" href="'+pathFor(t)+'"><div class="track-card-top"><span class="track-serial">TRACK '+String(t.order||1).padStart(2,"0")+'</span>'+statusPill(t.status)+'</div>',
 '<div class="track-card-body"><div class="signal-graphic" aria-hidden="true"><svg viewBox="0 0 140 100" fill="none"><path d="M0 75 C28 75 29 21 58 21S92 74 140 14" stroke="#147a69" stroke-width="2.5"/><path d="M0 95 C28 95 29 41 58 41S92 94 140 34" stroke="#147a69" opacity=".25"/><circle cx="58" cy="21" r="4" fill="#147a69"/></svg></div>',
 '<div><p class="track-discipline">'+esc(t.discipline)+'</p><h3>'+esc(t.name)+'</h3><p class="track-tagline">'+esc(t.tagline)+'</p></div></div>',
 '<div class="track-card-bottom"><span>Open research program</span><span class="round-arrow">'+ico("arrow")+'</span></div></a>'
 ].join("");
}
function releaseCard(r,t){
 return ['<a class="release-card" href="'+pathFor(t)+'releases/'+encodeURIComponent(r.id)+'/">',
 '<div><span class="release-label">RESEARCH RELEASE  /  '+esc(dateFmt(r.date))+'</span><h3>'+esc(r.title)+'</h3><p>'+esc(r.message)+'</p></div>',
 '<div class="release-side"><span class="released-track">'+esc(t.name)+'</span>'+ico("arrow",24)+'</div></a>'].join("");
}
function dnrTrack(catalog,t){
 const rs=catalog.releases.filter(x=>x.track===t.id),latest=rs[0];
 renderTo([
 '<section class="track-hero"><div class="container track-hero-content"><div class="breadcrumb"><a href="/">Mimicry</a><span>/</span><a href="/research/">Tracks</a><span>/</span>'+esc(t.name)+'</div>',
 '<div class="track-hero-top">'+label("RESEARCH TRACK 02 / THE DNR QUESTION","mint")+'<span class="track-hero-index">M—02</span></div>',
 '<h1>'+esc(t.name)+'<span class="mint-dot">.</span></h1><p class="track-hero-sub">'+esc(t.tagline)+'</p>',
 '<p class="track-hero-body">This is a deliberate fork back to a question that can get lost inside prediction scores: does a do-not-resuscitate order itself change what clinicians do, or is it a marker of illness and decisions already underway?</p>',
 '<div class="track-hero-actions"><a href="'+pathFor(t)+'releases/'+latest.id+'/" class="button button-primary">Examine the DNR evidence '+ico("arrow")+'</a><a class="text-link light-link" href="'+pathFor(t)+'methods/">Identification and methods '+ico("arrow",16)+'</a></div>',
 '<div class="track-hero-end">'+esc(t.discipline)+'<span>'+esc(t.status)+'</span></div></div></section>',
 '<section class="section"><div class="container"><div class="section-heading"><div>'+label("ONE QUESTION / THREE TESTS")+'<h2>What does the order change?</h2></div><p>Separate the legal meaning of a DNR directive, what happens at its timestamp, and the much harder question of whether it causes death.</p></div>',
 '<div class="principle-grid"><article>'+ico("book",25)+'<h3>Define the decision</h3><p>DNR limits CPR at arrest. DNR-only, DNI, and comfort measures must not be treated as interchangeable clinical actions.</p></article>',
 '<article>'+ico("activity",25)+'<h3>Watch what changes</h3><p>Measure treatment and monitoring before and after the actual order, with eligible full-code controls, early timing checks and explicit competing exits.</p></article>',
 '<article>'+ico("alert",25)+'<h3>Audit causality</h3><p>Expose residual prognostic imbalance, failed overlap, and unverified physician instruments before estimating what the order itself caused.</p></article></div>',
 latest?'<div class="dnr-feature"><div><span class="release-label">FORKED RESEARCH · '+esc(dateFmt(latest.date))+'</span><h3>'+esc(latest.title)+'</h3><p>'+esc(latest.message)+'</p><a href="'+pathFor(t)+'releases/'+latest.id+'/" class="button button-dark">Inspect the first result '+ico("arrow")+'</a></div><div class="dnr-feature-stat"><span>DOCUMENTED DNR-ONLY EVENTS ON COMMON SUPPORT</span><strong>'+fmt(latest.dnr_only_n)+'</strong><small>Not an identified treatment-effect cohort</small></div></div>':"",
 '</div></section>',
 '<section class="section pale-section"><div class="container"><div class="section-heading"><div>'+label("THE DNR RECORD")+'<h2>Prophecy 2 releases</h2></div></div>'+rs.map(r=>releaseCard(r,t)).join("")+'</div></section>',
 '<section class="section"><div class="container"><div class="read-next"><div>'+label("RELATED, BUT DIFFERENT")+'<h3>Prophecy remains its own track.</h3><p>The original program examines broader ICU prognosis, care-state forecasting and the limits of longitudinal simulation. It does not set Prophecy 2’s research agenda.</p></div><a href="/tracks/prophecy/" class="button button-dark">Visit Prophecy '+ico("arrow")+'</a></div></div></section>'
 ].join(""));
}

function track(catalog,t){
 if(t.id==="prophecy-2")return dnrTrack(catalog,t);
 const rs=catalog.releases.filter(r=>r.track===t.id), latest=rs[0];
 renderTo([
 '<section class="track-hero"><div class="container track-hero-content"><div class="breadcrumb"><a href="/">Mimicry</a><span>/</span><a href="/research/">Tracks</a><span>/</span>'+esc(t.name)+'</div>',
 '<div class="track-hero-top">'+label("RESEARCH TRACK "+String(t.order||1).padStart(2,"0"),"mint")+
 '<span class="track-hero-index">M—'+String(t.order||1).padStart(2,"0")+'</span></div>',
 '<h1>'+esc(t.name)+'<span class="mint-dot">.</span></h1><p class="track-hero-sub">'+esc(t.tagline)+'</p>',
 '<p class="track-hero-body">'+esc(t.description)+'</p>',
 '<div class="track-hero-actions"><a href="'+pathFor(t)+'releases/" class="button button-primary">Browse the findings '+ico("arrow")+'</a><a class="text-link light-link" href="'+pathFor(t)+'methods/">Research methods '+ico("arrow",16)+'</a></div>',
 '<div class="track-hero-end">'+esc(t.discipline)+'<span>'+esc(t.status)+'</span></div></div></section>',
 latest?'<section class="section"><div class="container"><div class="section-heading"><div>'+label("LATEST IN "+t.name.toUpperCase())+'<h2>What we have learned</h2></div><p>Explore verified aggregate findings, reproducible methods, and model limitations.</p></div><div class="latest-feature"><div class="latest-content"><span class="release-label">'+esc(dateFmt(latest.date))+' · '+esc(latest.dataset)+'</span><h3>'+esc(latest.title)+'</h3><p>'+esc(latest.message)+'</p><a class="button button-dark" href="'+pathFor(t)+'releases/'+latest.id+'/">Explore this release '+ico("arrow")+'</a></div><div class="latest-metric"><span>Compared with physiology alone</span><strong>'+fmt(latest.prediction_gain_relative*100,1)+'%</strong><span>lower competing-event log loss<br>with full documented care history</span><small>Prediction, not causation</small></div></div></div></section>':"",
 '<section class="section track-principles"><div class="container"><div class="section-heading"><div>'+label("A DIFFERENT SCIENTIFIC STANDARD")+'<h2>Look beyond one number</h2></div></div>',
 '<div class="principle-grid"><article>'+ico("nodes",25)+'<h3>Decisions are part of the system</h3><p>Physiology, treatment and monitoring evolve together. We model them as related, not interchangeable, processes.</p></article>',
 '<article>'+ico("alert",25)+'<h3>Failure is an output</h3><p>Our trajectory simulator fails key discharge-calibration tests. You can inspect those failures in the release.</p></article>',
 '<article>'+ico("book",25)+'<h3>Open methods</h3><p>Every release is linked to its assumptions, cohorts, code and limits on causal interpretation.</p></article></div>',
 '</div></section>',
 '<section class="section pale-section"><div class="container"><div class="section-heading"><div>'+label("THE RECORD")+'<h2>Release history</h2></div><a class="text-link" href="'+pathFor(t)+'releases/">All releases '+ico("arrow",16)+'</a></div>',
 rs.map(r=>releaseCard(r,t)).join("")+'</div></section>'
 ].join(""));
}
function releases(catalog,t) {
 const rs=catalog.releases.filter(x=>x.track===t.id);
 renderTo(frame(t.name+" / versioned results","Research releases","Every published round is a versioned record. New reviewed releases become available here automatically after merging into the research repository.")+
 '<section class="section section-compact"><div class="container"><div class="release-list">'+rs.map((r,i)=>releaseCard(r,t)).join("")+'</div><p class="foot-disclaimer">'+rs.length+' release'+(rs.length===1?"":"s")+' · Detailed documentation, test-set metrics and known failures included in each.</p></div></section>');
}
function research(catalog){
 renderTo(frame("Mimicry / research portfolio","Questions worth following","Each track has its own methods and publication history. Explore the research, including what has not yet been established.")+
 '<section class="section section-compact"><div class="container"><div class="research-grid">'+catalog.tracks.map(trackCard).join("")+'</div><div class="future-track"><div>'+label("FUTURE RESEARCH")+'<h3>A growing observatory</h3><p>Mimicry is designed for independent tracks. Each will maintain its own releases, validation gates and reproducible source record.</p></div><div class="future-icon">'+ico("nodes",36)+'</div></div></div></section>');
}
function about(){
 renderTo(frame("Why Mimicry exists","Be precise about uncertainty.","Health outcomes are not generated by biology alone. We believe serious science should make decisions, missing information and failed validation visible—not hide them behind a single score.")+
 '<section class="section section-compact"><div class="container"><div class="about-grid">'+
 '<article><span class="about-number">01</span><h2>Methods before confidence</h2><p>Every numerical claim needs a defined population, outcome, time zero and analysis design. Predictive scores cannot be mistaken for treatment effects.</p></article>',
 '<article><span class="about-number">02</span><h2>Failure is part of evidence</h2><p>Out-of-sample validation and multi-horizon calibration are acceptance gates. If a simulator gets discharge wrong, it is not a validated model.</p></article>',
 '<article><span class="about-number">03</span><h2>Patient privacy is non-negotiable</h2><p>Underlying MIMIC-IV patient records remain in their controlled server environment. This public portal contains reviewed aggregate releases and research code only.</p></article>'+
 '<article><span class="about-number">04</span><h2>Living, versioned science</h2><p>A new research round is published as an immutable, reviewed release with a dated URL. The live track page then points to the newest public result.</p></article>'+
 '</div><div class="callout-dark"><div>'+label("OPEN RESEARCH","mint")+'<h2>Follow the code,<br><em>not just the conclusion.</em></h2></div><a href="https://github.com/autonomio/Mimicry" rel="noopener noreferrer" target="_blank" class="button button-primary">View GitHub repository '+ico("arrow")+'</a></div></div></section>');
}
function dnrMethods(catalog,t){
 const m=catalog.releases.find(r=>r.track===t.id);
 renderTo([frame("PROPHECY 2 / CAUSAL INFERENCE","What would actually identify a DNR effect?",
 "Research methods built around the clinical meaning, timing and selection of DNR orders—not general mortality-model accuracy."),
 '<section class="section section-compact"><div class="container method-content">',
 '<div class="method-lead"><div>'+label("THE INTERVENTION")+'<h2>A DNR order is not a withdrawal order.</h2></div><p>Do not resuscitate limits attempted cardiopulmonary resuscitation at cardiac arrest. DNR-only, DNR/DNI and comfort-only orders are clinically different. An observational association involving all of them is not the effect of an isolated CPR directive.</p></div>',
 '<div class="dnr-method-steps">'+
 '<article><span>01 / ELIGIBILITY</span><h3>Who could receive the order?</h3><p>First ICU stay within an admission. Previously documented full-code state, with at least 24 hours elapsed in the ICU. Unrecorded status stays unknown, never silently recoded as full code.</p></article>'+
 '<article><span>02 / TIME ZERO</span><h3>The first hospital DNR order</h3><p>Anchor the analysis at the first recorded full-code to DNR-only or DNR/DNI order in the ICU, after checking hospital POE timestamps against charted status and reconciling contradictory records.</p></article>'+
 '<article><span>03 / RISK SET</span><h3>Patients eligible at the same time</h3><p>Give every full-code comparator a corresponding ICU-elapsed-time landmark. Do not require survival, discharge, later absence of DNR or dying in the eventual outcome cohort.</p></article>'+
 '<article><span>04 / ANALYSIS</span><h3>Measure support and observation separately</h3><p>Use recorded ventilation hours, pressor exposure, monitoring counts and explicit extubation events. Show pre-order trends, weighted comparator changes, competing ICU exits and sensitivity to limited common support.</p></article>'+
 '</div>',
 '<div class="dnr-estimand"><span class="figure-kicker">WHAT THE CURRENT ESTIMATE MEANS</span><h3>An observed event-time contrast</h3><p class="dnr-formula">Δ = (after − before)<sub>DNR order</sub> − (after − before)<sub>full-code risk set</sub></p><p>This measures weighted changes in observed treatment-hours per available ICU patient-hour, not a causal effect on survival or a patient who would otherwise have received CPR. Available ICU person-hours themselves depend on death and discharge.</p></div>',
 '<div class="method-two"><div><h3>The question we have <em>not</em> identified</h3><p>What would have happened to the same patient had an isolated CPR-only DNR order not been placed, holding preferences and other clinical decisions appropriately defined? That requires a meaningful and supported intervention and a credible comparison mechanism. Prognosis and care intentions omitted from the record prevent exchangeability here.</p></div>'+
 '<div><h3>Why the impressive IV is not enough</h3><p>An order-provider ID is documented at the time of ordering and does not establish random assignment. Hospital admitting providers are not necessarily ICU decision-makers. Strong preference variation or a first-stage F-statistic does not prove exclusion, independence, monotonicity or a mortality treatment effect.</p></div></div>',
 '<div class="limitations">'+label("HARD STOP RULES")+'<h2>What would invalidate a causal claim?</h2><ol>'+
 ['The DNR-only order cannot be isolated from coincident DNI, comfort-only or undocumented goals-of-care decisions.',
  'The comparison lacks overlap; very few effective controls remain for some DNR decisions.',
  'Important pre-order prognostic differences persist, including neurological disease, lactate and clinician expectations.',
  'Decedents are selected after exposure, or equal follow-up is required by conditioning on remaining alive or in the ICU.',
  'Deaths are attributed to a no-CPR directive without observing cardiac arrest, eligibility for CPR and other co-interventions.',
  'An instrumental variable is assumed valid from association strength alone.',
  'Recorded chart times are treated as prospective observation availability times without checking storage and order timestamps.',
  'The analysis claims causality because a confidence interval excludes zero.'].map((x,i)=>'<li><span>'+String(i+1).padStart(2,"0")+'</span><p>'+esc(x)+'</p></li>').join("")+
 '</ol></div>',
 '<div class="dnr-method-steps lower">'+
 '<article><span>NEXT / PHENOTYPE</span><h3>Reconstruct isolated DNR</h3><p>Audit simultaneous order bundles and temporal ambiguity; where intent is unavailable, state that it is unknown.</p></article>'+
 '<article><span>NEXT / IDENTIFICATION</span><h3>Audit arrest and CPR</h3><p>Test whether the observed record supports the CPR mechanism at all. Report partial-identification bounds when it cannot support point estimation.</p></article>'+
 '<article><span>NEXT / FALSIFICATION</span><h3>Reject weak instruments</h3><p>Require real pre-decision assignment, balance, negative-control practice effects and a defensible exclusion argument before any IV mortality estimate.</p></article>'+
 '<article><span>DO NOT / DRIFT</span><h3>No generic mortality simulator</h3><p>Prophecy 2 does not expand into policy transport dashboards unless they answer a predefined DNR-specific causal question.</p></article></div>',
 '<div class="reproduce-block"><div><h3>A separate research lineage</h3><p>This track forks at the ICU DNR event history and matched risk-set stage. It does not rewrite or invalidate the earlier Prophecy track. The current results are exploratory and conditional on retrospective fixed-weight uncertainty.</p></div><div class="reproduce-links"><a class="button button-dark" href="https://github.com/autonomio/Mimicry/pull/8" target="_blank" rel="noopener noreferrer">Inspect the Prophecy 2 review '+ico("arrow")+'</a><a class="text-link" href="'+pathFor(t)+'releases/'+m.id+'/">Open the first DNR audit '+ico("arrow",16)+'</a></div></div>',
 '</div></section>'].join(""));
}

function methods(catalog,t){
 if(t.id==="prophecy-2")return dnrMethods(catalog,t);
 const r=catalog.releases.find(x=>x.track===t.id);
 if(!r||!r.methods) return renderTo(frame(t.name,"Methods forthcoming","This research track has not published a method record."));
 const m=r.methods;
 const warnings=(m.warnings||[]).map((w,i)=>'<li><span>'+String(i+1).padStart(2,"0")+'</span><p>'+esc(w)+'</p></li>').join("");
 renderTo(frame(t.name+" / reproducibility","Methods, not mythology.","How the findings were obtained, what they mean, and what the data cannot identify.")+
 '<section class="section section-compact"><div class="container method-content">'+
 '<div class="method-lead"><div>'+label("RESEARCH DESIGN")+'<h2>A six-hour view of a changing system</h2></div><p>'+esc(m.cohort)+' '+esc(m.historical_split)+'</p></div>',
 '<div class="method-flow"><div><span>01</span><strong>Patient state</strong><small>Recorded history at t</small></div><div><span>02</span><strong>Care transitions</strong><small>Decisions and support</small></div><div><span>03</span><strong>Observation</strong><small>What is measured</small></div><div><span>04</span><strong>Competing exits</strong><small>Discharge and death</small></div></div>'+
 '<div class="method-two"><div><h3>What is being evaluated?</h3><p>'+esc(m.metrics)+'</p></div><div><h3>What is not being estimated?</h3><p>We do not estimate the effect of a hypothetical no-DNR policy or infer a patient would survive under different treatment decisions. Identifying those questions requires additional assumptions or data.</p></div></div>'+
 '<div class="limitations">'+label("NON-NEGOTIABLE LIMITATIONS")+'<h2>Read this before drawing conclusions</h2><ol>'+warnings+'</ol></div>'+
 '<div class="reproduce-block"><div><h3>Run, inspect, challenge</h3><p>Code, testing scripts, dated aggregate reports and publication rules are available in the source repository. MIMIC-IV data access remains governed by PhysioNet requirements.</p></div><div class="reproduce-links"><a class="button button-dark" href="https://github.com/autonomio/Mimicry/tree/master/research/mimic-iv" target="_blank" rel="noopener noreferrer">Research source '+ico("arrow")+'</a><a href="/tracks/'+esc(t.slug)+'/releases/'+esc(r.id)+'/" class="text-link">Inspect results '+ico("arrow",16)+'</a></div></div>',
 '</div></section>');
}
function breadcrumbs(t,r){
 return '<div class="breadcrumb light-breadcrumb"><a href="/">Mimicry</a><span>/</span><a href="'+pathFor(t)+'">'+esc(t.name)+'</a><span>/</span>'+esc(r.title)+'</div>';
}
function stat(label,value,description){
 return '<div class="stat"><span>'+esc(label)+'</span><strong>'+esc(value)+'</strong><p>'+esc(description||"")+'</p></div>';
}
function resultSummary(r){
 return '<div class="summary-insight"><p class="summary-question">What is the result?</p><p>'+esc(r.message)+'</p><span>Observed practice, not counterfactual treatment effects.</span></div>';
}
function narrativeModes(r){
 if(r.transport){
  const z=r.transport;
  const five=z.horizons.at(-1).exit, early=z.earlier_rolling_origin.horizons.at(-1);
  return '<div class="lens-panel" id="lens-panel"><div class="lens-header"><div>'+label("TWO WAYS TO READ THIS")+'<h3>What does it mean when a model stops traveling?</h3></div><div class="lens-switch" role="group" aria-label="Reading level"><button type="button" data-lens="public" aria-pressed="true">In plain language</button><button type="button" data-lens="technical" aria-pressed="false">Scientific detail</button></div></div>'+
  '<div class="lens-copy" data-lens-view="public"><p>Five days into the follow-up, the simulator predicts that nearly 8 in 10 people have left intensive care. But just over 7 in 10 actually had. Most of the mistake happens before the model tries to invent a patient’s future. <strong>Hospital histories changed in ways this older model did not fully capture.</strong></p></div>'+
  '<div class="lens-copy hidden" data-lens-view="technical"><p>The terminal hazard on actual patient histories predicts '+pct(five.prequential,2)+' 120-hour cumulative ICU exit versus '+pct(five.observed,2)+' observed; the full rollout predicts '+pct(five.simulated,2)+'. Its '+fmt(five.total_error*100,2)+'pp full error decomposes into '+fmt(five.local_error*100,2)+'pp prequential transport residual and '+fmt(five.recursive_error*100,2)+'pp additional trajectory feedback. The earlier 2017–2019 rolling-origin evaluation also overpredicts discharge by '+fmt(early.exit_error*100,2)+'pp. This is descriptive model criticism, not a causal policy-effect decomposition.</p></div></div>';
 }
 return '<div class="lens-panel" id="lens-panel"><div class="lens-header"><div>'+label("CHOOSE YOUR LENS")+'<h3>One result. Two ways to read it.</h3></div><div class="lens-switch" role="group" aria-label="Reading level"><button type="button" data-lens="public" aria-pressed="true">In plain language</button><button type="button" data-lens="technical" aria-pressed="false">Scientific detail</button></div></div>'+
 '<div class="lens-copy" data-lens-view="public"><p>When a model knows what care a person is receiving—and what clinicians measure—it predicts recorded ICU outcomes better than a model that looks at physiology alone. <strong>That does not mean the care decisions caused the deaths.</strong></p></div>'+
 '<div class="lens-copy hidden" data-lens-view="technical"><p>Across patient-disjoint historical cohorts, care-history features reduced held-out multiclass log loss by '+fmt(r.prediction.improvement.value,5)+' ('+fmt(r.prediction.improvement.relative*100,1)+'% relative); 95% patient-cluster bootstrap CI '+fmt(r.prediction.improvement.ci[0],5)+'–'+fmt(r.prediction.improvement.ci[1],5)+'. These are predictions under observed clinical practice, without identifying a counterfactual dynamic treatment regime.</p></div></div>';
}
function modelExplorer(r){
 const models=r.prediction.models;
 const options=models.map(x=>'<option value="'+esc(x.key)+'"'+(x.key==="physiology"?' selected':'')+'>'+esc(x.label)+'</option>').join("");
 return '<div class="figure" id="model-figure"><div class="figure-head"><div><span class="figure-kicker">FIGURE 01 · PREDICTIVE PERFORMANCE</span><h3>The information ladder</h3><p>Test-set multiclass log loss. Lower is better; each row is a differently informed model.</p></div><div class="figure-control"><label for="model-baseline">Compare against</label><select id="model-baseline">'+options+'</select></div></div><div id="model-bars" class="model-bars"></div><div class="figure-footer"><span>Historical test: '+fmt(r.summary.test)+' six-hour landmarks</span><span>2008–2016 / 2017–2019 / 2020–2022</span></div></div>';
}
function installModelExplorer(r){
 const render=()=>{
  const base=r.prediction.models.find(x=>x.key===$("#model-baseline").value);
  $("#model-bars").innerHTML=r.prediction.models.map(m=>{
   const delta=base.loss-m.loss;
   const isBest=m.key==="care_history";
   return '<div class="model-row '+(isBest?'model-row-best':'')+'"><div class="model-name">'+esc(m.label)+(isBest?'<span>FULL HISTORY</span>':'')+'</div><div class="model-track"><div class="model-fill" data-width="'+clamp(m.loss/0.39*100,0,100)+'"></div></div><div class="model-number">'+fmt(m.loss,5)+'</div><div class="model-delta '+(delta<0?'negative':'')+'">'+(Math.abs(delta)<0.00001?'Baseline':(delta>0?'−':'+')+fmt(Math.abs(delta),5))+'</div></div>'
  }).join("");
  $$(".model-fill",$("#model-bars")).forEach(el=>{el.style.width=Number(el.dataset.width)+"%";});
 };
 $("#model-baseline").addEventListener("change",render);render();
}
function renderCalibration(r) {
 const mx=Math.max(...r.prediction.calibration.flatMap(x=>[x.observed,x.predicted]))*1.22;
 return '<div class="figure"><div class="figure-head"><div><span class="figure-kicker">FIGURE 02 · CALIBRATION</span><h3>A good score is not enough.</h3><p>How often the event occurred, versus its average predicted probability in the test cohort.</p></div></div>'+
 '<div class="calibration-list">'+r.prediction.calibration.map(x=>{
  const w1=x.observed/mx*100,w2=x.predicted/mx*100;
  return '<div class="cal-row"><div class="cal-row-title">'+esc(x.event)+'</div><div class="cal-axis"><span class="cal-stem"></span><span class="cal-point actual-point"></span><span class="cal-point predicted-point"></span></div><div class="cal-values"><span>'+pct(x.observed,2)+'</span><span>'+pct(x.predicted,2)+'</span></div></div>'
 }).join("")+'</div>'+
 '<div class="chart-legend"><span><i class="actual-legend"></i>Observed</span><span><i class="predicted-legend"></i>Predicted</span></div>'+
 '<p class="figure-caution">'+ico("alert",17)+' ICU death is underpredicted in the later historical test set. Absolute risk estimates are not adequate for clinical use.</p></div>';
}
function installCalibration(r){
 const max=Math.max(...r.prediction.calibration.flatMap(x=>[x.observed,x.predicted]))*1.22;
 $$(".cal-row").forEach((el,i)=>{
  const d=r.prediction.calibration[i];
  const p1=d.observed/max*100,p2=d.predicted/max*100;
  const stem=$(".cal-stem",el),actual=$(".actual-point",el),pred=$(".predicted-point",el);
  stem.style.left=Math.min(p1,p2)+"%";
  stem.style.width=Math.abs(p1-p2)+"%";
  actual.style.left=p1+"%";
  pred.style.left=p2+"%";
 });
}
function lineChart(horizons,which){
 const keys={death:"Death",exit:"Discharged from ICU",icu:"Remaining in ICU"};
 const series=horizons.map(h=>({h:h.hours,a:h[which].observed*100,b:h[which].simulated*100}));
 const highest=Math.max(...series.flatMap(x=>[x.a,x.b]));
 const max=Math.max(1,Math.ceil(highest*1.18/(highest>25?10:highest>8?2:1))*(highest>25?10:highest>8?2:1));
 const W=720,H=330,L=60,R=18,T=22,B=55;
 const hmax=Math.max(...series.map(d=>d.h));
 const x=(d)=>L+(W-L-R)*d.h/hmax;
 const y=v=>T+(H-T-B)*(1-v/max);
 const path=key=>series.map((d,i)=>(i?'L':'M')+x(d).toFixed(2)+' '+y(d[key]).toFixed(2)).join(' ');
 const grid=[0,.25,.5,.75,1].map(fr=>'<line x1="'+L+'" y1="'+y(max*fr)+'" x2="'+(W-R)+'" y2="'+y(max*fr)+'" class="chart-grid"/><text x="'+(L-12)+'" y="'+(y(max*fr)+4)+'" text-anchor="end" class="axis-label">'+fmt(max*fr,highest<10?1:0)+'%</text>').join("");
 const xticks=series.map((d,i)=>'<text x="'+x(d)+'" y="'+(H-20)+'" text-anchor="middle" class="axis-label">'+d.h+'h</text>').join("");
 const pts=key=>series.map((d,i)=>'<circle cx="'+x(d)+'" cy="'+y(d[key])+'" r="5" class="point-'+key+'"><title>'+keys[which]+' · '+d.h+'h · '+(key==="a"?"Observed ":"Simulated ")+fmt(d[key],2)+'%</title></circle>').join("");
 return '<svg class="outcome-chart" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+esc(keys[which])+' over time, observed versus simulated percentages. Vertical axis 0 to '+fmt(max,1)+' percent.">'+grid+xticks+'<path class="line-actual" d="'+path('a')+'"/><path class="line-predicted" d="'+path('b')+'"/>'+pts('a')+pts('b')+'<text x="'+W/2+'" y="'+(H-1)+'" text-anchor="middle" class="axis-label">HOURS AFTER ICU HOUR 24</text></svg>';
}
function outcomeExplorer(r) {
 return ['<div class="figure outcome-figure"><div class="figure-head"><div><span class="figure-kicker">FIGURE 03 · LONGITUDINAL VALIDATION</span><h3>Can the simulator reproduce reality?</h3><p>Compare observed and simulated cumulative patient outcomes over five days.</p></div></div>',
 '<div class="outcome-controls" role="group" aria-label="Select outcome"><button type="button" class="active" data-outcome="death" aria-pressed="true">ICU death</button><button type="button" data-outcome="exit" aria-pressed="false">ICU exit</button><button type="button" data-outcome="icu" aria-pressed="false">Still in ICU</button></div>',
 '<div id="outcome-graph"></div><div class="chart-legend"><span><i class="actual-legend"></i>Observed</span><span><i class="predicted-legend"></i>Simulated</span></div>',
 '<div class="validation-failure">'+ico("alert",20)+'<div><strong>Long-horizon validation did not pass.</strong><p>The simulator overpredicts ICU discharge and underpredicts occupancy. A close mortality curve alone is not sufficient for a validated model.</p></div></div>',
 '<details class="scientist-detail"><summary>View exact values and validation gates '+ico("arrow",16)+'</summary><div id="outcome-table"></div></details></div>'].join('');
}
function installOutcomeExplorer(r){
 function chart(key){
  $("#outcome-graph").innerHTML=lineChart(r.simulation.horizons,key);
  $$("[data-outcome]").forEach(el=>{const active=el.dataset.outcome===key;el.classList.toggle("active",active);el.setAttribute("aria-pressed",String(active))});
  const name={death:"ICU death",exit:"ICU exit",icu:"Remaining in ICU"}[key];
  $("#outcome-table").innerHTML='<div class="table-scroll"><table><caption>'+esc(name)+' · observed vs simulated</caption><thead><tr><th>Horizon</th><th>Observed</th><th>Simulated</th><th>Difference</th><th>Gate</th></tr></thead><tbody>'+
  r.simulation.horizons.map(h=>'<tr><th>'+h.hours+'h</th><td>'+pct(h[key].observed,2)+'</td><td>'+pct(h[key].simulated,2)+'</td><td>'+((h[key].simulated-h[key].observed)*100>=0?'+':'')+fmt((h[key].simulated-h[key].observed)*100,2)+'pp</td><td>'+(!h.passed?'Not all passed':'Passed')+'</td></tr>').join("")+'</tbody></table></div>';
 }
 $$("[data-outcome]").forEach(el=>el.addEventListener("click",()=>chart(el.dataset.outcome)));
 chart("death");
}
function transportChart(z,event){
 const labels={exit:"Cumulative ICU exit",death:"Cumulative ICU death"};
 const data=z.horizons.map(h=>({h:h.hours,o:100*h[event].observed,p:100*h[event].prequential,s:100*h[event].simulated}));
 const W=750,H=350,L=65,R=18,T=22,B=54;
 const val=Math.max(...data.flatMap(v=>[v.o,v.p,v.s]));
 const ceil=Math.max(1,Math.ceil(val*1.12/(val>20?10:val>5?2:1))*(val>20?10:val>5?2:1));
 const x=h=>L+(W-R-L)*h/120;
 const y=v=>T+(H-T-B)*(1-v/ceil);
 const line=k=>data.map((q,i)=>(i?"L":"M")+x(q.h).toFixed(2)+" "+y(q[k]).toFixed(2)).join(" ");
 const props=[["o","#17846b","Observed"],["p","#ae805b","Model on actual histories"],["s","#2b5f7d","Full simulation"]];
 const grid=[0,.25,.5,.75,1].map(v=>'<line x1="'+L+'" x2="'+(W-R)+'" y1="'+y(ceil*v)+'" y2="'+y(ceil*v)+'" stroke="#dce5de"/><text x="'+(L-12)+'" y="'+(y(ceil*v)+4)+'" text-anchor="end" class="axis-label">'+fmt(ceil*v,val<8?1:0)+'%</text>').join("");
 const ticks=data.map(v=>'<text x="'+x(v.h)+'" y="'+(H-18)+'" text-anchor="middle" class="axis-label">'+v.h+'h</text>').join("");
 const shapes=props.map(([k,color,desc])=>
  '<path d="'+line(k)+'" stroke="'+color+'" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'+
  data.map(v=>'<circle cx="'+x(v.h)+'" cy="'+y(v[k])+'" r="5" fill="'+color+'" stroke="#fffef9" stroke-width="2"><title>'+desc+', '+v.h+' hours: '+fmt(v[k],2)+'%</title></circle>').join("")
 ).join("");
 return '<svg class="outcome-chart" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+esc(labels[event])+': observed, model prediction on real histories, and fully simulated risk across 24, 48, 72 and 120 hours.">'+grid+ticks+shapes+'</svg>';
}
function administrativeExitFigure(z){
 const a=z.icu_return_sensitivity;
 if(!a)return "";
 const difference=100*(a.later.exit_without_return24-a.earlier.exit_without_return24);
 return '<div class="figure transport-administrative">'+
  '<div class="figure-head"><div><span class="figure-kicker">ENDPOINT SENSITIVITY · ICU RE-ENTRY</span><h3>Leaving a stay is not always leaving intensive care.</h3><p>Some patients return to another ICU stay during the same hospital admission. Restricting first-stay exits to those without a return in the next 24 hours does not remove the historical shift.</p></div></div>'+
  '<div class="table-scroll"><table><caption>Five-day first ICU exit, with a 24-hour re-entry sensitivity</caption><thead><tr><th>Historical period</th><th>At-risk patients</th><th>All first ICU exits</th><th>Without return within 24h</th><th>With return in 24h, count</th></tr></thead><tbody>'+
  [a.earlier,a.later].map(x=>'<tr><th>'+esc(x.period)+'</th><td>'+fmt(x.n)+'</td><td>'+pct(x.original_exit,2)+'</td><td>'+pct(x.exit_without_return24,2)+'</td><td>'+fmt(x.exit_then_return24_n)+'</td></tr>').join("")+
  '</tbody></table></div><p class="figure-caution">'+ico("alert",17)+' The later-minus-earlier difference is '+fmt(difference,2)+' percentage points after excluding short-interval ICU returns. '+esc(a.caveat)+'</p></div>';
}
function transportExplorer(r){
 const z=r.transport;
 return '<section class="transport-section" aria-labelledby="transport-head">'+
 '<div class="section-heading heading-after"><div>'+label("THE NEW FINDING / TRANSPORT STRESS TEST")+'<h2 id="transport-head">The error lives in the hospital clock.</h2></div><p>Three trajectories reveal where a model stops describing its later clinical environment.</p></div>'+
 '<div class="figure"><div class="figure-head"><div><span class="figure-kicker">FIGURE · HISTORICAL TRANSPORT</span><h3>Actual care. Predicted care. Simulated care.</h3><p>Four future horizons from ICU hour 24, among '+fmt(z.cohort_n)+' patients. These are frequencies, not personalized risks.</p></div></div>'+
 '<div class="outcome-controls" role="group" aria-label="Transport outcome"><button type="button" data-transport-event="exit" aria-pressed="true" class="active">ICU discharge</button><button type="button" data-transport-event="death" aria-pressed="false">ICU death</button></div>'+
 '<div id="transport-graph"></div><div class="transport-legend"><span><i class="t-observed"></i>What happened</span><span><i class="t-history"></i>Prediction on actual histories</span><span><i class="t-simulated"></i>Fully simulated</span></div>'+
 '<div id="transport-interpretation" class="transport-reading" aria-live="polite"></div>'+
 '<details class="scientist-detail"><summary>Inspect all horizons, errors and uncertainty '+ico("arrow",16)+'</summary><div id="transport-exact-values"></div></details>'+
 '<p class="figure-caution">'+ico("alert",17)+' Prequential scores are based on actually observed histories; full simulation generates trajectories recursively. The components explain forecast failure, not the causal consequences of changing treatment.</p></div>'+
 '<div class="transport-findings">'+
 '<article><span class="figure-kicker">HISTORICAL REPLICATION</span><h3>An earlier failure, too.</h3><p>An earlier rolling-origin model (trained 2008–2013, calibrated 2014–2016, evaluated 2017–2019) also overpredicted five-day discharge.</p><div class="transport-large">'+fmt(z.earlier_rolling_origin.horizons.at(-1).exit_error*100,2)+'<span>percentage points</span></div><p class="tiny-note">Fixed-model patient bootstrap interval: '+fmt(z.earlier_rolling_origin.horizons.at(-1).exit_error_ci95[0]*100,2)+' to '+fmt(z.earlier_rolling_origin.horizons.at(-1).exit_error_ci95[1]*100,2)+'pp. Exploratory repeated historical testing, not prospective confirmation.</p></article>'+
 '<article><span class="figure-kicker">COMMON-SUPPORT STANDARDIZATION</span><h3>Not explained by recorded case mix alone.</h3><p>Standardizing recorded baseline severity and care history still leaves a lower discharge incidence in 2020–2022 versus 2017–2019.</p><div class="transport-large">'+fmt(z.historical_shift.standardized_exit_change*100,2)+'<span>percentage points</span></div><p class="tiny-note">Fixed-weight patient bootstrap interval '+fmt(z.historical_shift.ci95_fixed_weights[0]*100,2)+' to '+fmt(z.historical_shift.ci95_fixed_weights[1]*100,2)+'pp. Hidden illness severity and practice differences remain possible.</p></article>'+
 '</div>'+
 '<div class="figure"><div class="figure-head"><div><span class="figure-kicker">EXPLORATORY · ICU ENVIRONMENTS</span><h3>Where is the change most visible?</h3><p>Standardized five-day discharge differences by ICU group. Negative values mean fewer later-era discharges. These subgroup intervals are exploratory and not adjusted for multiple testing.</p></div></div>'+
 '<div class="table-scroll"><table><caption>ICU group differences between historical eras</caption><thead><tr><th>ICU group</th><th>Earlier / later n</th><th>Later minus earlier</th><th>95% interval</th></tr></thead><tbody>'+
 z.icu_unit_subgroups.map(x=>'<tr><th>'+esc(x.unit)+'</th><td>'+fmt(x.n_earlier)+' / '+fmt(x.n_later)+'</td><td>'+fmt(x.difference*100,2)+'pp</td><td>'+fmt(x.ci95[0]*100,2)+' to '+fmt(x.ci95[1]*100,2)+'pp</td></tr>').join("")+
 '</tbody></table></div></div>'+administrativeExitFigure(z)+'</section>';
}
function installTransportExplorer(r){
 if(!r.transport)return;
 const z=r.transport;
 function view(ev){
  $("#transport-graph").innerHTML=transportChart(z,ev);
  $$("[data-transport-event]").forEach(b=>{const on=b.dataset.transportEvent===ev;b.classList.toggle("active",on);b.setAttribute("aria-pressed",String(on));});
  const q=z.horizons.at(-1)[ev];
  const name=ev==="exit"?"ICU discharge":"ICU death";
  $("#transport-interpretation").innerHTML='<div class="transport-reading-heading">'+esc(name)+' at day five</div><div class="transport-reading-grid">'+
   '<div><span>Observed</span><strong>'+pct(q.observed,2)+'</strong></div>'+
   '<div><span>Predicted on real histories</span><strong>'+pct(q.prequential,2)+'</strong></div>'+
   '<div><span>Fully simulated</span><strong>'+pct(q.simulated,2)+'</strong></div></div>'+
   '<p>'+fmt(q.local_error*100,2)+'pp error already on the observed history; another '+fmt(q.recursive_error*100,2)+'pp when future states are generated. Their sum is '+fmt(q.total_error*100,2)+'pp. Signs indicate overprediction (+) or underprediction (−).</p>';
  $("#transport-exact-values").innerHTML='<div class="table-scroll"><table><caption>'+esc(name)+' by horizon; percentage points</caption><thead><tr><th>Hours</th><th>Observed</th><th>Actual-history forecast</th><th>Simulated</th><th>Historical error</th><th>Extra simulation error</th></tr></thead><tbody>'+
   z.horizons.map(h=>{const v=h[ev];return '<tr><th>'+h.hours+'h</th><td>'+pct(v.observed,2)+'</td><td>'+pct(v.prequential,2)+'</td><td>'+pct(v.simulated,2)+'</td><td>'+fmt(v.local_error*100,2)+'pp</td><td>'+fmt(v.recursive_error*100,2)+'pp</td></tr>'}).join("")+
   '</tbody></table></div><p class="tiny-note">The 95% patient-bootstrap interval for five-day historical '+esc(name.toLowerCase())+' error is '+fmt(q.local_ci95[0]*100,2)+' to '+fmt(q.local_ci95[1]*100,2)+' percentage points. It conditions on the fitted model. Simulation Monte Carlo variation is separate.</p>';
 }
 $$("[data-transport-event]").forEach(b=>b.addEventListener("click",()=>view(b.dataset.transportEvent)));
 view("exit");
}
function associationExplorer(r){
 return ['<div class="figure"><div class="figure-head"><div><span class="figure-kicker">FIGURE 04 · OBSERVATIONAL ASSOCIATIONS</span><h3>What changes around DNR orders?</h3><p>Differences in before–after care and monitoring, compared with eligible full-code risk sets.</p></div></div>',
 '<div class="effect-grid">'+r.decisions.effects.map(x=>{
  const num=fmt(x.estimate, x.unit==="percentage points"?2:4);
  const ci=x.ci.map(v=>fmt(v,x.unit==="percentage points"?2:4)).join(" to ");
  return '<div class="effect-card"><span>'+esc(x.label)+'</span><strong>'+num+'</strong><small>'+esc(x.unit)+'</small><p>Approximate 95% CI: '+esc(ci)+'</p></div>';
 }).join("")+'</div><div class="figure-caution">'+ico("alert",19)+' <p>'+esc(r.decisions.caution)+'</p></div></div>'].join('');
}
function dnrPlot(state,key){
 const names={
   invasive_ventilation:"Invasive-ventilation exposure",
   vasopressor_exposure:"Vasopressor exposure",
   map_recording:"Mean arterial-pressure recording intensity"};
 const x=state.outcomes[key],isShare=key!=="map_recording",units=isShare?"percentage points":"records / ICU hour";
 const arr=[
  {label:"Earlier placebo",key:"early_pre_event",note:"−24 to −12h, BEFORE the order"},
  {label:"Around the order",key:"near_order",note:"−4 to +4h"},
  {label:"Primary comparison",key:"primary",note:"−12 to +12h"}];
 const scale=isShare?100:1;
 const largest=Math.max(.04,...arr.flatMap(v=>x[v.key].ci95.map(n=>Math.abs(n*scale))))*1.26;
 const W=810,H=320,L=218,R=82,T=29;
 const center=(L+W-R)/2;
 const half=(W-R-L)/2;
 const project=q=>center+q*scale/largest*half;
 const ticks=[-1,-.5,0,.5,1].map(fr=>{
  const n=fr*largest;
  return '<line x1="'+project(n/scale)+'" x2="'+project(n/scale)+'" y1="34" y2="256" class="'+(fr===0?"dnr-zero":"dnr-chart-grid")+'"/>'+
   '<text x="'+project(n/scale)+'" y="275" text-anchor="middle" class="axis-label">'+(isShare?fmt(n,1):fmt(n,2))+'</text>';
 }).join("");
 const rows=arr.map((r,i)=>{
  const v=x[r.key],y=69+i*80;
  const x1=project(v.ci95[0]),x2=project(v.ci95[1]),xc=project(v.estimate);
  const color=i===2?"#167d68":"#b27751";
  return '<text x="18" y="'+(y-3)+'" class="dnr-row-title">'+esc(r.label)+'</text>'+
  '<text x="18" y="'+(y+15)+'" class="dnr-row-note">'+esc(r.note)+'</text>'+
  '<line x1="'+x1+'" x2="'+x2+'" y1="'+y+'" y2="'+y+'" stroke="'+color+'" stroke-width="4" stroke-linecap="round"/>'+
  '<line x1="'+x1+'" x2="'+x1+'" y1="'+(y-7)+'" y2="'+(y+7)+'" stroke="'+color+'" stroke-width="2"/>'+
  '<line x1="'+x2+'" x2="'+x2+'" y1="'+(y-7)+'" y2="'+(y+7)+'" stroke="'+color+'" stroke-width="2"/>'+
  '<circle cx="'+xc+'" cy="'+y+'" r="'+(i===2?7:5)+'" fill="'+color+'" stroke="#fffef9" stroke-width="2"><title>'+esc(names[key])+', '+r.label+': '+fmt(v.estimate*scale,isShare?2:4)+' '+units+'; interval '+fmt(v.ci95[0]*scale,2)+' to '+fmt(v.ci95[1]*scale,2)+'</title></circle>'+
  '<text x="'+(W-4)+'" y="'+(y+5)+'" class="dnr-chart-number" text-anchor="end">'+fmt(v.estimate*scale,isShare?2:3)+'</text>';
 }).join("");
 return '<svg class="dnr-forest" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+esc(names[key])+'. Three descriptive differences, before the order, around the order and over 12-hour intervals, with fixed-weight confidence intervals. Zero means no difference in changes.">'+ticks+rows+
 '<text x="'+center+'" y="308" text-anchor="middle" class="axis-label">DIFFERENCE IN BEFORE–AFTER CHANGES · '+esc(units.toUpperCase())+'</text></svg>';
}
function dnrRelease(catalog,t,r){
 const s=r.states.find(x=>x.id==="DNR_ONLY");
 const statCards=[
 ['FIRST DOCUMENTED DNR EVENTS',fmt(r.cohort.eligible_first_dnr),'Observed after full-code documentation'],
 ['MATCHABLE DNR EVENTS',fmt(r.cohort.represented_dnr),'DNR-only and DNR/DNI combined'],
 ['DNR-ONLY EVENTS',fmt(s.n_dnr),'Primary clinical question'],
 ['NO COMMON SUPPORT',fmt(r.cohort.outside_common_support),'Excluded from current risk-set analysis']
 ].map(x=>stat(x[0],x[1],x[2])).join("");
 renderTo([
 '<section class="release-hero dnr-release-hero"><div class="container">'+breadcrumbs(t,r),
 '<div class="release-hero-label">'+label("PROPHECY 2 / DNR FIRST","mint")+'<span>'+esc(dateFmt(r.date))+'</span></div>',
 '<h1>'+esc(r.title)+'<span class="mint-dot">.</span></h1>',
 '<p class="release-lead">'+esc(r.subtitle)+'</p>',
 '<div class="release-tags">'+statusPill(r.status)+statusPill("Causality not identified","pill-warn")+'</div>',
 '<div class="release-intro-meta"><span>MIMIC-IV v3.1 only</span><span>Forked before the general mortality simulator</span><span>Round '+r.round_number+'</span></div>',
 '</div></section>',
 '<section class="section section-overview"><div class="container">',
 '<div class="summary-insight"><p class="summary-question">THE QUESTION — NOT THE MODEL</p><p>'+esc(r.question.plain)+'</p><span>'+esc(r.question.identification_status)+'</span></div>',
 '<div class="stat-grid">'+statCards+'</div>',
 '<div class="dnr-meaning"><div>'+label("WHAT DNR ACTUALLY MEANS")+'<h2>CPR at arrest.<br><em>Not every other treatment.</em></h2></div><div><p>'+esc(r.question.intervention_definition)+'</p><p>That clinical distinction is why this fork separately studies DNR-only and DNR/DNI, rather than treating “DNR” as a single causal treatment.</p></div></div>',
 '<div class="lens-panel" id="dnr-lens"><div class="lens-header"><div>'+label("READ THE RESEARCH")+'<h3>One DNR question, two explanations.</h3></div><div class="lens-switch" role="group" aria-label="Reading level"><button type="button" data-dnr-lens="public" aria-pressed="true">Plain language</button><button type="button" data-dnr-lens="scientific" aria-pressed="false">Scientific detail</button></div></div>',
 '<div class="lens-copy" data-dnr-lens-view="public"><p>Patients often receive DNR orders when they are already very ill. When treatment subsequently changes, that does not tell us whether the order caused the change or whether clinicians and patients were already making broader decisions. Our study puts those explanations against the actual treatment record—and shows where the comparison fails.</p></div>',
 '<div class="lens-copy hidden" data-dnr-lens-view="scientific"><p>'+esc(r.methods.estimand)+' The DNR-only target is not an identified potential-outcome contrast. Subtype-specific entropy calibration, early negative controls, competing exit accounting and effective-control concentration form the falsification strategy.</p></div></div>',
 '<div class="section-heading heading-after"><div>'+label("01 / OBSERVED CARE")+'<h2>What changes at the order?</h2></div><p>Switch between DNR-only and DNR/DNI. Compare ventilation, vasopressors or pressure monitoring. The reference is an eligible full-code risk set—not a selected group of patients who later die.</p></div>',
 '<div class="figure dnr-main-figure"><div class="dnr-control-top"><div><span class="figure-kicker">A DECISION IS NOT A TREATMENT BUNDLE</span><h3>Two orders. Different clinical meanings.</h3></div><div class="dnr-status-tabs" role="group" aria-label="Type of DNR order">'+
 r.states.map(x=>'<button type="button" data-dnr-status="'+esc(x.id)+'" aria-pressed="'+String(x.id==="DNR_ONLY")+'" class="'+(x.id==="DNR_ONLY"?"active":"")+'">'+esc(x.label)+'</button>').join("")+
 '</div></div>',
 '<p id="dnr-state-meaning" class="dnr-state-meaning"></p>',
 '<div class="dnr-metric-controls" role="group" aria-label="Outcome to inspect"><button type="button" class="active" data-dnr-metric="invasive_ventilation" aria-pressed="true">Ventilation</button><button type="button" data-dnr-metric="vasopressor_exposure" aria-pressed="false">Vasopressors</button><button type="button" data-dnr-metric="map_recording" aria-pressed="false">Pressure monitoring</button></div>',
 '<div id="dnr-effect-chart" aria-live="polite"></div>',
 '<p class="dnr-forest-caption">Shown: weighted difference between the DNR group’s before–after change and the contemporaneously eligible full-code risk set, with approximate fixed-weight patient-clustered intervals. Earlier-placebo trend is measured before the order. These are <strong>associations, not effects caused by DNR</strong>.</p>',
 '<div id="dnr-effect-interpretation" class="dnr-effect-interpretation"></div>',
 '</div>',
 '<div class="section-heading heading-after"><div>'+label("02 / REAL TREATMENT EVENTS")+'<h2>What did clinicians record?</h2></div><p>Time-aligned extubation, later documentation and short-term mortality are different outcomes. None reveals a person’s wishes or the reason for a clinical decision by itself.</p></div>',
 '<div id="dnr-event-cards" class="dnr-event-cards"></div>',
 '<div class="dnr-pathway"><span class="figure-kicker">THE CORE CAUSAL PROBLEM</span><h3>Severe short-term mortality imbalance remains.</h3><div id="dnr-mortality-compare"></div><p>The unmatched prognosis and clinical intentions are not known merely because the measured variables were balanced. Do not convert this contrast into “deaths caused by DNR.”</p></div>',
 '<div class="section-heading heading-after"><div>'+label("03 / FALSIFICATION")+'<h2>Does the comparison survive scrutiny?</h2></div></div>',
 '<div class="dnr-falsification"><article><span>BASELINE MEASURED BALANCE</span><h3 id="dnr-balance-value"></h3><p>The maximum standardized difference on recorded covariates after within-subtype balancing. Zero is not proof of unmeasured exchangeability.</p></article>',
 '<article><span>WHEN EFFECTIVE CONTROLS DISAPPEAR</span><h3 id="dnr-overlap-value"></h3><p>Risk sets with fewer than two effective controls after weighting. A good average match can still conceal extremely concentrated weights.</p></article>',
 '<article><span>STRICTER OVERLAP RESTRICTION</span><h3 id="dnr-strict-value"></h3><p id="dnr-strict-text"></p></article></div>',
 '<div class="figure"><div class="figure-head"><div><span class="figure-kicker">DATA-PROVENANCE GO / NO-GO</span><h3>Can physician preference identify a causal DNR effect?</h3><p>Not from the currently documented assignment mechanism.</p></div></div>',
 '<div class="dnr-provider-audit"><strong>'+fmt(r.provenance.ordering_provider_matches_hospital_admitting)+' <span>/ '+fmt(r.provenance.icu_code_orders)+'</span></strong><p>ICU-time code-status orders entered by the patient’s hospital admitting provider.</p></div>',
 '<p class="figure-caution">'+ico("alert",17)+' The ordering clinician appears at the decision; the hospital admitting clinician is not automatically the ICU attending. A strong instrument first stage cannot establish assignment independence or exclusion.</p></div>',
 '<div class="dnr-fork-footer"><div>'+label("WHERE THE FORK HAPPENED")+'<h2>Back to the order, not another black-box prognosis model.</h2><p>'+esc(r.lineage.from_stage)+'. This track stops at the limits of identification rather than treating better prediction as an answer to the DNR question.</p></div>',
 '<div class="dnr-fork-actions"><a class="button button-dark" href="'+pathFor(t)+'methods/">Read the identification design '+ico("arrow")+'</a><a class="text-link" target="_blank" rel="noopener noreferrer" href="https://github.com/autonomio/Mimicry/pull/8">Review the research PR '+ico("arrow",16)+'</a></div></div>',
 '</div></section>'
 ].join(""));
 $("#dnr-lens").querySelectorAll("[data-dnr-lens]").forEach(btn=>btn.addEventListener("click",()=>{
  const key=btn.dataset.dnrLens;
  $$("[data-dnr-lens]",$("#dnr-lens")).forEach(x=>x.setAttribute("aria-pressed",String(x===btn)));
  $$("[data-dnr-lens-view]",$("#dnr-lens")).forEach(x=>x.classList.toggle("hidden",x.dataset.dnrLensView!==key));
 }));
 installDnrExplorer(r);
}
function installDnrExplorer(r){
 let status="DNR_ONLY",metric="invasive_ventilation";
 const names={invasive_ventilation:"Invasive ventilation",vasopressor_exposure:"Vasopressor exposure",map_recording:"MAP recording"};
 const mapStatus=()=>r.states.find(x=>x.id===status);
 const pctpp=(a,d=1)=>fmt(a*100,d)+" percentage points";
 const evCard=(title,x,note)=>'<article><span>'+esc(title)+'</span><div class="dnr-event-pair"><strong>'+pct(x.dnr,2)+'</strong><span>vs '+pct(x.full_code_control,2)+'</span></div><p>'+esc(note)+'</p></article>';
 function render(){
  const s=mapStatus(),eff=s.outcomes[metric].primary;
  const isRate=metric==="map_recording";
  const scale=isRate?1:100;
  const units=isRate?"recordings per ICU hour":"percentage points";
  $$("[data-dnr-status]").forEach(b=>{const on=b.dataset.dnrStatus===status;b.classList.toggle("active",on);b.setAttribute("aria-pressed",String(on));});
  $$("[data-dnr-metric]").forEach(b=>{const on=b.dataset.dnrMetric===metric;b.classList.toggle("active",on);b.setAttribute("aria-pressed",String(on));});
  $("#dnr-state-meaning").textContent=fmt(s.n_dnr)+" cases · "+s.meaning+". Not a random assignment.";
  $("#dnr-effect-chart").innerHTML=dnrPlot(s,metric);
  $("#dnr-effect-interpretation").innerHTML='<strong>'+esc(names[metric])+': '+fmt(eff.estimate*scale,isRate?4:2)+' '+esc(units)+'</strong>'+
  '<p>Approximate interval '+fmt(eff.ci95[0]*scale,isRate?4:2)+' to '+fmt(eff.ci95[1]*scale,isRate?4:2)+' '+esc(units)+'. This is the change in <em>recorded ICU treatment or monitoring rates</em>, not a DNR treatment effect.</p>';
  $("#dnr-event-cards").innerHTML=evCard("Extubation recorded within four hours",s.events.extubation_within_4h,"Procedure documentation; not proof of withdrawal as opposed to recovery or another care decision.")+
    evCard("New comfort-only status within 12 hours",s.events.documented_cmo_within_12h,"Structured documentation can miss conversations and other contemporaneous care limitations.")+
    evCard("ICU exit within 12 hours",s.events.icu_exit_within_12h,"Death and discharge change how long support and measurements can be observed.");
  const m=s.events.death_within_12h;
  $("#dnr-mortality-compare").innerHTML='<div><span>New '+esc(s.label)+' order</span><strong>'+pct(m.dnr,2)+'</strong></div><span class="dnr-versus">VERSUS</span><div><span>Eligible full-code comparator</span><strong>'+pct(m.full_code_control,2)+'</strong></div>';
  $("#dnr-balance-value").textContent=fmt(s.measured_balance.max_absolute_smd,3)+" max |SMD|";
  $("#dnr-overlap-value").textContent=fmt(s.positivity.risk_sets_under_two_effective_controls)+" / "+fmt(s.n_dnr);
  $("#dnr-strict-value").textContent=fmt(s.positivity.strict_n)+" cases";
  const strict=s.outcomes[metric].strict_overlap;
  const balance=s.positivity.strict_max_smd;
  const bad=balance>=.10;
  $("#dnr-strict-text").textContent="Restricting to risk sets with at least two effective controls gives an estimate of "+fmt(strict.estimate*scale,isRate?4:2)+" "+units+". But the strict group's maximum measured |SMD| is "+fmt(balance,3)+(bad?"—above the 0.10 diagnostic threshold. This does not validate that estimate.":"; unmeasured prognosis remains unresolved.");
 }
 $$("[data-dnr-status]").forEach(b=>b.addEventListener("click",()=>{status=b.dataset.dnrStatus;render();}));
 $$("[data-dnr-metric]").forEach(b=>b.addEventListener("click",()=>{metric=b.dataset.dnrMetric;render();}));
 render();
}

function release(catalog,t,r){
 if(r.kind==="dnr-audit")return dnrRelease(catalog,t,r);
 const latest=catalog.releases.find(x=>x.track===t.id)?.id===r.id;
 renderTo([
 '<section class="release-hero"><div class="container">'+breadcrumbs(t,r),
 '<div class="release-hero-label">'+label(t.name.toUpperCase()+" / RESEARCH RELEASE","mint")+'<span>'+esc(dateFmt(r.date))+'</span></div>',
 '<h1>'+esc(r.title)+'<span class="mint-dot">.</span></h1>',
 '<p class="release-lead">'+esc(r.subtitle)+'</p><div class="release-tags">'+statusPill(r.status)+statusPill(r.simulation.validation,'pill-warn')+'</div>',
 '<div class="release-intro-meta"><span>Dataset: '+esc(r.dataset)+'</span><span>Round '+String(r.round_number).padStart(2,'0')+'</span><span>Version '+esc(r.id)+'</span></div>',
 '</div></section>',
 '<section class="section section-overview"><div class="container">',
 resultSummary(r),
 '<div class="stat-grid">'+stat("PATIENTS",fmt(r.summary.patients),"Distinct first ICU stays")+stat("SIX-HOUR LANDMARKS",fmt(r.summary.landmarks),"Observed histories")+stat("OUT-OF-SAMPLE TEST",fmt(r.summary.test),"Latest historical cohort")+stat("PREDICTIVE IMPROVEMENT",fmt(r.prediction.improvement.relative*100,1)+"%","Relative reduction in log loss")+'</div>',
 narrativeModes(r),
 r.transport?transportExplorer(r):"",
 '<div class="section-heading heading-after"><div>'+label("01 / PREDICTION")+'<h2>What does the model learn?</h2></div><p>The difference between a physiological forecast and a forecast that also sees what treatment and monitoring have occurred.</p></div>',
 modelExplorer(r),renderCalibration(r),
 '<div class="section-heading heading-after"><div>'+label("02 / MODEL VALIDATION")+'<h2>The full trajectory test</h2></div><p>Longitudinal simulation must recreate ICU discharge and occupancy, not merely fit the risk of death.</p></div>',
 outcomeExplorer(r),
 '<div class="section-heading heading-after"><div>'+label("03 / TREATMENT AND MONITORING")+'<h2>Care is part of the record</h2></div><p>These are observational associations. They do not isolate what the DNR designation caused.</p></div>',
 associationExplorer(r),
 '<div class="closing-interpretation"><div>'+label("WHAT THIS DOES NOT SHOW")+'<h2>Prediction is not a policy experiment.</h2></div><p>'+esc(r.methods.warnings[2])+' '+esc(r.methods.warnings[3])+'</p></div>',
 '<div class="read-next"><div><span>CONTINUE READING</span><h3>How was this established?</h3><p>Understand the design, assumptions, chronology and verification rules.</p></div><a href="'+pathFor(t)+'methods/" class="button button-dark">Read the methods '+ico("arrow")+'</a></div>',
 '</div></section>'
 ].join(""));
 $("#lens-panel").querySelectorAll("[data-lens]").forEach(btn=>btn.addEventListener("click",()=>{
  const mode=btn.dataset.lens;
  $$("[data-lens]",$("#lens-panel")).forEach(x=>x.setAttribute("aria-pressed",String(x===btn)));
  $$("[data-lens-view]",$("#lens-panel")).forEach(x=>x.classList.toggle("hidden",x.dataset.lensView!==mode));
 }));
 installModelExplorer(r);installCalibration(r);installOutcomeExplorer(r);installTransportExplorer(r);
}
function notFound(){
 renderTo(frame("404 / Not found","This page isn't in the record.","The research may have moved, or this route was never published.")+'<section class="section section-compact"><div class="container"><a href="/" class="button button-dark">Return to Mimicry '+ico("arrow")+'</a></div></section>');
}
async function load(){
 try{
  const response=await fetch("/data/catalog.json",{cache:"no-cache"});
  if(!response.ok) throw new Error("Could not read research catalog");
  const catalog=await response.json();
  header(catalog);footer(catalog);
  const parts=currentPath.split("/").filter(Boolean);
  const trackSlug=parts[0]==="tracks"?parts[1]:null;
  const t=trackSlug?catalog.tracks.find(x=>x.slug===trackSlug):null;
  let pageData=null;
  if(t&&parts[2]==="releases"&&parts[3]){
    const meta=catalog.releases.find(x=>x.id===parts[3]&&x.track===t.id);
    if(!meta) return notFound();
    const rr=await fetch("/data/rounds/"+encodeURIComponent(meta.id)+".json",{cache:"no-cache"});
    if(!rr.ok) throw new Error("Research release could not be loaded");
    pageData=await rr.json();
  }
  if(parts.length===0)home(catalog);
  else if(parts[0]==="research"&&parts.length===1)research(catalog);
  else if(parts[0]==="about"&&parts.length===1)about();
  else if(t&&parts.length===2)track(catalog,t);
  else if(t&&parts[2]==="methods"&&parts.length===3)methods(catalog,t);
  else if(t&&parts[2]==="releases"&&parts.length===3)releases(catalog,t);
  else if(t&&parts[2]==="releases"&&pageData)release(catalog,t,pageData);
  else notFound();
 }catch(error){
  console.error(error);
  renderTo('<section class="error-screen container"><p class="eyebrow">RESEARCH UNAVAILABLE</p><h1>The evidence could not be loaded.</h1><p>Please try again or read the versioned source in GitHub.</p><a class="button button-dark" href="https://github.com/autonomio/Mimicry">Open repository '+ico("arrow")+'</a></section>');
 }
}
load();

