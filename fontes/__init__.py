"""Fontes de dados climáticos. Cada módulo expõe `FONTE`, `pontos()` e `fatos()`.

`pontos()` devolve o catálogo da fonte; `fatos()` gera observações com `data` em
AAAA-MM-DD ou AAAA-MM. O banco (`coletor.py`) resolve o nome da estação para
`ponto.id`, então a fonte nunca precisa conhecer o banco.

Hoje só `ciiagro`. INMET e NASA POWER entram depois da auditoria — ver PLANO.md.
"""
