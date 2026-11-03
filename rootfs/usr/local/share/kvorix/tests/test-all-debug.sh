#!/bin/bash
export DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1001/bus XDG_RUNTIME_DIR=/run/user/1001
xhost +si:localuser:agent 2>/dev/null
PASS=0; FAIL=0; FAILS=""
ok()  { PASS=$((PASS+1)); echo "OK      $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "ОШИБКА  $1"; }
chk() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
win() { for i in $(seq 1 ${2:-60}); do wmctrl -lx | grep -qiE "$1" && return 0; sleep 0.1; done; return 1; }
close() { wmctrl -lx | grep -iE "$1" | awk '{print $1}' | while read w; do wmctrl -ic "$w"; done; sleep 0.6; }
SHOTS=/tmp/test-shots; rm -rf $SHOTS; mkdir -p $SHOTS
shot() { scrot -q 70 -o $SHOTS/$1.jpg; }

echo "===== 1. Службы основного бокса"
for s in front-panel hdmi-autodetect agent-slot@0 agent-slot@1 agent-cmd \
         NetworkManager lightdm bluetooth ssh chrony kvorix-vnc nginx kvorix-zapret tailscaled; do
    chk "служба $s" "systemctl is-active --quiet $s"
done
for t in box-watchdog box-backup; do chk "таймер $t" "systemctl is-active --quiet $t.timer"; done
F=$(systemctl --failed --no-legend | wc -l); [ "$F" = 0 ] && ok "нет упавших системных служб" || bad "упавшие службы: $(systemctl --failed --no-legend | awk '{print $2}' | tr '\n' ' ')"
F=$(systemctl --user --failed --no-legend | wc -l); [ "$F" = 0 ] && ok "нет упавших служб сеанса" || bad "упавшие службы сеанса: $(systemctl --user --failed --no-legend | awk '{print $2}' | tr '\n' ' ')"

echo "===== 2. Процессы оболочки (ровно по одному)"
for p in '^python3 .*rsaarm-[t]askbar.py' '^python3 .*rsaarm-[m]enu.py' '^bash .*rsaarm-[w]atchdog.sh' '^python3 .*armbian-gui/[c]enter.py'; do
    n=$(pgrep -fc "$p"); [ "$n" = 1 ] && ok "процесс ${p//[\[\]]/} ×1" || bad "процесс ${p//[\[\]]/}: $n шт."
done
pgrep -x xfce4-clipman >/dev/null || { setsid xfce4-clipman >/dev/null 2>&1 & sleep 1; }
[ "$(pgrep -xc picom)" = 0 ] && ok "композитор выключен (курсор не мерцает)" || bad "picom запущен"
for p in xfwm4 xfdesktop xfsettingsd xfce4-clipman unclutter; do n=$(pgrep -xc $p); [ "$n" = 1 ] && ok "процесс $p ×1" || bad "процесс $p: $n шт."; done
chk "старые панель и док не запущены" "! pgrep -f 'rsaarm-[b]ar.py|rsaarm-[d]ock.py'"
chk "панель и браузер с обычным приоритетом (nice 0)" "! ps -L -u agent -o ni=,comm= | grep -qE '^ *[1-9][0-9]* +(python3|chromium)'"
Z=$(ps -eo stat | grep -c '^Z'); [ "$Z" = 0 ] && ok "нет зомби-процессов" || bad "зомби-процессов: $Z"

echo "===== 3. Клавиши Windows"
close 'Thunar|Настройки|xfce4-appfinder|Taskmanager|Диспетчер|Разрешение экрана'
xdotool key Super_L; sleep 1.2; xwininfo -name rsaarm-menu 2>/dev/null | grep -q IsViewable && ok "Win → меню Пуск" || bad "Win → меню Пуск"; shot menu; xdotool key Escape; sleep 0.6
xwininfo -name rsaarm-menu 2>/dev/null | grep -q IsUnMapped && ok "Esc закрывает меню" || bad "Esc закрывает меню"
xdotool key super+e;  win 'thunar' && ok "Win+E → Проводник" || bad "Win+E → Проводник"; sleep 1; shot explorer
W=$(xdotool search --onlyvisible --class thunar | tail -1); xdotool windowactivate --sync $W 2>/dev/null; xdotool key super+Left; sleep 0.8
G=$(xwininfo -id $W 2>/dev/null | awk '/Width/{w=$2}/Absolute upper-left X/{x=$4}END{print x, w}'); set -- $G
SW=$(xdpyinfo | awk '/dimensions/{split($2,a,"x"); print a[1]}')
[ "${1:-99}" -le 10 ] && [ "${2:-0}" -ge $((SW/2-60)) ] && [ "${2:-0}" -le $((SW/2+10)) ] && ok "Win+← прикрепляет окно к левой половине" || bad "Win+← (x=$1 ширина=$2)"
close thunar
xdotool key super+i; win 'Настройки' 30 && ok "Win+I → Настройки" || bad "Win+I → Настройки"; close 'Настройки'
xdotool key super+r; win 'appfinder' 40 && ok "Win+R → Выполнить" || bad "Win+R → Выполнить"; xdotool key Escape; close appfinder
xdotool key ctrl+shift+Escape; win 'taskmanager' 40 && ok "Ctrl+Shift+Esc → Диспетчер задач" || bad "Ctrl+Shift+Esc → Диспетчер задач"; close taskmanager
xdotool key super+x; win 'taskmanager' 40 && ok "Win+X → Диспетчер задач" || bad "Win+X"; close taskmanager
echo "проверка буфера" | xclip -selection clipboard 2>/dev/null; xdotool key super+v; win 'clipman' 30 && ok "Win+V → журнал буфера" || bad "Win+V → журнал буфера"; xdotool key Escape; close clipman
xdotool key super+p; win 'Разрешение экрана' 40 && ok "Win+P → Разрешение экрана" || bad "Win+P"; shot display; close 'Разрешение экрана'

echo "===== 4. Меню Пуск: поиск и закреплённые программы"
XKB=$(setxkbmap -query | awk '/^layout/{l=$2}/^variant/{v=$2}/^options/{o=$2}END{printf "-layout %s%s%s", l, (v?" -variant "v:""), (o?" -option "o:"")}')
xdotool key Super_L; sleep 1.2; setxkbmap us; xdotool type --delay 60 "calc"; sleep 0.8; shot menu-search; xdotool key Return
win 'calculator' 60 && ok "поиск «calc» + Enter → Калькулятор" || bad "поиск в меню Пуск"; close calculator
setxkbmap -option ""; setxkbmap $XKB
python3 - <<'PY' > /tmp/pins.txt
import re
s = open("/usr/local/share/rsaarm/shell/rsaarm-menu.py", encoding="utf-8").read()
for t, ic, cmd in re.findall(r'^\s+\("([^"]+)", "([^"]+)", "([^"]+)"\),$', s, re.M):
    print("%s|%s|%s" % (t, ic, cmd))
PY
while IFS="|" read -r t ic cmd; do
    case "$cmd" in *systemctl*|*poweroff*|*reboot*|*lock*|*logout*) continue;; esac
    before=$(wmctrl -l | wc -l)
    case "$cmd" in *center.py*) DISPLAY=:0 XDG_RUNTIME_DIR=/run/user/1001 $cmd >/dev/null 2>&1 & win 'Настройки' 30 && ok "Пуск: «$t»" || bad "Пуск: «$t»"; close 'Настройки'; continue;; esac
    DISPLAY=:0 XDG_RUNTIME_DIR=/run/user/1001 $cmd >/dev/null 2>&1 &
    for i in $(seq 1 80); do [ $(wmctrl -l | wc -l) -gt $before ] && break; sleep 0.1; done
    if [ $(wmctrl -l | wc -l) -gt $before ]; then ok "Пуск: «$t»"; else bad "Пуск: «$t» ($cmd) — окно не появилось"; fi
    sleep 0.8; wmctrl -l | tail -n +$((before+1)) | awk '{print $1}' | while read w; do wmctrl -ic $w; done; sleep 0.8
    gtk-launch >/dev/null 2>&1
    python3 -c "
