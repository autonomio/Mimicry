import {test} from "node:test";
import assert from "node:assert/strict";
import structuredClone from "node:util";
import {loadPublications,validatePublication} from "./publication.mjs";
const {tracks,releases}=loadPublications();
test("current reviewed aggregate release passes validation",()=>{
 assert.equal(validatePublication(tracks,releases),true);
});
test("different research tracks can coexist and have independent releases",()=>{
 const t=JSON.parse(JSON.stringify(tracks));
 t.tracks.push({...t.tracks[0],id:"another-track",slug:"another-track",name:"Another research track",description:"Independent future methods and results"});
 const r=JSON.parse(JSON.stringify(releases[0]));r.id="2026-10-26-second-round";r.date="2026-10-26";r.track="another-track";
 assert.equal(validatePublication(t,[...releases,r]),true);
});
test("malformed prediction improvement fails publication",()=>{
 const x=JSON.parse(JSON.stringify(releases[0]));x.prediction.improvement.value=42;
 assert.throws(()=>validatePublication(tracks,[x]),/improvement/);
});
test("raw patient identifiers fail publication",()=>{
 const x=JSON.parse(JSON.stringify(releases[0]));x.subject_id=12345678;
 assert.throws(()=>validatePublication(tracks,[x]),/Forbidden/);
});
test("false validation pass cannot be published",()=>{
 const x=JSON.parse(JSON.stringify(releases[0]));x.simulation.horizons[0].passed=true;
 assert.throws(()=>validatePublication(tracks,[x]),/gate/i);
});
test("invalid historical split fails publication",()=>{
 const x=JSON.parse(JSON.stringify(releases[0]));x.summary.training++;
 assert.throws(()=>validatePublication(tracks,[x]),/Split mismatch/);
});
test("unsupported new release track cannot publish",()=>{
 const x=JSON.parse(JSON.stringify(releases[0]));x.track="unknown-track";
 assert.throws(()=>validatePublication(tracks,[x]),/Unknown/);
});
