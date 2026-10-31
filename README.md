# clima_litoralsul Blueprint

Série climática dos **25 municípios do Litoral Sul Paulista e Vale do Ribeira**
(Litoral Sul, Vale do Ribeira e Alto Vale/Cabeceiras), integrando estações de superfície do
[CIIAGRO](http://www.ciiagro.org.br) e [INMET](https://portal.inmet.gov.br), e reanálise meteorológica global segregada via [NASA POWER](https://power.larc.nasa.gov).

Coleta em **Python 3.12 só com stdlib** (`urllib`, `sqlite3`, `re`, `json`,
`unittest`). O painel é um **SPA React + Tailwind v4** em `site/`, buildado com
Vite. Sem banco externo, sem servidor de aplicação, sem CDN em runtime.

## System Overview

O projeto opera como uma esteira unidirecional desacoplada de dados climáticos:

```
Fontes Meteorológicas
├── CIIAGRO (HTML)       ──► fontes/ciiagro.py (urllib + regex) ──┐
├── INMET (API REST)     ──► fontes/inmet.py (JSON / estações)  ──┼──► coletor.py: schema, upsert, consolidação
└── NASA POWER (API)     ──► fontes/nasa_power.py (reanálise)   ──┘        │
                                                                           ▼
                                                                  dados/clima.sqlite
                                                                           │ relatorio.py: agregação + faixa de sanidade
                                                                           ▼
                                                                  site/public/dados.json (versionado para deploy)
                                                                  ├── site/ (Vite + React)  ──► dashboard web estático
                                                                  └── latex/gerar.py (tectonic) ──► fichas A4 PDF (27 fichas)
```

## Local Interface & Invariants

### Scripts e Módulos Raiz
- `coletor.py`: CLI de coleta e gestão do banco de dados SQLite (`dados/clima.sqlite`).
  - Suporta a flag `--fonte {todas,ciiagro,inmet,nasa_power}` em `catalogo` e `coletar`.
  - `abrir(caminho) -> sqlite3.Connection`: Inicializa SQLite com schema multi-fonte e row factory.
  - `catalogo(conn, fonte)`: Sincroniza os 25 municípios de `municipios.csv` e vincula as estações físicas e pontos de reanálise com namespacing (`ciiagro:`, `inmet:`, `nasa:`).
  - `coletar(conn, desde, ate, diario, fonte)`: Coleta série mensal ou diária com rate-limiting interno (`PAUSA`).
  - `substituir_granularidade(conn, pontos_meses, diario)`: Remove granularidade oposta para cada mês.
  - `atualizar_primeiro_fato(conn)`: Recalcula a menor data de registro por estação.
  - `auditar(conn)`: Inspeciona cobertura temporal e desvios de sanidade multi-fonte sem escrever no banco.
- `relatorio.py`: Agregação estatística e geração de `site/public/dados.json`.
  - `exportar(conn) -> dict`: Agrupa estações pelas 3 regiões canônicas e calcula métricas sazonais, preservando proveniência e avisos de reanálise.
  - `escrever(conn, destino) -> Path`: Serializa `dados.json`.
  - `agregado(conn, ponto_id)`: Aplica faixas de sanidade (`LIMITES`) e computa médias mensais.
  - `resumo(ag)`: Calcula total anual, extremos de precipitação e distribuição sazonal (DJF, MAM, JJA, SON).
  - `solsticios(meses, chuva_ano)`: Calcula acumulados que antecedem os solstícios de inverno e verão.
  - `uso_local(dados)`: Gera diagnósticos agronômicos locais para preparo de solo, calagem e plantio.
  - `janela_seca(pm, seco, limite)` / `inicio_das_chuvas(...)`: Detecta meses secos e retorno das precipitações.
  - `rotulo(ag, validada)` / `normal(ag, validada)`: Assegura honestidade metodológica (restringe "normal climatológica" a séries válidas ≥ 30 anos).
  - `slug(nome)`: Converte nomes de estações e municípios em identificadores de URL amigáveis.
- `municipios.py`: Resolução de nomes e mapeamento regional dos 25 municípios.
  - `todos() -> tuple[dict[str, str], ...]`: Retorna a lista dos 25 municípios na ordem do CSV.
  - `regioes() -> tuple[str, ...]`: Retorna as 3 regiões canônicas (`Litoral Sul`, `Vale do Ribeira`, `Alto Vale e Cabeceiras`).
  - `resolver(nome_estacao: str) -> str | None`: Normaliza nomes com sufixos institucionais para municípios canônicos.
  - `normalizar(nome: str) -> str`: Remove acentos, hífens e formata em minúsculas para correspondência.
- `deploy.sh`: Pipeline de publicação que executa geração de PDFs, `relatorio.py`, testes unitários, checagens do SPA e build do Vite.
- `start.sh`: Servidor estático local em porta livre (0.0.0.0).

## Subdirectories & System Boundaries

- [fontes](./fontes/README.md): Módulos extratores de rede (CIIAGRO, INMET, NASA POWER) sem dependência de banco de dados nem bibliotecas externas.
- [latex](./latex/README.md): Gerador de código LaTeX e compilador tectonic de fichas A4 monocromáticas de página única com notas de proveniência.
- [site](./site/README.md): Aplicação cliente SPA em React, Tailwind CSS v4, e harness de verificação headless DOM SSR.

## Global Invariants

1. **Granularidade em `data`**: `length(data)` define a granularidade (`AAAA-MM-DD` = 10 para dias, `AAAA-MM` = 7 para meses). Um mês possui exclusivamente o registro mensal ou os registros diários (`substituir_granularidade`), evitando dupla contagem em agregações.
2. **Ausente é `NULL`, nunca `0`**: Leituras não registradas ou sensores inoperantes são gravados como `NULL`. Sentinelas de APIs (ex.: `-999.0` da NASA POWER) são convertidos para `None`. O valor `0` é estritamente restrito a medições físicas de fato nulas (ex.: chuva 0.0 mm).
3. **Segregação Estrita de Reanálise**: Dados de reanálise meteorológica global (NASA POWER) cobrem os municípios costeiros sem estação física de superfície (Itanhaém, Mongaguá, Peruíbe, Ilha Comprida), marcados com `tipo = "reanalise"`. Não há interpolação sintética, mesclagem estatística ou médias compostas entre reanálise e medições físicas de superfície. O painel e as fichas exibem avisos e badges de proveniência explícitos.
4. **Desacoplamento Fonte-Banco**: O módulo `fontes/` desconhece SQLite; retorna apenas dicionários canônicos de pontos e observações. O banco resolve vínculos e persistência no coletor.
5. **Honestidade Estatística**: Nenhuma série com menos de 30 anos completos ou anterior à automação sem validação formal recebe o título de "normal climatológica".
6. **Determinismo de Artefatos**: A compilação de PDFs fixa `SOURCE_DATE_EPOCH` na data de `dados.json`, gerando binários idênticos e evitando diffs falsos no repositório.

## Global Side Effects

- **Persistência SQLite**: `dados/clima.sqlite` armazena pontos, municípios e fatos climáticos.
- **Requisições de Rede**: Chamadas HTTP para `http://www.ciiagro.org.br`, `https://apitempo.inmet.gov.br` e `https://power.larc.nasa.gov` durante `catalogo` e `coletar`.
- **Geração de Arquivos**: Produz `site/public/dados.json`, `latex/fichas/*.tex`, `site/public/fichas/*.pdf` e `site/dist/`.
- **Publicação Git**: O script `deploy.sh` adiciona os arquivos gerados versionados e dispara o deploy remoto.

## System Verification

- Testes unitários do pipeline Python (39 testes):
  ```bash
  python3 -m unittest discover -s tests
  ```
- Verificação de renderização do SPA e contratos DOM:
  ```bash
  npm --prefix site run check
  ```
- Build de produção do cliente web:
  ```bash
  npm --prefix site run build
  ```
- Compilação e validação de páginas das fichas PDF:
  ```bash
  python3 latex/gerar.py --pdf
  ```

---

## Guia de Operação e Uso

### Coleta e Atualização de Dados

```bash
# Sincroniza catálogo de municípios e pontos de todas as fontes (ou use --fonte ciiagro/inmet/nasa_power)
python3 coletor.py catalogo

# Coleta série histórica mensal (todas as fontes ou fonte específica)
python3 coletor.py coletar --desde 2000-01 --ate 2026-10
python3 coletor.py coletar --fonte nasa_power --desde 1995-01 --ate 2026-10

# Inspeciona cobertura, desvios e valores suspeitos
python3 coletor.py auditar

# Agrega métricas e gera site/public/dados.json
python3 relatorio.py
```

### Visualização Local

```bash
./start.sh        # export + build + http.server em porta livre
./start.sh --dev  # Vite dev com hot reload
```

### Deploy (Netlify ou Vercel)

Build estático, sem backend. `dados.json` é **versionado** justamente porque o
deploy não tem acesso ao banco (que é gitignorado):

```bash
./deploy.sh
```

### Fichas em PDF (uma página por estação/ponto)

```bash
python3 latex/gerar.py --pdf                      # .tex + PDF em site/public/fichas/
tectonic -X compile latex/fichas/registro.tex     # compilação avulsa
```

Cada ficha cabe em **uma folha A4** e é **preto e branco estrito**: paleta na
escala `gray` do `xcolor` (barras `gray 0.15`, contorno `gray 0.75`, fundo de
cartão `gray 0.98`, caixa de aviso `gray 0.94`, texto secundário `gray 0.35`).

### Cobertura Integral (27 estações/pontos ativos, 25 municípios)

- **Litoral Sul (8 municípios, 8 estações/pontos)**: Cananéia, Iguape, Itariri, Pedro de Toledo (CIIAGRO) + Ilha Comprida, Itanhaém, Mongaguá, Peruíbe (NASA POWER Reanálise).
- **Vale do Ribeira (9 municípios, 11 estações)**: Barra do Turvo, Cajati, Eldorado, Jacupiranga, Juquiá, Miracatu, Pariquera-Açu (2 estações: CIIAGRO 298 e 299), Registro (2 estações: CIIAGRO 108 e 109 Unesp), Sete Barras.
- **Alto Vale e Cabeceiras (8 municípios, 8 estações)**: Apiaí, Barra do Chapéu, Iporanga, Itaóca, Itapirapuã Paulista, Juquitiba, Ribeira, Tapiraí.