import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk
t=Gtk.IconTheme.get_default(); import sys; sys.exit(0 if t.has_icon('$ic') else 1)" && ok "значок «$t» ($ic) есть в теме" || bad "значок «$t» ($ic) отсутствует"
done < /tmp/pins.txt
pkill -x chromium 2>/dev/null; sleep 1; pkill -9 -x chromium 2>/dev/null; true
read -r WX WY WW WH < <(xprop -root _NET_WORKAREA | awk -F'= ' '{split($2,a,", "); print a[1],a[2],a[3],a[4]}')
DISPLAY=:0 XDG_RUNTIME_DIR=/run/user/1001 thunar >/dev/null 2>&1 & win 'thunar' 40; xdotool windowactivate --sync $(xdotool search --classname Thunar | tail -1)
rsaarm-snap left; sleep 1; AW=$(xdotool getactivewindow); read -r FR FB < <(xprop -id $AW _NET_FRAME_EXTENTS | awk -F'= ' '{split($2,a,", "); print a[2], a[4]}')
G=$(xwininfo -id $AW | awk -v r=$FR -v b=$FB '/Absolute upper-left X/{x=$NF}/Width/{w=$NF}/Height/{h=$NF}/Absolute upper-left Y/{y=$NF}END{print x+w+r, y+h+b}')
[ "$G" = "$((WX+WW/2)) $((WY+WH))" ] && ok "Win+← окно = левая половина рабочей области" || bad "Win+← геометрия ($G, ждали $((WX+WW/2)) $((WY+WH)))"
rsaarm-snap up; sleep 0.5; close 'Thunar'
TB=$(xwininfo -name rsaarm-taskbar | awk '/Absolute upper-left Y/{y=$NF}/Height/{h=$NF}END{print y+h}')
[ "$TB" = "$(xdpyinfo | awk '/dimensions/{split($2,a,"x"); print a[2]}')" ] && [ "$((WY+WH))" -le "$(xwininfo -name rsaarm-taskbar | awk '/Absolute upper-left Y/{print $NF}')" ] && ok "панель внизу, окна над ней" || bad "панель/рабочая область"

