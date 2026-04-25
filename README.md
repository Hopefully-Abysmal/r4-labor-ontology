## R4 Labor Ontology (US-first)

This repo is a **US-first occupational + humanitarian task ontology** intended to support:

- Building a **skill tree** (task-up) for disaster relief / community resilience work
- Mapping tasks to **occupational skill spines** (SOC / O*NET) and research overlays (AI exposure, relatedness)
- Local-first community “supply site routing” / mutual-aid operations (WNC/R4 context)

### What’s in repo vs. reproducible

- **Tracked in git**: scripts + metadata (`Fetch-LaborData.ps1`, `SOURCES.txt`)
- **Not tracked**: large/vendor datasets in `downloads/` and `papers/` (see `.gitignore`)

### Fetch datasets

Run from the repo root:

```powershell
.\Fetch-LaborData.ps1
```

This pulls:

- O*NET 30.2 database (text + excel)
- O*NET related-occupations research dataset + operational matrix
- AIOE (AI occupational exposure) repo snapshot
- A small set of reference PDFs

Notes:
- Some sources (notably **BLS OEWS**) may return **HTTP 403** to automated clients; download manually as listed in `SOURCES.txt`.

### Data notes

Your exported ontology CSV(s) should be placed in `imports/` locally for analysis/ETL.
If we want to publish a sample, we should add a **scrubbed**/minimized version explicitly.

