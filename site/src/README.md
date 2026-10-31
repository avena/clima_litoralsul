# site/src

## Overview
React SPA presentation layer for the climatological observatory of Litoral Sul Paulista and Vale do Ribeira. Renders station cards, dual-axis SVG climatograms, seasonal metrics, solstice accumulations, and agronomic management advisories directly from static `dados.json`.

## Interface
- `App({ dados })`: Root dashboard React component with hash-based routing (`#/slug`), region grouping, and KPI cards.
- `Climatograma({ meses, foco, setFoco, fixo, setFixo, rotular })`: Pure SVG dual-axis chart (monthly precipitation bars on left y-axis, temperature range and lines on right y-axis).
- `iniciar()` in `main.jsx`: Application bootstrap; fetches `${import.meta.env.BASE_URL}dados.json` and mounts React DOM tree to `#root`.
- `anosFechados(n)` in `App.jsx`: Formats completed 12-month series counts for station listing labels.

## Invariants
- `[Climatograma.jsx:mes]`: Fixed month selection (`fixo`) via click overrides hover focus (`foco`); mouseout events do not clear a fixed month.
- `[Climatograma.jsx:rotular]`: Selecting a series in the legend activates numeric value labels for that series without hiding or mutating the geometric paths of the remaining three series.
- `[App.jsx:slug]`: Hash routing targets the unique station slug (`e.slug`) rather than the municipality slug, enabling multi-station navigation in municipalities with multiple sensors (e.g. `registro` vs `registro-unesp`).
- `[App.jsx:semEstacao]`: Municipalities lacking active CIIAGRO stations are retained in the listing as disabled visual markers (`aria-disabled="true"`) to prevent conflating missing data with non-existence.
- `[main.jsx:iniciar]`: A failed fetch for `dados.json` renders a descriptive inline message instructing the user to run `python3 relatorio.py`.

## Side Effects
- `[main.jsx:fetch]`: Network HTTP GET request to `${import.meta.env.BASE_URL}dados.json` at client startup.
- `[main.jsx:createRoot]`: Mounts React DOM tree to DOM element with ID `root`.
- `[App.jsx:window.location.hash]`: Subscribes to and mutates browser URL hash via `hashchange` events.

## Verification
Run: `npm --prefix site run check`
