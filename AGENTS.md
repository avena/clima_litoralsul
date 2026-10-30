# AGENTS.md

Coletor de dados climáticos do CIIAGRO para os **17 municípios do Litoral Sul
Paulista**. Python 3.12, **só stdlib**. O plano completo está em `PLANO.md`.

## Comandos

```bash
python3 coletor.py catalogo                        # 3 requisições, monta município+ponto
python3 coletor.py coletar --desde 2000-01 --ate 2026-10          # mensal, ~2 min
python3 coletor.py coletar --desde 2026-10-01 --ate 2026-10-31 --diario   # ~80 min/20 anos
python3 coletor.py auditar                         # cobertura + valores suspeitos
python3 -m unittest discover -s tests              # 16 testes, sem rede
```

`dados/clima.sqlite` é o banco. Não há instalação, não há `pip install`.

## Invariantes que não podem quebrar

1. **`length(data)` é a granularidade.** `AAAA-MM-DD` = dia, `AAAA-MM` = mês.
   Não adicione coluna `gran`; ela dessincroniza.
2. **Um mês tem OU a linha mensal OU os dias, nunca os dois.** Garantido por
   `substituir_granularidade`. Sem isso, `SUM(chuva)` por mês conta duas vezes.
3. **Ausente é `NULL`, nunca `0`.** Mas o site manda `0` para "sem sensor" —
   por isso `auditar` existe e nada é corrigido na coleta.
4. **A fonte devolve o nome da estação; o banco resolve para `ponto.id`.**
   `fontes/*.py` nunca importa `sqlite3` nem conhece o banco.

## Armadilhas do CIIAGRO (verificadas, não teóricas)

- O servidor devolve dados **antes da estação existir**: `Registro` tem 380 mm em
  `01/1995` e começou em `11/10/2005`. `Cananéia` tem `1 mm` em `01/2000` — placeholder.
- `horario.php?codigo=N` responde **mas ignora qualquer parâmetro de data**: é janela
  rolante de 7 dias. Não serve para série, por mais que pareça a página certa.
- `diario/cperiodo` devolve só um resumo por estação, não uma série.
- `/calendario` traz `Itariri` com início `31/12/1969` — epoch, não fundação.
- A umidade é rotulada `(mm)` no HTML do próprio site. É `%`.
- Status 200 até quando não há dado: "vazio" = ausência dos blocos `addRows`.

## Ambiente de destino

DreamHost Shared: Python **3.12.3** em `/usr/bin/python3`, web **só CGI**
(Phusion Passenger foi removido de todos os planos). Portanto: nada de Flask,
nada de `passenger_wsgi.py`, nada de WSGI. Coleta por cron no shell; saída web
só como HTML estático gerado por comando.

## Fora de escopo, com motivo

| Não usar | Motivo |
|---|---|
| Scrapy | 3 endpoints, sem paginação, sem crawl. `urllib` basta. |
| Flask / `web/` | não roda no Shared. |
| tabela `observacoes(estacao, timestamp, valor)` | não suporta mensal nem consolidação. |
| "normal climatológica" | exige 30 anos. |
| "recorde" com < 30 anos | é "extremo observado no período". |

## Onde estender

Nova fonte = um módulo em `fontes/` com `FONTE`, `pontos()` e `fatos(desde, ate)`.
Nada mais. INMET e NASA POWER ficam para depois da auditoria da série do CIIAGRO.
