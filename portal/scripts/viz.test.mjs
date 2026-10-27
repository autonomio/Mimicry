import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";
import {validateVizData,radiusFromCount,seriesFor,intervalStatistic} from "../site/viz/core.js";

const here=path.dirname(fileURLToPath(import.meta.url));
const data=JSON.parse(fs.readFileSync(path.join(here,"../data/viz/prophecy2-observations-v1.json"),"utf8"));
const release=JSON.parse(fs.readFileSync(path.join(here,"../data/rounds/2026-10-25-dnr-question-fork.json"),"utf8"));
const copy=()=>structuredClone(data);

test("real-data chart export matches the Prophecy 2 research release",()=>{
 assert.equal(validateVizData(data,release),true);
 assert.equal(data.cohort_bubbles.counts.eligible.n,3021);
 assert.equal(data.cohort_bubbles.counts.supported.n,2014);
 assert.equal(data.cohort_bubbles.counts.strict.n,1423);
 assert.equal(data.cohort_bubbles.complementary_suppression,true);
});

test("Gapminder-inspired circle area is proportional to aggregate count",()=>{
 const n1=50,n2=200,m=1000;
 const a=radiusFromCount(n1,m),b=radiusFromCount(n2,m);
 assert.ok(Math.abs(b*b/(a*a)-4)<1e-12);
});
test("all published time bins are observed, discrete, complete and ordered",()=>{
 for(const status of ["DNR_ONLY","DNR_DNI"]){
  for(const metric of ["invasive_ventilation","vasopressor_exposure","map_recording"]){
   for(const arm of ["DNR","RISKSET"]){
    const pts=seriesFor(data,status,metric,arm);
    assert.equal(pts.length,9);
    assert.deepEqual(pts.map(x=>x.from_hour),[-24,-20,-16,-12,-8,-4,0,4,8]);
    assert.ok(pts.every(x=>x.to_hour-x.from_hour===4));
   }
  }
 }
});
test("pointwise confidence ribbons cannot be invented",()=>{
 const x=copy();x.event_time.pointwise_ci_available=true;
 assert.throws(()=>validateVizData(x,release),/false inference/);
});
test("newly inserted patient identifier cannot enter public visualization",()=>{
 const x=copy();x.cohort_bubbles.points[0].subject_id=999;
 assert.throws(()=>validateVizData(x,release),/sensitive field/);
});
test("source cohort totals cannot change without research release",()=>{
 const x=copy();x.cohort_bubbles.counts.eligible.n=3000;
 assert.throws(()=>validateVizData(x,release),/eligible cohort/);
});
test("small-count cell cannot be displayed",()=>{
 const x=copy();x.cohort_bubbles.points[0].n=12;
 assert.throws(()=>validateVizData(x,release),/small cohort cell/);
});
test("public groups exhaust every subtype total at every stage",()=>{
 for(const stage of ["eligible","supported","strict"]){
  for(const sub of ["DNR_ONLY","DNR_DNI"]){
   const n=data.cohort_bubbles.points
    .filter(p=>p.stage===stage&&p.subtype===sub)
    .reduce((total,p)=>total+p.n,0);
   assert.equal(n,data.cohort_bubbles.counts[stage].subtypes[sub]);
  }
 }
});
test("cross-stage differencing never reveals an excluded cohort smaller than 30",()=>{
 for(const sub of ["DNR_ONLY","DNR_DNI"]){
  const ids=new Set(data.cohort_bubbles.points
   .filter(p=>p.stage==="eligible"&&p.subtype===sub).map(p=>p.id));
  for(const id of ids){
   const counts=["eligible","supported","strict"].map(stage=>
    data.cohort_bubbles.points.find(p=>p.stage===stage&&p.id===id).n);
   assert.ok(counts.every(n=>n>=30));
   for(let i=0;i<2;i++){
    const excluded=counts[i]-counts[i+1];
    assert.ok(excluded===0||excluded>=30);
   }
  }
 }
});
test("reviewer P1: a small between-stage excluded cohort is rejected",()=>{
 const x=copy();
 const set=(stage,unit,n)=>{
  const p=x.cohort_bubbles.points.find(p=>
   p.stage===stage&&p.subtype==="DNR_DNI"&&p.unit===unit);
  p.n=n;
 };
 // Totals remain unchanged; all published cells have >=30 cases;
 // all group series are nested. Only 8 MICU cases are excluded.
 set("supported","MICU",1009);
 set("supported","Other ICU units",213);
 set("strict","MICU",900);
 set("strict","Other ICU units",145);
 assert.throws(()=>validateVizData(x,release),/cross-stage difference exposes a small excluded cohort/);
});
test("changing group composition between published stages is rejected",()=>{
 const x=copy();
 const p=x.cohort_bubbles.points.find(p=>
  p.stage==="strict"&&p.subtype==="DNR_ONLY"&&p.unit==="Other ICU units");
 p.id+="__new_public_group";
 assert.throws(()=>validateVizData(x,release),/cross-stage group partition changed/);
});
test("public subgroup counts cannot be reconstructed by subtraction",()=>{
 const x=copy();
 const p=x.cohort_bubbles.points.find(p=>
  p.stage==="supported"&&p.subtype==="DNR_ONLY"&&p.unit==="Other ICU units");
 p.n-=5;
 assert.throws(()=>validateVizData(x,release),/public unit partition does not exhaust/);
});
test("missing or duplicate measured time-bin records are rejected",()=>{
 const x=copy();x.event_time.series[1]=structuredClone(x.event_time.series[0]);
 assert.throws(()=>validateVizData(x,release),/duplicated timepoint/);
});
test("analytic stage labels cannot be converted into patient time",()=>{
 const x=copy();x.cohort_bubbles.stages[1].id="hospital_day_2";
 assert.throws(()=>validateVizData(x,release),/unexpected analytic stages/);
});
test("original conditional estimate remains available alongside graph",()=>{
 const a=intervalStatistic(release,"DNR_ONLY","vasopressor_exposure","primary");
 const b=intervalStatistic(release,"DNR_ONLY","vasopressor_exposure","strict_overlap");
 assert.ok(a.estimate<-.04 && b.estimate>-.01);
 assert.ok(b.ci95[0]<0&&b.ci95[1]>0);
});
test("every public circle has source cell count above release threshold",()=>{
 assert.ok(data.cohort_bubbles.points.every(p=>p.n>=30));
});
