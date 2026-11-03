# Железо: Tanix TX3

| Узел | Что стоит | Состояние в Kvorix |
|---|---|---|
| SoC | Amlogic S905X3 (meson-sm1), 4× Cortex-A55 | до 2,1 ГГц (в Android 1,9), governor `ondemand` |
| GPU | Mali-G31 | Panfrost (Mesa), X11 glamor, Chromium на GPU |
| ОЗУ | 2 ГБ LPDDR3/4 | + zram |
| eMMC | 16 ГБ | система (после `armbian-install`) |
| Wi-Fi / Bluetooth | Broadcom BCM4330 (brcmfmac) | работает; **поиск сетей во время работы может подвесить чип** — не запускайте сканирование в цикле |
| Ethernet | 100 Мбит (TX3-100Mb) | работает |
| HDMI | 2.0, CEC | **сигнал HPD не работает** — монитор определяется по EDID через DDC (`hdmi-autodetect`) |
| Звук | HDMI | PipeWire; аналоговый AV не настроен |
| Передняя панель | FD6551, 4 цифры + значки | `front-panel` (свой драйвер на Python) |
| ИК-приёмник | NEC | `ir-keytable`, раскладка `/etc/rc_keymaps/kvorix-tx3.toml` |
| Видеодекодер | meson-vdec (v4l2m2m) | **выключен**: зависает при запуске ~1 из 3 раз |

## Дерево устройств

Используется `meson-sm1-tx3-bz.dtb` (ревизия TX3 BZ). Для других ревизий/приставок на S905X3 посмотрите список
`/boot/dtb/amlogic/meson-sm1-*.dtb` и поменяйте `FDT=` в `/boot/uEnv.txt`. Wi-Fi и передняя панель могут отличаться.

## Загрузчик

Заводской U-Boot не меняется. Kvorix загружается цепочкой ophub (`s905_autoscript` / `emmc_autoscript` → `u-boot.ext`
→ `uEnv.txt`). Переменные заводского U-Boot можно только читать: `sudo fw_printenv`. Сохраните их копию до экспериментов.

## Что не перенесено из Android

Сверено с заводской прошивкой: частоты CPU у Kvorix выше, прошивка Wi-Fi та же — переносить нечего.
