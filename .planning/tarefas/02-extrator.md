# Tarefa 02 — Extrator do HTML do CIIAGRO

**Status:** feito
**Depende de:** —
**Arquivos:** `fontes/ciiagro.py` (`blocos`, `_v`, `linhas`), `tests/fixtures/*.html`
**Testes:** T02.1 a T02.4 em `.planning/testes.md`

## Objetivo

Transformar o HTML de `cdiaria` (diário) e `cmensal` (mensal) em linhas com 8
colunas canônicas: `tmin, tmed, tmax, urmin, urmed, urmax, chuva`.

Função pura: recebe texto, devolve lista de dicts. Sem rede, sem banco, sem
Scrapy. É o que torna a raspagem testável.

## O formato real (descoberto, não suposto)

Não existe API. O dado está embutido no HTML como JavaScript de gráfico:

```javascript
data.addRows([['Apiaí',12.95,16.795,20.64], ...]);   // temperatura
data2.addRows([['Apiaí',1.016], ...]);               // chuva
data3.addRows([['Apiaí',72.4,83.05,93.7], ...]);     // umidade
```

Por isso **regex, não parser de HTML**. Um `<td>` aqui seria três camadas de
indireção para o mesmo número.

### Por que não usar a `<table>` da mesma página

A tabela existe, mas o cabeçalho repete `Mínima` três vezes (temperatura,
umidade) e usa `rowspan`/`colspan` de duas linhas. Mapear por nome de coluna —
a estratégia "robusta" usual — fica **ambíguo exatamente onde importa**. O
`addRows` é posicional e nomeado, e não tem essa ambiguidade.

## Subtarefas

### 02.1 — Salvar o HTML real como fixture

`tests/fixtures/` com 5 arquivos baixados em 2026-10-30: `cdiaria.html`,
`cmensal.html`, `calendario.html`, `periodo.html`, `estacoes.html`.

Sem fixture, o teste vira "o regex compila", que não prova nada. Com fixture, o
teste prova que a extração funciona **no HTML que existe hoje**, e quebra quando
o site mudar.

### 02.2 — Ler com `utf-8-sig`

O CIIAGRO responde com BOM. Sem `utf-8-sig`, o primeiro caractere vira lixo e o
primeiro regex falha de um jeito confuso.

### 02.3 — Quebrar o HTML em blocos

`blocos(html)` encontra todo `(\w+)\.addRows\(\[(.*?)\]\s*\);` e devolve
`{variável: [(estação, [valores])]}`.

Três detalhes que custaram tempo:
- `data` e `data2` são variáveis distintas; casar `data.addRows` sem âncora
  pegaria `data2.addRows` se o regex fosse preguiçoso demais.
- O fechamento é `]);`, às vezes com espaço antes do `)` — daí `\]\s*\);`.
- Usar `re.S`, porque as linhas são separadas por quebra de linha.

### 02.4 — Unir os três blocos por estação

`linhas(html)` percorre a **união** dos nomes de temperatura, umidade e chuva,
não só a lista de temperatura.

Motivo: estação que reporta chuva mas não temperatura é dado válido. Se a união
fosse pela temperatura, essa chuva some — e "dias com chuva ≥ 1 mm" fica baixo
sem ninguém perceber.

### 02.5 — Ausente é `None`, nunca `0`

`_v(valores, i)` devolve `None` quando a linha veio mais curta que o esperado.

**Não** converter `0` em `None` aqui: o site usa `0` como "sensor ausente" em
`urmed`, e o extrator não tem como distinguir de um zero real. Quem denuncia é
`auditar` (tarefa 04). Decisão consciente, documentada em teste.

### 02.6 — Cabeçalho não entra

O `addRows` não traz nome de coluna; o significado é **posicional** e vem do
`addColumn` logo acima na página. Ordem fixa: `tmin, tmed, tmax` / `chuva` /
`urmin, urmed, urmax`.

Se o CIIAGRO reordenar, o teste de valor (T02.2) quebra — que é a proteção.

## Critério de aceite

- [x] `linhas(cdiaria.html)` devolve 18 estações
- [x] `linhas(cmensal.html)` devolve 7 estações (01/2001)
- [x] Valores de Apiaí batem com a tabela publicada
- [x] Estação presente em só um dos blocos não é descartada
- [x] Nenhum teste toca a rede

## Decisões

- **Regex sobre `addRows`, não XPath sobre `<table>`.** Menos código, sem
  ambiguidade de cabeçalho, e testável sem Scrapy.
- **Um extrator para diário e mensal.** Os dois têm o mesmo formato de `addRows`;
  a diferença é só o parâmetro da requisição.
- **Zero preservado.** Corrigir na extração esconderia o problema do site.
