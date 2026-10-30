# Tarefa 05 — Relatório por município

**Status:** feito; a renderização migrou para a tarefa 06 (SPA React)
**Depende de:** 04
**Arquivos:** `relatorio.py`, `start.sh`
**Testes:** T05.1 a T05.8 em `.planning/testes.md`

## Objetivo

Gerar, por comando, `site/public/dados.json` com chuva, temperatura e a série
real de cada município — declarando fonte, período e quantidade de anos por
estação. O cálculo que exige honestidade fica em Python; o painel só desenha.

## Como ver

```bash
python3 relatorio.py        # escreve site/public/dados.json
./start.sh                  # exporta, builda e serve em porta aleatória
```

`dados.json` é versionado porque o deploy (Netlify/Vercel) não tem acesso ao
banco, que é gitignorado. Coletou de novo? Rode `relatorio.py` e commite o JSON.

## Formato de saída

Um JSON com `municipios`, e por município `slug`, `nome` e `estacoes`. Cada
estação traz `meses` (12 entradas), `resumo` achatado no objeto (chuva anual,
mês mais/menos chuvoso, amplitude, UR, `sazonal`), `rotulo`, `normal`, `aviso` e
`aviso_descarte` — nulos quando não há o que avisar. Município sem estação entra
com `estacoes: []`: sumir com ele transformaria "não há dado" em "não existe".

## Subtarefas

### 05.1 — Série por município

`relatorio.agregado(conn, ponto_id)` lê `fato` daquela estação e resume por mês do
ano.

A consulta filtra `length(data) = 7`. Como a invariante da tarefa 03 garante um
mês **ou** os dias dele, um município pode ter meses e dias misturados (estações
diferentes); agregar `substr(data,1,7)` sem o filtro somaria o total mensal com
os dias do mesmo mês.

### 05.2 — Cobertura declarada antes de qualquer número

Linha de metadados acima da tabela: `1992-10 a 2026-10 · 409 meses · normal
climatológica`. Sem isso o leitor não sabe se está vendo 34 anos ou 3 meses com
lacunas.

### 05.3 — Métricas mensais

Por mês do ano: chuva média, T mín/média/máx, UR média, e `n` (quantos anos
contribuíram). Rodapé com a chuva anual média dos anos que têm os 12 meses.

**Duas colunas do plano original saíram:**

- **dias com chuva ≥ 1 mm** exige `--diario`, e o banco é todo mensal. Fica para
  quando a série diária entrar; publicar a coluna vazia seria pior.
- **descarte de mês com < 20 dias** só faz sentido em série diária. Em mensal,
  ou o mês existe, ou não existe — e o `n` da coluna denuncia o buraco.

### 05.4 — Rótulos derivados de `n_anos`, nunca cravados

| `n_anos` | Rótulo |
|---|---|
| ≥ 30 **e série validada** | "normal climatológica" |
| < 30 | "médias do período AAAA–AAAA (n anos de dado)" |
| ≥ 30, série não validada | "médias do período … (n anos de dado; parte da série não validada)" |

A condição extra **e série validada** saiu da execução: Pariquera-Açu tem 34,1
anos, mas 11 deles anteriores a 2004-06 vieram sem explicação da fonte. Cravar
"normal climatológica" ali seria afirmar validação que ninguém fez.

Extremos não entraram: sem os 30 anos validados, "recorde" também não se sustenta.

### 05.5 — Lacunas explícitas

Mês sem dado vira `null` no JSON, não `0`; na tela, travessão. Série com buraco é
diferente de série seca.

### 05.6 — Faixa de sanidade na média

Leitura fora de `LIMITES` (T em [-20, 50] °C, UR em [0, 100] %, chuva mensal em
[0, 1000] mm) **não entra na média** e é contada no rodapé — `3 leitura(s) fora
da faixa de sanidade excluída(s) da média (tmed 2, tmax 1)`.

Achado na execução: sem isso o relatório de Miracatu publicava `55,9 °C` como
temperatura média de março, e Cananéia `52,6 °C` em setembro. O banco preserva o
valor; o relatório é seletivo e diz o que descartou.

### 05.7 — Renderização (migrada)

A primeira versão gerava um HTML por município com CSS embutido e SVG escrito em
Python. Funcionava offline, mas trocar de cidade era trocar de arquivo — o
mockup pedia um painel único. A tarefa 06 substituiu essa camada por um SPA
React sobre o mesmo `dados.json`; `relatorio.py` ficou só com a agregação.

### 05.8 — Nota de proveniência

Toda página do painel carrega: fonte, estação, código, período, anos com os 12
meses, contagem de descartes e o aviso de série pré-automação quando
`primeiro_fato < inicio_auto`.

## Critério de aceite

- [x] Um JSON com todos os municípios, `slug` sem acento (`pariquera-acu`)
- [x] Nenhum `0` onde a resposta correta é "sem dado"
- [x] Os 4 municípios sem estação aparecem com `estacoes: []`, não somem
- [x] Nota de proveniência sempre presente, com os anos calculados do banco
- [x] `n_anos < 30` nunca produz a palavra "normal climatológica"
- [x] Valor impossível não entra na média e aparece como descarte

## Fora de escopo

- **Tabela para a Wikipédia:** seria pesquisa inédita. As normais 1981-2010 são
  do INMET, não do CIIAGRO; publicar "média 2024-2026" como clima não se
  sustenta em fonte verificável.
- **ET0 / balanço hídrico:** Hargreaves–Samani precisa de latitude e produz
  estimativa, não medição. Se entrar, entra numa tarefa 06 com o rótulo
  "estimativa" no nome da coluna.
- **INMET e NASA POWER:** tarefa 07, só depois de a série do CIIAGRO estar
  auditada.
