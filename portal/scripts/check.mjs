import fs from "node:fs";
import path from "node:path";
import {loadPublications,root,outputDir,assert} from "./publication.mjs";
const {tracks,releases}=loadPublications();
function checkPage(url){
  const f=url==="/"?"index.html":url.slice(1)+"index.html";
  assert(fs.existsSync(path.join(outputDir,f)), "Missing route: "+url);
  const text=fs.readFileSync(path.join(outputDir,f),"utf8");
  assert(text.includes('<main id="main"') && text.includes('name="description"'),"Incomplete page "+url);
}
checkPage("/");
checkPage("/research/");
checkPage("/about/");
for(const track of tracks.tracks){
  checkPage("/tracks/"+track.slug+"/");
  checkPage("/tracks/"+track.slug+"/methods/");
  checkPage("/tracks/"+track.slug+"/releases/");
}
for(const release of releases){
  const route="/tracks/"+release.track+"/releases/"+release.id+"/";
  checkPage(route);
  const r=JSON.parse(fs.readFileSync(path.join(outputDir,"data","rounds",release.id+".json"),"utf8"));
  assert(r.id===release.id,"Published data changed");
}
const catalog=JSON.parse(fs.readFileSync(path.join(outputDir,"data","catalog.json"),"utf8"));
assert(catalog.tracks.length===tracks.tracks.length,"Catalog track count mismatch");
assert(catalog.releases.length===releases.length,"Catalog release count mismatch");
assert(catalog.releases[0].id===releases[0].id, "Latest release not correctly ordered");
assert(catalog.releases.every(r=>Number.isInteger(r.round_number)), "Round sequence missing");
for(const tr of catalog.tracks){
  assert(tr.count===catalog.releases.filter(r=>r.track===tr.id).length, "Track release counter mismatch");
  assert(!tr.latest||catalog.releases.some(r=>r.id===tr.latest),"Broken latest release pointer");
}
const js=fs.readFileSync(path.join(outputDir,"assets","site.js"),"utf8");
assert(js.includes("installOutcomeExplorer") && js.includes("data-lens"),"Interactive reading controls missing");
assert(js.includes("Long-horizon validation did not pass"),"Validation failure must be visible");
assert(js.includes("installTransportExplorer"), "Transport error explorer missing");
if(tracks.tracks.some(t=>t.id==="prophecy-2")){
 assert(js.includes("installDnrExplorer")&&js.includes("dnrMethods"),"Prophecy 2 interactive and identification pages missing");
 assert(js.includes("Severe short-term mortality imbalance remains."),"DNR causal confounding warning must be visible");
 assert(js.includes("max measured |SMD|")||js.includes("maximum measured |SMD|")||js.includes("maximum standardized difference"),"Overlap diagnosis must be explicit");
}
const csp=fs.readFileSync(path.join(outputDir,"_headers"),"utf8");
assert(csp.includes("Content-Security-Policy") && csp.includes("X-Content-Type-Options"),"Security headers missing");
const all=fs.readdirSync(outputDir);
assert(!all.some(x=>x.endsWith(".parquet")||x.endsWith(".joblib")||x.endsWith(".db")), "Patient-level artifact in public root");
console.log("Publication checks passed: "+tracks.tracks.length+" tracks, "+releases.length+" aggregate research releases, all routes and integrity constraints.");