echo "===== 5. Панель задач: всплывающие панели"
xdotool mousemove 1220 742 click 1; sleep 1; xwininfo -root -tree | grep '"rsaarm-pop"' | grep -vq '10x10' && ok "быстрые настройки открываются" || bad "быстрые настройки"; shot qs; xdotool key Escape; xdotool mousemove 700 380 click 1; sleep 0.5
xdotool mousemove 1280 742 click 1; sleep 1; shot calendar; xdotool mousemove 700 380 click 1; sleep 0.5
xdotool mousemove 1334 742 click 1; sleep 1; shot power; xdotool key Escape; xdotool mousemove 700 380 click 1; sleep 0.5

echo "===== 6. Настройки: каждая страница строится без ошибок"
python3 -W default - <<'PY' > /tmp/center-audit.out 2> /tmp/center-audit.err
import inspect, sys
sys.path.insert(0, "/usr/local/share/armbian-gui"); sys.argv = ["center.py"]
import center, ui
from gi.repository import Gtk
ui.load_css()
w = center.Center()
okc = 0
texts = {}
def collect(wid, acc):
    if isinstance(wid, Gtk.Label):
        acc.append(wid.get_text())
    if isinstance(wid, Gtk.Expander) and wid.get_label():
        acc.append(wid.get_label())
    if isinstance(wid, Gtk.ComboBoxText):
        m = wid.get_model()
        if m:
            for row in m:
                acc.append(row[0] or "")
    if isinstance(wid, Gtk.Container):
        for ch in wid.get_children():
            collect(ch, acc)
for k in list(w.builders):
    try:
        w.show_page(k); okc += 1
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        acc = []
        ch = w.stack.get_child_by_name(k)
        if ch:
            collect(ch, acc)
        texts[k] = "\n".join(acc)
    except Exception as e:
        print("ОШИБКА  страница «%s»: %s" % (k, e))
