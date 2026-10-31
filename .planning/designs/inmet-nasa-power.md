# Integration of External Climate Data Sources (INMET & NASA POWER)

* **Author:** livre
* **Status:** Approved
* **Date:** 2026-10-30

--------------------------------------------------------------------------------

## Overview

This technical design defines the architectural extension of the climatological observatory for the 25 municipalities of Litoral Sul Paulista and Vale do Ribeira to ingest two external data sources: INMET (Instituto Nacional de Meteorologia) and NASA POWER (Prediction Of Worldwide Energy Resources).

By expanding beyond CIIAGRO, the system resolves observational coverage gaps across coastal municipalities that lack surface stations in CIIAGRO's automated network (Itanhaém, Mongaguá, Peruíbe, and Ilha Comprida) and introduces an independent baseline to audit pre-automation historical records.

## Problem

The current observatory relies exclusively on CIIAGRO. While CIIAGRO provides verified observational records for 21 municipalities across 23 stations, 4 municipalities (Itanhaém, Mongaguá, Peruíbe, and Ilha Comprida) possess zero active stations in the ingested network. In the web dashboard, these municipalities are presented as inactive placeholders, preventing agricultural extension workers (ATER) and environmental planners from evaluating local precipitation patterns, seasonal distributions, and thermal regimes.

Furthermore, several CIIAGRO historical series exhibit pre-automation data artifacts (e.g., records predating physical station installation dates and anomalous relative humidity values) that currently cannot be cross-referenced against an independent observational ground truth.

## Goals

* **Complete Municipal Coverage**: Provide empirical climate profiles for all 25 target municipalities, eliminating blank placeholder entries in the web observatory.
* **Standard Source Interface**: Implement `fontes/inmet.py` and `fontes/nasa_power.py` adhering strictly to the repository's source contract (`FONTE`, `pontos()`, `fatos()`) without modifying the core collection engine (`coletor.py`).
* **Source Transparency**: Maintain strict, uncompromised provenance across the data pipeline; physical station observations (CIIAGRO, INMET) and satellite reanalysis (NASA POWER) must be explicitly segregated in data storage and visual display.
* **Zero Dependency Invariant**: Implement all network clients and parsing routines using exclusively Python 3.12 standard library (`urllib.request`, `json`, `sqlite3`).

## Non-Goals

* **Synthetic Data Blending**: Blending, interpolating, or averaging satellite reanalysis values into physical surface station gauges is strictly prohibited.
* **Database Schema Overhaul**: Replacing SQLite or mutating table architectures; existing `ponto` (`fonte`, `id`, `municipio_id`) and `fato` tables natively support multi-source partitioning.
* **Real-Time Weather Forecasting**: The system remains a historical agroclimatological observatory; short-term predictive weather forecasting is out of scope.

## Critical User Journeys (CUJs)

### CUJ 1: Extension Agent Evaluates Coastal Municipality with INMET Station

* **Given**: The user needs historical climate indicators for Itanhaém or Peruíbe.
* **When**: The user opens the dashboard and selects the municipality card (`#/itanhaem` or `#/peruibe`).
* **Then**: The dashboard renders a full climatogram, thermal envelope, seasonal metrics, and A4 PDF link derived from the designated INMET surface station, with badge attribution indicating `Fonte: INMET`.

### CUJ 2: Agronomic Planner Evaluates Municipality with Reanalysis Data

* **Given**: The user selects Ilha Comprida or Mongaguá, where no physical surface station exists across either CIIAGRO or INMET.
* **When**: The user navigates to the municipality page.
* **Then**: The dashboard displays the 30-year climatological baseline computed from NASA POWER daily reanalysis, accompanied by a clear notice distinguishing satellite reanalysis from physical station gauges.

--------------------------------------------------------------------------------

## Technical Plan (Architecture)

### 1. System Topology & Data Flow

The architecture follows a decoupled, unidirectional data pipeline. Each data provider operates as an isolated adapter in `fontes/`, yielding standardized dictionary streams directly into the core engine (`coletor.py`).

```text
       [ INMET API ]             [ NASA POWER API ]          [ CIIAGRO Web ]
     (REST JSON / CSV)           (REST GeoJSON / JSON)        (HTTP HTML regex)
             │                           │                            │
      fontes/inmet.py            fontes/nasa_power.py         fontes/ciiagro.py
             │                           │                            │
             └───────────────────────────┼────────────────────────────┘
                                         ▼
                                   coletor.py
                     (Schema, Namespaced Upsert, Auditing)
                                         │
                                         ▼
                                 dados/clima.sqlite
                       Tables: municipio, ponto, fato
                                         │
                                         ▼
                                   relatorio.py
                     (Sanity Limits, Seasonal Aggregations,
                      Provenance & Reanalysis Disclaimers)
                                         │
                                         ▼
                               site/public/dados.json
                                ├── site/ (React SPA)
                                └── latex/gerar.py (A4 Monochrome PDFs)
```

