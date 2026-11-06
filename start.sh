#!/usr/bin/env bash
# Exporta os dados, builda o dashboard e serve numa porta livre sorteada.
#
#   ./start.sh                 # porta aleatória, escuta em 0.0.0.0
#   PORT=8000 ./start.sh       # porta fixa
#   ./start.sh --dev           # atalho: vite dev, com hot reload (sem build)
#
# Escutar em 0.0.0.0 é o que deixa o navegador do Windows alcançar o WSL:
# http://<ip-do-wsl>:<porta>. Em WSL2, http://localhost:<porta> costuma
# funcionar também, porque o Windows encaminha localhost para o Linux.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-$(python3 - <<'PY'
import socket
with socket.socket() as s:
    s.bind(("0.0.0.0", 0))          # porta 0 = o SO sorteia uma livre
    print(s.getsockname()[1])
PY
)}"

# Porta opcional dedicada para a página do INMET (pode vir de PORT_INMET ou argumento)
PORT_INMET="${PORT_INMET:-}"
if [ "${1:-}" = "--inmet-porta" ] && [ -n "${2:-}" ]; then
  PORT_INMET="$2"
  shift 2
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"

echo "================================================================"
echo "  Observatório Agroclimático do Litoral Sul e Vale do Ribeira   "
echo "================================================================"
echo "Painel Climatológico (25 municípios):"
echo "  -> Linux/WSL:  http://localhost:$PORT"
[ -n "$IP" ] && echo "  -> Windows:    http://$IP:$PORT"
echo
echo "Dados Históricos INMET (rede nacional, 705 estações):"
echo "  -> Linux/WSL:  http://localhost:$PORT/inmet.html"
[ -n "$IP" ] && echo "  -> Windows:    http://$IP:$PORT/inmet.html"

if [ -n "$PORT_INMET" ]; then
  echo
  echo "Servidor Dedicado INMET (porta alternativa):"
  echo "  -> Linux/WSL:  http://localhost:$PORT_INMET"
  [ -n "$IP" ] && echo "  -> Windows:    http://$IP:$PORT_INMET"
fi
echo
echo "Ctrl+C para parar."
echo "================================================================"
echo

python3 relatorio.py

[ -d site/node_modules ] || npm --prefix site install --no-fund --no-audit

if [ "${1:-}" = "--dev" ]; then
  exec npm --prefix site run dev -- --host 0.0.0.0 --port "$PORT" --strictPort
fi

npm --prefix site run build

if [ -n "$PORT_INMET" ]; then
  # Sobe servidor dedicado na outra porta
  trap 'kill $(jobs -p) 2>/dev/null' EXIT
  python3 -m http.server "$PORT_INMET" --bind 0.0.0.0 --directory site/dist &
fi

exec python3 -m http.server "$PORT" --bind 0.0.0.0 --directory site/dist
