#!/usr/bin/env python3

import os
import sys
import json
import time
import logging
import subprocess
import signal
import pyudev
from typing import Dict, List, Any, Optional
import shutil

# Путь к домашней директории пользователя для логов
HOME_DIR = os.path.expanduser("~")
LOG_FILE = os.path.join(HOME_DIR, "usb_monitor.log")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("usb_monitor")

# Путь к файлу настроек
SETTINGS_FILE = os.path.join(HOME_DIR, "cache_tts/settings.json")

class USBMonitorService:
    def __init__(self):
        """Инициализация сервиса мониторинга USB-устройств."""
        self.context = pyudev.Context()
        self.monitor = pyudev.Monitor.from_netlink(self.context)
        self.monitor.filter_by(subsystem='block', device_type='partition')
        self.devices = {}  # Текущие подключенные устройства
        
        # Обработчики сигналов для корректного завершения
        signal.signal(signal.SIGTERM, self.handle_signal)
        signal.signal(signal.SIGINT, self.handle_signal)
        
        logger.info("USB Monitor Service инициализирован")
    
    def handle_signal(self, signum, frame):
        """Обработка сигналов для корректного завершения."""
        logger.info(f"Получен сигнал {signum}, завершение работы...")
        # Отмечаем все устройства как отключенные перед выходом
        self._mark_all_devices_disconnected()
        sys.exit(0)
    
    def _mark_all_devices_disconnected(self):
        """Отмечает все устройства как отключенные в файле настроек."""
        try:
            settings = self._load_settings()
            if 'usb_devices' in settings:
                settings['usb_devices'] = []  # Полностью очищаем список устройств
                self._save_settings(settings)
                logger.info("Все устройства удалены из настроек")
        except Exception as e:
            logger.error(f"Ошибка при отметке устройств как отключенных: {e}")
    
    def _load_settings(self) -> Dict[str, Any]:
        """Загрузка настроек из файла."""
        settings = {}
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
            else:
                logger.warning(f"Файл настроек {SETTINGS_FILE} не найден")
                # Если директория не существует, создадим её
                os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
                # Создаём базовые настройки, если файла нет
                settings = {
                    "voice": "ru-RU-Standard-D",
                    "tts_engine": "google_cloud",
                    "google_cloud_credentials": os.path.join(HOME_DIR, "main-scripts/credentials-google-api.json"),
                    "system_volume": 80,
                    "usb_devices": []
                }
                with open(SETTINGS_FILE, 'w') as f:
                    json.dump(settings, f, indent=4, ensure_ascii=False)
                logger.info(f"Создан новый файл настроек {SETTINGS_FILE}")
        except Exception as e:
            logger.error(f"Ошибка при загрузке настроек: {e}")
        return settings
    
    def _save_settings(self, settings: Dict[str, Any]) -> None:
        """Сохранение настроек в файл."""
        try:
            # Создаем директорию, если она не существует
            os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
            
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            logger.info("Настройки сохранены")
        except Exception as e:
            logger.error(f"Ошибка при сохранении настроек: {e}")
    
    def _run_command(self, command: str, shell: bool = False) -> tuple:
        """Выполнение команды и получение вывода."""
        try:
            if shell:
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
            else:
                result = subprocess.run(command.split(), capture_output=True, text=True)
            return result.stdout, result.stderr, result.returncode
        except Exception as e:
            logger.error(f"Ошибка выполнения команды {command}: {e}")
            return "", str(e), 1
    
    def _is_device_mounted(self, device_path: str) -> tuple:
        """Проверка, примонтировано ли устройство."""
        try:
            # Проверяем с помощью findmnt
            stdout, stderr, rc = self._run_command(f"findmnt -n -o TARGET {device_path}")
            if rc == 0 and stdout.strip():
                mount_point = stdout.strip()
                logger.debug(f"Устройство {device_path} уже примонтировано в {mount_point}")
                return True, mount_point
            
            # Дополнительная проверка через /proc/mounts
            with open('/proc/mounts', 'r') as f:
                for line in f:
                    if device_path in line:
                        mount_point = line.split()[1]
                        logger.debug(f"Устройство {device_path} найдено в /proc/mounts: {mount_point}")
                        return True, mount_point
            
            return False, ""
        except Exception as e:
            logger.error(f"Ошибка при проверке монтирования {device_path}: {e}")
            return False, ""
    
    def _mount_device(self, device_path: str) -> str:
        """Монтирование устройства."""
        try:
            # Проверяем, примонтировано ли уже устройство
            is_mounted, mount_point = self._is_device_mounted(device_path)
            if is_mounted:
                logger.info(f"Устройство {device_path} уже примонтировано в {mount_point}")
                return mount_point
            
            # Если нет, сначала пробуем через udisksctl
            stdout, stderr, rc = self._run_command(f"udisksctl mount -b {device_path}")
            
            if rc == 0 and "at " in stdout:
                mount_point = stdout.split("at ")[-1].strip()
                logger.info(f"Устройство {device_path} успешно примонтировано в {mount_point}")
                return mount_point
            else:
                logger.warning(f"Не удалось примонтировать через udisks2: {stderr}")
                
                # Пробуем получить информацию о файловой системе
                fs_stdout, fs_stderr, fs_rc = self._run_command(f"lsblk -o FSTYPE -n {device_path}")
                fstype = fs_stdout.strip() if fs_rc == 0 else "auto"
                
                # Создаем точку монтирования в домашней директории пользователя
                device_name = os.path.basename(device_path)
                mount_dir = os.path.join(HOME_DIR, "media", device_name)
                
                # Создаем директорию, если она не существует
                if not os.path.exists(mount_dir):
                    os.makedirs(mount_dir, exist_ok=True)
                
                # Пробуем монтировать напрямую через mount с sudo
                mount_cmd = f"sudo mount -t {fstype} {device_path} {mount_dir}"
                m_stdout, m_stderr, m_rc = self._run_command(mount_cmd, shell=True)
                
                if m_rc == 0:
                    logger.info(f"Устройство {device_path} успешно примонтировано в {mount_dir} через прямое монтирование")
                    return mount_dir
                else:
                    # Еще одна попытка - попробуем использовать fusermount, если файловая система поддерживается
                    if fstype.lower() in ['vfat', 'ntfs', 'exfat']:
                        if fstype.lower() == 'ntfs':
                            fuse_cmd = f"ntfs-3g {device_path} {mount_dir}"
                        elif fstype.lower() == 'exfat':
                            fuse_cmd = f"mount.exfat {device_path} {mount_dir}"
                        else:
                            fuse_cmd = f"mount -t {fstype} -o uid=$(id -u),gid=$(id -g) {device_path} {mount_dir}"
                        
                        f_stdout, f_stderr, f_rc = self._run_command(fuse_cmd, shell=True)
                        
                        if f_rc == 0:
                            logger.info(f"Устройство {device_path} успешно примонтировано в {mount_dir} через FUSE")
                            return mount_dir
                    
                    # Последняя попытка - попробуем читать устройство без монтирования
                    # и создать символическую ссылку в settings.json
                    logger.error(f"Не удалось примонтировать {device_path}: {m_stderr}")
                    
                    # Добавляем запись в settings.json с информацией о немонтированном устройстве
                    device_info = self._get_device_info(device_path)
                    if device_info:
                        device_info['mount_point'] = "Не примонтировано"
                        device_info['is_mounted'] = False
                        device_info['device_path'] = device_path
                        self.devices[device_path] = device_info
                        self.update_settings()
                        logger.warning(f"Устройство {device_path} добавлено как немонтированное")
                    
                    return ""
        except Exception as e:
            logger.error(f"Ошибка при монтировании {device_path}: {e}")
            return ""
    
    def _unmount_device(self, device_path: str) -> bool:
        """Размонтирование устройства."""
        try:
            is_mounted, _ = self._is_device_mounted(device_path)
            if not is_mounted:
                logger.info(f"Устройство {device_path} уже отмонтировано")
                return True
            
            stdout, stderr, rc = self._run_command(f"udisksctl unmount -b {device_path}")
            
            if rc == 0:
                logger.info(f"Устройство {device_path} успешно отмонтировано")
                return True
            else:
                logger.error(f"Не удалось отмонтировать {device_path}: {stderr}")
                return False
        except Exception as e:
            logger.error(f"Ошибка при отмонтировании {device_path}: {e}")
            return False
    
    def _get_device_info(self, device_path: str) -> Optional[Dict[str, Any]]:
        """Получение информации об устройстве."""
        try:
            # Получаем информацию о файловой системе, размере и метке устройства
            stdout, stderr, rc = self._run_command(f"lsblk -o NAME,SIZE,LABEL,FSTYPE,MODEL -J {device_path}")
            if rc != 0:
                logger.error(f"Ошибка получения информации о {device_path}: {stderr}")
                return None
            
            try:
                data = json.loads(stdout)
                if 'blockdevices' in data and data['blockdevices']:
                    device_data = data['blockdevices'][0]
                    
                    # Определяем имя устройства (метку или модель, или имя)
                    device_name = device_data.get('label', '') or device_data.get('model', '') or device_data.get('name', 'Неизвестно')
                    
                    return {
                        'name': device_name,
                        'size': device_data.get('size', 'Неизвестно'),
                        'filesystem': device_data.get('fstype', 'Неизвестно'),
                        'device': device_path,
                        'is_connected': True
                    }
            except json.JSONDecodeError:
                logger.error(f"Ошибка парсинга JSON для {device_path}")
                
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении информации о {device_path}: {e}")
            return None
    
    def _is_usb_device(self, device_path: str) -> bool:
        """Проверка, является ли устройство USB-накопителем."""
        try:
            stdout, stderr, rc = self._run_command(f"udevadm info --query=property {device_path}")
            if rc != 0:
                logger.error(f"Ошибка получения свойств {device_path}: {stderr}")
                return False
            
            return "ID_BUS=usb" in stdout
        except Exception as e:
            logger.error(f"Ошибка при проверке USB-статуса {device_path}: {e}")
            return False
    
    def _get_total_space(self, mount_point: str) -> str:
        """Получение общего размера устройства."""
        try:
            total, used, free = shutil.disk_usage(mount_point)
            # Преобразуем в читабельный формат
            if total > 1e9:  # Более 1 ГБ
                return f"{total / 1e9:.1f} GB"
            else:
                return f"{total / 1e6:.1f} MB"
        except Exception as e:
            logger.error(f"Ошибка при получении размера {mount_point}: {e}")
            return "Неизвестно"
    
    def handle_device_event(self, device):
        """Обработка событий подключения/отключения устройств."""
        device_path = device.device_node
        action = device.action
        
        # Проверяем, что это блочное устройство и раздел
        if device.device_type != 'partition':
            return
        
        logger.info(f"Обнаружено событие {action} для устройства {device_path}")
        
        if action == 'add':
            # Проверяем, что это USB-устройство при добавлении
            if self._is_usb_device(device_path):
                self.handle_device_added(device_path)
            else:
                logger.info(f"Устройство {device_path} не является USB-устройством, игнорируем")
        elif action == 'remove':
            # При удалении обрабатываем все устройства, так как проверка на USB может не работать
            self.handle_device_removed(device_path)
    
    def handle_device_added(self, device_path: str) -> None:
        """Обработка события подключения устройства."""
        try:
            logger.info(f"Обработка подключения устройства {device_path}")
            
            # Монтируем устройство
            mount_point = self._mount_device(device_path)
            if not mount_point:
                logger.error(f"Не удалось примонтировать {device_path}")
                return
            
            # Получаем информацию об устройстве
            device_info = self._get_device_info(device_path)
            if not device_info:
                logger.error(f"Не удалось получить информацию о {device_path}")
                return
            
            # Добавляем точку монтирования и путь к устройству
            device_info['mount_point'] = mount_point
            device_info['device'] = device_path  # Обязательно сохраняем путь к устройству
            
            # Получаем точный размер
            device_info['size'] = self._get_total_space(mount_point)
            
            # Сохраняем в словаре текущих устройств
            self.devices[device_path] = device_info
            
            # Обновляем настройки
            self.update_settings()
            
            logger.info(f"Устройство добавлено: {device_info}")
        except Exception as e:
            logger.error(f"Ошибка при обработке подключения {device_path}: {e}")
    
    def handle_device_removed(self, device_path: str) -> None:
        """Обработка события отключения устройства."""
        try:
            logger.info(f"Обработка отключения устройства {device_path}")
            
            # Удаляем из словаря текущих устройств
            if device_path in self.devices:
                device_info = self.devices.pop(device_path)
                logger.info(f"Устройство {device_path} удалено из списка")
                
                # Обновляем настройки, отмечая устройство как отключенное
                self.update_settings()
            else:
                logger.warning(f"Устройство {device_path} не найдено в списке текущих устройств")
                
                # Попробуем найти устройство в настройках и обновить его статус
                settings = self._load_settings()
                if 'usb_devices' in settings:
                    updated = False
                    for device in settings['usb_devices']:
                        if 'device' in device and device['device'] == device_path:
                            device['is_connected'] = False
                            updated = True
                            logger.info(f"Устройство {device_path} помечено как отключенное в настройках")
                    
                    if updated:
                        self._save_settings(settings)
                
        except Exception as e:
            logger.error(f"Ошибка при обработке отключения {device_path}: {e}")
    
    def update_settings(self) -> None:
        """Обновление файла настроек."""
        try:
            # Загружаем текущие настройки
            settings = self._load_settings()
            
            # Создаем список подключенных устройств
            usb_devices = []
            for device_info in self.devices.values():
                usb_devices.append({
                    'name': device_info['name'],
                    'size': device_info['size'],
                    'mount_point': device_info['mount_point'],
                    'filesystem': device_info['filesystem'],
                    'device': device_info['device'],  # Добавляем device_path в настройки
                    'is_connected': True
                })
            
            # Обновляем список устройств в настройках
            settings['usb_devices'] = usb_devices
            
            # Сохраняем настройки
            self._save_settings(settings)
            
            logger.info(f"Настройки обновлены: {len(usb_devices)} устройств")
        except Exception as e:
            logger.error(f"Ошибка при обновлении настроек: {e}")
    
    def scan_existing_devices(self) -> None:
        """Сканирование существующих USB-устройств при запуске."""
        try:
            logger.info("Сканирование существующих USB-устройств...")
            
            # Получаем список блочных устройств типа partition
            devices = self.context.list_devices(subsystem='block', DEVTYPE='partition')
            
            for device in devices:
                device_path = device.device_node
                
                # Проверяем, является ли устройство USB
                if self._is_usb_device(device_path):
                    logger.info(f"Найдено существующее USB-устройство: {device_path}")
                    self.handle_device_added(device_path)
            
            logger.info(f"Сканирование завершено. Найдено устройств: {len(self.devices)}")
        except Exception as e:
            logger.error(f"Ошибка при сканировании устройств: {e}")
    
    def run(self):
        """Основной цикл работы сервиса."""
        try:
            # Сначала сканируем существующие устройства
            self.scan_existing_devices()
            
            # Запускаем мониторинг новых устройств
            self.monitor.start()
            logger.info("Мониторинг USB-устройств запущен")
            
            for device in iter(self.monitor.poll, None):
                self.handle_device_event(device)
                
        except KeyboardInterrupt:
            logger.info("Получен сигнал прерывания, завершение работы...")
            self._mark_all_devices_disconnected()
        except Exception as e:
            logger.error(f"Непредвиденная ошибка: {e}")
            self._mark_all_devices_disconnected()

if __name__ == "__main__":
    # Запуск сервиса
    service = USBMonitorService()
    service.run() 