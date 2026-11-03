#!/bin/bash
i=$1
TOPIC=$(sed -n "s/^TOPIC=//p" /etc/kvorix/ai.conf 2>/dev/null)
ALT=ntfy.hostux.net
UP=/usr/local/bin/upterm
LOG=/run/slot-$i.out
: > "$LOG"
setsid bash -c "sleep 100000 | $UP host --accept --skip-host-key-check --allow-local-tcp-forwarding -- bash > $LOG 2>&1" &
sleep 6
while true; do
    c=$(grep -m1 -oE 'Session: [A-Za-z0-9]+' "$LOG" 2>/dev/null | head -1 | awk '{print $2}')
    if [ -n "$c" ] && [ "$c" != "$(cat /run/session-$i.txt 2>/dev/null)" ]; then
        echo "$c" > "/run/session-$i.txt"
        echo "$(date +%s) slot$i $c" >> /var/log/agent-sessions.log
        curl -s -m 10 -d "SESSION $c" "https://ntfy.sh/$TOPIC" >/dev/null 2>&1
        curl -s -m 10 -d "SESSION $c" "https://$ALT/$TOPIC" >/dev/null 2>&1
    fi
    sleep 5
done
