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
test("published subtotal cannot unmask lone small cell via subtraction",()=>{
 const x=copy();
 const counts=x.cohort_bubbles.counts.supported.subtypes.DNR_ONLY;
 const visible=x.cohort_bubbles.points.filter(p=>p.stage==="supported"&&p.subtype==="DNR_ONLY");
 const shown=visible.reduce((sum,p)=>sum+p.n,0);
 const remainder=counts-shown;
 assert.ok(remainder>=30);
 visible[0].n+=remainder-1; // now exactly one observation remains hidden
 assert.throws(()=>validateVizData(x,release),/unprotected residual small cell/);
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
