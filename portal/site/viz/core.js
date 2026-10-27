/**
 * Mimicry Viz — reusable, dependency-free scientific visual grammar.
 * All animated marks represent actual aggregated cohorts, not people.
 */
export const NAMESPACE = "http://www.w3.org/2000/svg";
export const COLORS = Object.freeze({
 DNR_ONLY:"#f4a477",DNR_DNI:"#65d4bc",RISKSET:"#7893a9",
 neutral:"#d3e0dd",ink:"#15353a",caution:"#eab06a"
});
export const STATUS_LABELS = Object.freeze({
 DNR_ONLY:"DNR only",DNR_DNI:"DNR + DNI",RISKSET:"Eligible full-code controls"
});
export const nfmt=(x,d=0)=>Number(x).toLocaleString("en-US",{
 minimumFractionDigits:d,maximumFractionDigits:d
});
export const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
export const esc=x=>String(x??"").replace(/[&<>"']/g,
 x=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[x]));
export const svg=(name,props={})=>{
 const e=document.createElementNS(NAMESPACE,name);
 for(const [k,v] of Object.entries(props))e.setAttribute(k,String(v));
 return e;
};
export const el=(tag,cls="",text="")=>{
 const node=document.createElement(tag);
 if(cls)node.className=cls;
 if(text)node.textContent=text;
 return node;
};
export const lineScale=(domain,range)=>v=>range[0]+
 ((v-domain[0])/(domain[1]-domain[0]))*(range[1]-range[0]);
export const radiusFromCount=(n,nmax,rmax=61)=>Math.sqrt(Math.max(0,n)/nmax)*rmax;
export const prefersReducedMotion=()=>typeof window!=="undefined"&&
 window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
