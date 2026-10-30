# Tarefa 04 — Auditoria da série

**Status:** feito
**Depende de:** 03
**Arquivos:** `coletor.py` (`auditar`)
**Testes:** coberto por T03.4 e pela verificação manual descrita abaixo

## Objetivo

Mostrar, por estação, o que foi coletado e o que merece desconfiança — sem
corrigir nada.

A coleta é deliberadamente burra: grava o que o site manda. O julgamento vive
aqui, visível, em vez de virar regra escondida no extrator.

## Por que isto não é opcional

O CIIAGRO tem dois defeitos que produzem série plausível e falsa:

1. **Serve dado antes da estação existir.** Registro: início `11/10/2005`,
   mas 380,2 mm em `01/1995`. Cananéia: `1 mm` em `01/2000`, placeholder.
2. **Usa `0` para "sensor ausente".** Em `01/2001`, todas as estações reportam
   `0.00 %` de umidade — não é 0 %, é coluna vazia.

Nenhum dos dois gera erro, status diferente de 200 ou exceção. Sem auditoria, os
dois entram no relatório como fato.

## Subtarefas

### 04.1 — Uma linha por estação

`SELECT` com `LEFT JOIN` de `municipio` e `fato`, agrupado por `ponto.id`.

`LEFT JOIN` de propósito: estação sem nenhuma linha coletada tem de aparecer
(com `0` linhas), não desaparecer da lista.

### 04.2 — Colunas do relatório

`estação | município | início | 1º fato | linhas | alertas`

`município` sai como `-` quando é `NULL` — são as 8 estações de municípios
vizinhos.

### 04.3 — Alerta `dado antes do início`

Dispara quando `substr(primeiro_fato,1,7) < substr(inicio_auto,1,7)` — comparando
**mês**, não a string inteira.

A comparação direta de strings dá falso positivo em toda estação saudável:
`"2011-01" < "2011-01-07"` é verdadeiro, então Apiaí (início 07/01/2011, primeiro
fato `2011-01`) aparecia com o alerta mesmo começando na data certa. Com a
comparação por mês, só sobram os casos reais.

### 04.4 — Alerta `início suspeito (site)`

Dispara quando `inicio_auto < 1970`. Pega o `31/12/1969` do Itariri, que é
epoch do sistema e não data de fundação.

### 04.5 — Alerta `umidade toda 0 (ausente)`

Dispara quando **todas** as linhas de uma estação têm `urmed = 0`.

"Todas" e não "alguma": um mês isolado com 0 é falha pontual de sensor, e
listar cada um viraria ruído. A estação inteira zerada é defeito de coluna.

### 04.6 — Alerta `chuva toda 0`

Dispara quando todas as linhas têm `chuva = 0`. Pode ser estação seca (raro em
26 anos) ou coluna quebrada — nos dois casos vale olhar.

## Verificação (o que rodar depois de coletar)

```bash
python3 coletor.py auditar
```

Esperado, com o catálogo completo:

- 23 linhas.
- 8 estações com município `-`.
- `Registro` com alerta `dado antes do início` se a coleta começar antes de 2005.
- `Itariri` com `início suspeito (site)`.
- Nenhuma estação dos 17 com `linhas = 0` (se houver, o intervalo coletado não
  cobre o início dela).

## Critério de aceite

- [x] Toda estação do catálogo aparece, mesmo com zero linhas
- [x] Os quatro alertas disparam nos casos conhecidos
- [x] O comando não altera o banco
- [x] Sai em texto alinhado, legível em terminal de 100 colunas

## Decisões

- **Relatar, não corrigir.** Nenhum `UPDATE` em `auditar`. Corrigir dado na
  auditoria destruiria a evidência do defeito.
- **`0` continua `0` no banco.** Converter na importação faria o banco parecer
  mais limpo e esconderia que o site tem um bug de unidade (rotula umidade como
  `mm`).
