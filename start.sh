#!/usr/bin/env bash
# Gera os relatórios do banco e serve numa porta livre sorteada.
#
#   ./start.sh                 # porta aleatória, escuta em 0.0.0.0
#   PORT=8000 ./start.sh       # porta fixa
#   ./start.sh Registro        # só um município
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

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
python3 relatorio.py "$@"

echo
echo "Linux/WSL:  http://localhost:$PORT"
[ -n "$IP" ] && echo "Windows:    http://$IP:$PORT"
echo "Ctrl+C para parar."
exec python3 -m http.server "$PORT" --bind 0.0.0.0 --directory relatorios
