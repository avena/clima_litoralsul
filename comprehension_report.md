# Stage 6: Comprehension Test Report

**Target Document:** `.planning/designs/inmet-nasa-power.md`  
**Semantic Ranges:** FeatureRange (lines 1–198), DetailedRange (lines 199–275)  
**Date:** 2026-10-30  

---

## What This Design Intends to Build (Paraphrase)

The design proposes an extension to the existing climatological observatory to incorporate observational data from INMET (Instituto Nacional de Meteorologia) and satellite/reanalysis climate data from NASA POWER. The primary objective is to achieve full coverage for all 25 municipalities across Litoral Sul Paulista and Vale do Ribeira by filling the data void in the 4 coastal municipalities that lack surface stations in CIIAGRO: Itanhaém, Mongaguá, Peruíbe, and Ilha Comprida.

The design establishes a strict methodological boundary: physical surface station observations (from CIIAGRO and INMET) and gridded reanalysis (from NASA POWER) will never be blended, averaged, or spatially interpolated. Instead, each data stream will retain its distinct provenance from collection to final presentation. In the web dashboard and printed single-page A4 PDF sheets, municipalities relying on NASA POWER reanalysis will be clearly identified with persistent disclaimers indicating that gridded models do not replace physical rain gauges and thermometers. Furthermore, overlapping records between CIIAGRO and INMET (in stations such as Registro and Iguape) will be cross-compared to identify pre-automation anomalies and audit sensor fidelity.

---

## How This Design Intends to Build It (Paraphrase)

The implementation introduces two new standalone ingestion modules (`fontes/inmet.py` and `fontes/nasa_power.py`) in the `fontes/` directory, adhering to the established three-member source interface: `FONTE`, `pontos()`, and `fatos()`. 

1. **Network Adapters**:
   * `fontes/inmet.py` accesses the public INMET REST API (`apitempo.inmet.gov.br`) to fetch station metadata and historical daily series, mapping missing sensors to `None` and namespacing station identifiers as `inmet:<id>`.
   * `fontes/nasa_power.py` accesses the NASA POWER Daily Point API to query centroid coordinates for unmonitored coastal municipalities (Ilha Comprida and Mongaguá), tagging outputs as `tipo = "reanalise"` with point IDs formatted as `nasa:<slug>`.

2. **Core Pipeline & Storage Integration**:
   * `coletor.py` is extended with a `--fonte` CLI argument to support selective or combined multi-source ingestion (`todas`, `ciiagro`, `inmet`, `nasa_power`). The SQLite schema preserves compatibility by adopting namespaced IDs (`ponto.id`), migrating legacy bare IDs (`63` -> `ciiagro:63`).
   * `coletor.py auditar` implements automated delta checks on overlapping station pairs to flag divergent precipitation and temperature months.

3. **Presentation & Output Layer**:
   * `relatorio.py` embeds `fonte` and `tipo` attributes into `site/public/dados.json`.
   * `site/src/App.jsx` activates cards for the 4 previously unmonitored municipalities, displays source attribution badges, and renders non-dismissible explanatory warnings for reanalysis entries.
   * `latex/gerar.py` formats grayscale A4 PDF sheets with appropriate source badges and reanalysis footnotes.

4. **Testing & Invariants**:
   * Offline test suites (`tests/test_inmet.py` and `tests/test_nasa_power.py`) are created alongside static JSON fixtures (`tests/fixtures/`) to guarantee deterministic execution of `unittest discover -s tests` without network dependencies.
   * Headless SSR tests in `site/check.jsx` are updated to assert the activation of all 25 municipalities and the presence of new source badges.

---

## Comprehension Findings & Ambiguities

1. **Paraphrase Alignment**: The document is self-contained. The relationship between the three source providers, the namespacing convention, and the visual distinction in downstream deliverables is clear.
2. **Ambiguity on Peruíbe Station Assignment**: While the narrative explains that Itanhaém and Peruíbe will be served by INMET, Section 3.A links INMET station `A712` to both Peruíbe and Iguape. Because A712 is physically located in Iguape, the document should state whether Peruíbe will ingest data from A712 (with explicit regional attribution, e.g. "Iguape/A712 — Estação de Referência para Peruíbe") or whether a distinct sensor/virtual point is used.
3. **Execution Sequence for SQLite Namespacing Migration**: In `Detailed Implementation Plan` under item 5 (`coletor.py`), the migration of existing numeric IDs (`63` -> `ciiagro:63`) must ensure existing foreign key references in `fato` (`fato.ponto_id`) are safely cascaded without orphaned records.
