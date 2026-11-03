#!/bin/bash
export DISPLAY=${DISPLAY:-:0} XAUTHORITY=${XAUTHORITY:-$HOME/.Xauthority}
DBUS=unix:path=/run/user/$(id -u)/bus
SD=/usr/local/share/rsaarm/shell
export XDG_RUNTIME_DIR=/run/user/$(id -u)
while true; do
    sleep 5
    N=$(pgrep -f 'rsaarm-[t]askbar.py' 2>/dev/null | wc -l)
    I=$(( ${I:-0} + 1 ))
    pgrep -u "$(id -u)" -x xfce4-clipman >/dev/null ||             DBUS_SESSION_BUS_ADDRESS=$DBUS setsid -f xfce4-clipman >/dev/null 2>&1 < /dev/null
    pgrep -u "$(id -u)" -f 'armbian-gui/[c]enter.py' >/dev/null ||             DBUS_SESSION_BUS_ADDRESS=$DBUS setsid -f python3 /usr/local/share/armbian-gui/center.py --prewarm                 >/dev/null 2>&1 < /dev/null
    if [ $(( I % 6 )) -eq 0 ]; then
        :
    fi
    if [ "$N" -eq 1 ] && [ $(( I % 6 )) -ne 0 ]; then
        continue
    fi
    W=$(DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY \
        xwininfo -root -tree 2>/dev/null | grep -E '"rsaarm-taskbar":' \
        | grep -cE ' [0-9]+x(52|60)[+]')
    if [ "$N" -eq 1 ] && [ "$W" -eq 1 ]; then
        continue
    fi
    echo "$(date +%H:%M:%S) аномалия: процессов=$N окон=$W — перезапуск" \
        >> /tmp/rsaarm-watchdog.log
    pkill -f 'rsaarm-[t]askbar.py' 2>/dev/null
    sleep 2
    {
        echo "$(date +%H:%M:%S) старт панели задач" >> /tmp/rsaarm-watchdog.log
        DBUS_SESSION_BUS_ADDRESS=$DBUS setsid env \
            RSAARM_THEME=$(cat $HOME/.config/rsaarm/theme 2>/dev/null || echo light) \
            python3 $SD/rsaarm-taskbar.py >/tmp/tb.log 2>&1 < /dev/null &
    }
done
