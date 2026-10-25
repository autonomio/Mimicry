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

test("historical discharge transport release is newest within same date",()=>{
 const recent=releases.find(x=>x.id==="2026-10-25-discharge-transport");
 assert.ok(recent&&recent.round_number===2);
 assert.equal(releases[0].id,recent.id);
 assert.equal(recent.transport.horizons.length,4);
 assert.ok(recent.transport.horizons.every(h=>!recent.simulation.horizons.find(s=>s.hours===h.hours).passed));
});
test("transport decomposition cannot silently contradict the underlying history",()=>{
 const x=JSON.parse(JSON.stringify(releases.find(x=>x.transport)));
 x.transport.horizons.at(-1).exit.prequential+=0.02;
 assert.throws(()=>validatePublication(tracks,[x]),/historical model error|Historical model error/i);
});
test("changing simulation figures without new validation cannot publish",()=>{
 const x=JSON.parse(JSON.stringify(releases.find(x=>x.transport)));
 x.transport.horizons.at(-1).exit.simulated+=0.04;
 assert.throws(()=>validatePublication(tracks,[x]),/Recursive feedback error|Transport contradicts/i);
});
test("round numbers are unique within a track",()=>{
 const x=JSON.parse(JSON.stringify(releases[0]));
 x.id="2026-10-25-conflicting-round";
 assert.throws(()=>validatePublication(tracks,[...releases,x]),/Duplicate round number/);
});

test("ICU-return endpoint sensitivity preserves source event counts",()=>{
 const x=JSON.parse(JSON.stringify(releases.find(x=>x.transport)));
 x.transport.icu_return_sensitivity.later.exit_then_return24_n += 30;
 assert.throws(()=>validatePublication(tracks,[x]),/ICU return count\/rate discrepancy/);
});

test("Prophecy 2 remains independent from Prophecy",()=>{
 const newTrack=tracks.tracks.find(t=>t.id==="prophecy-2");
 assert.ok(newTrack);
 assert.match(newTrack.tagline,/DNR/i);
 const fork=releases.find(r=>r.track==="prophecy-2");
 assert.ok(fork);
 assert.equal(fork.kind,"dnr-audit");
 assert.equal(fork.states.find(x=>x.id==="DNR_ONLY").n_dnr,792);
 assert.equal(fork.states.find(x=>x.id==="DNR_DNI").n_dnr,1222);
 assert.equal(fork.cohort.outside_common_support,1007);
 assert.equal(validatePublication(tracks,releases),true);
});
test("Prophecy 2 cannot pool DNR-only with DNR/DNI",()=>{
 const fork=JSON.parse(JSON.stringify(releases.find(r=>r.kind==="dnr-audit")));
 fork.states=[fork.states[0]];
 assert.throws(()=>validatePublication(tracks,[fork]),/DNR-only and DNR/);
});
test("Prophecy 2 cannot advertise identified mortality causation",()=>{
 const fork=JSON.parse(JSON.stringify(releases.find(r=>r.kind==="dnr-audit")));
 fork.question.identification_status="Identified randomized DNR effect";
 assert.throws(()=>validatePublication(tracks,[fork]),/identification/i);
});
test("Prophecy 2 cohort and selected support cannot be misreported",()=>{
 const fork=JSON.parse(JSON.stringify(releases.find(r=>r.kind==="dnr-audit")));
 fork.cohort.outside_common_support=1;
 assert.throws(()=>validatePublication(tracks,[fork]),/overlap attrition/);
});
test("Prophecy 2 fixed-weight interval must contain the reported contrast",()=>{
 const fork=JSON.parse(JSON.stringify(releases.find(r=>r.kind==="dnr-audit")));
 fork.states[0].outcomes.invasive_ventilation.primary.estimate=5;
 assert.throws(()=>validatePublication(tracks,[fork]),/DNR sensitivity CI/);
});
test("Prophecy 2 publication rejects patient identifiers",()=>{
 const fork=JSON.parse(JSON.stringify(releases.find(r=>r.kind==="dnr-audit")));
 fork.subject_id=123456789;
 assert.throws(()=>validatePublication(tracks,[fork]),/Forbidden/);
});
test("Prophecy 2's stringent overlap failure is retained in the record",()=>{
 const fork=releases.find(r=>r.kind==="dnr-audit");
 const dnr=fork.states.find(s=>s.id==="DNR_ONLY");
 assert.ok(dnr.positivity.strict_max_smd>.1);
 assert.ok(dnr.positivity.strict_n<dnr.n_dnr);
 assert.ok(dnr.positivity.risk_sets_under_two_effective_controls>dnr.n_dnr/2);
});
