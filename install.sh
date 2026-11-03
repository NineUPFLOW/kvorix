#!/bin/bash
# Kvorix — установка поверх чистого Armbian ophub (Amlogic S905X3, Debian 13 trixie).
#   sudo ./install.sh                 пакеты + файлы + службы
#   sudo ./install.sh --no-packages   только файлы и службы (пакеты уже стоят)
# © 2026 NineUPFLOW, GPL-3.0
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
[ "$(id -u)" = 0 ] || { echo "Запустите через sudo"; exit 1; }
id agent >/dev/null 2>&1 || { echo "Нет пользователя agent — создайте его при первой настройке Armbian"; exit 1; }
grep -q aarch64 <<<"$(uname -m)" || { echo "Нужна приставка arm64 (S905X3)"; exit 1; }

step() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }

if [ "${1:-}" != "--no-packages" ]; then
    step "Пакеты"
    apt-get update
    # tailscale ставится из своего репозитория, если он подключён
    PKGS=$(grep -v '^#' packages.txt | grep -vx tailscale)
    # shellcheck disable=SC2086
    DEBIAN_FRONTEND=noninteractive apt-get install -y $PKGS
    apt-cache policy tailscale 2>/dev/null | grep -q Candidate: && DEBIAN_FRONTEND=noninteractive apt-get install -y tailscale || \
        echo "tailscale пропущен: подключите репозиторий https://tailscale.com/download/linux/debian-trixie"
fi

step "Файлы Kvorix"
# своё не затираем: настройки сети и секреты этой приставки в репозитории отсутствуют
rsync -rlptD --exclude=etc/skel/ rootfs/ /
chown -R root:root /usr/local /etc/kvorix /etc/systemd/system
chmod 440 /etc/sudoers.d/* 2>/dev/null || true
visudo -c >/dev/null || { echo "Ошибка в /etc/sudoers.d — проверьте"; exit 1; }
chmod 700 /etc/kvorix

step "Настройки пользователя"
rsync -a rootfs/etc/skel/ /etc/skel/
rsync -a --ignore-existing rootfs/etc/skel/ /home/agent/
chown -R agent:agent /home/agent

step "Ссылки"
ln -sf /usr/share/fontconfig/conf.avail/10-hinting-slight.conf /etc/fonts/conf.d/
ln -sf /usr/share/fontconfig/conf.avail/70-no-bitmaps-except-emoji.conf /etc/fonts/conf.d/
ln -sfn ../../Kvorix-Icons/scalable/apps /usr/share/icons/Kvorix-Icons-Dark/scalable/apps

step "Службы"
systemctl daemon-reload
# как на эталонной приставке; Доступ ИИ (agent-*) не включается — его включают в Настройки → Доступ ИИ
for u in hdmi-autodetect front-panel kvorix-zapret kvorix-vnc kvorix-novnc kvorix-icons.path bt-agent bt-beacon \
         nebo-tune box-watchdog.timer box-backup.timer kvorix-config-snapshot.timer kvorix-mode-heal.timer kvorix-firstboot; do
    systemctl enable "$u" >/dev/null 2>&1 || echo "  пропущено: $u"
done

step "Первый запуск: ключи, пароль VNC, токен noVNC"
touch /etc/kvorix/.firstboot
/usr/local/sbin/kvorix-firstboot

step "Значки и заставка"
/usr/local/sbin/kvorix-make-icons
plymouth-set-default-theme kvorix && update-initramfs -u

step "Готово"
cat /etc/kvorix-release
echo "Перезагрузите приставку: sudo reboot"
