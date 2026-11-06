# Tarefa 09 — INMET: série histórica nacional, relatório e painel

**Status:** feito
**Depende de:** 05, 06
**Arquivos:** `dadoshistoricosinmet/coletar.py`,
`dadoshistoricosinmet/processar.py`, `dadoshistoricosinmet/exportar.py`,
`dadoshistoricosinmet/relatorio_inmet.py`, `dadoshistoricosinmet/README.md`,
`site/inmet.html`, `site/public/inmet_catalogo.json`,
`site/public/inmet_series.json`, `INMET_RELATORIO.md`, `start.sh`,
`site/vite.config.js`
**Testes:** T08.1–T08.4

## Objetivo

Consolidar toda a base histórica diária do INMET (2000–2026) em médias anuais e
acumulados por estação, gerar relatório Markdown e publicar um painel estático
com os dados reais. O CIIAGRO responde pelos 25 municípios; o INMET entra como
segunda fonte, nacional, para dar série longa e comparação regional.

O painel precisa mostrar a origem do dado. As URLs publicadas são
`https://portal.inmet.gov.br/dadoshistoricos` (pacotes anuais) e
`https://apitempo.inmet.gov.br/estacoes/T` (catálogo).

## Fonte

- 27 pacotes anuais (`2000.zip` … `2026.zip`), **1.849 MB**, baixados em 154 s.
- Cada ZIP tem um CSV horário por estação, `latin-1`, separador `;`, decimal
  vírgula, 8 linhas de metadados e cabeçalho na linha 9.
- Universo = **união dos códigos presentes nos arquivos**: 705 estações com
  série. O catálogo da API tem 669; as demais 19 entram no seletor sem série.

## Critérios

| Nível | Regra |
|---|---|
| Mês válido | ≥ 20 dias com temperatura |
| Ano válido | ≥ 300 dias com temperatura |
| `medido` | ≥ 5 anos válidos **e** ≥ 80 % de cobertura |
| `parcial` | tem série, abaixo de um dos limites |
| `insuficiente` | anos válidos escassos para média |

- Média do período = média dos anos válidos; acumulado = soma dos mesmos anos.
- 2026 é parcial (até 31/10) e fica **fora** das médias.
- Ausente é `NULL`, nunca `0`. `0` de chuva só quando o pluviômetro registrou
  zero.

Resultado: **705 estações, 123.007 meses, 10.687 anos, 7.305 normais** —
271 `medido`, 340 `parcial`, 94 `insuficiente`.

## Sanitização dos extremos

O arquivo tem picos isolados de sensor que não afetam a média mensal mas
contaminam `tmax_abs`/`tmin_abs`: Belém marca **45,0 °C** em 12/2005 e
**−5,0 °C** em 03/2020; Goiânia marca **−8,7 °C**.

`sanitizar_extremos` descarta o valor fora de `mediana ± max(3*MAD, 6 °C)` na
própria série da estação **para aquele mês do ano**, exigindo ≥ 5 anos. O piso
de 6 °C impede cortar variabilidade real. Só mexe em `tmax`/`tmin`; `tmed` e
chuva ficam intactos porque já estavam certos.

Aplicado ao banco: **1.727 células anuladas**. Belém passou a 38,5/19,8 °C e
Goiânia a 41,1/5,8 °C.

`-5,0` **não** é sentinela: 2020 tem ~54 mil leituras reais ≤ −5 °C no Sul. Um
filtro por valor fixo apagaria o frio legitimo.

## Painel

`site/inmet.html` foi reescrito em HTML/CSS/JS puro (o anterior carregava
Tailwind pelo CDN e só conhecia A712/A746/A766).

- Tema claro por padrão, chave `inmet_tema_v2`, sem `prefers-color-scheme`.
- Seletor Brasil + filtro UF + busca, tira de cobertura com 27 células, tiles
  em 3 blocos (6, 3 e 2 colunas), climatograma, série anual, tabela e CSV.
- Lê `inmet_catalogo.json` e `inmet_series.json` de `site/public/`.

`site/inmettodas.html` foi **apagado**: gerava perfis sintéticos a partir de
latitude/longitude (`gerarPerfilBrasil`) e não podia ser publicado como dado do
INMET. Com ele saíram `site/src/inmet_main.jsx`, `site/src/InmetApp.jsx` e
`site/public/inmet_regional.json`, que só existiam para alimentá-lo.

## Aceite

- [x] 27/27 ZIPs em cache e processados.
- [x] Banco com mensal, anual, normal e resumo; extremos sanitizados.
- [x] `INMET_RELATORIO.md` com resumo nacional e tabela por estação.
- [x] JSONs do site exportados e versionados.
- [x] `site/inmet.html` compila (`npm --prefix site run build`) e todos os IDs
      usados pelo JS existem no HTML.
- [x] `site/inmettodas.html` removido e `vite.config.js` sem o input.
- [x] `start.sh` sem o `cp` de `inmet_regional.json`.
- [x] 43 testes passando; T08 registrado em `.planning/testes.md`.

## Nota

O relatório usa "média do período", nunca "normal climatológica": 30 anos é o
mínimo convencional e a série ainda não foi validada contra outra fonte.
