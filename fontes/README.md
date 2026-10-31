# fontes

## Overview
Módulos de extração e ingestão climática com segregação de proveniência (estações de superfície vs. reanálise). Sem dependência de banco de dados ou bibliotecas externas (Python stdlib estrito).

## Fontes Suportadas
- `fontes/ciiagro.py`: Raspagem regex de dados do CIIAGRO/IAC (`http://www.ciiagro.org.br`) via endpoints HTML e blocos `addRows`.
- `fontes/inmet.py`: Estações automáticas de superfície do INMET (`https://apitempo.inmet.gov.br`) via API REST pública e agregação horária para diária/mensal (suporta `INMET_TOKEN`).
- `fontes/nasa_power.py`: Reanálise meteorológica global da NASA POWER (`https://power.larc.nasa.gov`) em grade 0.5° × 0.5° para municípios costeiros sem estação física de superfície (sentinela `-999.0` mapeado para `None`).

## Interface Canônica
Cada módulo de fonte expõe:
- `FONTE: str`: Identificador único (`"ciiagro"`, `"inmet"`, `"nasa_power"`).
- `pontos() -> list[dict]`: Catálogo de pontos com `id`, `nome`, `municipio`, `lat`, `lon`, `inicio_auto` e `tipo` (`"estacao"` ou `"reanalise"`).
- `fatos(desde: str, ate: str, diario: bool = False) -> Iterator[dict]`: Gerador de observações climáticas com métricas canônicas (`tmin`, `tmed`, `tmax`, `urmin`, `urmed`, `urmax`, `chuva`).

## Invariants
- `[fatos]`: Valores ausentes são sempre `None`, nunca `0`. O `0` é estritamente reservado para medição nula real (ex.: chuva 0.0 mm).
- `[nasa_power]`: Pontos virtuais recebem `tipo = "reanalise"`, preservando segregação estrita sem interpolação sintética com estações físicas.
- `[desacoplamento]`: Nenhum módulo de fonte importa `sqlite3` nem acessa o banco de dados.

## Verification
Run: `python3 -m unittest tests.test_ciiagro tests.test_inmet tests.test_nasa_power`