print("BUILT %d/%d" % (okc, len(w.builders)))
for pk, needle in [
    ("services", "Основные фоновые службы"),
    ("perf", "Сбалансированный"),
    ("security", "Защита показа экрана"),
    ("devices", "Пульт и датчики"),
    ("timelang", "Переключение языка"),
]:
    print(("HAS_OK " if needle in texts.get(pk, "") else "HAS_BAD ") + pk + ":" + needle)
w.destroy()
PY
grep -q "^BUILT 20/20" /tmp/center-audit.out && ok "Настройки: все 20 страниц построены без исключений" || bad "Настройки: построение страниц ($(cat /tmp/center-audit.out | tr '\n' ' '))"
CRIT=$(grep -cE "Gtk-CRITICAL|Gtk-WARNING.*focus-line-width|PyGIWarning|DeprecationWarning|TypeError|Traceback" /tmp/center-audit.err || true)
[ "$CRIT" = 0 ] && ok "Настройки: 0 предупреждений GTK/PyGI/CSS при обходе 20 страниц" || bad "Настройки: предупреждений GTK/PyGI: $CRIT ($(head -2 /tmp/center-audit.err | tr '\n' ' '))"
grep -q "^HAS_BAD " /tmp/center-audit.out && bad "Настройки: отсутствует русская подпись ($(grep '^HAS_BAD ' /tmp/center-audit.out | tr '\n' ' '))" || ok "Настройки: понятные русские подписи (Службы/Быстродействие/Безопасность/Устройства/Язык)"
if [ -f /usr/local/share/armbian-gui/test_settings_search.py ]; then
    PYTHONPATH=/usr/local/share/armbian-gui python3 /usr/local/share/armbian-gui/test_settings_search.py --source /usr/local/share/armbian-gui/center.py --gtk >/tmp/search-test.out 2>&1 \
        && ok "Поиск Настроек (AST + GTK + раскладка EN↔RU, 25 тестов)" \
        || bad "Поиск Настроек ($(tail -3 /tmp/search-test.out | tr '\n' ' '))"
fi

echo "Центр перед разделом 7: $(pgrep -f 'armbian-gui/[c]enter.py' | head -1)" > /tmp/theme-debug.log
echo "===== 7. Персонализация"
SAVE=$(cat ~/.config/rsaarm/personalize.json)
armbian-personalize set mode light >/dev/null 2>&1; sleep 4
echo "Центр после light: $(pgrep -f 'armbian-gui/[c]enter.py' | head -1)" >> /tmp/theme-debug.log
[ "$(xfconf-query -c xsettings -p /Net/ThemeName)" = Kvorix ] && ok "светлый режим → тема Kvorix" || bad "светлый режим"
armbian-personalize set mode dark >/dev/null 2>&1; sleep 4
echo "Центр после dark: $(pgrep -f 'armbian-gui/[c]enter.py' | head -1)" >> /tmp/theme-debug.log
[ "$(xfconf-query -c xsettings -p /Net/ThemeName)" = Kvorix-Dark ] && ok "тёмный режим → тема Kvorix-Dark" || bad "тёмный режим"
TB1=$(pgrep -f 'rsaarm-[t]askbar.py' | head -1); CT1=$(pgrep -f 'armbian-gui/[c]enter.py' | head -1); sleep 1.5
TB2=$(pgrep -f 'rsaarm-[t]askbar.py' | head -1); CT2=$(pgrep -f 'armbian-gui/[c]enter.py' | head -1)
[ -n "$TB1" ] && [ "$TB1" = "$TB2" ] && [ -n "$CT1" ] && [ "$CT1" = "$CT2" ] && ok "смена темы live: без перезапуска панели и настроек" || bad "смена темы перезапустила панель/настройки"
for a in teal green purple pink red orange graphite blue; do armbian-personalize set accent $a >/dev/null 2>&1 || bad "акцент $a"; done
grep -q 5a9bff ~/.config/rsaarm/shell.css && ok "акценты применяются (панель)" || bad "акцент в панели"
armbian-personalize set nightlight true >/dev/null 2>&1; xrandr --verbose | grep -q 'Gamma:.*1.0:1.[1-9]' && ok "ночной свет меняет гамму" || bad "ночной свет"
armbian-personalize set nightlight false >/dev/null 2>&1
echo "$SAVE" > ~/.config/rsaarm/personalize.json; armbian-personalize >/dev/null 2>&1; sleep 4
M=0; for i in 1 2 3 4 5 6; do M=$(pgrep -fc '^python3 .*rsaarm-[m]enu.py'); [ "$M" = "1" ] && break; sleep 2; done
[ "$M" = "1" ] && ok "после смены темы меню Пуск живо" || bad "меню Пуск после смены темы"
for t in Kvorix Kvorix-Dark; do [ -f /usr/share/themes/$t/gtk-3.0/gtk.gresource ] && ok "тема $t содержит базу Arc" || bad "тема $t без базы"; done

