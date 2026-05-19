# 05 — Existing tools survey

> **Status:** stub. To be filled in during Phase 1.
>
> **Goal:** know what already exists so we do not reinvent it; identify
> the gap that justifies AIgriculture.

## To document

- **FAO GAEZ Data Portal** — global suitability rasters under fixed
  scenarios. Not interactive at user-drawn region level; not multi-SSP at
  fine granularity; no integrated hindcast harness.
- **CGIAR CCAFS Climate Analogues** — finds "where today resembles your
  region's future." Useful complement, not a substitute.
- **EC JRC Agri4Cast + MARS Bulletin** — operational nowcasting for EU
  agriculture; near-real-time, not 5–10 year projections.
- **NASA Harvest, ESA WorldCereal** — large-scale crop monitoring; not
  suitability projection.
- **Plantvillage, OneSoil, Climate FieldView, Granular** — commercial /
  current-season tools. Mentioned only as context.
- **Academic projects 2022–2025** — Fitzgibbon et al. 2022
  [@Fitzgibbon2022], Sgubin et al. 2023 [@Sgubin2023], Lobell &
  Di Tommaso 2025 [@LobellDiTommaso2025], and the recent 17-crop
  suitability dataset paper (to be cited once added to `CITATIONS.bib`).

## Differentiation statement (to be sharpened)

AIgriculture combines, in one open tool:

1. **User-drawn regions.** Not pre-aggregated to national or NUTS-2 units.
2. **Multi-scenario, multi-model uncertainty** displayed transparently.
3. **An explicit hindcast harness** — the user can verify the tool against
   their own region's history.
4. **A three-tier model** that joins the FAO-lineage envelope approach,
   the AgMIP-lineage process model, and modern ML — each tier inspectable.
5. **Open-source, reproducible, citation-disciplined.**

## Verification checklist

- [ ] Each tool's URL resolves; current version captured.
- [ ] The differentiation statement is read by a domain expert (eventually)
      before AIgriculture is promoted publicly.
