import {COLORS,STATUS_LABELS,svg,nfmt,clamp,lineScale,seriesFor,intervalStatistic,asPercent,prefersReducedMotion} from "./core.js";

/** Four-hour observed-bin step chart. Motion reveals recorded bins, never interpolates physiology. */
export function mountEventTime(root,data,release,{getSubtype}){
 const W=920,H=500,L=83,R=159,T=46,B=87;
 let metric="invasive_ventilation",bin=5, timer=null;
 const chart=svg("svg",{viewBox:"0 0 920 500",role:"img",
  "aria-label":"Recorded four-hour event-time rates around a DNR order versus matched pseudo-time controls. Exact bin values; not a causal time discontinuity."});
 chart.classList.add("mv-event-svg");
 root.replaceChildren(chart);
 const x=lineScale([-24,12],[L,W-R]);
 const selectedName=document.querySelector("#mv-bin-time");
 const live=document.querySelector("#mv-time-readout");
 const details=document.querySelector("#mv-time-table");
 const slider=document.querySelector("#mv-timeline");
 const play=document.querySelector("#mv-time-play");
 const metricButtons=[...document.querySelectorAll("[data-mv-metric]")];
 const typeName=()=>STATUS_LABELS[getSubtype()];
 const metrics={
  invasive_ventilation:{label:"Invasive ventilation",max:1.0,unit:"%"},
  vasopressor_exposure:{label:"Vasopressor exposure",max:.75,unit:"%"},
  map_recording:{label:"MAP recording intensity",max:1.8,unit:"records / patient-hour"}
 };
 function format(v){
  return metric==="map_recording"?nfmt(v,3)+" /h":asPercent(v,1);
 }
 function timeLabel(from,to){
  const f=n=>n>0?"+"+n:n===0?"0":String(n);
  return f(from)+" to "+f(to)+" hours";
 }
 function pathFor(values,y){
  if(!values.length)return "";
  let d="M "+x(values[0].from_hour)+" "+y(values[0].value);
  for(const p of values){
   d+=" L "+x(p.to_hour)+" "+y(p.value);
   const next=values.find(q=>q.from_hour===p.to_hour);
   if(next)d+=" L "+x(next.from_hour)+" "+y(next.value);
  }
  return d;
 }
 function redraw(){
  chart.replaceChildren();
  const y=lineScale([0,metrics[metric].max],[H-B,T]);
  const ylabel=metric==="map_recording"?"RECORDS PER ICU PATIENT-HOUR":"SHARE OF OBSERVED ICU PATIENT-HOURS";
  const yTicks=Array.from({length:5},(_,i)=>i*metrics[metric].max/4);
  for(const val of yTicks){
   const yy=y(val);
   chart.append(svg("line",{x1:L,y1:yy,x2:W-R,y2:yy,class:"mv-chart-grid"}));
   const tick=svg("text",{x:L-18,y:yy+4,"text-anchor":"end",class:"mv-tick"});
   tick.textContent=metric==="map_recording"?nfmt(val,2):asPercent(val,0);
   chart.append(tick);
  }
  for(const val of [-24,-16,-8,0,8,12]){
   const xx=x(val);
   const t=svg("text",{x:xx,y:H-B+30,"text-anchor":"middle",class:"mv-tick"});
   t.textContent=val>0?"+"+val:val;
   chart.append(t);
  }
  const axis=svg("text",{x:(L+W-R)/2,y:H-23,"text-anchor":"middle",class:"mv-axis-title"});
  axis.textContent="HOURS FROM ORDER · CONTROLS ALIGNED TO PSEUDO-TIME";
  chart.append(axis);
  const yaxis=svg("text",{x:22,y:240,transform:"rotate(-90 22 240)","text-anchor":"middle",class:"mv-axis-title"});
  yaxis.textContent=ylabel;chart.append(yaxis);
  const zero=svg("line",{x1:x(0),x2:x(0),y1:T-17,y2:H-B+3,class:"mv-event-zero"});
  chart.append(zero);
  const zeroLabel=svg("text",{x:x(0)+12,y:T-23,class:"mv-zero-label"});
  zeroLabel.textContent="0h · DNR ORDER";
  chart.append(zeroLabel);
  const selectedFrom=-24+bin*4;
  const spotlight=svg("rect",{x:x(selectedFrom),y:T,width:x(4)-x(0),height:H-B-T,class:"mv-spotlight"});
  chart.append(spotlight);
  const lines=[
   {arm:"RISKSET",color:COLORS.RISKSET,name:"Full-code risk sets"},
   {arm:"DNR",color:COLORS[getSubtype()],name:typeName()}
  ];
  const endings=Object.fromEntries(lines.map(item=>{
   const v=seriesFor(data,getSubtype(),metric,item.arm).at(-1);
   return [item.arm,y(v.value)];
  }));
  const dnrLower=endings.DNR>endings.RISKSET;
  // Push direct labels *away* from each other, not toward the other curve.
  // Data lines remain untouched. This avoids misleading chart-label overlap.
  const offsets={
   DNR:dnrLower?17:-11,
   RISKSET:dnrLower?-9:17
  };
  for(const ln of lines){
   const rows=seriesFor(data,getSubtype(),metric,ln.arm);
   const path=svg("path",{d:pathFor(rows,y),class:"mv-observed-path",
                         stroke:ln.color});
   chart.append(path);
   const last=rows[rows.length-1];
   const end=svg("circle",{cx:x(12),cy:y(last.value),r:5,fill:ln.color,class:"mv-line-end"});
   chart.append(end);
   const label=svg("text",{x:W-R+16,y:y(last.value)+offsets[ln.arm],class:"mv-direct-label",
                          fill:ln.color});
   label.textContent=ln.arm==="DNR"?typeName():"Full-code controls";
   chart.append(label);
  }
  const tLines=svg("text",{x:W-R+15,y:H-B+20,class:"mv-small-label"});
  tLines.textContent="OBSERVED RATES";
  chart.append(tLines);
  // Invisible focusable discrete bins; no interpolation between recording windows.
  for(let j=0;j<9;j++){
   const rect=svg("rect",{x:x(-24+j*4),y:T,width:x(4)-x(0),height:H-B-T,
                       fill:"transparent",role:"button",tabindex:"0",
                       "aria-label":"Show observed window "+timeLabel(-24+j*4,-20+j*4)});
   rect.addEventListener("click",()=>setBin(j));
   rect.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();setBin(j);}});
   chart.append(rect);
  }
  paintReadout();
 }
 function paintReadout(){
  const from=-24+4*bin,to=from+4;
  const a=seriesFor(data,getSubtype(),metric,"DNR")[bin];
  const b=seriesFor(data,getSubtype(),metric,"RISKSET")[bin];
  selectedName.textContent=timeLabel(from,to);
  slider.value=String(bin);
  const signedDiff=format(a.value-b.value);
  const contrast=intervalStatistic(release,getSubtype(),metric);
  const scale=metric==="map_recording"?1:100;
  const units=metric==="map_recording"?"recordings per ICU patient-hour":"percentage points";
  const estimate=contrast?contrast.estimate*scale:0;
  const lo=contrast?.ci95[0]*scale,hi=contrast?.ci95[1]*scale;
  live.innerHTML='<div><span class="mv-mono">DOCUMENTED '+typeName().toUpperCase()+'</span>'+
   '<strong>'+format(a.value)+'</strong></div><div><span class="mv-mono">ELIGIBLE FULL-CODE CONTROLS</span>'+
   '<strong>'+format(b.value)+'</strong></div>'+
   '<p>During this four-hour bin, the recorded rates differ by '+(a.value>=b.value?"+":"−")+
   format(Math.abs(a.value-b.value))+'. This is <em>not</em> a causal effect.'+
   (from<0?" These observations precede the DNR order.":" Observations after the order are also shaped by ICU exit and death.")+'</p>'+
   '<p class="mv-formal-estimate">Full 12-hour difference-in-changes: <b>'+
   (estimate>=0?"+":"")+nfmt(estimate,metric==="map_recording"?3:2)+' '+units+'</b>'+
   '; conditional 95% interval '+nfmt(lo,metric==="map_recording"?3:2)+' to '+nfmt(hi,metric==="map_recording"?3:2)+
   '. These intervals do not apply to individual time bins.</p>';
  const u=document.querySelector("#mv-time-caution");
  u.textContent=from<0?
   "Before the order · documentation has not happened yet. Pre-order differences can reflect worsening illness, anticipation or other decisions.":
   "After the order · the patient population still observed in ICU changes as people die or leave. Event time is not randomized.";
  details.innerHTML='<thead><tr><th>Four-hour window</th><th>'+typeName()+'</th><th>Full-code controls</th></tr></thead><tbody>'+
   seriesFor(data,getSubtype(),metric,"DNR").map((r,i)=>{
    const t=seriesFor(data,getSubtype(),metric,"RISKSET")[i];
    return '<tr'+(i===bin?' class="mv-selected-row"':'')+'><th>'+
    timeLabel(r.from_hour,r.to_hour)+'</th><td>'+format(r.value)+'</td><td>'+format(t.value)+'</td></tr>';
   }).join("")+'</tbody>';
 }
 function setBin(next){
  bin=clamp(Number(next),0,8);
  redraw();
  if(bin===8)stop();
 }
 function setMetric(next){
  if(!(next in metrics))return;
  metric=next;
  metricButtons.forEach(btn=>{
   const on=btn.dataset.mvMetric===metric;
   btn.classList.toggle("active",on);
   btn.setAttribute("aria-pressed",String(on));
  });
  redraw();
 }
 function setSubtype(){redraw();}
 function stop(){
  if(timer!==null)clearInterval(timer);timer=null;
  play.textContent="▶ Play the recorded bins";
  play.setAttribute("aria-pressed","false");
 }
 function playPause(){
  if(timer!==null){stop();return;}
  if(bin>=8)bin=0;
  setBin(bin);
  play.textContent="Ⅱ Pause";
  play.setAttribute("aria-pressed","true");
  timer=setInterval(()=>{
   if(bin>=8){stop();return;}
   setBin(bin+1);
  },1150);
 }
 slider.addEventListener("input",e=>{stop();setBin(e.target.value);});
 play.addEventListener("click",playPause);
 metricButtons.forEach(btn=>btn.addEventListener("click",()=>{stop();setMetric(btn.dataset.mvMetric);}));
 setMetric(metric);
 return {setSubtype,setMetric,setBin,stop,destroy:stop};
}
