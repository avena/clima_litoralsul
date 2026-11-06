# Plano — clima_litoralsul

Série climática dos 25 municípios do **Litoral Sul Paulista + Vale do Ribeira**
(faixa costeira, baixo/médio curso e Alto Vale), a partir do CIIAGRO. Escopo
aprovado: **só CIIAGRO, escopo honesto** — nenhuma estimativa apresentada como
medição. A tarefa 09 acrescenta o arquivo histórico do INMET como segunda
fonte, nacional e de série longa.

## Índice

| Documento | Conteúdo |
|---|---|
| `tarefas/01-catalogo.md` | 17 municípios + 23 estações, coordenadas, datas de início (histórico; hoje 25 + 23) |
| `tarefas/07-ficha-a4.md` | ficha A4 em LaTeX, preto e branco, e uso no planejamento |
| `tarefas/08-litoral-e-vale.md` | 25 municípios em 3 regiões: Litoral Sul, Vale do Ribeira, Alto Vale |
| `tarefas/09-inmet-historico.md` | INMET nacional 2000–2026: mensal/anual, relatório e painel |
| `tarefas/02-extrator.md` | HTML do CIIAGRO → 8 colunas canônicas |
| `tarefas/03-coletor.md` | série histórica, UPSERT, invariante mês/dia |
| `tarefas/04-auditoria.md` | cobertura e valores suspeitos |
| `tarefas/05-relatorio.md` | agregação e export `dados.json` |
| `tarefas/06-painel-react.md` | SPA React + Tailwind, deploy Netlify/Vercel |
| `testes.md` | catálogo de cada teste e o que ele garante |
| `arquivo/PLANOSDEEPSEEK/` | material descartado, guardado como evidência |

| # | Tarefa | Depende de | Status |
|---|---|---|---|
| 01 | Catálogo | — | **feito** |
| 02 | Extrator | — | **feito** |
| 03 | Coletor | 01, 02 | **feito** |
| 04 | Auditoria | 03 | **feito** |
| 05 | Relatório | 04 | **feito** (JSON) |
| 06 | Painel React | 05 | **feito** |
| 07 | Ficha A4 | 05, 06 | **feito** (PDF P&B) |
| 08 | Litoral e Vale | 01, 05, 06, 07 | **feito** (25 municípios, 3 regiões) |
| 09 | INMET histórico | 05, 06 | **feito** (nacional 2000–2026) |

---

## 1. O que a fonte realmente oferece (verificado em 2026-10-30)

| Endpoint | Método | Conteúdo | Serve? |
|---|---|---|---|
| `/cbhrb/estacoes/diario/cdiaria` | POST `data=dd/mm/aaaa` | todas as estações do dia: T e UR mín/méd/máx, chuva | **sim** |
| `/cbhrb/estacoes/mensal/cmensal` | POST `parametro=mm/aaaa` | agregados mensais, todas as estações | **sim** |
| `/cbhrb/horario.php?codigo=N` | GET | janela rolante 7 dias / 24 h, **ignora parâmetro de data** | não |
| `/cbhrb/estacoes/diario/cperiodo` | POST | um resumo por estação, não uma série | não |
| `/cbhrb/estacoes/calendario` | GET | nome + início das atividades | sim (catálogo) |
| `/cbhrb/estacoes/diario/periodo` | GET | nome → `estacao_id` | sim (catálogo) |
| `/cbhrb/estacoes/` | GET | `L.marker([lat,lon], {title:"Nome"})` | sim (coordenadas) |

Não existe API pública. O dado vem embutido no HTML como
`data.addRows([['Registro',17.1,21.5,25.9], …])` — regex resolve, sem parser de
HTML, sem browser. Testado a 4 req/s sem rate-limit; a coleta usa 0,25 s de pausa
por educação, não por necessidade. Nenhuma requisição tem autenticação, sessão
ou cookie.

**A armadilha do nome:** `horario.php?codigo=N` responde 200 e parece a página
certa, mas devolve a janela rolante de 7 dias. Testado com `&data=2015-01-01`,
`&dia=`, `&data=2015-01-01`: todos ignorados. É a página mais atraente e a menos
útil do site.

## 2. As duas armadilhas que definem o projeto

### 2.1 Dado antes da estação existir

| Estação | início (`/calendario`) | dado servido |
|---|---|---|
| Registro | 11/10/2005 | 380,2 mm em 01/1995 |
| Pariquera-Açu | 16/06/2004 | 303,8 mm em 01/1995 |
| Cananéia | 31/08/2000 | `1` mm em 01/2000 (placeholder) |

Pode ser registro histórico convencional (ótimo, dá 30 anos) ou reconstrução
(inútil). Só o cruzamento com o INMET decide. Até lá a série pré-automação é
`suspeita` e `auditar` mostra o caso por estação. Nada é apagado na coleta.

### 2.2 `0` e "sem dado"

