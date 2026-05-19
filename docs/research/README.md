# Phase 1 — Research deliverables

This directory is the heart of Phase 1. Each deliverable below is a stand-alone,
citation-heavy Markdown document. **Every factual claim must resolve to an
entry in [`../../CITATIONS.bib`](../../CITATIONS.bib).** If you cannot cite a
primary source, you do not yet have the right to state it as a fact.

## Deliverables

| File | Purpose | Status |
|------|---------|--------|
| [`01-data-catalogue.md`](01-data-catalogue.md) | Every open dataset under consideration: provider, spatial/temporal resolution, coverage, access method, license, caveats, citation. | Stub |
| [`02-crop-knowledge-base.md`](02-crop-knowledge-base.md) | Crop-trait databases (ECOCROP, GAEZ, USDA PLANTS, TRY) and process-based crop models (WOFOST/PCSE, DSSAT, APSIM, AquaCrop, STICS). Decision matrix. | Stub |
| [`03-methodology.md`](03-methodology.md) | The three-tier modeling architecture: envelope screening → process-based projection → ML bias correction. Why this synthesis. | Stub |
| [`04-uncertainty-and-validation.md`](04-uncertainty-and-validation.md) | Hawkins–Sutton uncertainty decomposition. Hindcast harness design. Cross-validation strategy. Confounder handling. | Stub |
| [`05-existing-tools-survey.md`](05-existing-tools-survey.md) | State of the art — FAO GAEZ, CCAFS Climate Analogues, JRC MARS, academic projects. Differentiation statement for AIgriculture. | Stub |

## Workflow per document

1. Outline → fill the section TODOs.
2. For each claim, add a BibTeX entry to `CITATIONS.bib` and cite inline as
   `[@bibkey]`.
3. Verify each citation (resolve DOI / fetch URL / confirm dataset access).
4. Self-review against the [`CONTRIBUTING.md`](../../CONTRIBUTING.md)
   disciplines.
5. The document is "complete" only once an ADR has been written for every
   choice it justifies.