export const asPercent=(v,d=1)=>nfmt(v*100,d)+"%";
export const asSigned=(v,d=1)=>(v>=0?"+":"")+nfmt(v,d);
export function assert(cond,msg){if(!cond)throw new Error("Mimicry Viz: "+msg);}
export function validateVizData(v,release){
 assert(v?.schema_version===1 && v.kind==="scientific-viz-aggregate","invalid visual-data version");
 assert(v.track==="prophecy-2"&&v.release_id===release.id,"release mismatch");
 const c=v.cohort_bubbles;
 assert(c?.min_cell_n>=30 && c.stages.length===3,"aggregation or stage definition missing");
 assert(c.counts.eligible.n===release.cohort.eligible_first_dnr,"eligible cohort size mismatch");
 assert(c.counts.supported.n===release.cohort.represented_dnr,"common-support cohort mismatch");
 assert(c.counts.eligible.n-c.counts.supported.n===release.cohort.outside_common_support,"attrition mismatch");
 assert(["eligible","supported","strict"].every(id=>c.stages.some(s=>s.id===id)),"unexpected analytic stages");
 assert(c.counts.eligible.n>c.counts.supported.n && c.counts.supported.n>c.counts.strict.n,"invalid analytic attrition");
 const subtype=Object.fromEntries(release.states.map(s=>[s.id,s]));
 for(const [k,s] of Object.entries(subtype)){
  assert(c.counts.supported.subtypes[k]===s.n_dnr,"wrong subtype counts");
  assert(c.counts.strict.subtypes[k]===s.positivity.strict_n,"strict sample does not match study");
 }
 // A minimum cell count does NOT protect successive nested stages:
 // counts and means may reveal a five-person excluded subgroup through
 // differencing. Demand one stable, disjoint, exhaustive PUBLIC partition
 // across all stages, with at least 30 individuals for any nonzero attrition.
 assert(c.points.every(p=>p.n>=c.min_cell_n),"small cohort cell disclosed");
 assert(c.stable_partition===true && c.complementary_suppression===true,
        "cross-stage privacy protection disabled");
 assert(c.min_cross_stage_attrition>=c.min_cell_n,
        "cross-stage privacy threshold is too low");
 const analyticStages=["eligible","supported","strict"];
 for(const sub of Object.keys(subtype)){
  const initial=c.points.filter(p=>p.stage===analyticStages[0]&&p.subtype===sub);
  const groupNames=new Set(initial.map(p=>p.id));
  assert(groupNames.size===initial.length && groupNames.size>=2,
         "public cohorts must be distinct and partitioned");
  for(const stage of analyticStages){
   const rows=c.points.filter(p=>p.stage===stage&&p.subtype===sub);
   const total=rows.reduce((acc,p)=>acc+p.n,0);
   assert(total===c.counts[stage].subtypes[sub],
          "public unit partition does not exhaust published cohort");
   const current=new Set(rows.map(p=>p.id));
   assert(current.size===groupNames.size
          && [...groupNames].every(id=>current.has(id)),
          "cross-stage group partition changed");
  }
  for(const id of groupNames){
   const values=analyticStages.map(stage=>
     c.points.find(p=>p.stage===stage&&p.subtype===sub&&p.id===id).n);
   for(let i=0;i<values.length-1;i++){
    const excluded=values[i]-values[i+1];
    assert(excluded>=0,"cross-stage cohorts are not nested");
    assert(excluded===0||excluded>=c.min_cross_stage_attrition,
           "cross-stage difference exposes a small excluded cohort");
   }
  }
 }
 const keys=new Set();
 for(const m of c.points){
  assert(m.n>=c.min_cell_n,"small cohort cell disclosed");
  assert(m.subtype in subtype && ["eligible","supported","strict"].includes(m.stage),"invalid bubble category");
  assert(Number.isFinite(m.sofa)&&m.sofa>=0&&m.sofa<=24,"SOFA invalid");
  assert(Number.isFinite(m.invasive_before)&&m.invasive_before>=0&&m.invasive_before<=1,"treatment exposure invalid");
  const k=[m.stage,m.id].join("/");
  assert(!keys.has(k),"duplicate bubble cohort");
  keys.add(k);
 }
 const ts=v.event_time;
 assert(ts.pointwise_ci_available===false && ts.event_time_is_endogenous===true,"false inference about measured time");
 assert(ts.from_hours.join(",")==="-24,-20,-16,-12,-8,-4,0,4,8","time grid mismatch");
 assert(ts.series.length===2*2*3*9,"missing observed time series");
 const signature=new Set();
 for(const row of ts.series){
  assert(row.subtype in subtype,"unregistered time-series subtype");
  assert(["DNR","RISKSET"].includes(row.arm),"invalid comparison arm");
  assert(["invasive_ventilation","vasopressor_exposure","map_recording"].includes(row.metric),"invalid endpoint");
  assert(row.to_hour-row.from_hour===4&&ts.from_hours.includes(row.from_hour),"invented timepoint");
  assert(row.value>=0&&row.value<5&&Number.isFinite(row.value),"implausible recording intensity");
  if(row.metric!=="map_recording")assert(row.value<=1,"support exposure fraction invalid");
  const key=[row.subtype,row.arm,row.metric,row.from_hour].join("/");
  assert(!signature.has(key),"duplicated timepoint");
  signature.add(key);
 }
 const raw=JSON.stringify(v);
 for(const field of ["subject_id","stay_id","hadm_id","anchor_id","deathtime","patient_id","date_of_birth"]){
  assert(!raw.includes('"'+field+'"'),"sensitive field disclosed");
 }
 assert(v.provenance?.patient_rows_exported===false,"missing privacy guarantee");
 return true;
}
export function seriesFor(dataset,subtype,metric,arm){
 return dataset.event_time.series
  .filter(p=>p.subtype===subtype&&p.metric===metric&&p.arm===arm)
  .sort((a,b)=>a.from_hour-b.from_hour);
}
export function intervalStatistic(release,subtype,metric,window="primary"){
 return release.states.find(s=>s.id===subtype)?.outcomes[metric]?.[window];
}
