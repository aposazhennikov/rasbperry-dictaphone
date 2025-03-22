#!/bin/bash

# Проверка на root-права
if [ "$EUID" -ne 0 ]; then
  echo "Этот скрипт должен запускаться с правами суперпользователя (sudo)."
  exit 1
fi

# Получаем имя пользователя (не root)
REAL_USER=${SUDO_USER:-$USER}
HOME_DIR=$(eval echo ~$REAL_USER)
MEDIA_DIR="$HOME_DIR/media"

# Путь к скриптам
SCRIPT_DIR="$HOME_DIR/main-scripts"
VENV_DIR="$SCRIPT_DIR/venv"
SERVICE_FILE="$SCRIPT_DIR/usb-monitor.service"
SERVICE_DEST="/etc/systemd/system/usb-monitor.service"

# Создаем директорию для кэша и настроек
echo "Создание директорий для настроек и монтирования..."
mkdir -p "$HOME_DIR/cache_tts"
mkdir -p "$MEDIA_DIR"
chown -R $REAL_USER:$REAL_USER "$HOME_DIR/cache_tts"
chown -R $REAL_USER:$REAL_USER "$MEDIA_DIR"
chmod -R 755 "$HOME_DIR/cache_tts"
chmod -R 755 "$MEDIA_DIR"

# Установка зависимостей
echo "Установка необходимых пакетов..."
apt-get update
apt-get install -y python3-pip python3-venv python3-dev libmagic1 udisks2 python3-pyudev policykit-1 ntfs-3g exfat-utils

# Настройка прав доступа для пользователя
echo "Настройка прав доступа для монтирования USB-устройств..."

# Добавляем пользователя в необходимые группы
echo "Добавление пользователя в группы для доступа к устройствам..."
# Создаем группу plugdev, если она не существует
if ! getent group plugdev >/dev/null; then
    groupadd plugdev
fi

# Добавляем пользователя в группы
usermod -a -G plugdev,disk,dialout,cdrom,video,audio,sudo $REAL_USER

# Настраиваем PolicyKit для монтирования без пароля
echo "Настройка PolicyKit для монтирования USB без пароля..."
mkdir -p /etc/polkit-1/localauthority/50-local.d/
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

# Добавляем sudoers правило для монтирования без пароля
echo "Настройка sudo для монтирования без пароля..."
cat > /etc/sudoers.d/usb-mount << EOF
# Разрешаем пользователю монтировать устройства без пароля
$REAL_USER ALL=(ALL) NOPASSWD: /bin/mount, /bin/umount
EOF
chmod 440 /etc/sudoers.d/usb-mount

# Создаем udev правило для автоматического изменения прав на USB-устройства
echo "Создание udev правила для USB-устройств..."
cat > /etc/udev/rules.d/99-usb-storage.rules << EOF
# Правило для изменения прав на USB-устройства
SUBSYSTEM=="block", ATTRS{idVendor}=="*", ATTRS{idProduct}=="*", ACTION=="add", RUN+="/bin/chown $REAL_USER:$REAL_USER /dev/%k"
EOF

# Перезагружаем правила udev
echo "Перезагрузка правил udev..."
udevadm control --reload-rules
udevadm trigger

# Проверка существования виртуального окружения
if [ ! -d "$VENV_DIR" ]; then
    echo "Создание виртуального окружения Python..."
    sudo -u $REAL_USER python3 -m venv $VENV_DIR
fi

# Активация виртуального окружения и установка пакетов
echo "Установка Python-зависимостей..."
sudo -u $REAL_USER bash -c "source $VENV_DIR/bin/activate && pip install pyudev python-magic"

# Проверяем, есть ли файл скрипта
if [ ! -f "$SCRIPT_DIR/usb_monitor_service.py" ]; then
    echo "ОШИБКА: Файл $SCRIPT_DIR/usb_monitor_service.py не найден!"
    exit 1
fi

# Устанавливаем права на запуск
chmod +x "$SCRIPT_DIR/usb_monitor_service.py"
chown $REAL_USER:$REAL_USER "$SCRIPT_DIR/usb_monitor_service.py"

# Копирование service-файла
echo "Установка systemd-сервиса..."
cp $SERVICE_FILE $SERVICE_DEST

# Перезагрузка демона systemd
systemctl daemon-reload

# Останавливаем сервис, если он запущен
systemctl stop usb-monitor.service || true

# Включаем и запускаем сервис
echo "Запуск сервиса мониторинга USB-устройств..."
systemctl enable usb-monitor.service
systemctl start usb-monitor.service

# Проверка статуса
echo "Проверка статуса сервиса..."
sleep 2
systemctl status usb-monitor.service

echo "Установка завершена. Сервис мониторинга USB-устройств запущен."
echo "ВНИМАНИЕ: Для корректной работы рекомендуется перезагрузить систему, чтобы применились все изменения."
echo "Для проверки журнала сервиса: journalctl -u usb-monitor -f"
echo "Для проверки файла настроек: cat $HOME_DIR/cache_tts/settings.json" 