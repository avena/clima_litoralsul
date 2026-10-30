#!/usr/bin/env bash
# Exporta os dados, valida, builda e publica: o push é o deploy (Netlify/Vercel).
#
#   ./deploy.sh              # regenera o JSON e empurra para main
#   ./deploy.sh "mensagem"   # mesma coisa com mensagem de commit própria
#
# Commita só o que é gerado: `site/public/dados.json` e os PDFs em
# `site/public/fichas/`. Alteração de código você commita antes: o script aborta
# se houver outra coisa pendente, em vez de esconder no commit de dados.
set -euo pipefail
cd "$(dirname "$0")"

# O Netlify não tem TeX: o PDF sai daqui, versionado, e o build só copia
# `public/` para `dist/`. Sem tectonic na máquina, os PDFs antigos ficam como
# estão — melhor publicar ficha de ontem do que não publicar.
if command -v tectonic >/dev/null; then
  python3 latex/gerar.py --pdf
else
  echo "tectonic ausente: fichas .tex regeneradas, PDFs em site/public/fichas mantidos" >&2
  python3 latex/gerar.py
fi

python3 relatorio.py
python3 -m unittest discover -s tests -q
npm --prefix site run check
npm --prefix site run build

GERADOS='site/public/dados.json site/public/fichas'
if [ -n "$(git status --porcelain -- . ':!site/public/dados.json' ':!site/public/fichas')" ]; then
  echo "Há alteração pendente fora dos arquivos gerados — commite antes de publicar:" >&2
  git status --short -- . ':!site/public/dados.json' ':!site/public/fichas' >&2
  exit 1
fi

if git diff --quiet -- $GERADOS && [ -z "$(git status --porcelain -- $GERADOS)" ]; then
  echo "dados.json e PDFs sem mudança; nada a commitar."
else
  git add $GERADOS
  git commit -q -m "${1:-chore(dados): atualiza a série ($(date +%F))}"
fi

git push
echo "publicado: https://climalitoralsul.netlify.app"