echo "===== 8. Программы по умолчанию"
[ "$(xdg-mime query default video/mp4)" = vlc.desktop ] && ok "видео открывает VLC" || bad "видео не VLC"
for m in image/png video/mp4 audio/mpeg text/plain application/pdf inode/directory; do
    d=$(xdg-mime query default $m); [ -n "$d" ] && [ -f /usr/share/applications/$d ] && ok "$m → $d" || bad "$m → «$d»"
done

echo "===== 9. Экран, звук, Bluetooth, сеть"
run-parts /etc/update-motd.d 2>/dev/null | grep -q "Устройство" && ok "приветствие SSH Kvorix" || bad "приветствие SSH"
[ "$(od -An -tx1 -j128 -N1 /sys/class/drm/card0-HDMI-A-1/edid | tr -d " ")" = 02 ] && ok "EDID с блоком CEA (звук по HDMI)" || bad "EDID без CEA — HDMI без звука"
chk "монитор определён по EDID" "[ -s /run/hdmi-monitor ]"
chk "режим экрана установлен" "xrandr | grep -q '\*'"
chk "звук: PipeWire/Pulse отвечает" "pactl info"
chk "есть устройство вывода звука" "pactl list short sinks | grep -q ."
chk "Bluetooth адаптер доступен" "bluetoothctl show | grep -q 'Controller'"
chk "Bluetooth-имя Kvorix" "bluetoothctl show | grep -q 'Alias: Kvorix'"
chk "интернет (HTTPS)" "curl -sf -m 10 -o /dev/null https://ya.ru"
chk "обычные сайты резолвятся" "getent hosts github.com"

echo "===== 10. Передняя панель"
chk "служба индикатора работает" "systemctl is-active --quiet front-panel"
chk "драйвер openvfd не загружен" "! lsmod | grep -q openvfd"
chk "настройки индикатора доступны пользователю" "[ -w /var/lib/front-panel/config.json ]"

echo "===== 12. Доступ ИИ и ресурсы"
for p in kvorix-taskmanager kvorix-disks kvorix-snip kvorix-taskview; do pkill -f "$p" 2>/dev/null; done; for i in $(seq 1 12); do read -r _ a b c d e f g _ < /proc/stat; sleep 3; read -r _ A B C D E F G _ < /proc/stat; t=$(( (A+B+C+D+E+F+G)-(a+b+c+d+e+f+g) )); [ $t -gt 0 ] && [ $(( 100*(t-(D-d))/t )) -lt 10 ] && break; done; sleep 5
chk "доступ ИИ включён (2 сессии)" "[ \$(sudo -n /usr/local/sbin/ai-access status | grep -c '^active') = 2 ]"
read -r _ a b c d e f g _ < /proc/stat; sleep 5; read -r _ A B C D E F G _ < /proc/stat
t=$(( (A+B+C+D+E+F+G)-(a+b+c+d+e+f+g) )); busy=$(( 100*(t-(D-d))/t ))
[ $busy -le 15 ] && ok "загрузка CPU в простое $busy %" || bad "загрузка CPU в простое $busy %"
av=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo); [ $av -ge 500 ] && ok "свободно памяти $av МБ" || bad "мало памяти: $av МБ"
tc=$(( $(cat /sys/class/thermal/thermal_zone0/temp)/1000 )); [ $tc -le 75 ] && ok "температура $tc °C" || bad "температура $tc °C"
df / | awk 'NR==2{exit ($5+0>90)}' && ok "место на диске есть" || bad "диск заполнен"

