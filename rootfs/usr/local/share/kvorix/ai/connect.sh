#!/usr/bin/env bash
# Kvorix: подключение ИИ-агента к приставке (Linux / macOS / Git Bash на Windows).
#   bash connect.sh               — открыть туннель: localhost:2401 → SSH приставки
#   bash connect.sh run 'команда' — выполнить команду на приставке (пользователь agent, sudo без пароля)
#   bash connect.sh stop          — закрыть туннель
# Рядом должен лежать файл id_ed25519 (ключ из Настройки → Доступ ИИ).
set -euo pipefail
TOPIC="@TOPIC@"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEY="$DIR/id_ed25519"; PORT=2401
O=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=10
   -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -o BatchMode=yes -i "$KEY")
chmod 600 "$KEY" 2>/dev/null || true

kill_tun() {
    if command -v pkill >/dev/null; then pkill -f "ssh .*-L ${PORT}:127.0.0.1:22" 2>/dev/null || true
    else powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='ssh.exe'\" | ? { \$_.CommandLine -like '*-L ${PORT}:*' } | % { Stop-Process -Id \$_.ProcessId -Force }" 2>/dev/null || true; fi
}
alive() { ssh -p $PORT "${O[@]}" agent@127.0.0.1 true >/dev/null 2>&1; }

open_tun() {
    alive && return 0
    kill_tun
    # приставка публикует свежие коды сессий upterm в своей теме ntfy
    codes=$( { curl -sf -m 15 "https://ntfy.sh/$TOPIC/json?poll=1&since=12h"; curl -sf -m 15 "https://ntfy.hostux.net/$TOPIC/json?poll=1&since=12h"; } \
             | grep -oE 'SESSION [A-Za-z0-9]+' | awk '{print $2}' | tac | awk '!s[$0]++' | head -6 || true)
    for c in $codes; do
        ssh -fN -o ExitOnForwardFailure=yes -L $PORT:127.0.0.1:22 "${O[@]}" "$c:uptermd.upterm.dev@uptermd.upterm.dev" 2>/dev/null || continue
        sleep 1; alive && { echo "туннель открыт: ssh -p $PORT -i $KEY agent@127.0.0.1"; return 0; }
        kill_tun
    done
    echo "не удалось подключиться: приставка выключена или в Настройки → Доступ ИИ доступ выключен" >&2; return 1
}

case "${1:-open}" in
    stop) kill_tun ;;
    run)  open_tun >/dev/null; ssh -p $PORT "${O[@]}" agent@127.0.0.1 "${2:?команда}" ;;
    *)    open_tun ;;
esac
