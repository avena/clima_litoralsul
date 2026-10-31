"""Fontes de dados climáticos. Cada módulo expõe `FONTE`, `pontos()` e `fatos()`.

`pontos()` devolve o catálogo da fonte; `fatos()` gera observações com `data` em
AAAA-MM-DD ou AAAA-MM. O banco (`coletor.py`) resolve o nome da estação para
`ponto.id`, então a fonte nunca precisa conhecer o banco.

Fontes suportadas:
- `ciiagro`: estações agrometeorológicas do Estado de SP (raspagem HTML)
- `inmet`: estações de superfície automáticas do INMET (API REST)
- `nasa_power`: reanálise meteorológica global (0.5° × 0.5°) para municípios sem estação
"""
from __future__ import annotations

from . import ciiagro, inmet, nasa_power

__all__ = ["ciiagro", "inmet", "nasa_power"]