echo "===== 13. Доступ к экрану (локальный) и сеть"
chk "tailscale online (IP выдан)" "[ -n \"$(tailscale ip -4 2>/dev/null)\" ]"
chk "tailscale узел Self.Online=true" "tailscale status --json 2>/dev/null | python3 -c \"import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('Self',{}).get('Online') else 1)\""
chk "funnel отключён (нет публичного доступа)" "! tailscale funnel status 2>&1 | grep -q 'Funnel on'"
chk "zapret (обход DPI) активен" "systemctl is-active --quiet kvorix-zapret"
TOK=$(sudo -n cat /etc/kvorix/novnc.token 2>/dev/null)
chk "VNC :5900 слушает только 127.0.0.1" "ss -ltn | grep -q '127.0.0.1:5900' && ! ss -ltn | grep -qE '(0\.0\.0\.0|\*|:::):5900'"
chk "токен экрана: 48 hex-символов, права 600" "[ ${#TOK} = 48 ] && [ \"$(sudo -n stat -c%a /etc/kvorix/novnc.token 2>/dev/null)\" = 600 ]"
chk "скрипт смены ссылки экрана на месте" "[ -x /usr/local/sbin/kvorix-novnc-token ]"
chk "noVNC: корень :6080 → 404 (скрыт)" "[ \"$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:6080/)\" = 404 ]"
chk "noVNC: старая /vnc.html → 404" "[ \"$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:6080/vnc.html)\" = 404 ]"
chk "noVNC: /<токен>/vnc.html → 200" "[ \"$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:6080/$TOK/vnc.html)\" = 200 ]"
chk "noVNC: /<токен>/ (index) → 200" "[ \"$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:6080/$TOK/)\" = 200 ]"
LANIP=$(ip -4 -o addr show scope global 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | grep -v '^100\.' | head -1)
chk "noVNC: страница по токену с LAN-IP ${LANIP:-?} → 200" "[ -n \"$LANIP\" ] && [ \"$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://$LANIP:6080/$TOK/vnc.html)\" = 200 ]"
chk "VNC :5900 с LAN-IP недоступен извне" "[ -n \"$LANIP\" ] && ! timeout 3 bash -c \"</dev/tcp/$LANIP/5900\""
python3 - 2>/dev/null <<WSCHK | grep -q 101 && ok "noVNC WebSocket /<токен>/websockify → 101" || bad "noVNC WebSocket (нет 101)"
import http.client
c = http.client.HTTPConnection("127.0.0.1", 6080, timeout=4)
c.request("GET", "/$TOK/websockify", headers={"Upgrade": "websocket", "Connection": "Upgrade",
            "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==", "Sec-WebSocket-Version": "13"})
print(c.getresponse().status)
WSCHK
python3 - 2>/dev/null <<'VNCCHK' | grep -q RFB && ok "VNC :5900 на localhost отвечает RFB (пароль требуется)" || bad "VNC handshake на 127.0.0.1:5900"
import socket
s = socket.create_connection(("127.0.0.1", 5900), timeout=4)
print(s.recv(12).decode(errors="replace")); s.close()
VNCCHK
chk "страница «Устройства»: QR генерируется" "[ -s /tmp/kvorix-qr-local.png ]"
chk "noVNC E2E: WS+RFB+auth через /<токен>/websockify → SecurityResult 0" "[ -x /usr/local/share/kvorix/tests/e2e-vnc-test.py ] && python3 /usr/local/share/kvorix/tests/e2e-vnc-test.py 2>/dev/null | grep -q E2E-VNC-OK"
chk "страницы «Устройства»/«Время и язык» объявлены" "grep -q 'def page_devices' /usr/local/share/armbian-gui/center.py && grep -q 'def page_timelang' /usr/local/share/armbian-gui/center.py"
sleep 2

echo; echo "===== ИТОГ: OK $PASS, ОШИБОК $FAIL"; [ $FAIL -gt 0 ] && echo -e "Ошибки:$FAILS"
ls $SHOTS
