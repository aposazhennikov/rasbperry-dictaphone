#!/bin/bash

# Проверяем, запущен ли скрипт с правами root
if [ "$EUID" -ne 0 ]; then 
    echo "Пожалуйста, запустите скрипт с правами root (используйте sudo)"
    exit 1
fi

# Определяем пути
SERVICE_NAME="dictaphone"
SERVICE_FILE="$SERVICE_NAME.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_DIR="/etc/systemd/system"

# Копируем файл службы
echo "Копирование файла службы в $SYSTEMD_DIR..."
cp "$SCRIPT_DIR/$SERVICE_FILE" "$SYSTEMD_DIR/"

# Устанавливаем правильные разрешения
echo "Установка разрешений..."
chmod 644 "$SYSTEMD_DIR/$SERVICE_FILE"

# Перезагружаем демон systemd
echo "Перезагрузка демона systemd..."
systemctl daemon-reload

# Включаем службу для автозапуска
echo "Включение службы для автозапуска..."
systemctl enable "$SERVICE_NAME"

# Запускаем службу
echo "Запуск службы..."
systemctl start "$SERVICE_NAME"

# Проверяем статус
echo "Проверка статуса службы..."
systemctl status "$SERVICE_NAME"

echo "Установка службы завершена!"
echo "Для управления службой используйте следующие команды:"
echo "  sudo systemctl start $SERVICE_NAME    # Запуск службы"
echo "  sudo systemctl stop $SERVICE_NAME     # Остановка службы"
echo "  sudo systemctl restart $SERVICE_NAME  # Перезапуск службы"
echo "  sudo systemctl status $SERVICE_NAME   # Проверка статуса" 