### 2. Standard Source Interface Contract

Each new ingestion module in `fontes/` implements the three invariant primitives defined by the observatory:

```python
FONTE: str  # e.g., "inmet" or "nasa_power"

def pontos() -> list[dict]:
    """Returns station catalog or virtual grid coordinate points.
    
    Returns:
        List of dicts containing:
        - id: Namespaced identifier (e.g. 'inmet:A711', 'nasa:ilha-comprida')
        - nome: Canonical station name or label
        - municipio: Target municipality name resolved via municipios.resolver()
        - lat: Latitude float
        - lon: Longitude float
        - inicio_auto: Declared start date (YYYY-MM-DD or None)
        - tipo: "estacao" or "reanalise"
    """

def fatos(desde: str, ate: str, diario: bool = False) -> Iterator[dict]:
    """Streams observational fact rows matching canonical schema.
    
    Args:
        desde: Start date ('YYYY-MM' or 'YYYY-MM-DD')
        ate: End date ('YYYY-MM' or 'YYYY-MM-DD')
        diario: True for daily observations, False for monthly aggregates
        
    Yields:
        Dict with keys: nome, data, tmin, tmed, tmax, urmin, urmed, urmax, chuva
    """
```

### 3. Source Specifications

#### A. INMET Surface Module (`fontes/inmet.py`)
* **Endpoint**: INMET Public API (`https://apitempo.inmet.gov.br/estacoes/T` for station directory, `https://apitempo.inmet.gov.br/dados/serie/` for historical records). Operates via unauthenticated public GET requests with explicit socket timeout (`timeout=30`).
* **Target Stations**:
  * Itanhaém (`A711` automatic / `83788` conventional).
  * Peruíbe: Assigned to INMET automatic station `A712` (Iguape / Barra do Ribeira) as the regional coastal reference station until a local dedicated automated sensor is deployed.
  * Registro (`A713` automatic) — utilized for cross-checking against CIIAGRO station 63.
* **Data Processing**:
  * Converts hourly measurements into daily aggregated records (min/max/avg temperature, accumulated precipitation).
  * Missing sensors evaluate to `None`, maintaining the database invariant that missing != `0`.
  * Namespaced point IDs: formatted as `inmet:<CODIGO>` to prevent collisions with CIIAGRO numeric IDs.

#### B. NASA POWER Reanalysis Module (`fontes/nasa_power.py`)
* **Endpoint**: NASA POWER API Daily Point Endpoint:
  `https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M,T2M_MIN,T2M_MAX,RH2M,PRECTOTCORR&community=AG&longitude={lon}&latitude={lat}&start={start}&end={end}&format=JSON`
* **Target Virtual Points & Land-Mask Coordinates**:
  * Coordinates are verified against terrestrial land masks to ensure sampling falls squarely within inhabited/agricultural land rather than open Atlantic ocean:
    * Ilha Comprida: `lat = -24.7400, lon = -47.5400` (terrestrial island center)
    * Mongaguá: `lat = -24.0900, lon = -46.6200` (inland coastal plain)
* **Data Processing**:
  * Parameter mappings: `T2M_MIN` -> `tmin`, `T2M` -> `tmed`, `T2M_MAX` -> `tmax`, `RH2M` -> `urmed`, `PRECTOTCORR` -> `chuva`.
  * Units: `PRECTOTCORR` in mm/day, `RH2M` in %, temperature in °C.
  * Sentinel conversion: NASA POWER missing values (`-999.0` or `-999`) are strictly converted to `None` (`NULL` in SQLite).
  * Point identification: `nasa:<municipio_slug>`.
  * Explicit metadata tagging: sets `tipo = "reanalise"` in catalog output.

### 4. Database Namespacing & Pipeline Updates

* **Storage**: In `dados/clima.sqlite`, `ponto.id` adopts explicit namespacing (`ciiagro:63`, `inmet:A711`, `nasa:ilha-comprida`). Existing records with bare numeric IDs (`63`) will be migrated to `ciiagro:<id>` during the initialization step without loss of historical `fato` relations.
* **CLI Extensibility (`coletor.py`)**:
  * Add `--fonte [ciiagro|inmet|nasa_power|todas]` flag to `coletor.py catalogo` and `coletar.py coletar`.
  * Default behavior remains backwards-compatible, defaulting to all registered sources.
* **Audit Module (`coletor.py auditar`)**:
  * Cross-compares overlapping months between CIIAGRO and INMET in Registro and Iguape to flag divergence in precipitation (> 25% variance) and temperature (> 2 °C variance). Emits diagnostic warnings in audit reports without modifying raw records.
