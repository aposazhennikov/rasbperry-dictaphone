#!/usr/bin/env python3

import os
import json
import subprocess
import time
import vlc
from typing import List, Dict, Optional, Tuple, Set
import logging
from pathlib import Path
import magic  # для определения типа файла

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Опциональная инициализация Sentry
try:
    import sentry_sdk
    SENTRY_DSN = os.getenv('SENTRY_DSN')
    if SENTRY_DSN:
        sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=1.0)
        logger.info("Sentry успешно инициализирован")
    else:
        logger.info("SENTRY_DSN не установлен, логирование в Sentry отключено")
except ImportError:
    logger.info("sentry_sdk не установлен, логирование в Sentry отключено")

# Поддерживаемые аудио форматы
AUDIO_EXTENSIONS = {
    '.mp3', '.wav', '.ogg', '.m4a', '.wma', '.aac', 
    '.flac', '.alac', '.aiff', '.opus'
}

class USBDeviceManager:
    def __init__(self):
        """Инициализация менеджера USB-устройств."""
        logger.info("USB Device Manager инициализирован")
        # Инициализируем VLC с дополнительными опциями для отладки и кодеками
        vlc_opts = [
            '--verbose=2',  # Подробное логирование
            '--no-video',   # Отключаем видео
            '--aout=alsa',  # Используем ALSA для вывода звука
            '--codec=avcodec,all'  # Включаем все доступные кодеки
        ]
        self.vlc_instance = vlc.Instance(' '.join(vlc_opts))
        self.player = self.vlc_instance.media_player_new()
        self.current_media = None

    def _run_command(self, command: str, shell: bool = False) -> str:
        """
        Выполнение shell-команды и получение результата.
        
        Args:
            command (str): Команда для выполнения
            shell (bool): Использовать ли shell для выполнения команды

        Returns:
            str: Результат выполнения команды
        """
        try:
            if shell:
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
            else:
                result = subprocess.run(command.split(), capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Команда вернула ошибку: {result.stderr}")
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Ошибка при выполнении команды {command}: {e}")
            return ""

    def _get_block_devices(self) -> dict:
        """
        Получение информации о блочных устройствах через lsblk.
        
        Returns:
            dict: Информация о блочных устройствах
        """
        try:
            output = self._run_command("lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,LABEL,VENDOR,MODEL,SERIAL -J")
            logger.debug(f"lsblk output: {output}")
            return json.loads(output)
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка при разборе JSON от lsblk: {e}")
            return {"blockdevices": []}

    def _get_usb_devices(self) -> List[Dict[str, str]]:
        """
        Получение списка USB-устройств через различные системные команды.
        
        Returns:
            List[Dict[str, str]]: Список информации о USB-устройствах
        """
        try:
            lsusb_output = self._run_command("lsusb")
            logger.debug(f"lsusb output: {lsusb_output}")

            devices = []
            for sdx in self._run_command("ls /dev/sd*", shell=True).splitlines():
                if not sdx:
                    continue
                    
                udevadm_output = self._run_command(f"udevadm info --query=property {sdx}")
                logger.debug(f"udevadm output for {sdx}: {udevadm_output}")
                
                if "ID_BUS=usb" in udevadm_output:
                    devices.append({
                        'device': sdx,
                        'udevadm_info': udevadm_output
                    })
                    
            return devices
        except Exception as e:
            logger.error(f"Ошибка при получении списка USB-устройств: {e}")
            return []

    def _mount_device(self, device: str) -> str:
        """
        Монтирование USB-устройства с помощью udisks2.
        
        Args:
            device (str): Путь к устройству

        Returns:
            str: Точка монтирования или пустая строка
        """
        try:
            # Используем udisksctl для монтирования
            result = self._run_command(f"udisksctl mount -b {device}")
            
            # udisksctl возвращает строку вида "Mounted /dev/sda1 at /run/media/user/LABEL"
            if "at " in result:
                mount_point = result.split("at ")[-1].strip()
                logger.info(f"Устройство {device} успешно примонтировано в {mount_point}")
                return mount_point
                
            logger.error(f"Не удалось примонтировать {device}")
            return ""
            
        except Exception as e:
            logger.error(f"Ошибка при монтировании {device}: {e}")
            return ""

    def get_mounted_usb_devices(self) -> List[Dict[str, str]]:
        """
        Получение списка подключенных USB-накопителей.
        
        Returns:
            List[Dict[str, str]]: Список словарей с информацией о USB-накопителях
        """
        try:
            devices = []
            block_devices = self._get_block_devices()
            usb_devices = self._get_usb_devices()

            logger.info(f"Найдено USB-устройств: {len(usb_devices)}")
            logger.debug(f"USB devices: {usb_devices}")
            
            for usb_device in usb_devices:
                device_path = usb_device['device']
                logger.debug(f"Processing device: {device_path}")
                
                # Пропускаем основное устройство, если это диск
                if not device_path.endswith(('1', '2', '3', '4', '5')):
                    continue
                
                # Проверяем, примонтировано ли устройство
                mount_point = ""
                for device in block_devices.get('blockdevices', []):
                    if f"/dev/{device['name']}" == device_path:
                        mount_point = device.get('mountpoint', '')
                        break
                
                # Если устройство не примонтировано, монтируем его
                if not mount_point:
                    mount_point = self._mount_device(device_path)
                
                if mount_point:
                    devices.append({
                        'device': device_path,
                        'mount_point': mount_point
                    })
            
            return devices
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка примонтированных USB-устройств: {e}")
            return []

    def _is_audio_file(self, filename: str) -> bool:
        """
        Проверка, является ли файл аудио файлом.
        
        Args:
            filename (str): Имя файла

        Returns:
            bool: True если файл является аудио файлом
        """
        return Path(filename).suffix.lower() in AUDIO_EXTENSIONS

    def _get_audio_files(self, directory: str) -> List[str]:
        """
        Получение списка аудио файлов в директории.
        
        Args:
            directory (str): Путь к директории

        Returns:
            List[str]: Список путей к аудио файлам
        """
        try:
            audio_files = []
            for root, _, files in os.walk(directory):
                for file in files:
                    if self._is_audio_file(file):
                        full_path = os.path.join(root, file)
                        audio_files.append(full_path)
            return sorted(audio_files)
        except Exception as e:
            logger.error(f"Ошибка при поиске аудио файлов: {e}")
            return []

    def _validate_audio_file(self, file_path: str) -> bool:
        """
        Проверка валидности аудио файла.
        
        Args:
            file_path (str): Путь к аудио файлу

        Returns:
            bool: True если файл является валидным аудио файлом
        """
        try:
            # Используем python-magic для определения типа файла
            file_type = magic.from_file(file_path, mime=True)
            logger.debug(f"Тип файла {file_path}: {file_type}")
            
            if not file_type.startswith('audio/'):
                logger.warning(f"Файл {file_path} не является аудио файлом (тип: {file_type})")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Ошибка при проверке файла {file_path}: {e}")
            return False

    def _play_audio(self, file_path: str) -> None:
        """
        Воспроизведение аудио файла.
        
        Args:
            file_path (str): Путь к аудио файлу
        """
        try:
            print(f"\nВоспроизведение: {os.path.basename(file_path)}")
            logger.info(f"Воспроизведение файла: {file_path}")
            
            # Проверяем валидность файла
            if not self._validate_audio_file(file_path):
                print(f"Ошибка: файл {os.path.basename(file_path)} не является валидным аудио файлом")
                return
            
            # Останавливаем текущее воспроизведение
            self._stop_playback()
            
            # Создаем новый медиа объект с дополнительными опциями
            media_opts = ['input-repeat=1']  # Добавляем опции для отладки
            self.current_media = self.vlc_instance.media_new(file_path)
            for opt in media_opts:
                self.current_media.add_option(opt)
            
            # Устанавливаем обработчики событий
            event_manager = self.current_media.event_manager()
            event_manager.event_attach(vlc.EventType.MediaStateChanged, 
                                     lambda e: logger.debug(f"Состояние медиа изменилось: {e.type}"))
            
            self.player.set_media(self.current_media)
            
            # Воспроизводим
            result = self.player.play()
            logger.debug(f"Результат запуска воспроизведения: {result}")
            
            # Ждем начала воспроизведения
            time.sleep(0.5)
            
            # Проверяем статус
            state = self.player.get_state()
            logger.debug(f"Состояние плеера: {state}")
            
            if state == vlc.State.Error:
                error = self.player.get_media().get_mrl()
                logger.error(f"Ошибка воспроизведения: {error}")
                print(f"Ошибка воспроизведения файла: {os.path.basename(file_path)}")
                return
            
            duration = self.player.get_length() / 1000  # в секундах
            logger.info(f"Длительность файла: {duration:.2f} секунд")
            
            if duration > 0:
                print(f"Длительность: {duration:.2f} сек")
                # Ждем окончания воспроизведения
                while self.player.is_playing():
                    time.sleep(0.1)
            else:
                logger.warning(f"Не удалось определить длительность файла {file_path}")
                print("Ошибка: не удалось определить длительность файла")
                self._stop_playback()
                
        except Exception as e:
            logger.error(f"Ошибка при воспроизведении {file_path}: {e}")
            print(f"Ошибка при воспроизведении: {e}")
            self._stop_playback()

    def _stop_playback(self) -> None:
        """Остановка воспроизведения."""
        if self.player.is_playing():
            self.player.stop()
            time.sleep(0.1)  # Даем время на остановку

    def list_files(self, mount_point: str) -> None:
        """
        Вывод списка файлов на USB-накопителе и воспроизведение аудио файлов.
        
        Args:
            mount_point (str): Точка монтирования USB-накопителя
        """
        try:
            print(f"\nСодержимое USB-накопителя ({mount_point}):")
            
            # Получаем список всех файлов
            for root, dirs, files in os.walk(mount_point):
                level = root.replace(mount_point, '').count(os.sep)
                indent = '  ' * level
                print(f"{indent}{os.path.basename(root)}/")
                subindent = '  ' * (level + 1)
                for f in files:
                    print(f"{subindent}{f}")
            
            # Ищем аудио файлы
            audio_files = self._get_audio_files(mount_point)
            
            if audio_files:
                print(f"\nНайдено аудио файлов: {len(audio_files)}")
                for i, audio_file in enumerate(audio_files, 1):
                    print(f"{i}. {os.path.basename(audio_file)}")
                    self._play_audio(audio_file)
            else:
                print("\nАудио файлы не найдены")
                
        except Exception as e:
            logger.error(f"Ошибка при выводе списка файлов: {e}")

    def __del__(self):
        """Очистка ресурсов при удалении объекта."""
        self._stop_playback()

def main():
    """Основная функция программы."""
    try:
        usb_manager = USBDeviceManager()
        devices = usb_manager.get_mounted_usb_devices()
        
        if not devices:
            print("USB-накопители не найдены")
            return
        
        print(f"Найдено USB-накопителей: {len(devices)}")
        for device in devices:
            print(f"\nУстройство: {device['device']}")
            print(f"Точка монтирования: {device['mount_point']}")
            usb_manager.list_files(device['mount_point'])
            
    except KeyboardInterrupt:
        print("\nПрограмма остановлена пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")

if __name__ == "__main__":
    main() 