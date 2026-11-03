# Устройство системы

```
 Загрузка:  заводской U-Boot → s905_autoscript / emmc_autoscript (ophub) → u-boot.ext → uEnv.txt
            → ядро 6.12-ophub + uInitrd (Plymouth «kvorix», EDID монитора в initrd) → systemd
 Сеанс:     LightDM (автовход agent) → XFCE: xfwm4 + xfdesktop + оболочка rsaarm (панель, «Пуск»)
 Службы:    hdmi-autodetect, front-panel, kvorix-vnc/novnc, сторожа и таймеры Kvorix
```

## Оболочка (`/usr/local/share/rsaarm`, Python 3 + GTK 3)

| Файл | Что это |
|---|---|
| `shell/rsaarm-taskbar.py` | панель задач: закреплённые, окна (libwnck), трей, часы, всплывающие панели сети/звука/календаря |
| `shell/rsaarm-menu.py` | «Пуск»: поиск по программам, файлам и Настройкам, закреплённые, рекомендуемые; держится в памяти (`--prewarm`) |
| `shell/rsaarm-shell.sh`, `rsaarm-watchdog.sh` | запуск оболочки и сторож: перезапускает панель/меню, если они упали |
| `kvorix-restart-panel`, `-menu`, `-settings` | перезапуск частей оболочки (`/usr/local/bin`) |
| `shell/rsaarm.css`, `shell/rsaarm-dark.css` | стили светлой и тёмной темы |

## Настройки (`/usr/local/share/armbian-gui`)

`center.py` — приложение «Настройки» (`armbian-center`): меню разделов `MENU`, плитки «Главной» `TILES`, страницы
`page_*`. `ui.py` — общие элементы (карточки, кнопки; `ui._ic()` выбирает однотонный значок), `common.py` — запуск
команд, `settings_search.py` — поиск по всем параметрам, `monitor.py`, `autostart.py` — отдельные окна.
Тест поиска: `test_settings_search.py`.

## Службы systemd (`/etc/systemd/system`)

| Юнит | Назначение |
|---|---|
| `hdmi-autodetect.service` | EDID по DDC раз в 3 с, режим монитора, перестройка панели/меню (сбрасывает им `nice`) |
| `kvorix-mode-heal.timer` | возвращает видеорежим, если ядро его отклонило |
| `front-panel.service` | индикатор 88:88 (FD6551), настройки `/var/lib/front-panel/config.json` |
| `kvorix-vnc.service` / `kvorix-novnc.service` | x11vnc на 127.0.0.1:5900 → websockify :6081 → nginx :6080 (секретный путь) |
| `kvorix-icons.path` / `.service` | следит за каталогами программ и обновляет значки (`kvorix-make-icons`) |
| `kvorix-firstboot.service` | первый запуск: ключи SSH, пароль VNC, токен noVNC, темы Доступа ИИ |
| `box-watchdog.timer` | каждую минуту: роутер, SSH, слоты ИИ, Tailscale, температура |
| `box-backup.timer` | ежедневная копия настроек в `/srv/share/backup` |
| `kvorix-config-snapshot.timer` | еженедельный проверяемый снимок настроек (`kvorix-config-verify`) |
| `bt-agent.service`, `bt-beacon.service` | сопряжение Bluetooth без подтверждения, видимость адаптера |
| `nebo-tune.service` | governor `ondemand` для всех ядер при загрузке |
| `tty-console.service` | графическая консоль на tty2 (Xorg + urxvt) |
| `agent-slot@.service`, `agent-cmd.service`, `kvorix-autoreport.timer` | Доступ ИИ — выключены, управляются `ai-access on` / `off` |

## Важные команды (`/usr/local/sbin`, `/usr/local/bin`)

| Команда | Что делает |
|---|---|
| `hdmi-autodetect.py` | служба определения монитора |
| `armbian-screen-fit`, `display-chooser`, `armbian-display-auto` | режимы экрана, подгонка краёв, Win+P |
| `kvorix-health-check [--json]` | проверка здоровья |
| `kvorix-make-icons` | построить значки Kvorix для всех программ |
| `kvorix-build-image` | собрать образ прошивки без личных данных |
| `kvorix-firstboot` | создать ключи и пароли этой приставки |
| `kvorix-novnc-token` | новый секретный адрес показа экрана |
| `ai-access on` / `ai-access off` | включить / выключить Доступ ИИ |
| `kvorix-taskmanager`, `kvorix-disks`, `kvorix-snip` | диспетчер задач, диски, «Ножницы» |
| `kvorix-mediakeys` | медиаклавиши и громкость |

## Где лежат данные

| Путь | Что |
|---|---|
| `/etc/kvorix/` | секреты приставки (не в репозитории) |
| `/var/lib/hdmi-autodetect/` | выбранные режимы для каждого монитора (ключ — хэш EDID) |
| `/var/lib/front-panel/config.json` | настройки индикатора |
| `~/.config/rsaarm/` | тема, закреплённые, эффекты оболочки |
| `~/.config/armbian-tv/screen-fit.json` | сдвиг краёв экрана |
| `/usr/share/icons/Kvorix-Icons/scalable/apps` | сгенерированные значки |
| `/usr/local/share/kvorix/tests/` | автотесты |

## Тесты

- `test-all.sh` — 127 проверок: службы, процессы оболочки, горячие клавиши, «Пуск», панели, все страницы Настроек,
  персонализация, программы по умолчанию, экран/звук/Bluetooth/сеть, передняя панель, доступ, показ экрана.
- `kvorix-health-check` — быстрые проверки (службы, eMMC, память, снимки настроек, синтаксис скриптов GUI).
- `test-config-verify.py`, `test-health-check.py`, `test-front-panel.py`, `test_settings_search.py` — модульные тесты.
