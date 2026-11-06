# Tarefa 03 — Coletor da série histórica

**Status:** feito
**Depende de:** 01, 02
**Arquivos:** `fontes/ciiagro.py` (`_get`, `_post`, `_chaves`, `fatos`),
`coletor.py` (`substituir_granularidade`, `coletar`, `main`)
**Testes:** T03.1 a T03.4 em `.planning/testes.md`

## Objetivo

Baixar a série do CIIAGRO de 2000 até hoje e gravar em `fato`, sem duplicar, sem
apagar dado existente, e podendo ser interrompido e retomado.

## A inversão que define esta tarefa

O eixo da coleta é **data, não estação**.

`cdiaria` devolve **todas as estações de um dia** num POST. `cmensal` devolve
**todas de um mês**. Logo:

| Abordagem | Requisições para 2000→2026 |
|---|---|
| por estação (23 × período) | 23 × 315 = 7.245 |
| por data (mensal) | **315** |
| por data (diário) | 9.560 |

Coletar por estação é o dobro de requisições para obter o mesmo dado, e ainda
perde a possibilidade de um dia trazer uma estação nova.

## Subtarefas

### 03.1 — Cliente HTTP com tentativas

`_get(url, dados)` com `User-Agent` próprio, timeout de 60 s e 3 tentativas com
espera exponencial (1 s, 2 s).

Não há autenticação, cookie nem sessão: é POST de formulário simples. O
`User-Agent` é identificação, não camuflagem.

### 03.2 — POST de formulário

`_post(caminho, dados)` monta `application/x-www-form-urlencoded` e delega para
`_get`. Os dois endpoints têm o mesmo formato de resposta.

### 03.3 — Gerar a lista de períodos

`_chaves(desde, ate, diario)` devolve `AAAA-MM` (mensal) ou `AAAA-MM-DD`
(diário), inclusivo nas duas pontas.

A conta mensal é feita em índice de mês (`(ano*12+mês)`), não somando 1 ao mês:
`2000-12` + 1 mês tem de ser `2001-01`.

### 03.4 — Gerar os fatos

`fatos(desde, ate, diario)` é um **gerador**: uma requisição por período, `yield`
de uma linha por estação, `time.sleep(0.25)` depois de cada requisição.

Gerador, não lista: 26 anos × 22 estações são ~7 mil dicts, e o consumidor
grava em lote — não há motivo para materializar tudo em memória.

Devolve o **nome** da estação, não o id. O banco resolve o nome para `ponto.id`;
assim `fontes/ciiagro.py` nunca importa `sqlite3`.

### 03.5 — Pausa entre requisições

0,25 s por requisição. Não foi observado rate-limit a 4 req/s, então isso é
educação, não necessidade — e é o que mantém a coleta de 26 anos em ~2 min sem
arriscar bloqueio.

### 03.6 — UPSERT que não apaga

`ON CONFLICT(ponto_id, data) DO UPDATE SET x = COALESCE(excluded.x, x)`.

Se a nova coleta vier com `NULL` (sensor caiu), o valor antigo **permanece**.
Recoletar um período nunca piora o banco. O custo é que corrigir um valor
errado exige `DELETE` explícito — aceitável: dado climático não "corrige" sozinho.

### 03.7 — Invariante mês XOR dias

`substituir_granularidade(conn, pontos_meses, diario)` apaga a granularidade
oposta para cada `(ponto, mês)` antes de inserir.

Sem isso, quem coletasse mensal e depois diário teria o total do mês **e** os
dias do mesmo mês na tabela, e um `SUM(chuva) GROUP BY substr(data,1,7)`
dobraria a chuva.

A regra anterior — "dia vence mês numa `VIEW` com `ROW_NUMBER`" — foi escrita e
**descartada**: com mês parcial, ela somava só os dias coletados e reportava
menos chuva do que o mês fechado. A regra correta não é "qual granularidade
vence", é "só uma das duas existe".

### 03.8 — Primeiro dado de cada estação

Depois da gravação, `atualizar_primeiro_fato(conn)` recalcula
`ponto.primeiro_fato` como `MIN(data)` de `fato` — para **todas** as estações,
não só as do lote.

Isso existe porque o site devolve série **antes** da estação existir (Registro
tem 380 mm em 01/1995 e começou em 2005). Guardar os dois valores permite que
`auditar` mostre a discrepância em vez de escondê-la.

**Regressão corrigida:** a primeira versão gravava o mínimo do lote com
`COALESCE(primeiro_fato, ?)`, e o primeiro lote congelava o valor para sempre.
Coletar 1995 depois de 2026 deixava a estação marcada como começando em 2026, e
a auditoria perdia o alerta. Recalcular 23 linhas inteiras é mais barato do que
rastrear o mínimo incrementalmente — e sempre correto.

### 03.9 — CLI

`argparse` com `--db`, e subcomandos `catalogo`, `coletar`, `atualizar` e
`auditar`. `--diario` é flag de `coletar`; o padrão é mensal porque custa 25×
menos.

### 03.10 — Coleta incremental (`atualizar`)

`janela_incremental(ultimo, hoje)` devolve do último mês gravado até o **mês de
ontem**; `atualizar` chama `coletar` só nessa janela. Um a três meses, duas a
três requisições, 3 s — contra 315 requisições e ~2 min da série inteira.

O último mês é repetido de propósito: ele pode ter sido gravado no meio do mês e
estar incompleto. Recoletar não piora nada (o UPSERT usa `COALESCE`).

Mês guardado em dias faz a janela recuar para o mês anterior: a coleta é mensal
e `substituir_granularidade` apagaria os dias.

## Critério de aceite

- [x] `coletar --desde 2026-09 --ate 2026-10` grava 44 linhas em 22 estações
- [x] Rodar o mesmo comando duas vezes mantém 44 linhas
- [x] `coletar --diario` no mesmo mês remove a linha mensal e mantém só os dias
- [x] Estação fora do catálogo é ignorada com aviso, não derruba a coleta
- [x] Período inteiromente vazio escreve erro em stderr
- [x] Nenhuma requisição por estação

## Decisões

- **Mensal por padrão.** 315 requisições contra 9.560. O mensal não permite
  veranico; quando isso for necessário, `--diario` grava no mesmo `fato` e a
  invariante impede a dupla contagem.
- **`COALESCE` no UPSERT.** Coleta parcial nunca apaga medição boa.
- **Sem `--retomar` em `coletar`.** O UPSERT é idempotente: pedir um intervalo
  explícito é mais simples do que calcular onde parou. Para a rotina diária
  existe `atualizar`, que é onde a janela é calculada — repetir 315 requisições
  todo dia não se justifica.
