# Как помочь проекту

Спасибо, что хотите улучшить Kvorix!

## Сообщить о проблеме

Откройте [issue](https://github.com/NineUPFLOW/kvorix/issues/new/choose) и приложите:
модель и ревизию мини-ПК, версию Kvorix (`cat /etc/kvorix-release`), что делали, что ожидали, что получилось,
вывод `sudo kvorix-health-check` и `journalctl -p err -b`. **Не прикладывайте** пароли, ключи, токены, адреса noVNC.

## Прислать изменения

1. Сделайте fork и ветку от `main`.
2. Файлы в `rootfs/` лежат по своим путям в системе — правьте их там же.
3. Shell — `bash`, проверка `shellcheck`; Python 3.13, GTK 3 (PyGObject), без лишних зависимостей.
   Переводы строк — LF (Python-скрипты с CRLF не запускаются).
4. Проверьте на мини-ПК: `sudo ./install.sh`, затем `test-all.sh` и `kvorix-health-check` — без ошибок.
5. Откройте pull request: что и зачем изменено, как проверено.

Отправляя изменения, вы соглашаетесь распространять их по [GPL-3.0](LICENSE).

## Правила общения

[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
