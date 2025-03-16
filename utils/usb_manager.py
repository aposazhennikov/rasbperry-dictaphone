#!/usr/bin/env python3

import os
import json
import subprocess
import time
import vlc
from typing import List, Dict, Optional
import logging
from pathlib import Path
import magic
import sentry_sdk

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Поддерживаемые аудио форматы
AUDIO_EXTENSIONS = {
    '.mp3', '.wav', '.ogg', '.m4a', '.wma', '.aac', 
    '.flac', '.alac', '.aiff', '.opus'
}

class USBDeviceManager:
    def __init__(self):
        """Инициализация менеджера USB-устройств."""
        try:
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
        except Exception as e:
            logger.error(f"Ошибка при инициализации USB Device Manager: {e}")
            sentry_sdk.capture_exception(e)
            raise

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
            sentry_sdk.capture_exception(e)
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
            sentry_sdk.capture_exception(e)
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
            sentry_sdk.capture_exception(e)
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
            sentry_sdk.capture_exception(e)
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
                
                # Получаем информацию об устройстве из lsblk
                device_info = {}
                for device in block_devices.get('blockdevices', []):
                    if f"/dev/{device['name']}" == device_path:
                        device_info = {
                            'name': device.get('label', 'Без метки'),
                            'size': device.get('size', 'Неизвестно'),
                            'mount_point': device.get('mountpoint', ''),
                            'device': device_path
                        }
                        break
                
                if not device_info:
                    continue
                
                # Если устройство не примонтировано, монтируем его
                if not device_info['mount_point']:
                    mount_point = self._mount_device(device_path)
                    if mount_point:
                        device_info['mount_point'] = mount_point
                    else:
                        continue
                
                devices.append(device_info)
            
            return devices
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка примонтированных USB-устройств: {e}")
            sentry_sdk.capture_exception(e)
            return []

    def list_files(self, mount_point: str) -> None:
        """
        Вывод списка файлов на USB-накопителе.
        
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
                
        except Exception as e:
            logger.error(f"Ошибка при выводе списка файлов: {e}")
            sentry_sdk.capture_exception(e)
            print("Произошла ошибка при чтении содержимого флешки") 