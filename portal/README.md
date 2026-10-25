# Mimicry — living research observatory

Public website: https://mimicry.mikkokotila.com

The site is intentionally separate from any private clinical data warehouse. Mimicry is the umbrella publication platform; **Prophecy** is the first research track at `/tracks/prophecy/`. The same schema supports additional tracks without sharing their evidence or method claims.

## Publication workflow

1. Run and audit research on the restricted server. Keep all patient-level data, chart exports, model checkpoints, and credentials off GitHub.
2. Curate aggregate, scientifically reviewed outcomes in `portal/data/rounds/YYYY-MM-DD-<slug>.json`, with `track` set to a registered track in `portal/data/tracks.json`.
3. Preserve failed acceptance gates; the publication validator recomputes whether simulation results pass the gates. Do not relabel a failed model as validated.
4. Create a PR with the new aggregate release and reviewed methodology. CI runs `npm test`, `npm run build`, `npm run check` and prohibits known sensitive binary formats.
5. Merge to the production branch. Cloudflare Pages Git integration rebuilds and publishes the site's catalog, release index, interactive figures and permanent release URL automatically. Earlier release JSONs remain in the repository.

**Adding a track:** append a unique entry to `portal/data/tracks.json`; supply per-track content/release data. A separate track begins with its own evidence and limitations, not copied claims.

## Local commands

```bash
cd portal
npm test
npm run build
npm run check
```

There are no runtime application dependencies; output is a static multi-page site, including dynamic client-side charts sourced from **versioned, publish-safe JSON files**. Cloudflare publishes only `portal/dist`.

## Privacy and editorial gates

Only aggregate results are public. No `subject_id`, `stay_id`, `hadm_id`, per-patient rows, database files, Parquet files, model checkpoints, private credentials, or actual patient trajectories may appear in a release. Values on this site are *observational*, and no section claims a causal DNR effect or counterfactual policy outcome. The long-horizon Prophecy simulator currently **fails** its prespecified discharge/occupancy validation criteria. The model is not suitable for clinical use.

## Cloudflare Pages

- Project: `mimicry-research`
- Production Git source: `autonomio/Mimicry`, branch `master`
- Root directory: `portal`
- Build command: `npm run build && npm run check`
- Output directory: `dist`
- Custom domain: `mimicry.mikkokotila.com`

Future aggregate releases update on approved merges; this does **not** expose an endpoint or grant permission for the server to directly upload patient-level analyses.

**Repository protection:** `master` requires one independent approving GitHub review. Production publishing runs only after the reviewed PR is merged; preview deployments are available before approval.
