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
   '<a href="/tracks/prophecy/" '+(activeTrack==="prophecy"?'aria-current="page"':"")+'>Prophecy</a>',
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
 const t=catalog.tracks[0], latest=catalog.releases.find(r=>r.track===t.id);
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
function track(catalog,t){
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
 '<section class="section section-compact"><div class="container"><div class="about-grid">',
 '<article><span class="about-number">01</span><h2>Methods before confidence</h2><p>Every numerical claim needs a defined population, outcome, time zero and analysis design. Predictive scores cannot be mistaken for treatment effects.</p></article>',
 '<article><span class="about-number">02</span><h2>Failure is part of evidence</h2><p>Out-of-sample validation and multi-horizon calibration are acceptance gates. If a simulator gets discharge wrong, it is not a validated model.</p></article>',
 '<article><span class="about-number">03</span><h2>Patient privacy is non-negotiable</h2><p>Underlying MIMIC-IV patient records remain in their controlled server environment. This public portal contains reviewed aggregate releases and research code only.</p></article>',
 '<article><span class="about-number">04</span><h2>Living, versioned science</h2><p>A new research round is published as an immutable, reviewed release with a dated URL. The live track page then points to the newest public result.</p></article>',
 '</div><div class="callout-dark"><div>'+label("OPEN RESEARCH","mint")+'<h2>Follow the code,<br><em>not just the conclusion.</em></h2></div><a href="https://github.com/autonomio/Mimicry" rel="noopener noreferrer" target="_blank" class="button button-primary">View GitHub repository '+ico("arrow")+'</a></div></div></section>');
}
function methods(catalog,t){
 const r=catalog.releases.find(x=>x.track===t.id);
 if(!r) return renderTo(frame(t.name,"Methods forthcoming","This research track has not published a method record."));
 const m=r.methods;
 const warnings=m.warnings.map((w,i)=>'<li><span>'+String(i+1).padStart(2,"0")+'</span><p>'+esc(w)+'</p></li>').join("");
 renderTo(frame(t.name+" / reproducibility","Methods, not mythology.","How the findings were obtained, what they mean, and what the data cannot identify.")+
 '<section class="section section-compact"><div class="container method-content">',
 '<div class="method-lead"><div>'+label("RESEARCH DESIGN")+'<h2>A six-hour view of a changing system</h2></div><p>'+esc(m.cohort)+' '+esc(m.historical_split)+'</p></div>',
 '<div class="method-flow"><div><span>01</span><strong>Patient state</strong><small>Recorded history at t</small></div><div><span>02</span><strong>Care transitions</strong><small>Decisions and support</small></div><div><span>03</span><strong>Observation</strong><small>What is measured</small></div><div><span>04</span><strong>Competing exits</strong><small>Discharge and death</small></div></div>',
 '<div class="method-two"><div><h3>What is being evaluated?</h3><p>'+esc(m.metrics)+'</p></div><div><h3>What is not being estimated?</h3><p>We do not estimate the effect of a hypothetical no-DNR policy or infer a patient would survive under different treatment decisions. Identifying those questions requires additional assumptions or data.</p></div></div>',
 '<div class="limitations">'+label("NON-NEGOTIABLE LIMITATIONS")+'<h2>Read this before drawing conclusions</h2><ol>'+warnings+'</ol></div>',
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
   return '<div class="model-row '+(isBest?'model-row-best':'')+'"><div class="model-name">'+esc(m.label)+(isBest?'<span>FULL HISTORY</span>':'')+'</div><div class="model-track"><div class="model-fill" style="width:'+clamp(m.loss/0.39*100,0,100)+'%"></div></div><div class="model-number">'+fmt(m.loss,5)+'</div><div class="model-delta '+(delta<0?'negative':'')+'">'+(Math.abs(delta)<0.00001?'Baseline':(delta>0?'−':'+')+fmt(Math.abs(delta),5))+'</div></div>'
  }).join("");
 };
 $("#model-baseline").addEventListener("change",render);render();
}
function renderCalibration(r) {
 const mx=Math.max(...r.prediction.calibration.flatMap(x=>[x.observed,x.predicted]))*1.22;
 return '<div class="figure"><div class="figure-head"><div><span class="figure-kicker">FIGURE 02 · CALIBRATION</span><h3>A good score is not enough.</h3><p>How often the event occurred, versus its average predicted probability in the test cohort.</p></div></div>'+
 '<div class="calibration-list">'+r.prediction.calibration.map(x=>{
  const w1=x.observed/mx*100,w2=x.predicted/mx*100;
  return '<div class="cal-row"><div class="cal-row-title">'+esc(x.event)+'</div><div class="cal-axis"><span class="cal-stem" style="left:'+Math.min(w1,w2)+'%;width:'+Math.abs(w1-w2)+'%"></span><span class="cal-point actual-point" style="left:'+w1+'%"></span><span class="cal-point predicted-point" style="left:'+w2+'%"></span></div><div class="cal-values"><span>'+pct(x.observed,2)+'</span><span>'+pct(x.predicted,2)+'</span></div></div>'
 }).join("")+'</div>'+
 '<div class="chart-legend"><span><i class="actual-legend"></i>Observed</span><span><i class="predicted-legend"></i>Predicted</span></div>'+
 '<p class="figure-caution">'+ico("alert",17)+' ICU death is underpredicted in the later historical test set. Absolute risk estimates are not adequate for clinical use.</p></div>';
}
function lineChart(horizons,which){
 const keys={death:"Death",exit:"Discharged from ICU",icu:"Remaining in ICU"};
 const series=horizons.map(h=>({h:h.hours,a:h[which].observed*100,b:h[which].simulated*100}));
 const highest=Math.max(...series.flatMap(x=>[x.a,x.b]));
 const max=Math.max(1,Math.ceil(highest*1.18/(highest>25?10:highest>8?2:1))*(highest>25?10:highest>8?2:1));
 const W=720,H=330,L=60,R=18,T=22,B=55;
 const x=(i)=>L+(W-L-R)*i/(series.length-1);
 const y=v=>T+(H-T-B)*(1-v/max);
 const path=key=>series.map((d,i)=>(i?'L':'M')+x(i).toFixed(2)+' '+y(d[key]).toFixed(2)).join(' ');
 const grid=[0,.25,.5,.75,1].map(fr=>'<line x1="'+L+'" y1="'+y(max*fr)+'" x2="'+(W-R)+'" y2="'+y(max*fr)+'" class="chart-grid"/><text x="'+(L-12)+'" y="'+(y(max*fr)+4)+'" text-anchor="end" class="axis-label">'+fmt(max*fr,highest<10?1:0)+'%</text>').join("");
 const xticks=series.map((d,i)=>'<text x="'+x(i)+'" y="'+(H-20)+'" text-anchor="middle" class="axis-label">'+d.h+'h</text>').join("");
 const pts=key=>series.map((d,i)=>'<circle cx="'+x(i)+'" cy="'+y(d[key])+'" r="5" class="point-'+key+'"><title>'+keys[which]+' · '+d.h+'h · '+(key==="a"?"Observed ":"Simulated ")+fmt(d[key],2)+'%</title></circle>').join("");
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
function associationExplorer(r){
 return ['<div class="figure"><div class="figure-head"><div><span class="figure-kicker">FIGURE 04 · OBSERVATIONAL ASSOCIATIONS</span><h3>What changes around DNR orders?</h3><p>Differences in before–after care and monitoring, compared with eligible full-code risk sets.</p></div></div>',
 '<div class="effect-grid">'+r.decisions.effects.map(x=>{
  const num=fmt(x.estimate, x.unit==="percentage points"?2:4);
  const ci=x.ci.map(v=>fmt(v,x.unit==="percentage points"?2:4)).join(" to ");
  return '<div class="effect-card"><span>'+esc(x.label)+'</span><strong>'+num+'</strong><small>'+esc(x.unit)+'</small><p>Approximate 95% CI: '+esc(ci)+'</p></div>';
 }).join("")+'</div><div class="figure-caution">'+ico("alert",19)+' <p>'+esc(r.decisions.caution)+'</p></div></div>'].join('');
}
function release(catalog,t,r){
 const latest=catalog.releases.find(x=>x.track===t.id)?.id===r.id;
 renderTo([
 '<section class="release-hero"><div class="container">'+breadcrumbs(t,r),
 '<div class="release-hero-label">'+label("PROPHECY / RESEARCH RELEASE","mint")+'<span>'+esc(dateFmt(r.date))+'</span></div>',
 '<h1>'+esc(r.title)+'<span class="mint-dot">.</span></h1>',
 '<p class="release-lead">'+esc(r.subtitle)+'</p><div class="release-tags">'+statusPill(r.status)+statusPill(r.simulation.validation,'pill-warn')+'</div>',
 '<div class="release-intro-meta"><span>Dataset: '+esc(r.dataset)+'</span><span>Historical test: 2020–2022</span><span>Version '+esc(r.id)+'</span></div>',
 '</div></section>',
 '<section class="section section-overview"><div class="container">',
 resultSummary(r),
 '<div class="stat-grid">'+stat("PATIENTS",fmt(r.summary.patients),"Distinct first ICU stays")+stat("SIX-HOUR LANDMARKS",fmt(r.summary.landmarks),"Observed histories")+stat("OUT-OF-SAMPLE TEST",fmt(r.summary.test),"Latest historical cohort")+stat("PREDICTIVE IMPROVEMENT",fmt(r.prediction.improvement.relative*100,1)+"%","Relative reduction in log loss")+'</div>',
 narrativeModes(r),
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
 installModelExplorer(r);installOutcomeExplorer(r);
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
