# Tarefa 08 — Expansão para Litoral Sul e Vale do Ribeira (25 municípios em 3 regiões)

**Status:** feito
**Depende de:** 01, 05, 06, 07
**Arquivos:** `municipios.csv`, `municipios.py`, `coletor.py`, `relatorio.py`,
`site/src/App.jsx`, `site/check.jsx`, `latex/gerar.py`, `site/public/dados.json`,
`site/public/fichas/*.pdf`
**Testes:** T01.1, T01.4, T06.1–T06.3, T07.1–T07.7

## Objetivo

Ampliar o escopo geográfico para além dos 17 municípios da mesorregião Litoral
Sul Paulista original, incorporando os municípios do Alto Vale do Ribeira e
cabeceiras presentes no catálogo do CIIAGRO. O painel passa a cobrir 25
municípios divididos em 3 regiões geográficas canônicas, com 23 estações ativas
e 23 fichas A4 em PDF de página única.

## Os três recortes geográficos

1. **Litoral Sul** (8 municípios):
   Itanhaém, Itariri, Mongaguá, Pedro de Toledo, Peruíbe, Cananéia, Iguape, Ilha Comprida.
   (4 com estação: Cananéia, Iguape, Itariri, Pedro de Toledo; 4 sem estação:
   Itanhaém, Mongaguá, Peruíbe, Ilha Comprida).

2. **Vale do Ribeira** (9 municípios, todos com estação):
   Barra do Turvo, Cajati, Eldorado, Jacupiranga, Juquiá, Miracatu,
   Pariquera-Açu (2 estações), Registro (2 estações), Sete Barras.

3. **Alto Vale e Cabeceiras** (8 municípios, todos com estação):
   Apiaí, Barra do Chapéu, Iporanga, Itaóca, Itapirapuã Paulista, Juquitiba,
   Ribeira, Tapiraí.

## Subtarefas realizadas

### 08.1 — Esquema e catálogo
- `municipios.csv` atualizado para 25 linhas com coluna `regiao`.
- `municipios.py` atualizado com função `regioes()` que preserva a ordem canônica.
- `coletor.py` migra a tabela `municipio`: `microrregiao` → `regiao`.
- `coletor.py catalogo` vincula os 23 pontos sem perda de dados históricos.

### 08.2 — Relatório e ordenação
- `relatorio.py` exporta `regioes` e `regiao` para cada município, ordenando os
  municípios pela ordem canônica do CSV.

### 08.3 — Front-end e interface
- `site/src/App.jsx` agrupa a lista de estações pelas 3 regiões, exibindo
  títulos de seção (`col-span-full`) que mantêm a navegação limpa e clara.
- Subtítulo ajustado para "Litoral Sul e Vale do Ribeira · CIIAGRO".
- Aviso de municípios sem estação atualizado ("os outros 21 municípios têm").

### 08.4 — Fichas e PDFs
- `latex/gerar.py --pdf` compila todas as 23 fichas.
- Verificação visual e de páginas: 23 PDFs de exatamente 1 página A4 em P&B.
