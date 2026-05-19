# ADR 0006 — License

- **Status:** accepted
- **Date:** 2026-05-19

## Context

AIgriculture is a portfolio project whose scientific value depends on
transparency and reproducibility. The author wants any future audience —
employers, collaborators, downstream researchers — to be able to read,
verify, and extend the code without legal friction.

The dependency tree is overwhelmingly permissive-licensed (MIT, BSD,
Apache-2.0, plus the scientific-data licenses of Copernicus, NASA, ECCC,
USDA, etc., which apply to the data, not the code).

## Decision

License the source code under the **MIT License**.

## Consequences

- **Pros:** broadest possible reuse; maximum visibility; no friction for
  potential employers or commercial collaborators to read and run the code;
  matches the cultural norm in the Python scientific stack.
- **Cons:** no copyleft protection — a future fork could go closed-source.
  Considered acceptable for this project since the value is in the
  documented research artifacts and architecture, not in proprietary code.
- The license applies to code only. Each ingested dataset retains its own
  license (which is tracked in `docs/research/01-data-catalogue.md`).
  Notably:
  - Copernicus / ESA data: free and open under the Copernicus regulation.
  - USGS / NASA data: public-domain or free.
  - ECCC, NRCan, AAFC, StatCan: Open Government Licence — Canada.
  - FAO data: CC BY-NC-SA or CC BY 3.0 IGO (varies).

  Wherever the redistribution license of a derived product conflicts with
  MIT (e.g., a non-commercial dataset), the conflict will be flagged in
  the data catalogue and we will avoid redistributing — only reference the
  upstream source.

## Alternatives considered

- **Apache-2.0** — adds an explicit patent grant. Useful for projects with
  novel algorithms; we do not anticipate novel patentable algorithms here
  (our novelty is in synthesis and applied methodology). Slightly heavier
  license header overhead. Rejected on simplicity grounds.
- **AGPL-3.0** — would force any SaaS deployment of a fork to share source.
  Attractive philosophically but a strong deterrent to adoption by anyone
  who might be sensitive to copyleft. Rejected for a portfolio project.
- **No license** — defaults to "all rights reserved," which would make the
  code unusable by anyone but the author. Rejected.

## References

- [MIT License — OSI-approved text](https://opensource.org/licenses/MIT)
- [Copernicus data and information policy](https://www.copernicus.eu/en/access-data/copyright-and-licences)
- [Open Government Licence — Canada](https://open.canada.ca/en/open-government-licence-canada)
