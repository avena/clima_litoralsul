# dadoshistoricosinmet

Ingestão, consolidação e relatório dos **Dados Históricos Anuais do INMET**
disponibilizados em lote pelo Instituto Nacional de Meteorologia.

- **Série**: [portal.inmet.gov.br/dadoshistoricos](https://portal.inmet.gov.br/dadoshistoricos)
- **Catálogo**: [apitempo.inmet.gov.br/estacoes/T](https://apitempo.inmet.gov.br/estacoes/T)
- **Formato na fonte**: arquivos anuais (`2000.zip` até `2026.zip`), cada um com
  os CSVs horários de todas as estações automáticas do Brasil naquele ano.

---

## 1. Objetivo

A API online (`apitempo.inmet.gov.br`) exige token e não devolve série longa sem
credencial. O portal `dadoshistoricos` publica o arquivo anual público com todas
as medições de 1º de janeiro a 31 de dezembro.

O módulo:

1. Baixa os ZIPs anuais com cache local em `zips/` (ignorado pelo git).
2. Lê os CSVs **em memória** (`zipfile`), sem descompactar gigabytes no disco.
3. Agrega as leituras horárias em **mensal** e **anual** (o diário não é
   armazenado).
4. Consolida normal mensal, resumo por estação e exporta os JSONs do painel.

O universo é a **união dos códigos presentes nos arquivos** (705 estações com
série), não os 669 do catálogo da API — o catálogo só acrescenta estações sem
série histórica ao seletor.

---

## 2. Análise da Amostra Estatística de Anos

Para validar a estrutura sem baixar os 27 anos de uma vez, foi inspecionada uma
amostra de três eras:

- **2008**: início da expansão das automáticas no Vale do Ribeira (A712, A746).
- **2018**: era intermediária consolidada (A766).
- **2023**: era contemporânea recente.

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

**Conclusão**: a estrutura interna permaneceu estável por mais de 15 anos; as
variações (barra na data, pasta raiz) são tratadas no parser unificado.

---

## 3. Critérios de validade

| Nível | Regra |
|---|---|
| Mês válido | ≥ 20 dias com temperatura |
| Ano válido | ≥ 300 dias com temperatura |
| Status `medido` | ≥ 5 anos válidos **e** ≥ 80 % de cobertura |
| Status `parcial` | tem série, mas abaixo de um dos dois limites |
| Status `insuficiente` | anos válidos demais escassos para média |

Média do período = média dos **anos válidos**; acumulado = soma dos mesmos anos.
2026 entra como parcial (até 31/10) e fica fora das médias.

Os extremos `tmax`/`tmin` passam por `sanitizar_extremos`, que descarta o valor
fora de `mediana ± max(3*MAD, 6 °C)` **na própria série da estação para aquele
mês do ano**. É o que corrige Belém 45,0 °C/−5,0 °C e Goiânia −8,7 °C sem tocar
em médias nem em chuva: a média mensal já estava certa, só o pico do sensor
contaminava o extremo.

**Ausente é `NULL`, nunca `0`.** Chuva sem leitura válida fica `NULL` — o `0`
só aparece quando o pluviômetro de fato registrou zero.

---

## 4. Como usar

```bash
# 1. Baixar os ZIPs (27 arquivos, ~1,85 GB; 3 em paralelo por padrão)
python3 dadoshistoricosinmet/coletar.py

# 2. Processar em mensal + anual (multiprocessado)
python3 dadoshistoricosinmet/processar.py --desde 2000 --ate 2026 --paralelo 4

# 3. Exportar os JSONs consumidos pelo painel
python3 dadoshistoricosinmet/exportar.py

# 4. Relatório em Markdown (médias e acumulados por estação)
python3 dadoshistoricosinmet/relatorio_inmet.py
```

Todos aceitam `--db`/`--destino`/`--saida` para apontar outro caminho.

### Arquivos gerados

| Arquivo | Conteúdo |
|---|---|
| `inmet_nacional.sqlite` | `inmet_estacao`, `inmet_mensal`, `inmet_anual`, `inmet_normal`, `inmet_resumo` |
| `site/public/inmet_catalogo.json` | catálogo + resumo por estação (724 entradas) |
| `site/public/inmet_series.json` | normal mensal e série anual das 705 estações com dado |
| `INMET_RELATORIO.md` | médias anuais e acumulados do período por estação |

`inmet_catalogo.json` e `inmet_series.json` são **versionados**: o deploy do
painel é estático e não enxerga o banco.

---

## 5. Painel

`site/inmet.html` — HTML/CSS/JS puro, sem build de framework. Lê os dois JSONs
de `site/public/` e oferece seletor Brasil + filtro UF, busca, tira de cobertura
por ano, normal mensal, série anual, tabela e export CSV. Abre em modo claro por
padrão (`inmet_tema_v2` no `localStorage`).

O antigo `site/inmettodas.html` foi removido: gerava perfis sintéticos a partir
de latitude/longitude e não podia ser publicado como dado do INMET.

### Armadilhas verificadas na fonte

- O servidor devolve dados **antes de a estação existir**; `auditar`/status
  existem justamente para separar isso de clima real.
- Valores como `45` e `-5` aparecem sem casa decimal, mas **não** são
  sentinelas: 2020 tem ~54 mil leituras reais ≤ −5 °C no Sul. O filtro é
  estatístico, não por valor fixo.
- Um mês pode ter `tmed` correto e `tmax`/`tmin` corrompidos no mesmo registro.
- A umidade vem rotulada `(mm)` no HTML do portal; é `%`.