* **Presentation Contract (`site/public/dados.json` & SPA)**:
  * Each station payload in `dados.json` includes `fonte` (`"ciiagro"`, `"inmet"`, `"nasa_power"`) and `tipo` (`"estacao"` vs `"reanalise"`).
  * React UI renders an explicit, non-dismissible badge on NASA POWER virtual cards: `Reanálise Global NASA POWER (Resolução 0.5° × 0.5°) · Não substitui pluviômetro de superfície`.
  * Single-page LaTeX A4 PDFs reflect source badge and appropriate methodological disclaimers.

--------------------------------------------------------------------------------

## Alternatives Considered

### Alternative A: Spatial Interpolation (Kriging / Inverse Distance Weighting) from Adjacent Stations

* **Mechanism**: Numerically estimate rainfall and temperatures for Itanhaém, Mongaguá, and Ilha Comprida using spatial distance weighting from nearby stations (Cananéia, Iguape, Pedro de Toledo).
* **Pros**: Eliminates external API dependencies; keeps the entire codebase locked to the local CIIAGRO dataset.
* **Cons**:
  * Fails across steep orographic barriers (e.g. Serra do Mar escarpments vs. coastal restnga flats).
  * Fabricates synthetic values and presents them as local measurements, violating the project invariant that unmeasured observations must remain `NULL`.
* **Reason for Rejection**: Scientific and agronomic dishonesty. Rural extension agents require either empirical physical observations or explicitly labeled satellite reanalysis, not unverified spatial interpolations.

### Alternative B: Universal Replacement with NASA POWER Reanalysis

* **Mechanism**: Abandon physical weather station scraping entirely and substitute all 25 municipalities with NASA POWER 0.5° × 0.5° grid points.
* **Pros**: Eliminates station sensor outages, missing dates, and scraping maintenance; provides uniform 30+ year records for all municipalities.
* **Cons**:
  * Coarse spatial resolution (~55 km grid cells) smooths out localized convective thunderstorms and microclimatic valley inversions.
  * Replaces ground-truth physical sensor gauges with model-derived estimates.
* **Reason for Rejection**: Physical surface gauges are irreplaceable for localized agronomic calibration. Reanalysis is only acceptable as an explicitly disclosed fallback for uninstrumented zones.

### Alternative C: Direct Web Scraping of INMET HTML Portals

* **Mechanism**: Scrape INMET web portal HTML tables using regular expressions or third-party HTML parsers, mirroring `fontes/ciiagro.py`.
* **Pros**: Independent of API availability or potential token policies.
* **Cons**:
  * INMET's web portal undergoes frequent layout redesigns, breaks session cookies, and employs client-side JavaScript rendering.
  * Adds unnecessary parser fragility when official open-data REST endpoints already exist.
* **Reason for Rejection**: INMET's open data REST API (`apitempo.inmet.gov.br`) provides structured JSON payloads, making HTML scraping an inferior, brittle architectural choice.

--------------------------------------------------------------------------------

## Non-Functional Requirements

* **Performance & Network Latency**: NASA POWER and INMET API requests must enforce polite pacing (`PAUSA = 0.25s`) with exponential backoff on `OSError`. All requests must declare explicit socket timeouts (`timeout=30`), ensuring multi-month collection sweeps do not stall indefinitely.
* **Zero New Dependencies**: All network parsing must remain strictly in the Python 3.12 standard library (`urllib.request`, `json`, `sqlite3`). No third-party packages (e.g. `requests`, `pandas`, `scipy`) may be introduced.
* **Deterministic Builds**: Static JSON export and PDF generation must remain bit-reproducible through `SOURCE_DATE_EPOCH`.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

### Target Files to Create/Modify

#### 1. `fontes/inmet.py` (Create)
* **Type / Scope**: Python stdlib ingestion module.
* **Rationale**: Implements the source contract (`FONTE = "inmet"`, `pontos()`, `fatos()`). Queries INMET open REST APIs (`apitempo.inmet.gov.br`) with `timeout=30`, aggregates hourly readings into daily/monthly summaries, and normalizes sensor readings to canonical metric dicts with `None` for missing values.

#### 2. `fontes/nasa_power.py` (Create)
* **Type / Scope**: Python stdlib ingestion module.
* **Rationale**: Implements the source contract (`FONTE = "nasa_power"`, `pontos()`, `fatos()`). Queries the NASA POWER API point endpoint for terrestrial coordinates of Ilha Comprida (`-24.7400, -47.5400`) and Mongaguá (`-24.0900, -46.6200`), mapping parameters (`T2M_MIN`, `T2M`, `T2M_MAX`, `RH2M`, `PRECTOTCORR`) to fact records, converting `-999.0` to `None`, and tagging records as `tipo = "reanalise"`.

