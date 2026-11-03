<div align="center">

# Kvorix

**Русский** · [English](README.en.md) · [中文](README.zh.md)

**Быстрый «настольный компьютер» из ТВ-приставки Tanix TX3 (Amlogic S905X3)**

Armbian (Debian 13 «trixie») · ядро ophub 6.12 · XFCE с оболочкой в стиле Windows 11 · свои Настройки и значки

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)
![SoC](https://img.shields.io/badge/SoC-Amlogic%20S905X3-informational)
![Arch](https://img.shields.io/badge/arch-arm64-informational)
![Debian](https://img.shields.io/badge/Debian-13%20trixie-A81D33)

![Рабочий стол Kvorix](docs/img/desktop.jpg)

</div>

## Что это

Kvorix превращает дешёвую Android-приставку **Tanix TX3** в тихий домашний компьютер: браузер, файлы, видео, печать,
показ экрана на телефон — без командной строки.

- **Оболочка в стиле Windows 11:** панель задач по центру, «Пуск» с поиском и закреплёнными программами,
  Win+E / Win+I / Win+R / Win+P / Win+V / Ctrl+Shift+Esc, прикрепление окон к краям.
- **Экранная клавиатура** (Win+Ctrl+O) — для мыши и пульта.
- **Единые значки** во всей системе; новые программы получают значок автоматически.
- **Свои «Настройки»** как в Windows 11 — с поиском по всем параметрам.
- **Экран без HPD:** монитор определяется по EDID через DDC, родной режим и звук по HDMI, подгонка краёв для ТВ.
- **Передняя панель 88:88** (FD6551): часы, дата, температура, загрузка.
- **Показ экрана на телефон** по QR-коду (noVNC, только в домашней сети).
- **DNS через TLS** и **Tailscale** (обход блокировок зависит от провайдера и в Kvorix не входит).
- **Скорость:** до 2,1 ГГц, zram, GPU Panfrost, Chromium на GPU, нормальный приоритет оболочки.
- **Сам себя лечит:** сторож сети и служб, восстановление Tailscale, `kvorix-health-check`.

| «Пуск» | Настройки |
|---|---|
| ![Пуск](docs/img/start.jpg) | ![Настройки](docs/img/settings.jpg) |

## Установка

1. Запишите на карту/флешку образ **Armbian от ophub** для S905X3 (Debian trixie, ядро 6.12) —
   [ophub/amlogic-s9xxx-armbian](https://github.com/ophub/amlogic-s9xxx-armbian/releases); загрузитесь с него.
2. Создайте пользователя **`agent`** при первой настройке.
3. Установите Kvorix:

```bash
git clone https://github.com/NineUPFLOW/kvorix.git
cd kvorix
sudo ./install.sh
sudo reboot
```

Подробно — [docs/INSTALL.md](docs/INSTALL.md). Собрать свой образ для своих приставок — [docs/BUILD.md](docs/BUILD.md).

## Документация

| Раздел | О чём |
|---|---|
| [INSTALL](docs/INSTALL.md) | установка на Armbian, первый запуск, перенос на eMMC |
| [BUILD](docs/BUILD.md) | как собрать всё с нуля и сделать свой образ |
| [FEATURES](docs/FEATURES.md) | все возможности и где они настраиваются |
| [ARCHITECTURE](docs/ARCHITECTURE.md) | службы, скрипты, файлы |
| [HARDWARE](docs/HARDWARE.md) | Tanix TX3: железо и особенности |
| [SECURITY](SECURITY.md) | пароли, доступ, что менять |
| [TROUBLESHOOTING](docs/TROUBLESHOOTING.md) | частые проблемы |
| [CHANGELOG](CHANGELOG.md) | история версий |

Документация подробно написана на русском; README есть также на [английском](README.en.md) и [китайском](README.zh.md).

## Лицензия

Kvorix — © 2026 **NineUPFLOW**. Код, оформление, значки и документация распространяются по [GNU GPL v3.0](LICENSE):
можно использовать, изучать, менять и распространять с сохранением авторства и той же лицензии.
Сторонние компоненты — под своими лицензиями, см. [THIRD_PARTY.md](THIRD_PARTY.md).
