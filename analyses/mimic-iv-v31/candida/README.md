# Candida: fungus vs host

Follow-up to the compounds finding (micafungin exposure lift 14.5x in
ICU decedents): is it the fungus killing, or the drug marking salvage-stage
hosts? Answered with blood-culture data (`microbiologyevents`, structured).

## Design

- Population: first ICU stays per hospitalization (85,242).
- Candidemia: candida spp. in `BLOOD CULTURE` (+ myco/f-lytic bottles)
  drawn during the stay. n = 271.
- Micafungin: prescribed during the hospitalization (`prescriptions`,
  full-era coverage, unlike 50%-coverage eMAR). n = 1,924.
- Only 207/1,924 (11%) of micafungin use is directed at documented
  candidemia — 89% is empiric.
- Outcomes: died in ICU / died in hospital. Aggregates only.

## The 2x2 (hospital mortality)

| candidemia | micafungin | n | ICU death | hosp death | med age | med LOS |
|---|---|---|---|---|---|---|
| no | no | 83,254 | 6.2% | 10.2% | 65 | 1.9d |
| no | yes (empiric) | 1,717 | 26.9% | 47.3% | 60 | 4.3d |
| yes | no | 64 | 73.4% | 84.4% | 71 | 6.2d |
| yes | yes (directed) | 207 | 35.3% | 43.5% | 61 | 11.7d |

## Read

- **Untreated candidemia is near-uniformly fatal (84%)** — but n=64, oldest
  group, and confounded: cultures take days, so the untreated include those
  who died before results/treatment (immortal-time bias) and comfort-care
  patients where treatment was withheld.
- **The 14.5x micafungin lift is not a candida story**: 89% of use is
  empiric, and the empiric group dies at 47% — salvage-stage illness.
- Treated candidemia (44%) ≈ empiric group (47%): once treated, the fungus
  adds little beyond the salvage baseline — or, equivalently, treatment
  brings 84%-bound patients down to the salvage rate. Both readings fit;
  timing data (culture date → drug start → death) would separate them.

## Reproduce

On s0 (read-only): pipe `candida.sql` into `duckdb -readonly -csv $DB`.
Figure: `uv run --with matplotlib python make_plots.py`.
