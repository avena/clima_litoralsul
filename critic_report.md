# Stage 7: Critic Review Report

**Target Document:** `.planning/designs/inmet-nasa-power.md`  
**Review Target:** FeatureRange (lines 1–198)  
**Reviewers:** `egm-design`, `egm-structural`, `egm-style`  
**Date:** 2026-10-30  

---

## 1. Design & Engineering Findings (`egm-design`)

### 🔴 Blocker / Major

* **CRITIC-DESIGN-01: Grid Point Placement Risk for NASA POWER (Offshore or Plateau Bias)**
  * *Observation*: Section 3.B specifies municipal centroid coordinates (`lat = -24.7400, lon = -47.5400` for Ilha Comprida, `lat = -24.0900, lon = -46.6200` for Mongaguá). Given NASA POWER's 0.5° (~55 km) grid cell size, arbitrary centroid placement on narrow coastal strips risks sampling oceanic sea-surface data or high-altitude Serra do Mar plateau cells rather than the coastal plain.
  * *Required Mitigation*: The specification must mandate that the coordinate pairs are verified against land-sea masks and explicitly locked to the terrestrial agricultural zone of the municipality.

* **CRITIC-DESIGN-02: Network Timeout and Silent Freeze Prevention for INMET API**
  * *Observation*: Section "Non-Functional Requirements" specifies polite pacing (`PAUSA = 0.25s`) and exponential backoff on `OSError`, but omits explicit per-request socket timeouts. The government INMET API can hang indefinitely on broken connections without throwing `OSError`.
  * *Required Mitigation*: Mandate an explicit `timeout=30` (or `60`) on all `urllib.request.urlopen()` calls to prevent unhandled pipeline hangs during historical collection sweeps.

---

## 2. Structural & Traceability Findings (`egm-structural`)

### 🟡 Major / Minor

* **CRITIC-STRUCT-01: Unresolved Open Questions Remaining in Specification**
  * *Observation*: Section "Open Questions" contains two questions (coordinate binding criteria and INMET authentication constraints) that were discussed but not formally decided within the architecture text.
  * *Required Mitigation*: Resolve both questions within the document:
    1. Confirm coordinate binding uses verified terrestrial coordinates.
    2. Document that INMET REST endpoints are public and unauthenticated, noting that bulk downloads use public station query paths. Remove the open questions once answered.

* **CRITIC-STRUCT-02: Units and Dimension Validation for NASA POWER Metrics**
  * *Observation*: Parameter mapping references `PRECTOTCORR` -> `chuva` and `RH2M` -> `urmed`, but does not document expected units or scale factors.
  * *Required Mitigation*: Add explicit verification that `PRECTOTCORR` is delivered in mm/day (matching project schema) and `RH2M` is in percentage (0–100%), with missing/invalid values (`-999.0` in NASA POWER) strictly converted to `None`.

---

## 3. Style & Tone Review (`egm-style`)

* **CRITIC-STYLE-01: Plain-English Compliance**
  * *Observation*: The text adheres to the plain-English standard, avoiding promotional jargon, empty adjectives, and marketing buzzwords.
  * *Status*: **Pass**.

---

## Summary of Critic Findings

| Finding ID | Reviewer | Severity | Description |
|---|---|---|---|
| `CRITIC-DESIGN-01` | `egm-design` | 🔴 Major | Land-mask verification for coastal NASA POWER grid coordinates |
| `CRITIC-DESIGN-02` | `egm-design` | 🟡 Major | Explicit socket timeout on INMET HTTP requests |
| `CRITIC-STRUCT-01` | `egm-structural` | 🟡 Major | Formal resolution and removal of Open Questions |
| `CRITIC-STRUCT-02` | `egm-structural` | 🟢 Nit | NASA POWER `-999.0` sentinel to `None` and unit validation |
