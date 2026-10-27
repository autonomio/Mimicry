import {COLORS,STATUS_LABELS,svg,el,clamp,lineScale,nfmt,asPercent,prefersReducedMotion} from "./core.js";

/**
 * Aggregate CohortSpace: study-filter animation, NOT patient trajectories.
 * SVG circles are positioned by actual summary statistics; area ∝ N.
 * Every reported cell has at least 30 source encounters.
 */
export function mountCohortSpace(root,dataset,{getSubtype,onSubtypeChange}){
 const layout={w:900,h:520,l:94,r:56,t:36,b:92};
 const x=lineScale([0,10],[layout.l,layout.w-layout.r]);
 const y=lineScale([0,.8],[layout.h-layout.b,layout.t]);
 const all=dataset.cohort_bubbles.points;
 const keys=[...new Map(all.map(p=>[p.id,{id:p.id,unit:p.unit,subtype:p.subtype}])).values()];
 const maxN=Math.max(...all.map(p=>p.n));
 let stage="eligible",selectedUnit=null,transition=null;
 const board=svg("svg",{viewBox:"0 0 900 520",role:"img",
  "aria-label":"Aggregate ICU cohorts, positioned by mean first-day SOFA and proportion of pre-order invasive ventilation. Circles represent different ICU groups and code status subtypes, not patients."});
 board.classList.add("mv-bubble-chart");
 root.replaceChildren(board);
 const bg=svg("rect",{x:0,y:0,width:900,height:520,fill:"transparent"});
 board.append(bg);
 for(const val of [0,.2,.4,.6,.8]){
  const yy=y(val);
  board.append(svg("line",{x1:layout.l,y1:yy,x2:layout.w-layout.r,y2:yy,class:"mv-chart-grid"}));
  const text=svg("text",{x:layout.l-15,y:yy+5,"text-anchor":"end",class:"mv-tick"});
  text.textContent=Math.round(val*100)+"%";
  board.append(text);
 }
 for(const val of [0,2,4,6,8,10]){
  const xx=x(val);
  board.append(svg("line",{x1:xx,y1:layout.t,x2:xx,y2:layout.h-layout.b,class:"mv-chart-grid mv-chart-grid-x"}));
  const t=svg("text",{x:xx,y:layout.h-layout.b+29,"text-anchor":"middle",class:"mv-tick"});
  t.textContent=val;
  board.append(t);
 }
 const xLabel=svg("text",{x:(layout.l+layout.w-layout.r)/2,y:layout.h-28,"text-anchor":"middle",class:"mv-axis-title"});
 xLabel.textContent="MEAN DAY-ONE SOFA · HIGHER = MORE ORGAN DYSFUNCTION";
 board.append(xLabel);
 const yLabel=svg("text",{x:25,y:260,transform:"rotate(-90 25 260)","text-anchor":"middle",class:"mv-axis-title"});
 yLabel.textContent="INVASIVE VENTILATION IN PREVIOUS SIX HOURS";
 board.append(yLabel);
 const bubbles=new Map();
 const mgrp=svg("g",{class:"mv-bubbles"});
 board.append(mgrp);
 for(const key of keys){
  const group=svg("g",{role:"button",tabindex:"0","aria-label":STATUS_LABELS[key.subtype]+", "+key.unit});
  group.classList.add("mv-bubble-mark");
  const halo=svg("circle",{cx:0,cy:0,r:0,class:"mv-bubble-halo"});
  const dot=svg("circle",{cx:0,cy:0,r:0,fill:COLORS[key.subtype],class:"mv-bubble-dot"});
  const label=svg("text",{x:0,y:0,"text-anchor":"middle",class:"mv-bubble-name"});
  const title=svg("title");title.textContent=STATUS_LABELS[key.subtype]+", "+key.unit+" — aggregate";
  group.append(halo,dot,label,title);
  mgrp.append(group);
  const info={key,group,halo,dot,label,current:{cx:0,cy:0,r:0},target:{cx:0,cy:0,r:0}};
  bubbles.set(key.id,info);
  group.addEventListener("pointerenter",()=>{selectedUnit=key.id;detail();});
  group.addEventListener("focus",()=>{selectedUnit=key.id;detail();});
  group.addEventListener("pointerleave",()=>{selectedUnit=null;detail();});
  group.addEventListener("blur",()=>{selectedUnit=null;detail();});
  const click=()=>onSubtypeChange(key.subtype);
  group.addEventListener("click",click);
  group.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();click();}});
 }
 const rootCard=document.querySelector("#mv-space-detail");
 const summary=document.querySelector("#mv-stage-summary");
 const table=document.querySelector("#mv-space-table");
 function detail(){
  const p=all.find(d=>d.id===selectedUnit&&d.stage===stage)
    || all.filter(d=>d.stage===stage&&d.subtype===getSubtype())
      .sort((a,b)=>b.n-a.n)[0];
  if(!p)return;
  rootCard.innerHTML='<span class="mv-mono">'+p.unit+' / '+STATUS_LABELS[p.subtype]+'</span>'+
   '<strong>'+nfmt(p.n)+'</strong><small>documented orders in this aggregate</small>'+
   '<p>Mean SOFA <b>'+nfmt(p.sofa,2)+'</b> · invasive ventilation during the previous six hours <b>'+asPercent(p.invasive_before,1)+'</b>.</p>';
 }
 function stageSummary(){
  const info=dataset.cohort_bubbles.counts[stage];
  const visible=all.filter(x=>x.stage===stage);
  const unseen=info.n-visible.reduce((acc,x)=>acc+x.n,0);
  const s=dataset.cohort_bubbles.stages.find(x=>x.id===stage);
  summary.innerHTML='<div><span class="mv-mono">CURRENT ANALYTIC POPULATION</span>'+
   '<strong>'+nfmt(info.n)+'</strong><p>'+s.explanation+'</p></div>'+
   '<div class="mv-stage-subcounts"><span><i class="mv-dot mv-dnr"></i>DNR only '+nfmt(info.subtypes.DNR_ONLY)+'</span>'+
   '<span><i class="mv-dot mv-dni"></i>DNR + DNI '+nfmt(info.subtypes.DNR_DNI)+'</span></div>';
  const msg=document.querySelector("#mv-space-censor");
  msg.textContent="To protect small groups and small between-stage changes, MICU is shown separately and all other ICU units are pooled into one aggregate. Every stage uses the same grouping.";
  table.innerHTML='<thead><tr><th>ICU group</th><th>Documented order</th><th>Count</th><th>SOFA mean</th><th>Ventilation before order</th></tr></thead><tbody>'+
   visible.sort((a,b)=>b.n-a.n).map(p=>'<tr><th>'+p.unit+'</th><td>'+STATUS_LABELS[p.subtype]+'</td><td>'+nfmt(p.n)+'</td><td>'+nfmt(p.sofa,2)+'</td><td>'+asPercent(p.invasive_before,1)+'</td></tr>').join("")+
   '</tbody>';
 }
 function paint(){
  for(const z of bubbles.values()){
   const q=z.current,active=q.r>.2,focused=z.key.subtype===getSubtype();
   z.group.setAttribute("opacity",String(active?(focused?1:.34):0));
   z.group.setAttribute("pointer-events",active?"auto":"none");
   z.group.setAttribute("aria-hidden",active?"false":"true");
   z.group.setAttribute("tabindex",active?"0":"-1");
   for(const c of [z.dot,z.halo]){
    c.setAttribute("cx",q.cx.toFixed(2));
    c.setAttribute("cy",q.cy.toFixed(2));
   }
   z.dot.setAttribute("r",q.r.toFixed(2));
   z.halo.setAttribute("r",(q.r+5).toFixed(2));
   z.label.setAttribute("x",q.cx);
   z.label.setAttribute("y",q.cy+3);
   z.label.textContent=active&&q.r>25?(z.key.unit==="Other ICU units"?"Other":z.key.unit):"";
  }
 }
 function setStage(next){
  if(transition)cancelAnimationFrame(transition);
  stage=next;
  const visible=new Map(all.filter(p=>p.stage===stage).map(p=>[p.id,p]));
  const begin=new Map([...bubbles].map(([id,z])=>[id,{...z.current}]));
  for(const z of bubbles.values()){
   const p=visible.get(z.key.id);
   z.target=p?{cx:x(p.sofa),cy:y(p.invasive_before),r:Math.max(9,radiusFromN(p.n))}:
    {...z.current,r:0};
  }
  stageSummary();
  if(selectedUnit&&!visible.has(selectedUnit))selectedUnit=null;
  detail();
  const updateButtons=()=>document.querySelectorAll("[data-mv-stage]").forEach(btn=>{
   const active=btn.dataset.mvStage===stage;
   btn.classList.toggle("active",active);
   btn.setAttribute("aria-pressed",String(active));
  });
  updateButtons();
  if(prefersReducedMotion()){
   for(const z of bubbles.values())z.current={...z.target};
   paint();return;
  }
  const started=performance.now(),dur=680;
  function frame(t){
   const f=clamp((t-started)/dur,0,1),ease=1-Math.pow(1-f,3);
   for(const [id,z] of bubbles){
    const a=begin.get(id),b=z.target;
    z.current={
     cx:a.cx+(b.cx-a.cx)*ease,
     cy:a.cy+(b.cy-a.cy)*ease,
     r:a.r+(b.r-a.r)*ease
    };
   }
   paint();
   if(f<1)transition=requestAnimationFrame(frame);
  }
  transition=requestAnimationFrame(frame);
 }
 function radiusFromN(n){return Math.sqrt(n/maxN)*62;}
 function setSubtype(subtype){paint();if(!selectedUnit)detail();}
 for(const z of bubbles.values())z.current={...z.target};
 // Initial paint without an implied transition from an arbitrary origin.
 function init(){
  stage="eligible";
  for(const z of bubbles.values()){
   const p=all.find(p=>p.stage===stage&&p.id===z.key.id);
   z.current=z.target=p?{cx:x(p.sofa),cy:y(p.invasive_before),r:Math.max(9,radiusFromN(p.n))}:
    {cx:layout.l,cy:layout.h-layout.b,r:0};
  }
  paint();stageSummary();detail();
 }
 init();
 return {setStage,setSubtype,getStage:()=>stage,destroy:()=>{if(transition)cancelAnimationFrame(transition);}};
}
