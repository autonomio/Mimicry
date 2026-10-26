import {STATUS_LABELS,svg,nfmt,esc,intervalStatistic} from "./core.js";

/**
 * EvidenceMatrix: each point and whisker is a real reported aggregate
 * estimate and its CONDITIONAL interval; never draws confidence bands
 * where the research has no interval.
 */
export function mountEvidenceMatrix(root,release,{getSubtype}){
 const metricDefs=[
  {id:"invasive_ventilation",label:"Invasive ventilation",unit:"pp",mult:100},
  {id:"vasopressor_exposure",label:"Vasopressor exposure",unit:"pp",mult:100},
  {id:"map_recording",label:"MAP recording",unit:"/h",mult:1}
 ];
 const specs=[
  {id:"early_pre_event",label:"Earlier pre-order",hint:"Negative-control timing"},
  {id:"near_order",label:"At the order",hint:"−4 to +4 hours"},
  {id:"primary",label:"Main",hint:"−12 to +12 hours"},
  {id:"strict_overlap",label:"Strict overlap",hint:"Control support restricted"}
 ];
 let selected={metric:"vasopressor_exposure",test:"strict_overlap"};
 const grid=document.createElement("div");
 grid.className="mv-evidence-grid";
 const detail=document.createElement("div");
 detail.className="mv-evidence-detail"; detail.setAttribute("aria-live","polite");
 root.replaceChildren(grid,detail);
 const cell=(row,spec,s)=>{
  const item=s.outcomes[row.id][spec.id];
  const mult=row.mult;
  const estimate=item.estimate*mult;
  const lower=item.ci95[0]*mult,upper=item.ci95[1]*mult;
  const max=Math.max(...specs.flatMap(z=>s.outcomes[row.id][z.id].ci95
   .map(x=>Math.abs(x*mult))),.1)*1.15;
  const zero=76,range=61;
  const px=v=>zero+v/max*range;
  const color=lower>0||upper<0?"#248a76":"#bf865f";
  const figure=svg("svg",{viewBox:"0 0 152 34",role:"img",
   "aria-label":"Estimate "+nfmt(estimate,2)+row.unit+
   ", interval "+nfmt(lower,2)+" to "+nfmt(upper,2)});
  figure.append(svg("line",{x1:zero,y1:3,x2:zero,y2:30,class:"mv-matrix-zero"}));
  figure.append(svg("line",{x1:px(lower),y1:17,x2:px(upper),y2:17,
   stroke:color,"stroke-width":3,"stroke-linecap":"round"}));
  for(const endpoint of [lower,upper]){
   figure.append(svg("line",{x1:px(endpoint),y1:11,x2:px(endpoint),y2:23,
    stroke:color,"stroke-width":2}));
  }
  figure.append(svg("circle",{cx:px(estimate),cy:17,r:5,fill:color,stroke:"#fff","stroke-width":1.5}));
  const button=document.createElement("button");
  button.type="button";button.className="mv-evidence-cell";
  button.dataset.metric=row.id;button.dataset.test=spec.id;
  button.setAttribute("aria-pressed",String(row.id===selected.metric&&spec.id===selected.test));
  const display=(estimate>0?"+":"")+nfmt(estimate,row.mult===100?2:3)+row.unit;
  button.append(figure);
  const big=document.createElement("strong");big.textContent=display;button.append(big);
  const small=document.createElement("small");
  small.textContent=nfmt(lower,row.mult===100?2:3)+" to "+nfmt(upper,row.mult===100?2:3);
  button.append(small);
  button.addEventListener("click",()=>{
   selected={metric:row.id,test:spec.id};
   redrawSelection();
  });
  return button;
 };
 function redraw(){
  const s=release.states.find(s=>s.id===getSubtype());
  grid.replaceChildren();
  const corner=document.createElement("div");corner.className="mv-evidence-corner";
  corner.textContent="RECORDED OUTCOME";grid.append(corner);
  for(const spec of specs){
   const h=document.createElement("div");h.className="mv-evidence-head";
   h.innerHTML='<strong>'+spec.label+'</strong><span>'+spec.hint+'</span>';
   grid.append(h);
  }
  for(const m of metricDefs){
   const head=document.createElement("div");head.className="mv-evidence-rowhead";
   head.innerHTML='<strong>'+m.label+'</strong><span>'+ (m.mult===100?"percentage-point change":"records per patient-hour")+'</span>';
   grid.append(head);
   for(const spec of specs)grid.append(cell(m,spec,s));
  }
  redrawSelection();
 }
 function redrawSelection(){
  const s=release.states.find(s=>s.id===getSubtype());
  grid.querySelectorAll("button.mv-evidence-cell").forEach(b=>{
   const on=b.dataset.metric===selected.metric&&b.dataset.test===selected.test;
   b.classList.toggle("is-selected",on);
   b.setAttribute("aria-pressed",String(on));
  });
  const metric=metricDefs.find(x=>x.id===selected.metric);
  const spec=specs.find(x=>x.id===selected.test);
  const a=s.outcomes[selected.metric][selected.test];
  const scale=metric.mult,hasZero=a.ci95[0]<=0&&a.ci95[1]>=0;
  const strict=selected.test==="strict_overlap";
  const weak=s.positivity.strict_max_smd>.10;
  const report=(a.estimate*scale>0?"+":"")+nfmt(a.estimate*scale,metric.mult===100?2:3);
  detail.innerHTML='<div class="mv-evidence-detail-main"><span class="mv-kicker">SELECTED OBSERVATIONAL CONTRAST · '+STATUS_LABELS[getSubtype()]+'</span>'+
   '<h3>'+metric.label+' · '+spec.label.toLowerCase()+'</h3>'+
   '<p><strong>'+report+' '+metric.unit+'</strong> (conditional interval '+nfmt(a.ci95[0]*scale,metric.mult===100?2:3)+
   ' to '+nfmt(a.ci95[1]*scale,metric.mult===100?2:3)+').'+
   (hasZero?" The interval includes no difference.":" The displayed interval excludes no difference, but causal interpretation is not identified.")+'</p></div>'+
   (strict?'<aside class="mv-evidence-verdict"><strong>'+(weak?'Strict-sample balance failed':'Measured strict-sample balance')+'</strong>'+
   '<p>'+nfmt(s.positivity.strict_n)+' DNR orders survive this overlap restriction. Maximum measured |SMD| = '+
   nfmt(s.positivity.strict_max_smd,3)+(weak?', above the prespecified 0.10 diagnostic.':' ; hidden prognosis remains unmeasured.')+
   ' This sensitivity does not identify a treatment effect.</p></aside>':
   '<aside class="mv-evidence-verdict"><strong>Why the qualifier matters</strong>'+
   '<p>These are differences in measured changes around nonrandom decisions. Confidence intervals condition on fitted weights and do not account for all clinical uncertainty.</p></aside>');
 }
 redraw();
 return {setSubtype:redraw,destroy:()=>{}};
}
