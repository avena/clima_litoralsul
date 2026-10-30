# Tarefa 06 — Painel React (SPA)

**Status:** feito
**Depende de:** 05
**Arquivos:** `site/`, `start.sh`, `netlify.toml`, `vercel.json`,
`.github/workflows/deploy.yml`
**Testes:** T06.1 em `.planning/testes.md` (`npm --prefix site run check`)

## Objetivo

Um painel único que troca de município sem recarregar a página, com o visual do
mockup do Stitch e os números do banco — nunca dados cravados no JavaScript.

## Subtarefas

### 06.1 — Dados vêm do Python

`relatorio.py` exporta `site/public/dados.json` (38 KiB, 15 estações). Média,
chuva anual, estação do ano, faixa de sanidade e rótulo são calculados ali, onde
há teste. O React não recalcula nada: se recalculasse, existiriam duas versões
da mesma mentira possível.

`dados.json` é versionado: o deploy não vê `dados/clima.sqlite` (gitignorado).

### 06.2 — Troca de município sem reload

Estado do React (`useState`) + rota em hash **por estação** (`#/registro-unesp`).
Hash porque dispensa rewrite de rota no host; `hashchange` mantém voltar/avançar
e link compartilhado funcionando.

A primeira versão listava municípios num `<select>` e deixava as duas estações
de Registro e Pariquera-Açu como abas. Trocado por um grid de cards — a escolha
fica visível para quem não sabe que existe um menu — e cada estação passou a ter
card e URL próprios (`relatorio.py` exporta `slug` e `municipio` por estação).
Município sem estação continua com card, porém desativado (`aria-disabled`,
`cursor-not-allowed`): sumir seria dizer que o município não existe, mas card
clicável prometeria uma série que não há. A rota antiga (`#/itanhaem`) ainda
abre o aviso, para link já compartilhado não virar tela vazia.

### 06.3 — Componentes

- `Card`: KPI com rótulo, valor, unidade e até três linhas de detalhe.
- `Climatograma`: SVG de eixo duplo — chuva em barras (mm, esquerda) e t
  mín/méd/máx em linhas (°C, direita), com o envelope térmico sombreado entre
  mín e máx, um polígono por trecho contínuo (não liga meses com buraco). A
  legenda é o filtro de séries; com uma só visível, o valor de cada mês é
  impresso no gráfico (modo leitura). Desmarcar a última não é permitido, para
  não sobrar um gráfico mudo.
- `Ranking`: chuva anual de todas as estações, da maior para a menor, com a
  estação aberta destacada.
- `Sazonal`: barras horizontais DJF/MAM/JJA/SON, em mm e em %.
- `Tabela`: matriz mensal com micro-barra proporcional ao mês mais chuvoso.

Mês sem medição é `—` e não desenha barra nem ponto. Hover no gráfico alimenta
uma faixa de inspeção com chuva, T mín/méd/máx, UR e `n` do mês.

### 06.4 — Tailwind v4 buildado, sem CDN

`@tailwindcss/vite` + `@import "tailwindcss"` com o tema em `@theme`
(`--color-fundo`, `--color-chuva`, …). O Play CDN foi rejeitado: compila CSS no
navegador, exige internet e o próprio Tailwind o declara "dev only" — ou seja,
flash de página sem estilo, exatamente o que o painel deveria evitar.

Efeito colateral aceito: `site/` precisa de Node 20+ para buildar. Nada do
pipeline Python depende disso.

### 06.5 — Deploy estático

`netlify.toml` (base `site`) e `vercel.json` (`cd site && npm run build`,
`site/dist`). `site/dist` e `site/node_modules` são gitignorados;
`site/public/dados.json` não. `.github/workflows/deploy.yml` chama o deploy hook
da plataforma quando `site/**` muda, com `always_deploy: true` — o hook é útil
justamente no commit que só troca dados.

## Critério de aceite

- [x] Trocar de município não recarrega a página nem pisca
- [x] Nenhum número escrito à mão no JSX: tudo vem de `dados.json`
- [x] Climatograma de eixo duplo com envelope térmico
- [x] Município sem estação mostra aviso, não gráfico de zeros
- [x] Aviso de série não validada e contagem de descartes visíveis
- [x] `npm run build` gera `site/dist` sem dependência de CDN
- [x] `npm run check` renderiza o painel fora do navegador e falha em regressão
- [x] `./start.sh` continua servindo numa porta livre, acessível do Windows

## Fora de escopo

- **Exportar CSV/PNG a partir do painel:** botão que baixa precisa de backend ou
  de biblioteca de canvas; hoje é ruído visual.
- **Mapa das estações:** exige GeoJSON e decisão sobre coordenadas não
  verificadas do `/calendario`.
- **Filtro por período:** o painel mostra a série inteira; recorte por ano exige
  agregar de novo no cliente e um controle que ninguém pediu ainda.
