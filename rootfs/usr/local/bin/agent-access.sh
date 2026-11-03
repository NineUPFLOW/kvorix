#!/bin/bash
TOPIC=$(sed -n "s/^TOPIC=//p" /etc/kvorix/ai.conf 2>/dev/null)
SLOTS=3
INTERVAL=1800

stop_all() {
    pkill -TERM -f 'agent-slot\.sh' 2>/dev/null
    sleep 1
    pkill -TERM -f 'upterm.*--accept' 2>/dev/null
    sleep 1
    pkill -KILL -f 'upterm.*--accept' 2>/dev/null
    for i in $(seq 0 $((SLOTS-1))); do
        rm -f "/run/session-$i.txt"
    done
    sleep 1
}

start_all() {
    for i in $(seq 0 $((SLOTS-1))); do
        setsid /usr/local/bin/agent-slot.sh "$i" >/dev/null 2>&1 &
        sleep 1
    done
}

while true; do
    stop_all
    start_all
    echo "$(date '+%F %T') цикл: запущено $SLOTS сессий (интервал ${INTERVAL}s)" >> /var/log/agent-sessions.log
    sleep $INTERVAL
done
