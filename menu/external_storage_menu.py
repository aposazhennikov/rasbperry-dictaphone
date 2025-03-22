#!/usr/bin/env python3

import os
import json
import logging
import shutil
from typing import List, Dict, Optional, Tuple
import sentry_sdk

# Отключаем отладочные сообщения от Sentry
logging.getLogger('sentry_sdk.errors').setLevel(logging.INFO)

# Интеграция с Sentry для отслеживания ошибок
sentry_sdk.init(
    dsn="https://990b663058427f36a87004fc14319c09@o4508953992101888.ingest.de.sentry.io/4508953994330192",
    # Добавляем данные о пользователе и запросах
    send_default_pii=True,
    # Включаем отслеживание исключений в фоновых потоках
    enable_tracing=True,
)

from menu.base_menu import BaseMenu

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Путь к файлу настроек
SETTINGS_FILE = "/home/aleks/cache_tts/settings.json"

class ExternalStorageMenu(BaseMenu):
    """Меню для работы с внешними носителями на основе данных из settings.json."""
    
    def __init__(self, settings_manager=None, debug=False, menu_manager=None):
        """Инициализация меню внешних носителей."""
        super().__init__("Внешний носитель")
        self.name = "Внешний носитель"  # Добавляем атрибут name
        self.items = []  # Добавляем пустой список пунктов меню
        self.settings_manager = settings_manager
        self.debug = debug
        self.initialized = False
        self.current_selection = 0  # Добавляем индекс текущего выбранного пункта
        self.menu_manager = menu_manager  # Добавляем ссылку на MenuManager для доступа к плееру
        
        # Инициализируем Sentry для отслеживания ошибок
        if sentry_sdk.Hub.current.client is None:
            sentry_sdk.init(
                dsn="https://77fc0f04b25e4c0ab8bfaf5f80f7026f@o4505325265362944.ingest.sentry.io/4505325267591168",
                traces_sample_rate=1.0,
            )
        
        try:
            self.initialized = self._load_settings()
            # self.display()  # Удаляем вызов display() из конструктора
        except Exception as e:
            error_msg = f"Ошибка при инициализации меню внешнего носителя: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)

    def __str__(self) -> str:
        """
        Строковое представление меню.
        
        Returns:
            str: Название меню
        """
        return "Внешний носитель"

    def __repr__(self) -> str:
        """
        Подробное строковое представление меню.
        
        Returns:
            str: Подробная информация о меню
        """
        return "Внешний носитель"

    def get_tts_text(self) -> str:
        """
        Получение текста для озвучки.
        
        Returns:
            str: Текст для озвучки
        """
        try:
            return "Внешний носитель"
        except Exception as e:
            logger.error(f"Ошибка при получении текста для озвучки: {e}")
            sentry_sdk.capture_exception(e)
            return "Ошибка меню"

    def _load_settings(self) -> Dict:
        """
        Загрузка настроек из файла settings.json.
        
        Returns:
            Dict: Настройки приложения
        """
        try:
            settings_file = "/home/aleks/cache_tts/settings.json"
            if not os.path.exists(settings_file):
                logger.error(f"Файл настроек {settings_file} не существует")
                # Создаем директорию для settings.json, если она не существует
                os.makedirs(os.path.dirname(settings_file), exist_ok=True)
                # Создаем пустой файл настроек с базовой структурой
                default_settings = {"usb_devices": []}
                with open(settings_file, 'w') as f:
                    json.dump(default_settings, f, indent=4, ensure_ascii=False)
                return default_settings
                
            with open(settings_file, 'r') as f:
                settings = json.load(f)
                logger.debug(f"Загружены настройки: {settings}")
                return settings
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка при парсинге JSON из файла настроек: {e}")
            sentry_sdk.capture_exception(e)
            return {"usb_devices": []}
        except Exception as e:
            logger.error(f"Ошибка при загрузке настроек: {e}")
            sentry_sdk.capture_exception(e)
            return {"usb_devices": []}

    def _get_usb_menu_items(self) -> List[Dict[str, str]]:
        """
        Получение списка подключенных USB-накопителей для меню из settings.json.
        
        Returns:
            List[Dict[str, str]]: Список пунктов меню для USB-накопителей
        """
        try:
            # Загружаем настройки с информацией о флешках
            settings = self._load_settings()
            if not settings:
                logger.error("Не удалось загрузить настройки из settings.json")
                sentry_sdk.capture_message("Не удалось загрузить настройки для внешних носителей", level="error")
                return []
                
            usb_devices = settings.get("usb_devices", [])
            logger.info(f"Найдено устройств в настройках: {len(usb_devices)}")
            
            # Проверяем, что у нас есть подключенные устройства
            connected_devices = [device for device in usb_devices if device.get("is_connected", False)]
            logger.info(f"Подключенных устройств в настройках: {len(connected_devices)}")
            
            if not connected_devices:
                logger.warning("В настройках нет подключенных устройств")
                return []
            
            # Проверяем, действительно ли устройства до сих пор подключены
            menu_items = []
            for i, device in enumerate(connected_devices, 1):
                logger.debug(f"Проверка устройства: {device.get('device', 'Неизвестно')}")
                
                # Проверяем, есть ли все необходимые поля
                if not all(k in device for k in ['mount_point', 'device', 'name', 'size']):
                    logger.warning(f"Устройство {i} не содержит всех необходимых полей: {device}")
                    continue
                    
                if self._is_device_available(device):
                    # Форматируем имя флешки для отображения
                    device_name = device['name']
                    if device_name == device['device'].split('/')[-1]:
                        device_name = f"Флешка {i}"
                        
                    menu_items.append({
                        'title': f"{device_name} ({device['size']})",
                        'mount_point': device['mount_point'],
                        'device': device['device'],
                        'filesystem': device.get('filesystem', 'Неизвестно')
                    })
                    logger.info(f"Добавлено устройство в меню: {device_name}")
                else:
                    logger.warning(f"Устройство {device['device']} указано как подключенное, но недоступно")
                    sentry_sdk.capture_message(f"Устройство {device['device']} недоступно, хотя помечено как подключенное", level="warning")
            
            return menu_items
        except Exception as e:
            logger.error(f"Ошибка при получении списка USB-накопителей: {e}")
            sentry_sdk.capture_exception(e)
            return []
    
    def _is_device_available(self, device: Dict) -> bool:
        """
        Проверяет, доступно ли устройство.
        
        Args:
            device (Dict): Информация об устройстве
            
        Returns:
            bool: True, если устройство доступно, иначе False
        """
        try:
            # Проверяем существование точки монтирования
            if not os.path.exists(device.get('mount_point', '')):
                return False
                
            # Проверяем доступность для чтения
            try:
                os.listdir(device['mount_point'])
                return True
            except (PermissionError, FileNotFoundError):
                return False
        except Exception as e:
            logger.error(f"Ошибка при проверке доступности устройства: {e}")
            sentry_sdk.capture_exception(e)
            return False
    
    # Определяем поддерживаемые форматы файлов
    AUDIO_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.m4a', '.wma', '.aac', '.flac', '.alac', '.opus', '.aiff'}
    TEXT_EXTENSIONS = {'.txt', '.epub', '.fb2', '.pdf', '.doc', '.docx'}
    
    def _list_files(self, mount_point: str):
        """
        Создает и возвращает подменю для навигации по файлам на флешке.
        Отображает только папки и файлы поддерживаемых форматов.
        
        Args:
            mount_point (str): Точка монтирования устройства
            
        Returns:
            SubMenu: Меню для навигации по файлам
        """
        try:
            from menu.menu_item import MenuItem, SubMenu
            
            # Создаем новое подменю для просмотра файлов
            files_menu = SubMenu(name=f"Файлы на флешке")
            
            # Проверяем доступность пути
            if not os.path.exists(mount_point) or not os.path.isdir(mount_point):
                logger.error(f"Путь недоступен: {mount_point}")
                error_item = MenuItem(
                    name="Ошибка доступа к флешке",
                    speech_text="Ошибка доступа к флешке"
                )
                files_menu.add_item(error_item)
                return files_menu
                
            # Сканируем содержимое директории
            items = os.listdir(mount_point)
            
            # Сортируем: сначала папки, потом файлы
            dirs = []
            files = []
            
            for item in items:
                item_path = os.path.join(mount_point, item)
                if os.path.isdir(item_path):
                    dirs.append(item)
                else:
                    ext = os.path.splitext(item)[1].lower()
                    if ext in self.AUDIO_EXTENSIONS or ext in self.TEXT_EXTENSIONS:
                        files.append(item)
            
            # Добавляем папки
            for dir_name in sorted(dirs):
                dir_path = os.path.join(mount_point, dir_name)
                dir_item = MenuItem(
                    name=dir_name,
                    speech_text=dir_name,
                    action=lambda path=dir_path: self._list_files(path)
                )
                files_menu.add_item(dir_item)
                
            # Добавляем файлы
            for file_name in sorted(files):
                file_path = os.path.join(mount_point, file_name)
                ext = os.path.splitext(file_name)[1].lower()
                
                # Используем разные действия в зависимости от типа файла
                if ext in self.AUDIO_EXTENSIONS:
                    # Для аудио файлов используем существующий плеер
                    file_item = MenuItem(
                        name=file_name,
                        speech_text=file_name,
                        action=lambda path=file_path: self._play_audio_file(path)
                    )
                else:  # Текстовые файлы
                    file_item = MenuItem(
                        name=file_name,
                        speech_text=file_name,
                        action=lambda path=file_path: self._view_text_file(path)
                    )
                files_menu.add_item(file_item)
            
            # Если папка пуста, добавляем информационный пункт
            if not dirs and not files:
                empty_item = MenuItem(
                    name="Папка пуста",
                    speech_text="Папка пуста"
                )
                files_menu.add_item(empty_item)
                
            # Устанавливаем родительское меню
            parent_menu = self.current_menu if hasattr(self, 'current_menu') else self
            files_menu.parent = parent_menu
            
            return files_menu
            
        except Exception as e:
            logger.error(f"Ошибка при создании меню файлов: {e}")
            sentry_sdk.capture_exception(e)
            
            # Возвращаем меню с сообщением об ошибке
            error_menu = SubMenu(name="Ошибка")
            error_menu.add_item(MenuItem(
                name=f"Ошибка: {str(e)}",
                speech_text="Произошла ошибка при чтении файлов"
            ))
            return error_menu
            
    def _play_audio_file(self, file_path: str):
        """
        Воспроизводит аудио файл напрямую через playback_manager.
        
        Args:
            file_path (str): Путь к аудио файлу
            
        Returns:
            Any: Результат воспроизведения
        """
        try:
            logger.info(f"Воспроизведение аудио файла с флешки: {file_path}")
            
            # Проверяем доступность файла
            if not os.path.exists(file_path):
                logger.error(f"Файл не найден: {file_path}")
                return "Ошибка: файл не найден"
                
            # Здесь мы будем использовать существующий плеер из MenuManager
            if hasattr(self, 'menu_manager') and self.menu_manager and hasattr(self.menu_manager, 'playback_manager'):
                # Формируем информацию о воспроизводимом файле
                playback_manager = self.menu_manager.playback_manager
                player = playback_manager.player
                
                # Останавливаем текущее воспроизведение если есть
                if player.is_playing():
                    player.stop()
                
                # Отображаем информацию на экране с помощью display_manager
                file_name = os.path.basename(file_path)
                if hasattr(self.menu_manager, 'display_manager') and self.menu_manager.display_manager:
                    self.menu_manager.display_manager.display_message(
                        f"Воспроизведение: {file_name}", 
                        title="Аудиоплеер"
                    )
                
                # Воспроизводим файл напрямую
                result = player.play_file(file_path)
                
                # Активируем режим аудиоплеера
                self.menu_manager.player_mode_active = True
                
                return result
            else:
                logger.error("Нет доступа к playback_manager для воспроизведения")
                return "Ошибка воспроизведения: нет доступа к плееру"
                
        except Exception as e:
            logger.error(f"Ошибка при воспроизведении аудио: {e}")
            sentry_sdk.capture_exception(e)
            return f"Ошибка воспроизведения: {str(e)}"
            
    def _view_text_file(self, file_path: str):
        """
        Отображает текстовый файл.
        
        Args:
            file_path (str): Путь к текстовому файлу
            
        Returns:
            str: Содержимое файла или сообщение об ошибке
        """
        try:
            logger.info(f"Чтение текстового файла: {file_path}")
            
            # Простое чтение текстового файла
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(2000)  # Читаем первые 2000 символов
                
            return f"Содержимое файла: {os.path.basename(file_path)}\n\n{content}..."
            
        except Exception as e:
            logger.error(f"Ошибка при чтении текстового файла: {e}")
            sentry_sdk.capture_exception(e)
            return f"Ошибка чтения файла: {str(e)}"

    def _copy_files_to_usb(self, mount_point: str, filesystem: str) -> None:
        """
        Создает подменю с опциями копирования файлов на USB-накопитель.
        
        Args:
            mount_point (str): Точка монтирования USB-накопителя
            filesystem (str): Тип файловой системы
            
        Returns:
            SubMenu: Меню выбора опций копирования
        """
        try:
            from menu.menu_item import MenuItem, SubMenu
            
            # Проверяем доступность устройства
            if not os.path.exists(mount_point):
                logger.error(f"Точка монтирования {mount_point} недоступна")
                error_menu = SubMenu(name="Ошибка доступа")
                error_menu.add_item(MenuItem(
                    name="Флешка была отключена",
                    speech_text="Флешка была отключена"
                ))
                # Устанавливаем parent для error_menu
                if hasattr(self, 'menu_manager') and self.menu_manager:
                    error_menu.parent = self.menu_manager.current_menu
                return error_menu
                
            # Создаем подменю для копирования
            copy_menu = SubMenu(name="Копирование файлов")
            
            # Устанавливаем родительское меню для copy_menu
            if hasattr(self, 'menu_manager') and self.menu_manager:
                copy_menu.parent = self.menu_manager.current_menu
            
            # Получаем список доступных папок с записями
            records_dir = "/home/aleks/records"
            if not os.path.exists(records_dir):
                logger.error(f"Директория с записями {records_dir} не найдена")
                error_item = MenuItem(
                    name="Директория с записями не найдена",
                    speech_text="Директория с записями не найдена"
                )
                copy_menu.add_item(error_item)
                return copy_menu
                
            # Получаем размер свободного места на флешке
            free_space = self._get_free_space(mount_point)
            logger.info(f"Свободное место на флешке: {self._format_size(free_space)}")
            
            # Папки для поиска записей
            folders = ["A", "B", "C"]
            
            # Получаем размер всех аудиозаписей
            all_files_size = 0
            folder_sizes = {}
            
            for folder in folders:
                folder_path = os.path.join(records_dir, folder)
                if os.path.exists(folder_path):
                    folder_size = self._get_folder_size(folder_path)
                    all_files_size += folder_size
                    folder_sizes[folder] = folder_size
            
            # Добавляем пункт для копирования всех записей
            copy_all_item = MenuItem(
                name=f"Скопировать все аудиозаписи из всех папок ({self._format_size(all_files_size)})",
                speech_text=f"Скопировать все аудиозаписи из всех папок. Общий размер {self._format_size(all_files_size)}",
                action=lambda: self._perform_copy_operation(records_dir, mount_point, all_files_size, free_space, copy_all=True)
            )
            copy_menu.add_item(copy_all_item)
            
            # Добавляем пункты для копирования записей из каждой папки
            for folder in folders:
                folder_path = os.path.join(records_dir, folder)
                if os.path.exists(folder_path) and folder_sizes.get(folder, 0) > 0:
                    folder_item = MenuItem(
                        name=f"Скопировать все аудиозаписи из папки {folder} ({self._format_size(folder_sizes[folder])})",
                        speech_text=f"Скопировать все аудиозаписи из папки {folder}. Размер {self._format_size(folder_sizes[folder])}",
                        action=lambda f=folder, s=folder_sizes[folder]: self._perform_copy_operation(
                            os.path.join(records_dir, f), 
                            mount_point, 
                            s, 
                            free_space
                        )
                    )
                    copy_menu.add_item(folder_item)
            
            # Если нет записей
            if all_files_size == 0:
                no_files_item = MenuItem(
                    name="Нет доступных аудиозаписей для копирования",
                    speech_text="Нет доступных аудиозаписей для копирования"
                )
                copy_menu.add_item(no_files_item)
            
            logger.info(f"Создано меню копирования файлов с родителем: {copy_menu.parent}")
            return copy_menu
                
        except Exception as e:
            logger.error(f"Ошибка при создании меню копирования файлов: {e}")
            sentry_sdk.capture_exception(e)
            
            # Возвращаем меню с сообщением об ошибке
            error_menu = SubMenu(name="Ошибка")
            error_menu.add_item(MenuItem(
                name=f"Ошибка: {str(e)}",
                speech_text="Произошла ошибка при подготовке к копированию файлов"
            ))
            # Устанавливаем parent для error_menu в случае ошибки
            if hasattr(self, 'menu_manager') and self.menu_manager:
                error_menu.parent = self.menu_manager.current_menu
            return error_menu
    
    def _get_free_space(self, path: str) -> int:
        """
        Получает размер свободного места на диске.
        
        Args:
            path (str): Путь к директории на диске
            
        Returns:
            int: Размер свободного места в байтах
        """
        try:
            stat = os.statvfs(path)
            # Свободное место = размер блока * количество свободных блоков
            return stat.f_frsize * stat.f_bavail
        except Exception as e:
            logger.error(f"Ошибка при получении свободного места: {e}")
            sentry_sdk.capture_exception(e)
            return 0
    
    def _get_folder_size(self, folder_path: str) -> int:
        """
        Вычисляет размер всех аудиофайлов в директории.
        
        Args:
            folder_path (str): Путь к директории
            
        Returns:
            int: Суммарный размер файлов в байтах
        """
        try:
            total_size = 0
            for root, _, files in os.walk(folder_path):
                for filename in files:
                    if any(filename.lower().endswith(ext) for ext in self.AUDIO_EXTENSIONS):
                        file_path = os.path.join(root, filename)
                        total_size += os.path.getsize(file_path)
            return total_size
        except Exception as e:
            logger.error(f"Ошибка при вычислении размера папки {folder_path}: {e}")
            sentry_sdk.capture_exception(e)
            return 0
    
    def _format_size(self, size_bytes: int) -> str:
        """
        Форматирует размер в байтах в читаемый вид.
        
        Args:
            size_bytes (int): Размер в байтах
            
        Returns:
            str: Отформатированный размер
        """
        try:
            if size_bytes < 1024:
                return f"{size_bytes} байт"
            
            kb = size_bytes / 1024
            if kb < 1024:
                return f"{kb:.1f} Кб"
                
            mb = kb / 1024
            if mb < 1024:
                return f"{int(mb)} Мб"
                
            gb = mb / 1024
            mb_remainder = int((gb - int(gb)) * 1024)
            return f"{int(gb)} Гб {mb_remainder} Мб"
        except Exception as e:
            logger.error(f"Ошибка при форматировании размера: {e}")
            sentry_sdk.capture_exception(e)
            return "Неизвестный размер"
    
    def _perform_copy_operation(self, source_path: str, dest_path: str, required_space: int, available_space: int, copy_all=False) -> str:
        """
        Выполняет копирование файлов с проверкой свободного места.
        
        Args:
            source_path (str): Путь к источнику (папка с записями)
            dest_path (str): Путь назначения (флешка)
            required_space (int): Требуемое место в байтах
            available_space (int): Доступное место в байтах
            copy_all (bool): Флаг копирования всех папок
            
        Returns:
            str: Сообщение о результате операции
        """
        try:
            # Проверяем, достаточно ли места
            if required_space > available_space:
                error_msg = f"Недостаточно места на флешке. Требуется: {self._format_size(required_space)}, доступно: {self._format_size(available_space)}"
                logger.warning(error_msg)
                
                # Если есть menu_manager, озвучиваем ошибку
                if hasattr(self, 'menu_manager') and self.menu_manager and hasattr(self.menu_manager, 'tts_manager'):
                    voice = self.menu_manager.settings_manager.get_voice()
                    self.menu_manager.tts_manager.play_speech("Недостаточно места на флешке", voice_id=voice)
                
                return error_msg
            
            # Отображаем сообщение о ходе копирования
            if hasattr(self, 'menu_manager') and self.menu_manager and hasattr(self.menu_manager, 'display_manager'):
                self.menu_manager.display_manager.display_message(
                    "Копирование файлов в процессе...",
                    title="Копирование на флешку"
                )
            
            # Создаем директории на флешке
            if copy_all:
                # Копируем из всех папок A, B, C
                folders = ["A", "B", "C"]
                for folder in folders:
                    src_folder = os.path.join(source_path, folder)
                    if os.path.exists(src_folder):
                        dest_folder = os.path.join(dest_path, folder)
                        # Создаем директорию, если её нет
                        os.makedirs(dest_folder, exist_ok=True)
                        self._copy_audio_files(src_folder, dest_folder)
            else:
                # Копируем из одной конкретной папки
                folder_name = os.path.basename(source_path)
                dest_folder = os.path.join(dest_path, folder_name)
                # Пробуем создать директорию, если у нас нет прав, используем корень флешки с префиксом
                try:
                    os.makedirs(dest_folder, exist_ok=True)
                    self._copy_audio_files(source_path, dest_folder)
                except PermissionError:
                    logger.warning(f"Нет прав для создания папки {dest_folder}, копируем в корень с префиксом")
                    self._copy_audio_files(source_path, dest_path, prefix=f"{folder_name}_")
            
            success_msg = "Копирование успешно завершено"
            logger.info(success_msg)
            
            # Если есть menu_manager, отображаем и озвучиваем успех
            if hasattr(self, 'menu_manager') and self.menu_manager:
                if hasattr(self.menu_manager, 'display_manager'):
                    self.menu_manager.display_manager.display_message(
                        success_msg,
                        title="Копирование на флешку"
                    )
                if hasattr(self.menu_manager, 'tts_manager'):
                    voice = self.menu_manager.settings_manager.get_voice()
                    self.menu_manager.tts_manager.play_speech(success_msg, voice_id=voice)
                
                # Возвращаемся в меню внешнего носителя
                if hasattr(self.menu_manager, 'current_menu') and hasattr(self.menu_manager.current_menu, 'parent'):
                    logger.info(f"Возвращаемся в родительское меню после копирования: {self.menu_manager.current_menu.parent}")
                    # Не меняем текущее меню напрямую, так как это должно делаться через menu_manager
            
            return success_msg
            
        except PermissionError:
            error_msg = "Нет прав для копирования файлов на флешку"
            logger.error(error_msg)
            sentry_sdk.capture_exception()
            
            # Озвучиваем ошибку
            if hasattr(self, 'menu_manager') and self.menu_manager and hasattr(self.menu_manager, 'tts_manager'):
                voice = self.menu_manager.settings_manager.get_voice()
                self.menu_manager.tts_manager.play_speech(error_msg, voice_id=voice)
                
            return error_msg
        except Exception as e:
            error_msg = f"Ошибка при копировании файлов: {e}"
            logger.error(error_msg)
            sentry_sdk.capture_exception(e)
            
            # Озвучиваем ошибку
            if hasattr(self, 'menu_manager') and self.menu_manager and hasattr(self.menu_manager, 'tts_manager'):
                voice = self.menu_manager.settings_manager.get_voice()
                self.menu_manager.tts_manager.play_speech("Произошла ошибка при копировании файлов", voice_id=voice)
                
            return error_msg
    
    def _copy_audio_files(self, src_dir: str, dest_dir: str, prefix: str = "") -> None:
        """
        Копирует все аудиофайлы из исходной директории в целевую.
        
        Args:
            src_dir (str): Исходная директория
            dest_dir (str): Целевая директория
            prefix (str): Префикс для имен файлов в целевой директории
        """
        try:
            # Проверяем, существует ли исходная директория
            if not os.path.exists(src_dir):
                logger.warning(f"Исходная директория {src_dir} не существует")
                return
                
            # Создаем целевую директорию, если она не существует
            os.makedirs(dest_dir, exist_ok=True)
            
            # Проверяем права на запись в целевую директорию
            if not os.access(dest_dir, os.W_OK):
                logger.error(f"Нет прав на запись в директорию {dest_dir}")
                raise PermissionError(f"Нет прав на запись в директорию {dest_dir}")
            
            # Копируем все аудиофайлы
            for root, _, files in os.walk(src_dir):
                for filename in files:
                    # Проверяем, является ли файл аудиофайлом
                    if any(filename.lower().endswith(ext) for ext in self.AUDIO_EXTENSIONS):
                        src_file = os.path.join(root, filename)
                        
                        # Определяем имя файла с префиксом, если указан
                        dest_filename = prefix + filename if prefix else filename
                        
                        # Сохраняем относительную структуру папок если не используем префикс
                        if not prefix:
                            rel_path = os.path.relpath(root, src_dir)
                            if rel_path != '.':  # Если файл не в корне исходной директории
                                dest_subdir = os.path.join(dest_dir, rel_path)
                                os.makedirs(dest_subdir, exist_ok=True)
                                dest_file = os.path.join(dest_subdir, dest_filename)
                            else:
                                dest_file = os.path.join(dest_dir, dest_filename)
                        else:
                            # Если используем префикс, помещаем все файлы прямо в целевую директорию
                            dest_file = os.path.join(dest_dir, dest_filename)
                        
                        # Копируем файл
                        shutil.copy2(src_file, dest_file)
                        logger.debug(f"Скопирован файл {src_file} в {dest_file}")
                        
        except Exception as e:
            logger.error(f"Ошибка при копировании аудиофайлов: {e}")
            sentry_sdk.capture_exception(e)
            raise

    def show_device_menu(self, device_info: Dict[str, str]) -> None:
        """
        Показать меню для конкретного USB-накопителя.
        
        Args:
            device_info (Dict[str, str]): Информация об устройстве
            
        Returns:
            bool: True для продолжения, None для возврата в предыдущее меню
        """
        try:
            from menu.menu_item import MenuItem, SubMenu
            
            # Создаем подменю для выбранного устройства
            device_name = device_info.get('title', 'USB-накопитель')
            device_menu = SubMenu(name=device_name)
            
            # Добавляем пункты в подменю устройства
            device_menu.add_item(MenuItem(
                name="Посмотреть файлы на флешке",
                speech_text="Посмотреть файлы на флешке",
                action=lambda: self._list_files(device_info['mount_point'])
            ))
            
            device_menu.add_item(MenuItem(
                name="Скопировать файлы на флешку",
                speech_text="Скопировать файлы на флешку",
                action=lambda: self._copy_files_to_usb(device_info['mount_point'], device_info.get('filesystem', 'Неизвестно'))
            ))
            
            # Убираем пункт "Назад", так как используется кнопка KEY_BACK
            
            # Устанавливаем родительское меню
            device_menu.parent = self
            
            return device_menu  # Возвращаем новое подменю для перехода в него
            
        except Exception as e:
            logger.error(f"Ошибка при работе с меню USB-накопителя: {e}")
            sentry_sdk.capture_exception(e)
            print(f"Произошла ошибка при работе с USB-накопителем: {e}")
            return None

    def display(self) -> None:
        """Отображение меню внешних носителей."""
        try:
            while True:
                # Получаем обновленный список USB-накопителей при каждом отображении меню
                usb_devices = self._get_usb_menu_items()
                
                if not usb_devices:
                    print("\nПодключенных флешек нет")
                    input("\nНажмите Enter для возврата в главное меню...")
                    break
                
                print("\nДоступные USB-накопители:")
                for i, device in enumerate(usb_devices, 1):
                    print(f"{i}. {device['title']}")
                print("0. Назад")
                
                choice = input("\nВыберите флешку: ")
                
                if choice == "0":
                    break
                    
                try:
                    choice_idx = int(choice) - 1
                    if 0 <= choice_idx < len(usb_devices):
                        # После выбора пользователя снова проверяем, что устройство доступно
                        device_info = usb_devices[choice_idx]
                        if self._is_device_available(device_info):
                            self.show_device_menu(device_info)
                        else:
                            print("\nФлешка была отключена")
                            sentry_sdk.capture_message(f"Флешка {device_info.get('device', 'неизвестно')} была отключена при попытке доступа", level="warning")
                    else:
                        print("Неверный выбор. Попробуйте снова.")
                except ValueError:
                    print("Пожалуйста, введите число.")
                except Exception as inner_e:
                    logger.error(f"Ошибка при работе с меню USB-накопителя: {inner_e}")
                    sentry_sdk.capture_exception(inner_e)
                    print(f"Произошла ошибка: {inner_e}")
                    
        except Exception as e:
            logger.error(f"Ошибка при отображении меню внешних носителей: {e}")
            sentry_sdk.capture_exception(e)
            print(f"Произошла ошибка при работе с меню: {e}") 

    def get_current_item(self):
        """
        Возвращает текущий выбранный пункт меню.
        
        Returns:
            MenuItem: Текущий выбранный пункт меню или None, если меню пусто
        """
        try:
            if not self.items:
                return None
            
            if 0 <= self.current_selection < len(self.items):
                return self.items[self.current_selection]
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении текущего пункта меню: {e}")
            sentry_sdk.capture_exception(e)
            return None
            
    def move_up(self):
        """Перемещение вверх по списку пунктов меню (циклически)"""
        try:
            if not self.items:
                return
            self.current_selection = (self.current_selection - 1) % len(self.items)
        except Exception as e:
            logger.error(f"Ошибка при перемещении вверх по меню: {e}")
            sentry_sdk.capture_exception(e)
    
    def move_down(self):
        """Перемещение вниз по списку пунктов меню (циклически)"""
        try:
            if not self.items:
                return
            self.current_selection = (self.current_selection + 1) % len(self.items)
        except Exception as e:
            logger.error(f"Ошибка при перемещении вниз по меню: {e}")
            sentry_sdk.capture_exception(e)

    def on_enter(self):
        """
        Вызывается при входе в меню внешних носителей.
        Обновляет список пунктов меню на основе подключенных устройств.
        """
        try:
            from menu.menu_item import MenuItem
            
            # Очищаем текущий список пунктов меню
            self.items = []
            self.current_selection = 0
            
            # Получаем список USB-накопителей
            usb_devices = self._get_usb_menu_items()
            
            # Если устройства найдены, добавляем их в меню
            if usb_devices:
                for device in usb_devices:
                    # Создаем пункт меню для каждого устройства
                    device_item = MenuItem(
                        name=device['title'], 
                        speech_text=device['title'],
                        action=lambda dev=device: self.create_device_menu(dev)
                    )
                    self.add_item(device_item)
                
                # Убираем пункт "Назад", так как используется кнопка KEY_BACK
            else:
                # Если устройств нет, добавляем информационный пункт
                no_devices_item = MenuItem(
                    name="Нет подключенных USB-накопителей",
                    speech_text="Нет подключенных USB-накопителей"
                )
                self.add_item(no_devices_item)
                
                # Убираем пункт "Назад", так как используется кнопка KEY_BACK
                
            logger.info(f"Обновлено меню внешних носителей, добавлено {len(self.items)} пунктов")
            return True
        except Exception as e:
            logger.error(f"Ошибка при обновлении меню внешних носителей: {e}")
            sentry_sdk.capture_exception(e)
            return False
            
    def create_device_menu(self, device_info):
        """
        Создает и возвращает меню для работы с конкретным устройством.
        
        Args:
            device_info (dict): Информация об устройстве
            
        Returns:
            SubMenu: Меню устройства или None при ошибке
        """
        try:
            from menu.menu_item import MenuItem, SubMenu
            
            # Создаем подменю для устройства
            device_name = device_info.get('title', 'USB-накопитель')
            mount_point = device_info.get('mount_point', '')
            filesystem = device_info.get('filesystem', 'Неизвестно')
            
            # Проверяем, что точка монтирования существует
            if not os.path.exists(mount_point):
                logger.error(f"Точка монтирования не существует: {mount_point}")
                error_menu = SubMenu(name="Ошибка")
                error_menu.add_item(MenuItem(
                    name="Флешка недоступна или была отключена",
                    speech_text="Флешка недоступна или была отключена"
                ))
                error_menu.parent = self
                return error_menu
            
            # Создаем меню с именем устройства
            device_menu = SubMenu(name=device_name)
            
            # Сохраняем информацию об устройстве в меню
            device_menu.device_info = device_info
            
            # Добавляем пункты меню
            device_menu.add_item(MenuItem(
                name="Посмотреть файлы на флешке",
                speech_text="Посмотреть файлы на флешке",
                action=lambda: self._list_files(mount_point)
            ))
            
            device_menu.add_item(MenuItem(
                name="Скопировать файлы на флешку",
                speech_text="Скопировать файлы на флешку",
                action=lambda: self._copy_files_to_usb(mount_point, filesystem)
            ))
            
            # Устанавливаем родительское меню
            device_menu.parent = self
            
            logger.info(f"Создано меню для устройства: {device_name}")
            
            return device_menu
            
        except Exception as e:
            logger.error(f"Ошибка при создании меню устройства: {e}")
            sentry_sdk.capture_exception(e)
            return None

    def handle_select(self):
        """
        Обрабатывает выбор текущего пункта меню
        
        Returns:
            Any: Результат выбора текущего пункта меню
        """
        try:
            # Получаем текущий выбранный пункт
            item = self.get_current_item()
            if not item:
                logger.warning("Нет выбранного пункта меню")
                return None
                
            # Если пункт имеет действие, выполняем его
            logger.info(f"Выбран пункт: {getattr(item, 'name', 'Неизвестный пункт')}")
            
            if hasattr(item, 'action') and callable(item.action):
                logger.info("Выполнение действия пункта меню")
                result = item.action()
                
                # Если действие вернуло подменю, переходим в него
                if result and isinstance(result, object) and hasattr(result, 'items') and hasattr(result, 'name'):
                    logger.info(f"Переход в подменю: {result.name}")
                    if hasattr(self, 'menu_manager') and self.menu_manager:
                        self.menu_manager.set_menu(result)
                        return True
                
                return result
            else:
                logger.warning("Выбранный пункт не имеет действия")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при обработке выбора пункта меню: {e}")
            sentry_sdk.capture_exception(e)
            return None