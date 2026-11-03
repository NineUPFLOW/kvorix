# Сторонние компоненты

Kvorix — © 2026 NineUPFLOW, GPL-3.0 (файл [LICENSE](LICENSE)): всё в `rootfs/` (скрипты, Настройки, оболочка,
темы Kvorix, значки Kvorix, заставка), `install.sh` и документация.

Образ прошивки дополнительно содержит чужие программы — каждая под своей лицензией. Исходные тексты пакетов Debian
доступны через `apt source <пакет>` и на https://sources.debian.org.

| Компонент | Откуда | Лицензия |
|---|---|---|
| Armbian (сборка ophub), скрипты `armbian-*` | https://github.com/ophub/amlogic-s9xxx-armbian | GPL-2.0 |
| Ядро Linux 6.12-ophub, dtb | https://github.com/ophub/kernel | GPL-2.0 |
| Debian 13 «trixie» (пакеты из `packages.txt`) | https://www.debian.org | разные свободные, см. `/usr/share/doc/*/copyright` |
| XFCE (xfwm4, xfdesktop, Thunar …) | https://xfce.org | GPL-2.0 / LGPL |
| Papirus (символы для значков Kvorix) | https://github.com/PapirusDevelopmentTeam/papirus-icon-theme | GPL-3.0 |
| zapret / nfqws | https://github.com/bol-van/zapret | MIT |
| noVNC, websockify | https://github.com/novnc | MPL-2.0 / LGPL-3.0 |
| x11vnc | https://github.com/LibVNC/x11vnc | GPL-2.0 |
| upterm (Доступ ИИ) | https://github.com/owenthereal/upterm | Apache-2.0 |
| Tailscale | https://tailscale.com | BSD-3-Clause (клиент) |
| Chromium | https://www.chromium.org | BSD-3-Clause и др. |
| Шрифт Inter | https://rsms.me/inter | OFL-1.1 |

Значки Kvorix сгенерированы из символов Papirus (`kvorix-make-icons`), поэтому тема значков распространяется по GPL-3.0.
Товарные знаки Tanix, Amlogic, Windows и др. принадлежат их владельцам; Kvorix с ними не связан.
