#!/bin/bash
OUT=$(sed -n "s/^OUT_TOPIC=//p" /etc/kvorix/ai.conf 2>/dev/null)
[ -z "$OUT" ] && exit 0
temp=$(( $(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0)/1000 ))
load=$(cut -d' ' -f1-3 /proc/loadavg)
up=$(uptime -p 2>/dev/null | sed 's/^up //')
memtot=$(awk '/^MemTotal/{printf "%.0f", $2/1024}' /proc/meminfo)
memav=$(awk '/MemAvailable/{printf "%.0f", $2/1024}' /proc/meminfo)
swapu=$(free -m | awk '/^Swap:/{if($2>0) printf "%.0f МБ из %.0f МБ", $3, $2; else print "нет"}')
root=$(df -h / | awk 'NR==2{print $3" из "$2" ("$5"), свободно "$4}')
boot=$(df -h /boot | awk 'NR==2{print $3" из "$2" ("$5")"}')
fail=$(systemctl --failed --no-legend 2>/dev/null | wc -l)
en=$(systemctl list-unit-files --state=enabled --no-legend 2>/dev/null | wc -l)
pkgs=$(dpkg -l 2>/dev/null | grep -c ^ii)
wlan=$(ip -4 -o addr show wlan0 2>/dev/null | awk '{print $4}' | head -1)
tsip=$(tailscale ip -4 2>/dev/null | head -1)
ports=$(ss -ltn 2>/dev/null | grep -cE ':(5900|6080|6081)')
slots=$(/usr/local/sbin/ai-access status 2>/dev/null | grep -c active)
agents=$(/usr/local/sbin/ai-access who 2>/dev/null | grep -c "ИИ-агент")
msg="**📊 Отчёт Kvorix — $(date '+%d.%m.%Y %H:%M') МСК**

🌡️ **Температура процессора:** ${temp} °C
⚙️ **Нагрузка (1/5/15 мин):** ${load}
🕒 **Работает без перезагрузки:** ${up}
💾 **Накопитель eMMC (/):** занято ${root}; /boot: ${boot}
🧠 **Память:** доступно ${memav} МБ из ${memtot} МБ; zram-swap: ${swapu}
🔧 **Службы:** включено ${en}, упавших ${fail}
📦 **Пакетов установлено:** ${pkgs}
🌐 **Сеть:** Wi-Fi ${wlan}; Tailscale: ${tsip:-оффлайн}
👁️ **Экран (VNC):** порты 5900/6080/6081 слушают: ${ports}/3; QR — на странице «Устройства» (только LAN)
🤖 **Доступ ИИ-агентов:** слотов активно ${slots}, подключено сейчас агентов: ${agents}"
for h in https://ntfy.sh https://ntfy.hostux.net; do
    if curl -s -m 10 -X POST -H "Title: 📊 Отчёт Kvorix" -H "Markdown: yes" -H "Tags: chart" --data-binary "$msg" "$h/$OUT" -o /dev/null; then exit 0; fi
done