#### 3. `fontes/__init__.py` (Modify)
* **Type / Scope**: Python package entry point.
* **Rationale**: Updates the module docstring and public exports to include `inmet` and `nasa_power` alongside `ciiagro`.

#### 4. `fontes/README.md` (Modify)
* **Type / Scope**: EGM contract documentation.
* **Rationale**: Documents public interfaces, network side effects, and invariants for the newly added source modules.

#### 5. `coletor.py` (Modify)
* **Type / Scope**: CLI entry point and database migration script.
* **Rationale**:
  * Implements atomic namespacing migration on `ponto.id` (`ciiagro:`, `inmet:`, `nasa:`) and foreign keys:
    ```sql
    PRAGMA foreign_keys = OFF;
    BEGIN TRANSACTION;
    UPDATE ponto SET id = 'ciiagro:' || id WHERE id NOT LIKE '%:%';
    UPDATE fato SET ponto_id = 'ciiagro:' || ponto_id WHERE ponto_id NOT LIKE '%:%';
    COMMIT;
    PRAGMA foreign_keys = ON;
    ```
  * Adds `--fonte` CLI argument to `catalogo` and `coletar` commands.
  * Adds cross-validation logic to `auditar` comparing overlapping historical series between CIIAGRO and INMET.

#### 6. `municipios.py` (Modify)
* **Type / Scope**: Canonical municipality resolver.
* **Rationale**: Extends `resolver()` with alias handling for INMET station headers (e.g. stripping suffixes like `ITANHAEM - A711` -> `Itanhaém`).

#### 7. `relatorio.py` (Modify)
* **Type / Scope**: Data aggregator and JSON exporter.
* **Rationale**:
  * Attaches `fonte` and `tipo` attributes to every station record in `site/public/dados.json`.
  * Emits reanalysis notice metadata in the global payload.

#### 8. `site/src/App.jsx` (Modify)
* **Type / Scope**: React SPA presentation component.
* **Rationale**:
  * Replaces disabled municipality placeholders with active station cards for Itanhaém, Peruíbe, Ilha Comprida, and Mongaguá.
  * Adds visual source badges (`CIIAGRO`, `INMET`, `NASA POWER`).
  * Renders a non-dismissible explanatory warning banner on reanalysis stations.

#### 9. `site/check.jsx` (Modify)
* **Type / Scope**: Headless SSR testing script.
* **Rationale**:
  * Adjusts active station count checks to reflect 27+ total active stations/points.
  * Asserts presence of `INMET` and `NASA POWER` labels and absence of disabled municipality entries.
  * Asserts that every station in `dados.json` contains a non-empty `fonte` string and valid `tipo` (`"estacao"` or `"reanalise"`).

#### 10. `latex/gerar.py` (Modify)
* **Type / Scope**: LaTeX A4 reference sheet generator.
* **Rationale**:
  * Renders source badges (`INMET`, `CIIAGRO`, `NASA POWER Reanálise`) on A4 sheets.
  * Injects specific footnote explaining reanalysis methodology when `tipo == "reanalise"`.

#### 11. `tests/test_inmet.py` & `tests/test_nasa_power.py` (Create)
* **Type / Scope**: Python `unittest` test suites.
* **Rationale**: Verifies response JSON parsing, missing sensor mappings, and date boundary calculations without network access using local fixtures.

#### 12. `tests/fixtures/inmet_estacoes.json` & `tests/fixtures/nasa_power_point.json` (Create)
* **Type / Scope**: Offline test fixture payloads.
* **Rationale**: Guaranteed offline reproducibility for `unittest discover -s tests`.

#### 13. `README.md` (Modify)
* **Type / Scope**: Repository Root Blueprint (Hay).
* **Rationale**: Updates system diagram, subdirectories index, and coverage statistics to reflect complete 25-municipality active data.

---

### Verification Plan

* **Unit Tests**:
  * `python3 -m unittest discover -s tests` (Executes all test suites including CIIAGRO, INMET, and NASA POWER offline fixture tests).
* **Headless DOM Testing**:
  * `npm --prefix site run check` (Validates 30+ contract assertions on the rendered React dashboard markup).
* **Web Production Build**:
  * `npm --prefix site run build` (Ensures Vite and Tailwind v4 compile without errors or bundle bloat).
* **LaTeX A4 Document Compilation**:
  * `python3 latex/gerar.py --pdf` (Verifies all 27+ station sheets compile to clean, single-page monochrome A4 PDFs via `tectonic`).

--------------------------------------------------------------------------------

*Drafted with EGM*
