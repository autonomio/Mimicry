import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const dataDir = path.join(root, "data");
export const outputDir = path.join(root, "dist");
export function readJson(file) { return JSON.parse(fs.readFileSync(file, "utf8")); }
export function assert(ok, msg) { if (!ok) throw new Error(msg); }
const number = (v, msg) => assert(typeof v === "number" && Number.isFinite(v), msg + ": expected finite number");

export function validatePublication(catalog, releases) {
  assert(catalog.schema_version === 1, "Unsupported tracks schema");
  assert(catalog.domain === "mimicry.mikkokotila.com", "Wrong domain");
  assert(Array.isArray(catalog.tracks) && catalog.tracks.length, "No research tracks");
  const seen = new Set();
  for (const t of catalog.tracks) {
    assert(/^[a-z][a-z0-9-]+$/.test(t.slug), "Invalid track slug " + t.slug);
    assert(t.id === t.slug && !seen.has(t.slug), "Track id mismatch or duplicate");
    seen.add(t.slug);
    for (const k of ["name","description","tagline","discipline","status"]) assert(typeof t[k] === "string" && t[k].length > 3, "Missing " + k + " on " + t.slug);
  }
  const ids = new Set();
  const roundPerTrack = new Set();
  for (const r of releases) {
    assert(r.schema_version === 1, "Invalid release schema");
    assert(/^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9-]+$/.test(r.id), "Invalid release id");
    assert(!ids.has(r.id), "Duplicate release " + r.id);
    ids.add(r.id);
    const roundKey=r.track+":"+r.round_number;
    assert(!roundPerTrack.has(roundKey), "Duplicate round number within research track");
    roundPerTrack.add(roundKey);
    assert(seen.has(r.track), "Unknown research track " + r.track);
    assert(Number.isInteger(r.round_number) && r.round_number>=1, "Missing positive research round number");
    assert(/^\d{4}-\d{2}-\d{2}$/.test(r.date), "Invalid date " + r.id);
    for (const k of ["title","subtitle","status","message","dataset"]) assert(typeof r[k] === "string" && r[k].length > 3, "Missing " + k);
    for (const [k,v] of Object.entries(r.summary)) {
      number(v, k);
      assert(v >= 0, "Negative " + k);
    }
    assert(r.summary.patients >= 11 && r.summary.test >= 11, "Small reported population");
    assert(r.summary.training + r.summary.validation + r.summary.test === r.summary.landmarks, "Split mismatch");
    assert(r.prediction.models.length >= 3, "Missing nested models");
    const seenModels = new Set();
    for (const m of r.prediction.models) {
      assert(!seenModels.has(m.key), "Repeated model");
      seenModels.add(m.key);
      number(m.loss, "loss"); number(m.brier, "brier");
      assert(m.loss > 0 && m.loss < 5 && m.brier > 0 && m.brier < 2, "Implausible predictive metric");
    }
    const a = r.prediction.models.find(m=>m.key==="physiology");
    const b = r.prediction.models.find(m=>m.key==="care_history");
    assert(a && b && Math.abs(a.loss-b.loss-r.prediction.improvement.value)<0.0001, "Headline improvement incorrect");
    const improvement=r.prediction.improvement;
    assert(improvement.ci.length===2 && improvement.ci[0]<=improvement.value && improvement.value<=improvement.ci[1], "Bad improvement interval");
    for (const x of r.prediction.calibration) {
      number(x.observed,"observed");number(x.predicted,"predicted");
      assert(x.observed>=0 && x.observed<=1 && x.predicted>=0 && x.predicted<=1, "Bad probability");
    }
    for (const x of r.decisions.effects) {
      number(x.estimate,"effect");
      assert(Array.isArray(x.ci) && x.ci.length===2 && x.ci[0]<=x.estimate && x.estimate<=x.ci[1], "Bad association interval");
    }
    assert(r.decisions.n_dnr>=11 && r.simulation.n>=11,"Insufficient cohort size");
    assert(r.simulation.horizons.length>=2,"Missing multihorizon evaluation");
    for(const h of r.simulation.horizons) {
      for(const state of ["death","exit","icu"]) { number(h[state].observed,"observed");number(h[state].simulated,"simulated"); }
      assert(Math.abs(h.death.observed+h.exit.observed+h.icu.observed-1)<0.006,"Observed state mass inconsistent at "+h.hours);
      assert(Math.abs(h.death.simulated+h.exit.simulated+h.icu.simulated-1)<0.006,"Simulated state mass inconsistent at "+h.hours);
      const gates=r.simulation.gates,dr=h.death.simulated/h.death.observed,er=h.exit.simulated/h.exit.observed;
      const pass=dr>=gates.death_ratio[0] && dr<=gates.death_ratio[1] && er>=gates.exit_ratio[0] && er<=gates.exit_ratio[1] && Math.abs(h.icu.simulated-h.icu.observed)<gates.icu_occupancy_error_max;
      assert(pass===h.passed,"Declared pass/fail differs from gates at "+h.hours);
    }
    if (r.transport) {
      const z=r.transport;
      assert(z.cohort_n>=11 && z.simulator_replicates>=2,"Transport cohort/replicates missing");
      assert(Array.isArray(z.horizons) && z.horizons.length>=2,"Transport horizons missing");
      let prev=0;
      for(const h of z.horizons){
        number(h.hours,"transport horizon");
        assert(h.hours>prev && h.hours<=144,"Transport horizon ordering/eligibility invalid");
        prev=h.hours;
        const parent=r.simulation.horizons.find(v=>v.hours===h.hours);
        assert(parent,"Transport must correspond to independently recorded rollout horizon");
        assert(h.n===z.cohort_n,"Transport denominator changed");
        for(const state of ["death","exit"]){
          const o=h[state];
          for(const k of ["observed","prequential","simulated","local_error","recursive_error","total_error"])number(o[k],state+" "+k);
          for(const k of ["observed","prequential","simulated"])assert(o[k]>=0 && o[k]<=1,"Invalid "+state+" probability");
          const near=(a,b)=>Math.abs(a-b)<0.00001;
          assert(near(o.local_error,o.prequential-o.observed),"Historical model error disagrees");
          assert(near(o.recursive_error,o.simulated-o.prequential),"Recursive feedback error disagrees");
          assert(near(o.total_error,o.simulated-o.observed),"Full error disagrees");
          assert(near(o.local_error+o.recursive_error,o.total_error),"Transport decomposition fails conservation");
          assert(near(o.observed,parent[state].observed) && near(o.simulated,parent[state].simulated),"Transport contradicts rollout source");
          assert(Array.isArray(o.local_ci95) && o.local_ci95.length===2
           && o.local_ci95[0]<=o.local_error && o.local_error<=o.local_ci95[1],"Invalid historical error CI");
        }
        assert(h.exit.observed+h.death.observed<=1.00001,"Observed competing state mass exceeds one");
        assert(h.exit.simulated+h.death.simulated<=1.00001,"Simulated competing state mass exceeds one");
      }
      assert(Array.isArray(z.earlier_rolling_origin?.horizons) && z.earlier_rolling_origin.horizons.length>=2,"Earlier rolling-origin check required");
      for(const h of z.earlier_rolling_origin.horizons){
        number(h.hours,"earlier horizon");number(h.exit_error,"earlier rolling-origin error");
        assert(Math.abs(h.exit_error-(h.prequential_exit-h.observed_exit))<.00001,"Earlier rolling-origin decomposition inconsistent");
        assert(h.exit_error_ci95[0]<=h.exit_error && h.exit_error<=h.exit_error_ci95[1],"Earlier CI inconsistent");
      }
      const sh=z.historical_shift;
      assert(sh.earlier_n>=100 && sh.later_n>=100,"Historical comparison undersized");
      for(const k of ["baseline_domain_auc","raw_exit_change","standardized_exit_change"])number(sh[k],"historical shift");
      assert(sh.ci95_fixed_weights[0]<=sh.standardized_exit_change && sh.standardized_exit_change<=sh.ci95_fixed_weights[1],"Historical interval inconsistent");
      if (z.icu_return_sensitivity) {
        const a=z.icu_return_sensitivity;
        for (const era of ["earlier","later"]){
          const x=a[era];
          assert(x.n>=100 && x.exit_then_return24_n>=0 && Number.isInteger(x.exit_then_return24_n),"Invalid ICU return cohort");
          for (const k of ["original_exit","exit_without_return24","exit_without_return7d"]){
            number(x[k],"return sensitivity");
            assert(x[k]>=0 && x[k]<=1,"Impossible ICU exit fraction");
          }
          assert(x.original_exit>=x.exit_without_return24 && x.exit_without_return24>=x.exit_without_return7d,"Return sensitivity violates monotonicity");
          assert(Math.abs(x.original_exit-x.exit_without_return24-x.exit_then_return24_n/x.n)<0.00002,"ICU return count/rate discrepancy");
        }
        const old=z.earlier_rolling_origin.horizons.at(-1);
        const now=z.horizons.at(-1);
        assert(Math.abs(a.earlier.original_exit-old.observed_exit)<0.00002,"Earlier exit conflicts with source");
        assert(Math.abs(a.later.original_exit-now.exit.observed)<0.00002,"Later exit conflicts with source");
        assert(typeof a.caveat==="string" && a.caveat.length>30,"ICU return caveat required");
      }
      assert(Array.isArray(z.scientific_limitations) && z.scientific_limitations.length>=3,"Scientific caveats required");
    }
    assert(r.methods.warnings.length>=4,"Methods limitations required");
    const raw=JSON.stringify(r);
    for(const forbidden of [/"subject_id"\s*:/,/"stay_id"\s*:/,/"hadm_id"\s*:/,/"patient_id"\s*:/,/"raw_rows"\s*:/,/"date_of_birth"\s*:/,/"email"\s*:/,/"access_token"\s*:/,/"api_key"\s*:/,/"password"\s*:/]){
      assert(!forbidden.test(raw),"Forbidden raw/sensitive field in release");
    }
  }
  assert(releases.length>0,"At least one research release required");
  return true;
}
export function loadPublications() {
  const tracks=readJson(path.join(dataDir,"tracks.json"));
  const releases=fs.readdirSync(path.join(dataDir,"rounds")).filter(x=>x.endsWith(".json")).map(name=>readJson(path.join(dataDir,"rounds",name)));
  validatePublication(tracks,releases);
  releases.sort((a,b)=>b.date.localeCompare(a.date)||(b.round_number-a.round_number)||b.id.localeCompare(a.id));
  return {tracks,releases};
}
