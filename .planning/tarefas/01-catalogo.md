# Tarefa 01 — Catálogo de municípios e estações

**Status:** feito
**Depende de:** —
**Arquivos:** `municipios.csv`, `municipios.py`, `coletor.py` (`abrir`, `catalogo`),
`fontes/ciiagro.py` (`pontos`, `inicios`, `codigos`, `coordenadas`)
**Testes:** T01.1 a T01.8 em `.planning/testes.md`

## Objetivo

Ter a lista canônica dos 17 municípios e o catálogo das 23 estações do CIIAGRO
no banco, com código, nome, município, latitude, longitude e data de início.
Sem isso nenhuma coleta pode ser amarrada a um lugar.

## Por que isto vem antes da série

A série é inútil sem saber **de quem** ela é. E o catálogo responde de imediato
a pergunta que decide o projeto: quantos dos 17 municípios têm estação, e desde
quando. Rodar a coleta primeiro produziria números bonitos para municípios que
não existem na fonte.

## Subtarefas

### 01.1 — Lista canônica dos 17 municípios

`municipios.csv` com duas colunas: `municipio,microrregiao`. As duas
microrregiões são Itanhaém (5 municípios) e Registro (12). O CSV é **dado, não
código**: quem revisar a lista edita planilha, não Python.

Não usar YAML: exigiria `PyYAML` para 18 linhas. `csv` é stdlib.

### 01.2 — Normalização de nome de município

`municipios.normalizar()` remove acento, troca hífen por espaço, colapsa espaço
e baixa a caixa. `"Pariquera-Açu"` → `"pariquera acu"`.

Necessário porque o CIIAGRO escreve `Cananéia` com acento e `Pariquera-Açu` com
hífen, e a comparação direta de string falha em metade dos casos.

### 01.3 — Casamento estação → município

`municipios.resolver()` tenta, nesta ordem: nome exato normalizado; prefixo cada
vez mais curto (`"registro unesp"` → `"registro"`; `"pariquera acu 2"` →
`"pariquera acu"`); senão `None`.

O prefixo é genérico de propósito: uma lista fixa de sufixos (`unesp`, `2`,
`ii`) quebraria na próxima estação com nome composto. Estação sem município
**não é erro** — são as 8 estações de municípios vizinhos, mantidas como
referência.

### 01.4 — Código numérico da estação

`GET /cbhrb/estacoes/diario/periodo` e regex em
`name="estacao_id[]" value="(\d+)"…>Nome`. É a **única** página que expõe o
código, e o código é a chave de `ponto.id`.

### 01.5 — Data de início

`GET /cbhrb/estacoes/calendario`, tabela `Local | Início das atividades`,
convertida de `dd/mm/aaaa` para `AAAA-MM-DD` para comparar direto com `fato.data`.

O site tem lixo aqui: `Itariri` aparece com `31/12/1969`, que é epoch, não
fundação. O valor é guardado como veio e `auditar` alerta `início suspeito`.

### 01.6 — Coordenadas

`GET /cbhrb/estacoes/` e regex em `L.marker([lat,lon], {title:"Nome"})`.
As coordenadas estão no HTML do próprio mapa — não precisa de DevTools, XHR,
GeoJSON, geocodificação nem API do IBGE.

### 01.7 — Esquema e UPSERT

`coletor.abrir()` cria `municipio`, `ponto` e `fato` com `IF NOT EXISTS`.
`coletor.catalogo()` faz UPSERT por `municipio.nome` e `ponto.id`, **sem tocar em
`fato`**: recoletar o catálogo não pode apagar série.

## Critério de aceite

- [x] `python3 coletor.py catalogo` imprime `17 municípios, 23 estações (15 dentro dos 17, 8 fora do escopo)`
- [x] Toda estação tem código, nome, latitude, longitude e data de início
- [x] Estação de município vizinho entra com `municipio_id = NULL`, não é descartada
- [x] Rodar `catalogo` duas vezes não duplica nem apaga linha
- [x] Nenhuma requisição além das 3 páginas de catálogo

## Decisões

- **`ponto.id` = código do CIIAGRO**, não um id artificial. Preserva a
  rastreabilidade e evita um mapa de tradução a mais.
- **As 8 estações fora dos 17 ficam no banco.** Custo zero, e servem de
  referência para interpolação futura.
- **Data de início do site é guardada crua.** Corrigir `1969` na importação
  esconderia o problema; `auditar` mostra.
