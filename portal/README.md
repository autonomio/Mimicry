# Mimicry — living research observatory

Public website: https://mimicry.mikkokotila.com

The site now has two distinct research tracks: **Prophecy** (policy-dependent ICU prognosis and simulation) and **Prophecy 2** (the specific DNR causal question, forked before the general simulator). They have independent releases, clinical questions and methods.

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

Use Node.js 20 or newer and run these commands from `portal/` in the order shown. `npm test` validates the publication logic; `npm run build` generates `dist/`; `npm run check` then reads those generated pages, the catalog and the security headers. Rebuild after changing publication data or site sources so the final check examines the current output. These three verification commands use only Node.js built-ins and the repository sources, so they do not require an npm package installation.

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

## Research round 02

The second Prophecy research round is the historical transport analysis: `data/rounds/2026-10-25-discharge-transport.json`. It includes an interactive observed-versus-real-history-predicted-versus-simulated trajectory explorer, a previous rolling-origin check and measured-case-mix-standardized ICU-discharge comparisons. The original inaugural release is preserved unchanged apart from explicit chronological round numbering. Both use the same canonical published evidence schema, with additional fail-fast conservation checks for transport metrics.

## Separate DNR track: Prophecy 2

Prophecy 2 is accessible at /tracks/prophecy-2/ with a separate methods and release history. Its releases carry kind=dnr-audit and are validated independently of Prophecy's mortality-model schema. The first DNR-only clinical question is anchored to the actual hospital code-status order, not to a generic prediction output. The page makes false IV assumptions, limited comparison overlap, high early mortality selection and failed strict balance visibly explicit. It is not a causal DNR effect publication.

## Mimicry Viz — reusable visual research engine

The [Mimicry Viz MVP](docs/MIMICRY-VIZ-MVP.md) powers a [five-scene Prophecy 2 DNR investigation](docs/PROPHECY-2-FLAGSHIP-STORYBOARD.md) at `/tracks/prophecy-2/stories/the-dnr-order/`. Animated study-cohort aggregates, observed event-time playback, a specification/uncertainty matrix, and a mortality-claim audit are sourced entirely from reviewed summary data; no individual MIMIC-IV records are published. The engine is reusable through independently registered story adapters and publication-linked aggregate data contracts.
