# clima_litoralsul

Série climática dos **17 municípios da mesorregião Litoral Sul Paulista**
(microrregiões de Itanhaém e Registro), a partir das estações do
[CIIAGRO](http://www.ciiagro.org.br).

Coleta em **Python 3.12 só com stdlib** (`urllib`, `sqlite3`, `re`, `json`,
`unittest`). O painel é um **SPA React + Tailwind v4** em `site/`, buildado com
Vite. Sem banco externo, sem servidor de aplicação, sem CDN em runtime.

## Onde está cada coisa

| Arquivo | Responsável por | Como rodar |
|---|---|---|
| `municipios.csv` | os 17 municípios (nome, microrregião) — a lista é entrada fixa, não vem do site | — |
| `municipios.py` | lê o CSV e cria/atualiza `municipio` | chamado por `coletor.py` |
| `coletor.py` | **CLI e banco**: schema, `abrir`, `catalogo`, `coletar`, `auditar` e a consolidação (`substituir_granularidade`, `atualizar_primeiro_fato`) | `python3 coletor.py …` |
| `fontes/ciiagro.py` | **raspagem**: POST nos endpoints, regex no `addRows` do HTML, devolve `{estação: {coluna: valor}}`. Não conhece `sqlite3` | chamado por `coletor.py` |
| `relatorio.py` | **agregação e export**: médias por mês do ano, chuva anual, estações do ano, faixa de sanidade, rótulo "normal climatológica" → `site/public/dados.json` | `python3 relatorio.py` |
| `site/` | **render**: SPA React (um único `dados.json`, troca de município sem recarregar) + Tailwind v4 | `npm --prefix site run dev` |
| `start.sh` | exporta, builda e serve numa porta livre em `0.0.0.0` | `./start.sh` |
| `tests/` | 25 testes Python sobre HTML real em `tests/fixtures/` | `python3 -m unittest discover -s tests` |
| `dados/clima.sqlite` | banco (gitignorado, gerado pela coleta) | — |
| `.planning/` | plano, tarefas e catálogo de testes — comece por `.planning/PLANO.md` | — |

O fluxo é sempre o mesmo, e cada etapa é um arquivo separado:

```
CIIAGRO (HTML)
   │  fontes/ciiagro.py        raspagem: urllib + regex no addRows
   ▼
dados/clima.sqlite             coletor.py: schema, upsert, consolidação
   │  relatorio.py            agregação + faixa de sanidade
   ▼
site/public/dados.json         (versionado: é o que o deploy usa)
   │  site/ (Vite + React)    render
   ▼
site/dist/                     estático: Netlify, Vercel ou qualquer host
```

## Começar

```bash
python3 coletor.py catalogo                                    # 3 requisições
python3 coletor.py coletar --desde 2000-01 --ate 2026-10       # mensal, ~2 min
python3 coletor.py auditar                                     # cobertura; não escreve
python3 relatorio.py                                           # gera dados.json
```

`coletar` sem `catalogo` não grava nada: o banco resolve a estação **por nome**,
e o que não estiver em `ponto` é ignorado com aviso "fora do catálogo".

Mês anterior a 2000 responde em ~1,5 s (contra ~0,24 s dos recentes), então
varredura longa precisa rodar em background — `timeout` no meio não dá erro, só
trunca a série.

## Ver o painel

```bash
./start.sh                # export + build + http.server em porta livre
./start.sh --dev          # Vite dev com hot reload
PORT=8000 ./start.sh      # porta fixa
```

O script imprime a URL de `localhost` e a do IP do WSL; escuta em `0.0.0.0`,
então o navegador do Windows alcança. Precisa de Node 20+ só para o `site/`; a
coleta continua sem dependência nenhuma.

O painel abre com os 17 municípios em cards (nome, número de estações e
período): clicar troca a cidade sem recarregar e sem piscar, e a URL guarda a
escolha (`#/registro`) para poder ser compartilhada. Abaixo vêm os cards de KPI
(chuva anual, temperatura média, amplitude sazonal, UR), o climatograma de eixo
duplo (chuva em barras, T mín/méd/máx em linhas, faixa térmica sombreada), a
distribuição sazonal da chuva e a matriz mensal com micro-barras. Layout de uma
coluna no celular; no gráfico, o toque fixa o mês que o hover mostra no desktop.

No rodapé ficam a data de sincronização do `dados.json`, o período coberto, o
hash do build e do commit inicial, o link do repositório e o resumo do ambiente.

## Deploy (Netlify ou Vercel)

Build estático, sem backend. `dados.json` é **versionado** justamente porque o
deploy não tem acesso ao banco (que é gitignorado):

```bash
python3 relatorio.py       # atualiza site/public/dados.json
git add site/public/dados.json && git commit -m "chore(dados): atualiza a série"
git push
```

- **Netlify**: `netlify.toml` já define base `site`, `npm run build`, publish
  `dist`. Conecte o repositório e pronto.
- **Vercel**: `vercel.json` roda `cd site && npm run build` e publica
  `site/dist`.
- **Hook manual** (`.github/workflows/deploy.yml`): criado para forçar o build
  da plataforma quando os dados mudam sem mudar código. Salve a URL do hook em
  `NETLIFY_DEPLOY_HOOK_URL` e/ou `VERCEL_DEPLOY_HOOK_URL` nos *Secrets* do
  GitHub; o passo correspondente só roda se o secret existir.

Rota é hash (`#/pariquera-acu`), então não precisa de rewrite no servidor.

## O que a fonte entrega

| Endpoint | Conteúdo |
|---|---|
| `diario/cdiaria` (POST `data=dd/mm/aaaa`) | **todas** as estações num dia: T e UR mín/média/máx, chuva |
| `mensal/cmensal` (POST `parametro=mm/aaaa`) | agregados mensais, todas as estações |
| `horario.php?codigo=N` | janela rolante de 7 dias — **sem histórico**, por mais que pareça a página certa |

Não há API. Os números vêm em `data.addRows([['Registro',17.1,21.5,25.9],…])`
dentro do HTML; o extrator é regex, testado contra HTML real em `tests/fixtures/`.

## Cobertura medida (do banco, não do calendário do site)

4.914 linhas mensais, `1990-01` a `2026-10`, 23 estações.

- **≥30 anos de dado**: Pariquera-Açu (34,1), Registro (31,6) — só alcançam isso
  porque o CIIAGRO serve série anterior ao início que ele mesmo declara
  (`/calendario` diz 2004 e 2005).
- **20-29 anos**: Miracatu (26,9), Cananéia (26,8), Sete Barras (26,7),
  Jacupiranga (25,8).
- **13-19 anos**: Iguape, Ribeira, Tapiraí, Juquitiba, Itariri, Eldorado,
  Registro Unesp, Apiaí, Cajati, Iporanga, Itaóca, Juquiá.
- **6-8 anos**: Pedro de Toledo, Pariquera-Açu 2, Barra do Chapéu, Barra do
  Turvo, Itapirapuã Paulista.
- **Sem estação CIIAGRO**: Itanhaém, Mongaguá, Ilha Comprida. Peruíbe só na rede
  principal (`/ema/index.php?id=56`), fora desta versão.

**13 dos 17 municípios** têm estação — 15 é o número de estações, porque Registro
e Pariquera-Açu têm duas cada. As 8 estações de municípios vizinhos ficam no
banco com `municipio_id` nulo, como referência.

## Duas armadilhas que mudam interpretação

1. **O site serve dados antes de a estação existir.** Registro tem 380 mm em
   `01/1995`, mas começou em 2005. Pode ser registro histórico convencional ou
   reconstrução — só o cruzamento com o INMET decide. Até lá, série
   pré-automação é `suspeita` e o `auditar` mostra o caso em cada estação.
2. **`0` significa "sem medição", não "zero".** Em `01/2001` todas as estações
   reportam `0.00 %` de umidade. Some com o "vazio" que a página devolve sem
   motivo aparente e você tem uma seca que nunca aconteceu.

## Banco

`dados/clima.sqlite`, três tabelas: `municipio`, `ponto`, `fato`.

- `ponto.id` é o código da estação no CIIAGRO (ex.: `63` = Registro).
- `fato.data` em `AAAA-MM-DD` (dia) ou `AAAA-MM` (mês) — `length(data)` é a
  granularidade, e um mês guarda **ou** o total mensal **ou** os dias.
- `INSERT … ON CONFLICT DO UPDATE` com `COALESCE`: recoletar não duplica nem
  apaga.

A faixa de sanidade (T em [-20, 50] °C, UR em [0, 100], chuva/mês ≤ 1000 mm) só
existe no `relatorio.py`: valor fora fica no banco e sai da média, contado como
descarte.

## Limitações

- Sem INMET ou NASA POWER: 3 municípios sem estação e séries curtas continuam curtas.
- Sem insolação (estação automática não mede) e sem ET0.
- Sem "dias com chuva ≥ 1 mm": o banco é mensal; exige `coletar --diario` antes.
- Sem normal climatológica publicável: 30 anos de dado medido não é o mesmo que
  normal 1991-2020 do INMET, e o painel só usa o rótulo quando a série valida.
- Coleta respeita o servidor: 0,25 s entre requisições, 3 tentativas, User-Agent
  próprio.

Dados pertencem ao CIIAGRO / Governo do Estado de São Paulo — verifique os
termos de uso antes de redistribuir.
