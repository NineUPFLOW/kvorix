#!/bin/bash
STATE=/run/box-watchdog.fails
LOG="logger -t box-watchdog"
fail=$(cat "$STATE" 2>/dev/null || echo 0)
GW=$(ip -4 route show default dev wlan0 2>/dev/null | awk '{print $3; exit}')
if [ -n "$GW" ] && ping -c2 -W2 "$GW" >/dev/null 2>&1; then
    [ "$fail" -ne 0 ] && $LOG "связь с роутером ($GW) восстановлена"
    fail=0
else
    fail=$((fail + 1)); $LOG "нет связи с роутером, попытка $fail"
fi
case "$fail" in
    2|4) $LOG "связь с роутером отсутствует; радио не переключаю автоматически" ;;
    8) fail=0 ;;
esac
echo "$fail" > "$STATE"
for svc in ssh armbian-cluster-node agent-slot@0 agent-slot@1; do
    if systemctl is-enabled --quiet "$svc" 2>/dev/null && ! systemctl is-active --quiet "$svc"; then
        $LOG "служба $svc остановлена — перезапускаю"; systemctl restart "$svc" 2>/dev/null || true
    fi
done
# Tailscale: связь с сервером, поднятая до сети/обхода DPI, может «замёрзнуть» навсегда — два раза подряд офлайн при живом роутере → перезапуск
TS=/run/box-watchdog.ts
if [ "$fail" -eq 0 ] && systemctl is-active --quiet tailscaled; then
    if tailscale status --json 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get("BackendState")=="Running" and not d["Self"].get("Online") else 1)' 2>/dev/null; then
        n=$(( $(cat "$TS" 2>/dev/null || echo 0) + 1 ))
        if [ "$n" -ge 2 ]; then $LOG "tailscale не на связи с сервером — перезапускаю"; systemctl restart tailscaled; n=0; fi
        echo "$n" > "$TS"
    else
        echo 0 > "$TS"
    fi
fi
T=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0)
[ "$T" -gt 80000 ] && $LOG "высокая температура CPU: $((T/1000)) °C"
exit 0
