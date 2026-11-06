#!/usr/bin/env bash
# Update diário: raspa o que falta, regenera o JSON, builda e publica.
#
#   ./update-diario.sh
#
#   cron: 15 6 * * *  /home/livre/clima_litoralsul/update-diario.sh >> /tmp/update-diario.log 2>&1
#
# `set -e` de propósito: se a coleta falhar, o deploy não roda — publicar
# série pela metade é pior do que publicar a de ontem.
set -euo pipefail
cd "$(dirname "$0")"

python3 coletor.py atualizar
./deploy.sh
# O deploy só acontece em push para `main`; o push acima foi do branch atual
# (`dev`). Fast-forward explícito: se `main` divergiu, o git recusa em vez de
# publicar outra coisa.
git push origin HEAD:main
