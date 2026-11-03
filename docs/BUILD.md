# Как собрать Kvorix самому

Есть два пути: **установить Kvorix поверх чистого Armbian** (шаги 1–4) и затем, если нужно,
**собрать свой образ** для раздачи (шаг 5). Всё делается на самой приставке (arm64), отдельный компьютер нужен только
для записи карт.

## 1. База: Armbian от ophub

Kvorix собран на образе [ophub/amlogic-s9xxx-armbian](https://github.com/ophub/amlogic-s9xxx-armbian):

| Параметр | Значение |
|---|---|
| Образ | `Armbian_*_amlogic_s905x3_trixie_6.12.*_server` или `_desktop` (Releases ophub) |
| Ядро | 6.12.x-ophub |
| dtb | `meson-sm1-tx3-bz.dtb` (TX3 BZ; для других ревизий — см. [HARDWARE](HARDWARE.md)) |

1. Запишите образ ophub на карту, загрузитесь (как в [INSTALL](INSTALL.md), шаг 2).
2. В `/boot/uEnv.txt` (или `extlinux.conf`) укажите нужный dtb: `FDT=/dtb/amlogic/meson-sm1-tx3-bz.dtb`.
3. Пройдите первичную настройку Armbian, создайте пользователя **`agent`** (имя важно: часть путей рассчитана на него).

## 2. Пакеты

```bash
sudo apt update
sudo apt install -y $(grep -v '^#' packages.txt)
```

[`packages.txt`](../packages.txt) — полный список пакетов, поставленных вручную на эталонной приставке.
Tailscale ставится из своего репозитория: https://tailscale.com/download/linux/debian-trixie.

## 3. Файлы Kvorix

```bash
git clone https://github.com/NineUPFLOW/kvorix.git
cd kvorix
sudo ./install.sh
```

`install.sh`:

1. копирует [`rootfs/`](../rootfs) в `/` (скрипты, службы, Настройки, оболочка, темы, значки, заставка);
2. ставит пакеты из `packages.txt` (флаг `--no-packages` — пропустить);
3. ставит настройки пользователя по умолчанию; обход блокировок использует `nfqws` из
   [bol-van/zapret](https://github.com/bol-van/zapret) (уже лежит в `rootfs/usr/local/sbin`);
4. включает службы Kvorix и запускает `kvorix-firstboot` (свои ключи, пароль VNC, токен noVNC);
5. строит значки (`kvorix-make-icons`) и тему Plymouth `kvorix` (`update-initramfs`).

Повторный запуск безопасен: файлы просто обновятся.

## 4. Проверить

```bash
sudo kvorix-health-check            # все пункты PASS
bash /usr/local/share/kvorix/tests/test-all.sh > /tmp/test.out 2>&1; grep -E '^(ОШИБКА|=====)' /tmp/test.out
```

`test-all.sh` открывает и закрывает окна на экране — запускайте из графического сеанса, когда никто не работает.

## 5. Собрать свой образ (для своих приставок)

На приставке с готовой и настроенной системой:

```bash
sudo kvorix-build-image /путь/к/Armbian_ophub.img.gz /var/tmp/kvx-build
```

Скрипт [`kvorix-build-image`](../rootfs/usr/local/sbin/kvorix-build-image):

1. берёт из базового образа ophub разметку и загрузочный раздел (там скрипты загрузки с SD/USB);
2. копирует работающую систему в новый раздел (без `/proc`, `/sys`, кэшей, журналов, бэкапов, профиля браузера);
3. ставит в загрузочный раздел ядро, dtb, initrd и заставку с приставки, прописывает новые UUID в `uEnv.txt` и `fstab`;
4. **удаляет всё личное:** сети Wi-Fi и их пароли, ключи SSH, Tailscale, Bluetooth-пары, токены noVNC/VNC,
   «Доступ ИИ» (ключи, темы ntfy), историю, `machine-id`; ставит пароль `agent`/`kvorix` со сменой при первом входе;
5. включает `kvorix-firstboot` и растяжение раздела при первом запуске;
6. проверяет, что в образе нет секретов исходной приставки (иначе завершается с ошибкой).

Нужно свободного места примерно столько, сколько занимает система (+0,5 ГБ). Затем сжать и выложить:

```bash
xz -T0 -6 -k /var/tmp/kvx-build/kvorix.img
sha256sum kvorix.img.xz > kvorix.img.xz.sha256
```

## Структура репозитория

```
rootfs/          файлы, которые ложатся в / (как на приставке)
  usr/local/bin  оболочка, утилиты, Настройки (armbian-center), диспетчер задач …
  usr/local/sbin службы: hdmi-autodetect, firstboot, сборка образа, значки, проверки
  usr/local/share/armbian-gui   приложение «Настройки» (Python + GTK 3)
  usr/local/share/rsaarm        оболочка: панель задач, «Пуск», стили
  usr/share/icons/Kvorix-Icons* тема значков
  usr/share/themes/Kvorix*      темы GTK/xfwm4
  usr/share/plymouth/themes/kvorix  заставка загрузки
  etc/systemd/system            службы и таймеры Kvorix
  etc/skel                      настройки пользователя по умолчанию
packages.txt     пакеты Debian
install.sh       установка на чистый Armbian
docs/            документация
```
