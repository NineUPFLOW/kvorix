# Установка Kvorix

## Что нужно

- Tanix TX3 (S905X3) — проверено на ревизии **TX3 (BZ)**, 2 ГБ ОЗУ / 16 ГБ eMMC.
- microSD или USB-флешка **от 8 ГБ** (A1/A2 или USB 3.0 — от носителя зависит скорость).
- Монитор или ТВ по HDMI, USB-клавиатура и мышь, интернет (кабель или Wi-Fi).

## 1. Armbian от ophub

1. Скачайте образ для S905X3 (Debian **trixie**, ядро **6.12**) со страницы
   [ophub/amlogic-s9xxx-armbian → Releases](https://github.com/ophub/amlogic-s9xxx-armbian/releases),
   например `Armbian_*_amlogic_s905x3_trixie_6.12.*_desktop.img.gz`.
2. Запишите на носитель программой [balenaEtcher](https://etcher.balena.io/) (распаковывать не нужно).
3. В разделе `BOOT` носителя откройте `uEnv.txt` и укажите dtb приставки:
   `FDT=/dtb/amlogic/meson-sm1-tx3-bz.dtb`.

## 2. Загрузиться с карты

**С Android:** выключите приставку из розетки, вставьте носитель, зубочисткой зажмите кнопку **reset** в гнезде AV
и, не отпуская, включите питание; отпустите через 5–10 секунд, когда появится заставка.
Дальше приставка грузится с носителя, пока он вставлен.

**Если уже стоит Armbian:** вставьте носитель и перезагрузитесь; если грузится eMMC — способом с reset.

## 3. Первичная настройка Armbian

Мастер первого входа попросит пароль root, создать пользователя — назовите его **`agent`**, — часовой пояс и язык.
Подключите сеть (`nmtui` или значок сети).

## 4. Установить Kvorix

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/NineUPFLOW/kvorix.git
cd kvorix
sudo ./install.sh
sudo reboot
```

`install.sh` (повторный запуск безопасен):

1. ставит пакеты из [`packages.txt`](../packages.txt) (`--no-packages` — пропустить);
2. копирует [`rootfs/`](../rootfs) в `/` и настройки пользователя по умолчанию в `/home/agent`;
3. включает службы Kvorix (Доступ ИИ — выключен);
4. запускает `kvorix-firstboot`: свои ключи SSH, пароль показа экрана, секретный адрес noVNC, темы Доступа ИИ;
5. строит значки и заставку загрузки.

Tailscale ставится, если подключён его репозиторий: https://tailscale.com/download/linux/debian-trixie.

## 5. Перенести на встроенную память (eMMC) — по желанию

Система на eMMC быстрее карты. **Android будет стёрт** — сохраните заводскую прошивку заранее.

```bash
sudo armbian-install
```

Выберите модель **TX3** (S905X3). После «Done» выключите, выньте носитель, включите.

## Что дальше

- Смените пароль `agent`, если он простой ([SECURITY](../SECURITY.md)).
- [FEATURES](FEATURES.md) — все возможности, [TROUBLESHOOTING](TROUBLESHOOTING.md) — если что-то не так.
