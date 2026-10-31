# Fontes Meteorológicas e Ingestão de Dados

Módulos de extração e ingestão com segregação estrita de proveniência (estações físicas de superfície vs. reanálise atmosférica global). Sem dependências externas de rede ou banco de dados (Python 3.12 stdlib estrito).

---

## Guia de Conferência das Fontes

Abaixo estão registradas todas as origens, endpoints, a natureza de cada uma (se é Página Web raspada ou API REST estruturada em JSON) e como conferir diretamente.

| Fonte | Natureza | Formato | Autenticação | Onde conferir / URL base |
|---|---|---|---|---|
| **CIIAGRO** (IAC) | **Página Web** (HTML) | HTML com scripts `addRows` | Nenhuma (aberto) | `http://www.ciiagro.org.br/cbhrb/estacoes/` |
| **NASA POWER** | **API REST Oficial** | JSON estruturado | Nenhuma (aberto, público) | `https://power.larc.nasa.gov/api/temporal/daily/point` |
| **INMET** | **API REST + Arquivo** | JSON / CSV compactado | Token p/ API de medição; Aberto p/ catálogo e downloads anuais | `https://apitempo.inmet.gov.br/estacoes/T` e `https://portal.inmet.gov.br/dadoshistoricos` |

---

### 1. CIIAGRO (`fontes/ciiagro.py`)
- **É Página Web ou API?** **PÁGINA WEB (HTML)**. O CIIAGRO não fornece API pública. Os dados são extraídos raspando as páginas geradas pelo servidor PHP e interceptando blocos JavaScript `data.addRows(...)` via expressões regulares.
- **URLs de conferência no navegador**:
  - Catálogo georreferenciado e mapa: [http://www.ciiagro.org.br/cbhrb/estacoes/](http://www.ciiagro.org.br/cbhrb/estacoes/)
  - Relação de estações e códigos: [http://www.ciiagro.org.br/cbhrb/estacoes/diario/periodo](http://www.ciiagro.org.br/cbhrb/estacoes/diario/periodo)
  - Calendário e datas de fundação: [http://www.ciiagro.org.br/cbhrb/estacoes/calendario](http://www.ciiagro.org.br/cbhrb/estacoes/calendario)
- **Como testar via terminal (`curl`)**:
  ```bash
  # Consulta a matriz mensal de Outubro/2026:
  curl -X POST -d "parametro=10/2026" http://www.ciiagro.org.br/cbhrb/estacoes/mensal/cmensal
  ```

---

### 2. NASA POWER (`fontes/nasa_power.py`)
- **É Página Web ou API?** **API REST OFICIAL (JSON)**. Serviço público da NASA Langley Research Center alimentado pelo modelo de reanálise atmosférica global MERRA-2 e satélites do projeto CERES.
- **Resolução e escopo**: Grade regular de 0.5° × 0.5° (~55 km). Utilizada estritamente para cobrir os 4 municípios litorâneos sem estação física de superfície (Itanhaém, Mongaguá, Peruíbe e Ilha Comprida).
- **Como conferir no navegador**:
  Abra no navegador ou chame via `curl` a consulta direta do ponto de Itanhaém (`lat=-24.18`, `lon=-46.79`):
  [https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M,T2M_MAX,T2M_MIN,RH2M,PRECTOTCORR&community=AG&longitude=-46.79&latitude=-24.18&start=20240101&end=20240105&format=JSON](https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M,T2M_MAX,T2M_MIN,RH2M,PRECTOTCORR&community=AG&longitude=-46.79&latitude=-24.18&start=20240101&end=20240105&format=JSON)
- **Como testar via terminal (`curl`)**:
  ```bash
  curl "https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M,T2M_MAX,T2M_MIN,RH2M,PRECTOTCORR&community=AG&longitude=-46.79&latitude=-24.18&start=20240101&end=20240105&format=JSON"
  ```
- **Pontos e Coordenadas Terrestres Fixadas**:
  - Itanhaém (`nasa:itanhaem`): `-24.18, -46.79`
  - Mongaguá (`nasa:mongagua`): `-24.09, -46.62`
  - Peruíbe (`nasa:peruibe`): `-24.32, -47.00`
  - Ilha Comprida (`nasa:ilha-comprida`): `-24.74, -47.54`

---

### 3. INMET (`fontes/inmet.py`)
- **É Página Web ou API?** **API REST OFICIAL (JSON)** + portal de arquivos anuais em lote (CSV/ZIP).
- **Catálogo de Estações Automáticas (aberto e público)**:
  - URL no navegador: [https://apitempo.inmet.gov.br/estacoes/T](https://apitempo.inmet.gov.br/estacoes/T)
  - Retorna um array JSON com todas as estações do território nacional (incluindo Iguape A712, Barra do Turvo A746 e Registro A766).
- **Série de Medições da API**:
  - Endpoint: `https://apitempo.inmet.gov.br/token/estacao/{inicio}/{fim}/{codigo}/{token}`
  - Nota de autenticação: Para consultas pontuais de medições horárias via API, o INMET passou a exigir chave de acesso (`INMET_TOKEN`), cadastrada gratuitamente no portal [https://portal.inmet.gov.br](https://portal.inmet.gov.br). A variável de ambiente `INMET_TOKEN` é lida automaticamente pelo coletor.
- **Séries Históricas em Lote (aberto)**:
  - Portal de dados históricos: [https://portal.inmet.gov.br/dadoshistoricos](https://portal.inmet.gov.br/dadoshistoricos) (arquivos ZIP anuais contendo todas as leituras de todas as estações).
- **Estações mapeadas no território**:
  - `inmet:A712`: Iguape (`-24.6716, -47.5458`)
  - `inmet:A746`: Barra do Turvo (`-24.9627, -48.4163`)
  - `inmet:A766`: Registro (`-24.5330, -47.8641`)

---

## Contrato de Interface dos Módulos Python

Todo módulo em `fontes/*.py` implementa:
1. `FONTE: str` (ex.: `"ciiagro"`, `"nasa_power"`, `"inmet"`).
2. `pontos() -> list[dict]`: Retorna a lista de pontos com identificador prefixado, nome, município, coordenadas e `tipo` (`"estacao"` ou `"reanalise"`).
3. `fatos(desde: str, ate: str, diario: bool = False) -> Iterator[dict]`: Gerador que emite dicionários de dados canônicos (`tmin`, `tmed`, `tmax`, `urmin`, `urmed`, `urmax`, `chuva`).

## Invariantes Garantidos
- **Desacoplamento**: Nenhum arquivo em `fontes/` importa `sqlite3` ou acessa o banco de dados.
- **Segregação Estrita**: Dados de reanálise são isolados de medições de superfície. Sentinelas de erro/ausência (como `-999.0` da NASA ou `-9999` do INMET) são convertidos em `None`.
