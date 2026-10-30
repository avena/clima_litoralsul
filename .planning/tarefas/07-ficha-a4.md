# Tarefa 07 — Ficha A4 em LaTeX e uso no planejamento

**Status:** feito (ficha não compilada nesta máquina: não há LaTeX instalado)
**Depende de:** 05, 06
**Arquivos:** `latex/gerar.py`, `latex/fichas/*.tex`, `relatorio.py`,
`site/src/App.jsx`, `site/public/dados.json`
**Testes:** T07.1–T07.6 em `.planning/testes.md`

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

## O que falta

- **Compilar.** Nenhum motor LaTeX nesta máquina (`pdflatex`, `tectonic`,
  `latexmk` ausentes; `sudo` pede senha). A ficha foi revisada colando o `.tex`
  no Overleaf (pdfLaTeX). Onde o PDF fica para download ainda não foi decidido.
- **Conferir se cabe em uma página** em cada uma das 15 fichas.
