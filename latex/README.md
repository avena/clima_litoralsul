# latex

## Overview
Automated typesetting generator producing print-ready, single-page A4 reference sheets (fichas climatológicas) in strict monochrome grayscale for extension agents (ATER). Generates LaTeX source code from `dados.json` and compiles reproducible PDFs using `tectonic`.

## Interface
- `compilar(arquivos: list[Path], destino: Path, gerado: str) -> list[Path]`: Compiles `.tex` files to `.pdf` in `destino` using `tectonic`.
- `gerar(dados: dict, destino: Path) -> list[Path]`: Writes 23 `.tex` files to `destino` from structured JSON payload.
- `ficha(est: dict, gerado: str, regiao: list[dict]) -> str`: Produces complete LaTeX document string adhering to single-page A4 geometry and grayscale palette.
- `tex(texto: str) -> str`: Escapes LaTeX control characters and translates UTF-8 dashes/degrees into T1-safe macros.
- `num(valor: float | None, casas: int = 0) -> str`: Formats numeric values to pt-BR standard, rendering missing entries as `---`.
- `main(argv=None) -> int`: Command-line interface accepting `--dados`, `--saida`, `--pdf`, and `--pdf-em`.

## Invariants
- `[gerar.py:compilar]`: Sets environment variable `SOURCE_DATE_EPOCH` to the UTC timestamp of `dados["gerado"]`, ensuring deterministic and byte-identical PDF compilation across repeated runs.
- `[gerar.py:tex]`: Replaces `—` with `\textemdash{}`, `–` with `\textendash{}`, and `°` with `\textdegree{}` to avoid silent glyph dropping or slot corruption (`¤`) in 8-bit `ec-lmr` fonts under XeTeX/tectonic.
- `[gerar.py:\kpicard]`: Card geometry is constrained to `\dimexpr0.32\textwidth-2\fboxsep-2\fboxrule\relax`, ensuring three indicator cards and two `\hfill` spaces fit horizontally on a single line.
- `[gerar.py:ficha]`: Palette is strictly limited to the `xcolor` `gray` scale (0.15 for bars, 0.75 for borders, 0.98 for card backgrounds, 0.94 for warnings, 0.35 for captions), ensuring full legibility when printed on monochrome laser toner.

## Side Effects
- `[gerar.py:write_text]`: Writes 23 station `.tex` files into `latex/fichas/`.
- `[gerar.py:subprocess.run]`: Spawns external `tectonic` compiler to write 23 binary PDF documents to `site/public/fichas/`.

## Verification
Run: `python3 latex/gerar.py --pdf`
