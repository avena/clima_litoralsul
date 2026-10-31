# site

## Overview
Web client package and static site configuration for the climatological observatory. Bundles the React application via Vite and Tailwind CSS v4, and provides headless DOM testing against production `dados.json`.

## Interface
- [src](./src/README.md): React source components, dual-axis climatogram SVG visualizer, and entry point.
- `check.jsx`: Node.js SSR verification script rendering `<App dados={dados} />` to string and asserting 31 contract checks without requiring a browser.
- `vite.config.js`: Vite bundling configuration injecting `__COMMIT__`, `__COMMIT_INICIAL__`, and `__BUILD__` build-time metadata.
- `index.html`: Static HTML entry template defining viewport, meta tags, and root mounting node.

## Invariants
- `[check.jsx:checagens]`: All 31 headless SSR assertions must evaluate to true, verifying active station counts, routes, formatting, and absence of `NaN`/`undefined`/`Infinity` in rendered markup.
- `[vite.config.js:define]`: Commit hashes fallback to local `git rev-parse` or `"local"` when CI environment variables (`COMMIT_REF`, `VERCEL_GIT_COMMIT_SHA`) are absent.
- `[package.json:build]`: Static distribution in `site/dist/` copies assets from `site/public/` (`dados.json` and `fichas/*.pdf`) directly to root without rewrites.

## Side Effects
- `[vite.config.js:execSync]`: Executes local `git` CLI queries during bundle compilation.
- `[check.jsx:readFileSync]`: Reads `site/public/dados.json` from the local filesystem during testing.
- `[npm run build]`: Emits static HTML, CSS, JavaScript, and asset bundles to `site/dist/`.

## Verification
Run: `npm --prefix site run check && npm --prefix site run build`
