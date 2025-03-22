#!/bin/bash

# Требуются права суперпользователя
if [ "$EUID" -ne 0 ]; then
  echo "Этот скрипт должен запускаться с правами суперпользователя (sudo)."
  echo "Этот скрипт должен запускаться с правами суперпользователя (sudo)."
  exit 1
fi

# Получаем имя текущего пользователя
REAL_USER=${SUDO_USER:-$USER}
HOME_DIR=$(eval echo ~$REAL_USER)
MEDIA_DIR="$HOME_DIR/media"

echo "Настройка прав для пользователя $REAL_USER..."

# 1. Создаем директорию для монтирования в домашнем каталоге
echo "Создание директории для монтирования USB-устройств..."
mkdir -p "$MEDIA_DIR"
chown -R $REAL_USER:$REAL_USER "$MEDIA_DIR"
chmod -R 755 "$MEDIA_DIR"

# 2. Создаем директорию для кэша и настроек
echo "Создание директории для настроек..."
mkdir -p "$HOME_DIR/cache_tts"
chown -R $REAL_USER:$REAL_USER "$HOME_DIR/cache_tts"
chmod -R 755 "$HOME_DIR/cache_tts"

# 3. Добавляем пользователя в необходимые группы
echo "Добавление пользователя в группы для доступа к устройствам..."
# Создаем группу plugdev, если она не существует
if ! getent group plugdev >/dev/null; then
    groupadd plugdev
fi

# Добавляем пользователя в группы
usermod -a -G plugdev,disk,dialout,cdrom,video,audio,sudo $REAL_USER

# 4. Настраиваем PolicyKit для монтирования без пароля
echo "Настройка PolicyKit для монтирования USB без пароля..."
cat > /etc/polkit-1/localauthority/50-local.d/10-udisks2.pkla << EOF
[udisks2-mount-system]
Identity=unix-user:$REAL_USER
Action=org.freedesktop.udisks2.filesystem-mount-system
ResultAny=yes
ResultInactive=yes
ResultActive=yes

[udisks2-mount]
Identity=unix-user:$REAL_USER
Action=org.freedesktop.udisks2.filesystem-mount
ResultAny=yes
ResultInactive=yes
ResultActive=yes

[udisks2-eject]
Identity=unix-user:$REAL_USER
Action=org.freedesktop.udisks2.eject-media
ResultAny=yes
ResultInactive=yes
ResultActive=yes
EOF

chmod 644 /etc/polkit-1/localauthority/50-local.d/10-udisks2.pkla

# 5. Добавляем sudoers правило для монтирования без пароля
echo "Настройка sudo для монтирования без пароля..."
cat > /etc/sudoers.d/usb-mount << EOF
# Разрешаем пользователю монтировать устройства без пароля
$REAL_USER ALL=(ALL) NOPASSWD: /bin/mount, /bin/umount
EOF
chmod 440 /etc/sudoers.d/usb-mount

# 6. Создаем udev правило для автоматического изменения прав на USB-устройства
echo "Создание udev правила для USB-устройств..."
cat > /etc/udev/rules.d/99-usb-storage.rules << EOF
# Правило для изменения прав на USB-устройства
SUBSYSTEM=="block", ATTRS{idVendor}=="*", ATTRS{idProduct}=="*", ACTION=="add", RUN+="/bin/chown $REAL_USER:$REAL_USER /dev/%k"
EOF

# 7. Перезагружаем правила udev
echo "Перезагрузка правил udev..."
udevadm control --reload-rules
udevadm trigger

# 8. Настройка разрешений для работы с дисковыми устройствами
echo "Настройка дополнительных разрешений..."
chmod 666 /dev/sd*
chown -R root:disk /dev/sd*

echo "Настройка завершена. Для применения всех изменений рекомендуется перезагрузить систему."
echo "ВАЖНО: После перезагрузки запустите службу мониторинга USB командой:"
echo "sudo systemctl restart usb-monitor.service" 