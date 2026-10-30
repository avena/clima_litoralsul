#!/usr/bin/env bash
# Exporta os dados, valida, builda e publica: o push é o deploy (Netlify/Vercel).
#
#   ./deploy.sh              # regenera o JSON e empurra para main
#   ./deploy.sh "mensagem"   # mesma coisa com mensagem de commit própria
#
# Só commita `site/public/dados.json`. Alteração de código você commita antes:
# o script aborta se houver outra coisa pendente, em vez de esconder no commit
# de dados.
set -euo pipefail
cd "$(dirname "$0")"

python3 relatorio.py
python3 -m unittest discover -s tests -q
npm --prefix site run check
npm --prefix site run build

if [ -n "$(git status --porcelain -- . ':!site/public/dados.json')" ]; then
  echo "Há alteração pendente fora de dados.json — commite antes de publicar:" >&2
  git status --short -- . ':!site/public/dados.json' >&2
  exit 1
fi

if git diff --quiet -- site/public/dados.json; then
  echo "dados.json sem mudança; nada a commitar."
else
  git add site/public/dados.json
  git commit -q -m "${1:-chore(dados): atualiza a série ($(date +%F))}"
fi

git push
echo "publicado: https://clima-litoralsul.netlify.app"
