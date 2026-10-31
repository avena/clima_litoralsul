# Stage 9: Implementation Readiness Test Report

**Target Document:** `.planning/designs/inmet-nasa-power.md`  
**Review Target:** DetailedRange (lines 199–275)  
**Reviewers:** `egm-implementation-readiness`, `egm-codebase-details`, `egm-style`  
**Date:** 2026-10-30  

---

## 1. Implementation Readiness Findings (`egm-implementation-readiness`)

### 🔴 Major Finding

* **READINESS-01: Explicit SQL Migration for Primary/Foreign Key Namespacing**
  * *Observation*: Target file 5 (`coletor.py`) specifies migrating `ponto.id` from numeric IDs (`63`) to namespaced IDs (`ciiagro:63`). Because `fato.ponto_id` has a foreign key constraint referencing `ponto(id)`, an unprepared `UPDATE` will trigger SQLite constraint violations or leave orphaned rows.
  * *Actionable Remedy*: The plan must specify the atomic migration transaction:
    ```sql
    PRAGMA foreign_keys = OFF;
    BEGIN TRANSACTION;
    UPDATE ponto SET id = 'ciiagro:' || id WHERE id NOT LIKE '%:%';
    UPDATE fato SET ponto_id = 'ciiagro:' || ponto_id WHERE ponto_id NOT LIKE '%:%';
    COMMIT;
    PRAGMA foreign_keys = ON;
    ```
    This ensures zero ambiguity and prevents database corruption during the transition.

### 🟡 Minor Finding

* **READINESS-02: Alias Resolution in `municipios.py` for INMET Station Headers**
  * *Observation*: INMET API payloads return station names in uppercase strings (e.g. `"ITANHAEM"` or `"IGUAPE"`). While `municipios.normalizar()` handles diacritics and case, auxiliary text such as `"ITANHAEM - A711"` or `"IGUAPE (AEROPORTO)"` may appear in catalogue responses.
  * *Actionable Remedy*: Explicitly note in `municipios.py` scope whether direct alias mapping is needed in `municipios.py:resolver()` for incoming INMET station naming variants.

---

## 2. Codebase Details & Verification Alignment (`egm-codebase-details`)

### 🟢 Nits & Confirmations

* **CODEBASE-01: SPA Schema Integrity in `site/check.jsx`**
  * *Observation*: The plan updates `site/check.jsx` for the increased station count (27+).
  * *Recommendation*: Add an explicit assertion in `check.jsx` verifying that every station entry in `dados.json` possesses a non-empty `fonte` string and a valid `tipo` value (`"estacao"` or `"reanalise"`).

* **CODEBASE-02: Verification Harness Alignment**
  * *Observation*: All verification commands (`python3 -m unittest discover -s tests`, `npm --prefix site run check`, `npm --prefix site run build`, `python3 latex/gerar.py --pdf`) strictly mirror existing CI and `deploy.sh` commands.
  * *Status*: **Pass**.

---

## 3. Implementation Readiness Verdict

| Finding ID | Reviewer | Severity | Status |
|---|---|---|---|
| `READINESS-01` | `egm-implementation-readiness` | 🔴 Major | Requires atomic migration script definition |
| `READINESS-02` | `egm-implementation-readiness` | 🟡 Minor | Verify name alias handling in `municipios.py` |
| `CODEBASE-01` | `egm-codebase-details` | 🟢 Nit | Add `fonte`/`tipo` schema assertions to `check.jsx` |

* **Overall Verdict:** **Ready with minor amendments**. The file breakdown, rationale, and verification layers provide a concrete, executable roadmap for implementation.