`01/2001` devolve `0.00` de umidade para todas as estações. `0` não é medição, é
sensor ausente. E período inválido devolve 200 com zero blocos, indistinguível
de "estação fora do ar". Por isso: ausente é `NULL`, e a coleta grita quando um
período inteiro vem vazio.

## 3. Cobertura medida (do banco, em 2026-10-30 — não estimada)

4.914 linhas, todas mensais, `1990-01` a `2026-10`. Anos de dado ≠ anos de
intervalo: Miracatu cobre 36 anos de calendário com 26,9 anos de dado.

| Estação | Município | Desde | Meses | Anos de dado |
|---|---|---|---|---|
| Miracatu | Miracatu | 1990-01 | 323 | 26,9 |
| Pariquera-Açu | Pariquera-Açu | 1992-10 | **409** | **34,1** |
| Registro | Registro | 1994-11 | 379 | **31,6** |
| Cananéia | Cananéia | 2000-01 | 321 | 26,8 |
| Sete Barras | Sete Barras | 2000-03 | 320 | 26,7 |
| Jacupiranga | Jacupiranga | 2000-03 | 310 | 25,8 |
| Iguape | Iguape | 2004-01 | 219 | 18,2 |
| Eldorado | Eldorado | 2000-03 | 197 | 16,4 |
| Ribeira | Ribeira | 2005-11 | 238 | 19,8 |
| Tapiraí | Tapiraí | 2005-08 | 231 | 19,2 |
| Juquitiba | Juquitiba | 2008-01 | 216 | 18,0 |
| Itariri | Itariri | 2008-05 | 213 | 17,8 |
| Apiaí | Apiaí | 2011-01 | 189 | 15,8 |
| Registro Unesp | Registro | 2009-09 | 191 | 15,9 |
| Cajati | Cajati | 2011-02 | 185 | 15,4 |
| Iporanga | Iporanga | 2011-01 | 184 | 15,3 |
| Itaóca | Itaóca | 2011-01 | 184 | 15,3 |
| Juquiá | Juquiá | 2008-05 | 158 | 13,2 |
| Barra do Chapéu | Barra do Chapéu | 2018-08 | 99 | 8,2 |
| Pedro de Toledo | Pedro de Toledo | 2018-08 | 99 | 8,2 |
| Pariquera-Açu 2 | Pariquera-Açu | 2018-08 | 97 | 8,1 |
| Barra do Turvo | Barra do Turvo | 2018-08 | 76 | 6,3 |
| Itapirapuã Paulista | Itapirapuã Paulista | 2018-08 | 76 | 6,3 |

**Três séries começam antes do que o `/calendario` declara** e isso não era
sabido quando o plano foi escrito: Pariquera-Açu `1992-10` (11,7 anos antes),
Registro `1994-11` (10,9 antes), Miracatu `1990-01`. Nenhuma célula nula de
`tmed` ou `chuva` nas três. É o que permite, pela primeira vez, falar em
normal climatológica — **se** o dado pré-automação for registro convencional.
Se for reconstrução, é número bonito sem base. Só o INMET decide, e nada foi
descartado: `auditar` marca as três com `dado antes do início`.

**21 dos 25 municípios têm estação** (23 é o número de *estações*, porque
Registro e Pariquera-Açu têm duas cada). Sem nenhuma: Itanhaém, Mongaguá, Ilha
Comprida e Peruíbe — esta última só na rede principal
(`/ema/index.php?id=56`), com navegação diferente, fora desta versão.

As 8 estações do Alto Vale e Cabeceiras (Apiaí, Barra do Chapéu, Iporanga,
Itaóca, Itapirapuã Paulista, Juquitiba, Ribeira, Tapiraí) foram integradas na
tarefa 08, formando os 3 recortes geográficos do painel: Litoral Sul, Vale do
Ribeira e Alto Vale e Cabeceiras.

**Consequência:** A série real de cada município é declarada individualmente,
com honestidade metodológica e sem interpolação.

## 4. Arquitetura

```
coletor.py          CLI + SQLite (schema, upsert, invariante, auditoria)
relatorio.py        lê o banco e escreve site/public/dados.json
fontes/ciiagro.py   FONTE, pontos(), fatos() — não conhece o banco
municipios.py       os 25 municípios em 3 regiões + casamento de nome de estação
municipios.csv      dados, não código (municipio, regiao)
site/               SPA React + Tailwind v4 (Vite) sobre dados.json
start.sh            export + build + http.server numa porta livre
tests/              31 testes contra HTML real em tests/fixtures/
```

A camada de cálculo e a de render são separadas de propósito: o número é
produzido em Python (com teste) e o React não recalcula nada. `site/` é o único
lugar do repositório que precisa de Node.

Contrato de uma fonte: `FONTE`, `pontos() -> list[dict]`, `fatos(desde, ate) ->
Iterator[dict]`. Duas funções. A fonte devolve **o nome da estação**; o banco
resolve para `ponto.id`. Assim `fontes/*.py` nunca importa `sqlite3`, e adicionar
INMET é adicionar um arquivo.

