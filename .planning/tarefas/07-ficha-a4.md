# Tarefa 07 — Ficha A4 em LaTeX e uso no planejamento

**Status:** feito — 15 fichas compiladas, uma página A4 cada
**Depende de:** 05, 06
**Arquivos:** `latex/gerar.py`, `latex/fichas/*.tex`, `relatorio.py`,
`site/src/App.jsx`, `site/public/dados.json`
**Testes:** T06.2, T07.1–T07.7 em `.planning/testes.md`; compilação verificada à
mão (ver "Verificação")

## Objetivo

Uma página A4 por estação, dizendo em letras garrafais que são **médias de vários
anos fechados**, não previsão, e o que esses números permitem decidir no
calendário agrícola. Mesma informação no painel, no mesmo texto.

## Subtarefas

### 07.1 — O texto nasce no Python, não no papel

`relatorio.py` exporta `estacao.uso` (orientação específica, derivada dos números
daquela série) e `regiao.uso` (o que vale para qualquer município). O site e a
ficha LaTeX renderizam a mesma lista; nenhum dos dois reescreve a frase.

Motivo direto: as mensagens escritas à mão por cidade tinham duas frases contra
os dados — "junho e julho com mínimas médias abaixo de 10 °C" em Barra do Turvo
(junho = 14,6 °C) e "dez a março, mais de 40% da chuva" em Jacupiranga (verão
DJF = 39,8%). Texto gerado com o número dentro não tem como divergir.

Limiares declarados, não medidos: `LIMITE_SECO = 100` mm/mês (janela de preparo),
`LIMITE_UMIDO = 120` mm/mês (água para corretivo em cobertura), `SERIE_CURTA = 10`
anos fechados (abaixo disso a ficha diz "série curta"). Onde o limiar não se
aplica, o item explica em vez de inventar conselho — Iguape não tem janela seca,
Cananéia tem 79 mm no mês "mais seco", que não é déficit.

### 07.2 — Sazonal com total, %, média e extremos

`estacao.sazonal` passou a trazer `mm`, `pct`, `media`, `max`/`max_mes` e
`min`/`min_mes`. Antes o SPA calculava máx/mín/média das próprias linhas
mensais; agora o card lê o JSON, e o `latex/gerar.py` lê o mesmo campo. A soma
das quatro estações continua fechando exatamente com a chuva anual (T05.7).

### 07.3 — Antes dos solstícios

`estacao.solsticios` traz o acumulado que antecede cada virada do dia:

- **inverno (21/06):** janeiro a maio;
- **verão (21/12):** junho a novembro.

Dezembro fica depois do solstício de verão e entra no total anual, não nos
acumulados. É referência de estação — a chuva é a média do mês inteiro,
inclusive dos dias posteriores à data.

### 07.4 — A página

`python3 latex/gerar.py` escreve `latex/fichas/<slug>.tex` (15 fichas) a partir de
`site/public/dados.json`, não do banco. Layout: cabeçalho com meses medidos e
anos fechados, caixa "leia antes de usar", dois blocos de KPI, tabela mensal com
barras em `\rule`, tabela sazonal, acumulados de solstício, orientação local,
orientação regional e rodapé com fonte, link e ressalva de umidade.

Sem `pgfplots`: barras em `\rule` não pedem pacote extra e o LaTeX puro cabe em
`pdflatex` no Overleaf. Umidade relativa fica fora porque a fonte usa `0` para
"sensor ausente".

### 07.5 — Card no painel

`<Uso>` é renderizado depois de "Chuva anual por estação": a lista local em
aberto e a geral dentro de um `<details>`, que no celular não empurra o gráfico
para fora da primeira tela.

### 07.6 — Preto e branco estrito

A ficha é impressa em toner na ATER, e matiz não sobrevive à impressão P&B: o
azul `1B7F9E` do painel vira cinza médio e some contra a barra. Toda a paleta é
a escala `gray` do `xcolor`:

