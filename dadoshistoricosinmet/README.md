# dadoshistoricosinmet

Submódulo de ingestão, análise e consolidação dos **Dados Históricos Anuais do INMET** disponibilizados em lote pelo Instituto Nacional de Meteorologia.

- **URL de Origem**: [https://portal.inmet.gov.br/dadoshistoricos](https://portal.inmet.gov.br/dadoshistoricos)
- **Formato na fonte**: Arquivos compactados anuais (`2000.zip` até `2026.zip`), cada um contendo os CSVs horários de todas as estações meteorológicas automáticas do Brasil daquele ano.

---

## 1. Ideia e Objetivo

Enquanto a API online do INMET (`apitempo.inmet.gov.br`) exige chave/token pessoal e responde `204 No Content` para intervalos históricos longos sem credencial, o portal **dadoshistoricos** fornece o arquivo anual público consolidado com todas as medições de 1º de janeiro a 31 de dezembro.

O objetivo deste módulo é:
1. Baixar os arquivos anuais `.zip` sob demanda com cache local em `zips/` (ignorado pelo git).
2. Ler e processar os CSVs das estações em streaming diretamente da memória (via `zipfile`), sem descompactar gigabytes de dados no disco.
3. Consolidar os dados horários em médias e totais diários e mensais.
4. Armazenar em banco SQLite estruturado (`inmet_historico.sqlite`) e exportar JSON (`inmet_regional.json`) para consumo em painéis e visualizações web.

---

## 2. Análise da Amostra Estatística de Anos

Para validar a consistência da estrutura de dados ao longo do tempo sem necessidade de baixar todos os 27 anos de uma vez, foi selecionada uma **amostra estatística representativa de três eras**:
- **2008**: Início da expansão das estações automáticas no Vale do Ribeira e Litoral Sul (ativação de Iguape A712 e Barra do Turvo A746).
- **2018**: Era intermediária consolidada (ativação de Registro A766).
- **2023**: Era contemporânea recente.

### Resultados da Inspeção dos ZIPs e CSVs:

| Característica | 2008 | 2018 | 2023 |
|---|---|---|---|
| **Tamanho do ZIP** | 72.4 MB (418 arquivos) | 112.4 MB (597 arquivos) | 102.1 MB (567 arquivos) |
| **Pasta interna no ZIP** | Subpasta `2008/` | Subpasta `2018/` | Raiz do ZIP |
| **Padrão de Nome do CSV** | `INMET_SE_SP_{COD}_{NOME}_{INI}_A_{FIM}.CSV` | Idêntico | Idêntico |
| **Encoding** | `latin-1` (ISO-8859-1) | `latin-1` | `latin-1` |
| **Separador de campo** | Ponto e vírgula (`;`) | Ponto e vírgula (`;`) | Ponto e vírgula (`;`) |
| **Separador decimal** | Vírgula (`,`) | Vírgula (`,`) | Vírgula (`,`) |
| **Linhas de Metadados** | Linhas 1 a 8 | Linhas 1 a 8 | Linhas 1 a 8 |
| **Linha de Cabeçalho** | Linha 9 (20 colunas) | Linha 9 (20 colunas) | Linha 9 (20 colunas) |
| **Início dos Dados** | Linha 10 (horários) | Linha 10 (horários) | Linha 10 (horários) |
| **Formato da Data** | `AAAA-MM-DD` | `AAAA-MM-DD` | `AAAA/MM/DD` (normalizado p/ hífen) |
| **Formato da Hora** | `HH:MM` | `HH:MM` | `HHMM UTC` |
| **Sentinela de Ausência** | `-9999` | `-9999` | `-9999` ou campo vazio (`;;`) |

**Conclusão**: A estrutura interna do INMET permaneceu estável por mais de 15 anos. As variações observadas (formato de barra na data e presença de pasta raiz) foram integralmente tratadas no parser unificado.

---

## 3. Estações Mapeadas na Região

- **A712 - Iguape**: Latitude -24.6716, Longitude -47.5458, Altitude 2.7m (ativa desde 2006).
- **A746 - Barra do Turvo**: Latitude -24.9627, Longitude -48.4163, Altitude 659.9m (ativa desde 2008).
- **A766 - Registro**: Latitude -24.5330, Longitude -47.8641, Altitude 35.0m (ativa desde 2017).

---

## 4. Como Usar

### Processar anos em cache ou específicos:
```bash
# Processa a amostra estatística padrão (2008, 2018, 2023):
python3 dadoshistoricosinmet/processar.py

# Processa um ano avulso (baixa o zip se necessário):
python3 dadoshistoricosinmet/processar.py --ano 2024

# Processa uma lista de anos:
python3 dadoshistoricosinmet/processar.py --anos 2015,2016,2017,2018,2019,2020

# Processa todas as estações do Brasil (não apenas as regionais):
python3 dadoshistoricosinmet/processar.py --ano 2023 --todas-estacoes
```

### Arquivos Gerados:
- `dadoshistoricosinmet/inmet_historico.sqlite`: Banco SQLite com tabelas `inmet_estacao`, `inmet_diario` e `inmet_mensal`.
- `dadoshistoricosinmet/inmet_regional.json`: JSON estruturado contendo as séries consolidadas para visualização em dashboards web.