### Schema

```sql
municipio(id INTEGER PRIMARY KEY, nome TEXT UNIQUE, regiao TEXT);
ponto(id TEXT PRIMARY KEY, fonte TEXT, nome TEXT, municipio_id INTEGER,
      lat REAL, lon REAL, inicio_auto TEXT, primeiro_fato TEXT);
fato(ponto_id TEXT, data TEXT, tmin REAL, tmed REAL, tmax REAL,
     urmin REAL, urmed REAL, urmax REAL, chuva REAL, PRIMARY KEY(ponto_id, data));
```

- `length(data)` **é** a granularidade. Sem coluna `gran` para dessincronizar.
- **Invariante**: para cada `(ponto, mês)` existe OU a linha mensal OU os dias,
  garantido por `substituir_granularidade`. Sem isso um `SUM` por mês soma os dois.
- UPSERT com `COALESCE(excluded.x, x)` — recoletar não duplica nem apaga.

## 5. Ambiente de destino (verificado em `~/dreamhost`)

| Item | Realidade |
|---|---|
| Python | 3.12.3, `/usr/bin/python3`, CPython, glibc 2.39 |
| Web | **só CGI**. Phusion Passenger removido de todos os planos |
| Deploy | repo bare + hook `post-receive`, sem SFTP |

Logo: coleta por **cron** no shell, painel é **build estático** (Netlify/Vercel) a
partir de `site/public/dados.json`. `Flask`, `web/`, `passenger_wsgi.py` e
`requirements.txt` não entram.

## 6. Revisão do material `arquivo/PLANOSDEEPSEEK/`

Gerado por outra ferramenta; ~1.900 linhas, 26 testes verdes. Aproveitado: a lista
dos 17 municípios, o parsing pt-BR e a ideia das 8 linhas da tabela climática.
Descartado, com motivo:

| Item | Problema |
|---|---|
| Coletor em `horario.php` | devolve 7 dias e ignora data — **não produz série histórica**, que é o objetivo |
| Eixo de coleta | 23 requisições para 1 data; `cdiaria` dá as 23 estações num POST |
| `selectors.py` | o próprio arquivo diz "CANDIDATOS, NÃO VALIDADOS"; e o cabeçalho `Mínima` repete 3×, quebrando o mapeamento por nome de coluna |
| `README.md` | corrompido: contém `</BDS:create_file>` e o `requirements.txt` embutido |
| `passenger_wsgi.py` | mira Passenger, removido da DreamHost |
| Scrapy + MCP | 3 endpoints, sem crawl. `urllib` faz o mesmo sem infraestrutura |
| `tabela_clima.py` | rótulos "recorde" e "compensada" cravados mesmo com `n_anos=2`, anulando o rodapé honesto |
| `web/` (Flask) | não roda no Shared |
| Tabela Wikipédia | pesquisa inédita sem normais publicadas |

Os 26 testes dele provavam a matemática. Nenhum tocava a raspagem — daí README
verde com coletor que não coleta.

## 7. Decisões registradas

- **Mensal primeiro.** 315 requisições (~2 min) contra 9.560 (~80 min) para a
  mesma janela. O mensal não permite veranico; `--diario` grava no mesmo `fato`.
- **Sem view de consolidação.** Uma `VIEW` com `ROW_NUMBER` foi escrita e
  removida: escolhia o dia sobre o mês e, com mês parcial, somava só parte do mês.
  A regra certa não é "dia vence" — é "um dos dois existe". A view volta na
  tarefa 07, quando houver uma segunda fonte real para justificar a escolha.
- **Sem framework de teste.** `unittest` da stdlib, 23 testes, ~0,6 s, sem rede.
- **Git em `main`, histórico linear**, primeiro commit só com `README.md`;
  `dados/` e `__pycache__/` fora do versionamento.

## 8. Pendências, em ordem

1. **Faixa de sanidade em `auditar`** (tarefa 06, a criar). No relatório já
   existe (`LIMITES` em `relatorio.py`: T em [-20, 50], chuva mensal ≤ 1000, UR
   em [0, 100]) e o descarte é contado no rodapé. Falta o mesmo no `auditar`,
   para `tmed = 873,35` de Miracatu em `03/1990` não passar limpo.
2. **Origem do dado pré-2000.** Pariquera-Açu e Registro passam de 30 anos; a
   palavra "normal climatológica" só entra depois do cruzamento com o INMET —
   hoje o relatório as chama de "médias do período … não validada".
3. **Peruíbe**, que só existe em `/ema/index.php?id=56` — outra navegação, outra
   tarefa.
4. **Série diária** (`--diario`), só quando veranico e dias secos forem
   necessários. O banco já suporta, via `substituir_granularidade`. É também o
   que destrava a coluna "dias com chuva ≥ 1 mm", hoje fora do relatório.
