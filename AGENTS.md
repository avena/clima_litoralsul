# AGENTS.md

Coletor de dados climáticos do CIIAGRO para os **17 municípios do Litoral Sul
Paulista**. Python 3.12, **só stdlib**. Planos em `.planning/` — comece por
`.planning/PLANO.md`.

## Comandos

```bash
python3 coletor.py catalogo                        # 3 requisições; rode antes de coletar
python3 coletor.py coletar --desde 2000-01 --ate 2026-10           # mensal, ~2 min
python3 coletor.py coletar --desde 2026-10-01 --ate 2026-10-31 --diario
python3 coletor.py auditar                         # cobertura + suspeitas; nunca escreve
./start.sh                                         # relatórios em porta aleatória, 0.0.0.0
python3 -m unittest discover -s tests              # 23 testes, ~0,6 s, sem rede
python3 -m unittest tests.test_ciiagro.TestBanco.test_upsert_nao_duplica   # um teste só
```

`dados/clima.sqlite` é o banco. Não há instalação, não há `pip install` — e não é
pacote: `coletor.py` é a única entrada executável (`relatorio.py` só lê o banco).

Três coisas que custam tempo de depuração:

- **`coletar` sem `catalogo` não grava nada.** O banco resolve a estação por nome
  em `ponto`; o que não estiver lá é ignorado com aviso "fora do catálogo".
- **Mês anterior a 2000 responde em ~1,5 s** (contra ~0,24 s dos recentes),
  então uma varredura de 1990 com `timeout 180` morre no meio sem mensagem.
  Rode em background.
- **Os testes comparam com HTML real em `tests/fixtures/`.** Se falharem depois de
  o site mudar, baixe a página de novo; não ajuste o valor esperado "até passar".

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
- `Miracatu` em `03/1990` vem no `addRows` cru como `tmed = 873,35`: coluna
  deslocada na fonte, não bug do extrator. Preserve — limpar na coleta apagaria
  a evidência. `auditar` **ainda não** pega isso: só alerta cobertura, `0` de
  umidade/chuva e início suspeito. Não existe faixa de sanidade implementada.
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

## Documentação — obrigatório

Todo plano, tarefa e catálogo de teste mora em `.planning/`. Não criar `PLANO.md`
na raiz nem pasta `docs/`:

```
.planning/PLANO.md        índice, decisões, cobertura, revisão do material antigo
.planning/tarefas/NN-*.md uma tarefa por arquivo: objetivo, subtarefas, aceite
.planning/testes.md       um ID e um "o que garante" por teste
.planning/arquivo/        material de terceiros (ignorado pelo git)
```

**Toda função tem docstring no formato Google**, com uma linha de resumo no
imperativo e as seções que se aplicarem — `Args:`, `Returns:`, `Raises:`,
`Efeitos:`, `Nota:`. Função privada também (`_get`, `_v`), porque é onde o
`porquê` costuma sumir. Ver `coletor.coletar` e `fontes.ciiagro.linhas` como
modelo.

**Todo teste tem docstring dizendo o que ele garante** — não o que ele faz. Se
não der para escrever essa frase, o teste não protege nada e deve sair. Cada
teste novo entra também em `.planning/testes.md` com um ID (`T03.4`).

Tarefa nova = arquivo novo em `.planning/tarefas/` + linha no índice do
`.planning/PLANO.md`. Tarefa concluída muda o próprio status, não é apagada.

## Git

Histórico linear em `main`, commits em português com prefixo
(`feat(ciiagro):`, `docs:`, `test:`, `chore:`). `dados/` e `__pycache__/` são
ignorados — o banco não é versionado.

