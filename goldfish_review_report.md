# Goldfish Annotated Review Report

* **Status:** Resolved
* **Target:** `.planning/designs/inmet-nasa-power.md` (`full file`)
* **Accepted Fixes:** 7/7 applied
* **Date:** 2026-10-30

## Prioritized Findings & AI Suggestions

### 1. [CRITIC-DESIGN-01] [`egm-design`] - Severity: High
* **Affected Scope:** Section 3.B (NASA POWER Reanalysis Module)
* **Discrepancy Description:** Centroid coordinates for narrow coastal municipalities (Ilha Comprida, Mongaguá) risk ocean sampling due to 0.5° grid resolution.
* **Rationale:** A 0.5° grid cell (~55 km) could pull marine data if the point is placed offshore.
* ***AI Suggestion:*** PROPOSE FIX
* ***Justification:*** Coordinates must be explicitly locked to verified terrestrial agricultural ground.
* ***Proposed Edit:***
  * Location: Section 3.B
  * Change: Explicitly lock Ilha Comprida to `lat = -24.7400, lon = -47.5400` (terrestrial island center) and Mongaguá to `lat = -24.0900, lon = -46.6200` (inland coastal plain), documenting land-mask verification.

### 2. [READINESS-01] [`egm-implementation-readiness`] - Severity: High
* **Affected Scope:** Target File 5 (`coletor.py`)
* **Discrepancy Description:** Migrating `ponto.id` from `63` to `ciiagro:63` without disabling foreign keys will trigger foreign key constraint errors or orphan `fato` records.
* **Rationale:** SQLite enforces foreign keys when enabled; modifying primary keys referenced by `fato` requires an atomic migration block.
* ***AI Suggestion:*** PROPOSE FIX
* ***Justification:*** Document the exact transaction script to ensure safe, idempotent migration.
* ***Proposed Edit:***
  * Location: Section "Detailed Implementation Plan", Target File 5
  * Change: Include atomic SQL block:
    ```sql
    PRAGMA foreign_keys = OFF;
    BEGIN TRANSACTION;
    UPDATE ponto SET id = 'ciiagro:' || id WHERE id NOT LIKE '%:%';
    UPDATE fato SET ponto_id = 'ciiagro:' || ponto_id WHERE ponto_id NOT LIKE '%:%';
    COMMIT;
    PRAGMA foreign_keys = ON;
    ```

### 3. [CRITIC-DESIGN-02] [`egm-design`] - Severity: Medium
* **Affected Scope:** Non-Functional Requirements & `fontes/inmet.py`
* **Discrepancy Description:** Lacks explicit socket timeout on INMET HTTP requests, risking silent hanging on severed connections.
* **Rationale:** Government APIs often stall without closing sockets.
* ***AI Suggestion:*** PROPOSE FIX
* ***Justification:*** Standardize `timeout=30` on all `urllib.request.urlopen()` calls.
* ***Proposed Edit:***
  * Location: Non-Functional Requirements and `fontes/inmet.py` specification
  * Change: Mandate explicit `timeout=30` on all HTTP requests.

### 4. [CRITIC-STRUCT-01] [`egm-structural`] - Severity: Medium
* **Affected Scope:** Section "Open Questions"
* **Discrepancy Description:** Open Questions 1 and 2 remain unanswered in the completed design document.
* **Rationale:** Leaving open questions forces the implementer to make ad-hoc architectural decisions.
* ***AI Suggestion:*** PROPOSE FIX
* ***Justification:*** Resolve both questions and remove the section.
* ***Proposed Edit:***
  * Location: Section "Open Questions"
  * Change: Remove Open Questions section and integrate decisions: coordinate binding uses terrestrial agricultural plain coordinates; INMET endpoints use public unauthenticated REST API.

### 5. [CRITIC-STRUCT-02] [`egm-structural`] - Severity: Low
* **Affected Scope:** Section 3.B (NASA POWER Reanalysis Module)
* **Discrepancy Description:** Missing sensor sentinel values (`-999.0`) and metric units not explicitly detailed.
* **Rationale:** Ingesting `-999.0` as precipitation or temperature would catastrophically corrupt climate statistics.
* ***AI Suggestion:*** PROPOSE FIX
* ***Justification:*** Document sentinel mapping: `-999.0` -> `None`.
* ***Proposed Edit:***
  * Location: Section 3.B
  * Change: Document `-999.0` conversion to `None` and units (`PRECTOTCORR` in mm/day, `RH2M` in %).

### 6. [READINESS-02] [`egm-implementation-readiness`] - Severity: Low
* **Affected Scope:** `municipios.py`
* **Discrepancy Description:** INMET station names with auxiliary descriptions may not match canonical names without aliases.
* **Rationale:** Normalization strips accents, but suffixes like `- A711` require stripping.
* ***AI Suggestion:*** PROPOSE FIX
* ***Justification:*** Ensure `municipios.py:resolver()` strips station codes or includes an explicit alias table.
* ***Proposed Edit:***
  * Location: Section "Detailed Implementation Plan", Target Files
  * Change: Add `municipios.py` to target files for alias handling.

### 7. [CODEBASE-01] [`egm-codebase-details`] - Severity: Low
* **Affected Scope:** Target File 8 (`site/check.jsx`)
* **Discrepancy Description:** Lacks assertions for presence and validity of `fonte` and `tipo` in `dados.json`.
* **Rationale:** Headless tests should prevent schema drift on metadata fields.
* ***AI Suggestion:*** PROPOSE FIX
* ***Justification:*** Add assertion requirements to Target File 8.
* ***Proposed Edit:***
  * Location: Section "Detailed Implementation Plan", Target File 8
  * Change: Require assertions that every station in `dados.json` has valid `fonte` and `tipo`.
