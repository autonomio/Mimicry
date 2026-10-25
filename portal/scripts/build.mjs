import fs from "node:fs";
import path from "node:path";
import { root, dataDir, outputDir, loadPublications } from "./publication.mjs";

const { tracks, releases } = loadPublications();
fs.rmSync(outputDir, {recursive:true,force:true});
fs.mkdirSync(outputDir,{recursive:true});
const put=(rel,value)=>{const p=path.join(outputDir,rel);fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,value);};
const copy=(source,rel)=>{const p=path.join(outputDir,rel);fs.mkdirSync(path.dirname(p),{recursive:true});fs.copyFileSync(source,p);};
const esc=(s)=>String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;");
const hostname="https://mimicry.mikkokotila.com";
const routes=[];
function page(route,pageType,title,description) {
  const url=route==="/" ? "/" : route.replace(/\/?$/,"/");
  routes.push(url);
  const html=[
  '<!doctype html><html lang="en"><head>',
  '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
  '<meta name="theme-color" content="#0c1b22"><meta name="color-scheme" content="light">',
  '<meta name="description" content="'+esc(description)+'">',
  '<meta property="og:site_name" content="Mimicry — Research Observatory">',
  '<meta property="og:type" content="website"><meta property="og:title" content="'+esc(title)+'">',
  '<meta property="og:description" content="'+esc(description)+'">',
  '<meta property="og:url" content="'+hostname+url+'">',
  '<meta name="twitter:card" content="summary">',
  '<link rel="canonical" href="'+hostname+url+'">',
  '<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">',
  '<link rel="preconnect" href="https://fonts.googleapis.com">',
  '<link rel="stylesheet" href="/assets/site.css">',
  '<title>'+esc(title)+'</title></head>',
  '<body data-page="'+esc(pageType)+'" data-route="'+esc(url)+'">',
  '<a class="skip" href="#main">Skip to research</a>',
  '<div id="site-header"></div><main id="main" tabindex="-1"><div class="loading-stage"><span class="load-orbit" aria-hidden="true"></span><p>Opening the research observatory…</p></div></main>',
  '<div id="site-footer"></div>',
  '<noscript><div class="noscript">This interactive research portal requires JavaScript. The underlying research methodology and reproducible code are available at <a href="https://github.com/autonomio/Mimicry">GitHub</a>.</div></noscript>',
  '<script type="module" src="/assets/site.js"></script>',
  '</body></html>'].join("");
  const file=url==="/"?"index.html":url.substring(1)+"index.html";
  put(file,html);
}
const title="Mimicry — A living research observatory";
page("/","home",title,"Transparent, interactive research on health, decisions and the systems that shape outcomes.");
page("/research/","tracks","Research tracks | Mimicry","Explore research tracks, methods, datasets, published results and scientific validation status.");
page("/about/","about","Our approach | Mimicry","Open methods, versioned evidence, reproducibility, and what we cannot conclude.");
for(const track of tracks.tracks){
  page("/tracks/"+track.slug+"/","track",track.name+" | Mimicry",track.description);
  page("/tracks/"+track.slug+"/methods/","methods",track.name+" — Methods | Mimicry","Methods, assumptions, data provenance, reproducibility and scientific limitations for "+track.name+".");
  page("/tracks/"+track.slug+"/releases/","releases",track.name+" — Research releases | Mimicry","Chronological, versioned research releases and validation status for "+track.name+".");
  for(const r of releases.filter(x=>x.track===track.id)){
    page("/tracks/"+track.slug+"/releases/"+r.id+"/","release",r.title+" | "+track.name+" | Mimicry",r.message);
  }
}
page("/404/","notfound","Page not found | Mimicry","Return to the Mimicry research observatory.");
copy(path.join(root,"site","site.js"),"assets/site.js");
copy(path.join(root,"site","site.css"),"assets/site.css");
copy(path.join(root,"site","favicon.svg"),"assets/favicon.svg");
put("data/catalog.json",JSON.stringify({
  schema_version:1,site:tracks.site,domain:tracks.domain,mission:tracks.mission,
  tracks:tracks.tracks.map(t=>({...t,
    latest:releases.find(r=>r.track===t.id)?.id || null,
    count:releases.filter(r=>r.track===t.id).length})),
  releases:releases.map(r=>({id:r.id,track:r.track,title:r.title,subtitle:r.subtitle,date:r.date,status:r.status,review_status:r.review_status,
    dataset:r.dataset,message:r.message,prediction_gain_relative:r.prediction.improvement.relative,simulation_validation:r.simulation.validation,simulation_all_pass:r.simulation.horizons.every(h=>h.passed)})),
  latest:releases[0]?.id||null
},null,2)+"\n");
for(const r of releases){
  put("data/rounds/"+r.id+".json",JSON.stringify(r,null,2)+"\n");
}
put("robots.txt","User-agent: *\nAllow: /\nSitemap: "+hostname+"/sitemap.xml\n");
put("sitemap.xml",'<?xml version="1.0" encoding="utf-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+routes.map(r=>'<url><loc>'+hostname+r+'</loc></url>').join("")+'</urlset>');
put("404.html",fs.readFileSync(path.join(outputDir,"404","index.html")));
put("_headers",[
"/*",
"  X-Content-Type-Options: nosniff",
"  Referrer-Policy: strict-origin-when-cross-origin",
"  Permissions-Policy: camera=(), microphone=(), geolocation=()",
"  X-Frame-Options: DENY",
"  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
"",
"/data/catalog.json",
"  Cache-Control: public, max-age=60, must-revalidate",
"",
"/data/rounds/*",
"  Cache-Control: public, max-age=120, must-revalidate",
"",
"/assets/*",
"  Cache-Control: public, max-age=120, must-revalidate",
""
].join("\n"));
console.log("Built Mimicry portal: "+tracks.tracks.length+" track(s), "+releases.length+" reviewed release(s), "+routes.length+" routes.");
