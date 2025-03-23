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
    level=logging.INFO,  # Поменяли с DEBUG на INFO
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("usb_monitor.log"),  # Логи идут в файл
        logging.StreamHandler()  # И на консоль, но будут только INFO и выше
    ]
)
logger = logging.getLogger(__name__)

# Отключаем логи VLC
os.environ["VLC_VERBOSE"] = "-1"  # Отключаем подробные логи VLC

# Опциональная инициализация Sentry
try:
    import sentry_sdk
    SENTRY_DSN = os.getenv('SENTRY_DSN')
    if SENTRY_DSN:
        sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=1.0)
        logger.info("Sentry успешно инициализирован")
    else:
        logger.debug("SENTRY_DSN не установлен, логирование в Sentry отключено")
except ImportError:
    logger.debug("sentry_sdk не установлен, логирование в Sentry отключено")

# Поддерживаемые аудио форматы
AUDIO_EXTENSIONS = {
    '.mp3', '.wav', '.ogg', '.m4a', '.wma', '.aac', 
    '.flac', '.alac', '.aiff', '.opus'
}

# Путь к файлу настроек
SETTINGS_FILE = "/home/aleks/cache_tts/settings.json"

class USBDeviceManager:
    def __init__(self):
        """Инициализация менеджера USB-устройств."""
        try:
            logger.debug("USB Device Manager инициализирован")
            # Инициализируем VLC с дополнительными опциями для отладки и кодеками
            vlc_opts = [
                '--verbose=-1',  # Минимальное логирование
                '--no-video',    # Отключаем видео
                '--aout=alsa',   # Используем ALSA для вывода звука
                '--codec=avcodec,all'  # Включаем все доступные кодеки
            ]
            self.vlc_instance = vlc.Instance(' '.join(vlc_opts))
            self.player = self.vlc_instance.media_player_new()
            self.current_media = None
        except Exception as e:
            logger.error(f"Ошибка при инициализации USB Device Manager: {e}")
            try:
                sentry_sdk.capture_exception(e)
            except:
                pass
            raise

    def _run_command(self, command: str, shell: bool = False) -> Tuple[str, str, int]:
        """
        Выполнение shell-команды и получение результата.
        
        Args:
            command (str): Команда для выполнения
            shell (bool): Использовать ли shell для выполнения команды

        Returns:
            Tuple[str, str, int]: (stdout, stderr, returncode)
        """
        try:
            if shell:
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
            else:
                result = subprocess.run(command.split(), capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Команда '{command}' вернула ошибку: {result.stderr}")
            return result.stdout, result.stderr, result.returncode
        except subprocess.CalledProcessError as e:
            logger.error(f"Ошибка при выполнении команды {command}: {e}")
            try:
                sentry_sdk.capture_exception(e)
            except:
                pass
            return "", str(e), 1

    def _is_device_mounted(self, device: str) -> Tuple[bool, str]:
        """
        Проверяет, примонтировано ли устройство.
        
        Args:
            device (str): Путь к устройству

        Returns:
            Tuple[bool, str]: (примонтировано, точка монтирования)
        """
        try:
            # Проверяем через findmnt
            stdout, stderr, rc = self._run_command(f"findmnt -n -o TARGET {device}")
            if rc == 0 and stdout.strip():
                mount_point = stdout.strip()
                logger.debug(f"Устройство {device} уже примонтировано в {mount_point}")
                return True, mount_point

            # Дополнительная проверка через /proc/mounts
            with open('/proc/mounts', 'r') as f:
                for line in f:
                    if device in line:
                        mount_point = line.split()[1]
                        logger.debug(f"Устройство {device} найдено в /proc/mounts: {mount_point}")
                        return True, mount_point

            return False, ""
        except Exception as e:
            logger.error(f"Ошибка при проверке монтирования {device}: {e}")
            try:
                sentry_sdk.capture_exception(e)
            except:
                pass
            return False, ""

    def _mount_device(self, device: str) -> str:
        """
        Монтирование USB-устройства с помощью udisks2.
        
        Args:
            device (str): Путь к устройству

        Returns:
            str: Точка монтирования или пустая строка
        """
        try:
            # Проверяем, примонтировано ли уже устройство
            is_mounted, mount_point = self._is_device_mounted(device)
            if is_mounted:
                logger.info(f"Устройство {device} уже примонтировано в {mount_point}")
                return mount_point

            # Если не примонтировано, монтируем
            stdout, stderr, rc = self._run_command(f"udisksctl mount -b {device}")
            
            # udisksctl возвращает строку вида "Mounted /dev/sda1 at /run/media/user/LABEL"
            if rc == 0 and "at " in stdout:
                mount_point = stdout.split("at ")[-1].strip()
                logger.info(f"Устройство {device} успешно примонтировано в {mount_point}")
                return mount_point
            else:
                logger.error(f"Не удалось примонтировать {device}: {stderr}")
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
            # Получаем список блочных устройств
            stdout, stderr, rc = self._run_command("lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,LABEL,VENDOR,MODEL,SERIAL,FSTYPE -J")
            if rc != 0:
                logger.error(f"Ошибка выполнения lsblk: {stderr}")
                return []
            
            block_devices = json.loads(stdout)
            
            # Получаем список USB устройств
            stdout, stderr, rc = self._run_command("ls /dev/sd* 2>/dev/null", shell=True)
            if rc != 0 and not stdout:
                logger.error(f"Ошибка при поиске USB устройств: {stderr}")
                return []

            # Обрабатываем каждое найденное устройство
            for sdx in stdout.splitlines():
                if not sdx:
                    continue

                # Проверяем, является ли устройство разделом (имеет цифру в конце)
                if not any(c.isdigit() for c in sdx):
                    continue

                # Проверяем, является ли устройство USB
                stdout, stderr, rc = self._run_command(f"udevadm info --query=property {sdx}")
                if rc != 0:
                    logger.error(f"Ошибка получения информации об устройстве {sdx}: {stderr}")
                    continue

                if "ID_BUS=usb" not in stdout:
                    logger.debug(f"Устройство {sdx} не является USB устройством")
                    continue

                logger.info(f"Найдено USB-устройство: {sdx}")
                
                # Получаем информацию об устройстве из lsblk
                device_info = None
                for device in block_devices.get('blockdevices', []):
                    device_name = f"/dev/{device['name']}"
                    if device_name == sdx or any(f"/dev/{child['name']}" == sdx for child in device.get('children', [])):
                        # Проверяем, есть ли дети (разделы) для этого устройства
                        if device.get('children'):
                            for child in device['children']:
                                if f"/dev/{child['name']}" == sdx:
                                    device_info = {
                                        'name': child.get('label', 'Без метки'),
                                        'size': child.get('size', 'Неизвестно'),
                                        'mount_point': child.get('mountpoint', ''),
                                        'device': sdx,
                                        'fstype': child.get('fstype', 'Неизвестно')
                                    }
                                    break
                        else:
                            device_info = {
                                'name': device.get('label', 'Без метки'),
                                'size': device.get('size', 'Неизвестно'),
                                'mount_point': device.get('mountpoint', ''),
                                'device': sdx,
                                'fstype': device.get('fstype', 'Неизвестно')
                            }
                        break
                
                if not device_info:
                    logger.warning(f"Не удалось получить информацию о устройстве {sdx}")
                    continue

                # Пытаемся получить точку монтирования
                mount_point = self._mount_device(sdx)
                if mount_point:
                    device_info['mount_point'] = mount_point
                    device_info['is_mounted'] = True
                    devices.append(device_info)
                    logger.info(f"Добавлено устройство: {device_info}")
                else:
                    logger.warning(f"Не удалось примонтировать устройство {sdx}")
            
            logger.info(f"Найдено примонтированных USB-устройств: {len(devices)}")
            
            # Обновляем настройки
            self._update_settings(devices)
            
            return devices
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка примонтированных USB-устройств: {e}")
            try:
                sentry_sdk.capture_exception(e)
            except:
                pass
            return []
    
    def _update_settings(self, devices: List[Dict[str, str]]) -> None:
        """
        Обновляет файл настроек информацией о USB-устройствах.
        
        Args:
            devices: Список устройств
        """
        try:
            if not os.path.exists(os.path.dirname(SETTINGS_FILE)):
                os.makedirs(os.path.dirname(SETTINGS_FILE))
                
            # Загружаем текущие настройки
            settings = {}
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
            
            # Обновляем информацию о USB-устройствах
            settings['usb_devices'] = [
                {
                    'name': device['name'],
                    'size': device['size'],
                    'mount_point': device['mount_point'],
                    'filesystem': device.get('fstype', 'Неизвестно'),
                    'is_connected': True
                } for device in devices
            ]
            
            # Сохраняем обновленные настройки
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
                
            logger.info(f"Настройки обновлены: {len(devices)} устройств")
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении настроек: {e}")

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
                # Воспроизводим файл и ждем окончания
                self.player.play_file(file_path)
                
                # Проверяем, начал ли плеер воспроизведение
                if self.player.is_playing:
                    if self.debug:
                        print(f"Воспроизведение файла начато: {file_path}")
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
        if self.player.is_playing:
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