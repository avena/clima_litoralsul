# EGM Drift Report (2026-10-30)

## README.md

- `coletor.py`: A assinatura documentada `coletar(conn, desde, ate, diario, pausa)` inclui o parâmetro `pausa`, mas a implementação real em `coletor.py` é `coletar(conn: sqlite3.Connection, desde: str, ate: str, diario: bool) -> None`. O controle de cadência de rede é interno via constante `PAUSA = 0.25` em `fontes/ciiagro.py`.
- `relatorio.py`: As funções públicas `normal(ag, validada) -> bool`, `slug(nome) -> str`, `janela_seca(pm, seco, limite) -> list[str]` e `inicio_das_chuvas(...)` existem no código mas foram omitidas da listagem de interface do blueprint.
- `municipios.py`: A função auxiliar pública `normalizar(nome: str) -> str` está presente no módulo mas não foi listada na interface.

## site/README.md

No drift detected.

## site/src/README.md

No drift detected.

## fontes/README.md

- Comando de verificação: O comando documentado `python3 -m unittest tests.test_ciiagro.TestExtrator tests.test_ciiagro.TestPeriodo` falha com `AttributeError`. As classes reais em `tests/test_ciiagro.py` são `TestExtracao` e `TestPeriodos`.
- `fontes/ciiagro.py:pontos`: A docstring da função no código-fonte ainda faz referência legada a "quando for dos 17", divergindo do catálogo expandido de 25 municípios em `municipios.csv`.

## latex/README.md

No drift detected.