| Nome | Valor | Onde |
|---|---|---|
| `barras` | `gray 0.15` | preenchimento das barras do minigráfico |
| `borda` | `gray 0.75` | contorno dos cartões de KPI |
| `fundocard` | `gray 0.98` | fundo dos cartões (quase branco, economiza toner) |
| `cinzaclaro` | `gray 0.94` | caixa "Leia antes de usar" |
| `cinza` | `gray 0.35` | rótulos e rodapés secundários |

A hierarquia passa a vir de peso de traço e de caixa (versal vs. `\scriptsize`),
não de matiz. Elementos:

- cabeçalho com título, linha da estação e a ressalva de série curta em
  `\footnotesize` negrito;
- aviso institucional em dois parágrafos rotulados — "Leia antes de usar" e
  "Aplicação prática";
- `\kpicard` em duas linhas de três, com `\hfill`: rótulo, número em `\Large` e
  rodapé de contexto, todos centralizados numa `minipage` de `1.4cm`;
- "Tabela 1" e "Tabela 2" centralizados acima da tabela (`center`), barras
  alinhadas à esquerda e números à direita (coluna `r`);
- listas com `\itemsep` de `0.5pt`, `\footnotesize` na local e `\scriptsize` na
  regional — é o que faz cinco itens caberem junto com as duas tabelas.

Largura do cartão: `\dimexpr0.32\textwidth-2\fboxsep-2\fboxrule`, de modo que
cartão + contorno meça exatamente `0.32\textwidth`; três cartões dão `0.96` e
sobram `0.04` para os dois `\hfill` — nenhuma linha estoura para a segunda.

### 07.7 — Armadilha do XeTeX: `°` sai como `¤`

O `.tex` é escrito para pdfLaTeX, onde `inputenc` declara `°`, `—` e `–` e
imprime certo. O `tectonic` só tem motor XeTeX: ele ignora o `inputenc` e manda o
Unicode cru para a fonte `ec-lmr`, que é uma fonte de 8 bits. O `°` (U+00B0) cai
no slot 0xB0 do T1, que é o **símbolo de moeda** — a ficha sai impressa como
`21,4 ¤C`, sem erro e sem aviso. O travessão é pior: não existe no slot nenhum e
é **descartado em silêncio**, então "49 mm/mês — é a janela" vira "49 mm/mês é a
janela".

Correção em `tex()`: `—` → `\textemdash{}`, `–` → `\textendash{}`,
`°` → `\textdegree{}`. São comandos definidos em T1 e renderizam igual nos dois
motores. Efeito colateral bom: o `\textemdash` dentro do texto JSON deixa de
depender do ligadura `---`.

## Verificação

```bash
python3 latex/gerar.py
for f in latex/fichas/*.tex; do tectonic -X compile --outdir /tmp/pdf "$f"; done
python3 /tmp/opencode/conta_paginas.py /tmp/pdf/*.pdf   # 1 página em cada
grep -h "Overfull\|Missing character" /tmp/pdf/*.log    # tem que ser vazio
pdftoppm -r 120 -png -singlefile /tmp/pdf/barra-do-turvo.pdf /tmp/pdf/barra
```

Resultado em 2026-10-30: **15 fichas, 15 PDFs de uma página, zero `Overfull
hbox` e zero glifo ausente**. A rasterização é obrigatória, não opcional: foi ela
que mostrou o `¤` que nenhum log acusou.

## O que falta

- **Onde o PDF fica para download.** O `.tex` é versionado; o PDF não. Decidir se
  `deploy.sh` passa a rodar `tectonic` e publicar `site/public/fichas/*.pdf` com
  botão no SPA — depende de o build de produção ter TeX, o que o Netlify não tem
  por padrão.
- **`\kpicard` no limite.** Três cartões usam `0.96\textwidth`; sobra `0.04` para
  os dois `\hfill`. Qualquer aumento de `\fboxsep` ou da largura do cartão
  derruba o terceiro para a linha de baixo — e aí a ficha passa de uma página.
