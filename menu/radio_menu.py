#!/usr/bin/env python3
"""
Модуль для управления меню радиостанций.
"""
import os
import glob
import logging
import sentry_sdk
from .menu_item import MenuItem, SubMenu

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RadioMenu(SubMenu):
    """Класс для управления меню радиостанций"""
    
    def __init__(self, parent=None, menu_manager=None):
        """
        Инициализация меню радиостанций
        
        Args:
            parent: Родительское меню
            menu_manager: Менеджер меню для доступа к playback_manager
        """
        try:
            super().__init__("Радио", parent=parent)
            self.menu_manager = menu_manager
            
            # Словарь с путями к папкам станций
            self.station_directories = {
                "Юмор": "/home/aleks/humor",
                "Трошин": "/home/aleks/troshin",
                "Шаов": "/home/aleks/shaov",
                "Наука": "/home/aleks/science",
                "Политика": "/home/aleks/politics",
                "Природа": "/home/aleks/nature"
            }
            
            # Создаем директории станций, если их нет
            self._create_station_directories()
            
            # Создаем структуру меню 
            self._create_radio_structure()
            logger.info("Создано меню радиостанций")
        except Exception as e:
            logger.error(f"Ошибка при создании меню радиостанций: {e}")
            sentry_sdk.capture_exception(e)
            raise
    
    def _create_station_directories(self):
        """Создает директории для станций, если они не существуют"""
        try:
            for station, directory in self.station_directories.items():
                if not os.path.exists(directory):
                    logger.info(f"Создаем директорию для станции {station}: {directory}")
                    os.makedirs(directory, exist_ok=True)
        except Exception as e:
            logger.error(f"Ошибка при создании директорий станций: {e}")
            sentry_sdk.capture_exception(e)
    
    def _create_radio_structure(self):
        """Создает структуру меню радиостанций"""
        try:
            # Создаем список доступных радиостанций
            stations = list(self.station_directories.keys())
            
            # Добавляем каждую радиостанцию в меню
            for station in stations:
                # Создаем подменю для станции, с обработчиком входа в это меню
                station_menu = StationSubMenu(
                    station, 
                    parent=self,
                    directory=self.station_directories[station],
                    menu_manager=self.menu_manager
                )
                self.add_item(station_menu)
                
            logger.info(f"Создано {len(stations)} радиостанций в меню")
        except Exception as e:
            logger.error(f"Ошибка при создании структуры меню радиостанций: {e}")
            sentry_sdk.capture_exception(e)
            raise


class StationSubMenu(SubMenu):
    """Класс для подменю конкретной радиостанции с аудиофайлами"""

    def __init__(self, name, parent=None, directory=None, menu_manager=None):
        """
        Инициализация подменю радиостанции
        
        Args:
            name: Название станции
            parent: Родительское меню
            directory: Путь к директории с аудиофайлами
            menu_manager: Менеджер меню для доступа к playback_manager
        """
        try:
            super().__init__(name, parent=parent)
            self.directory = directory
            self.menu_manager = menu_manager
            
            # Устанавливаем обработчик входа в меню
            self.on_enter = self._load_audio_files
            
            logger.info(f"Создано подменю станции {name}, директория: {directory}")
        except Exception as e:
            logger.error(f"Ошибка при создании подменю станции {name}: {e}")
            sentry_sdk.capture_exception(e)
            raise
    
    def _load_audio_files(self):
        """
        Загружает список аудиофайлов при входе в меню
        """
        try:
            # Очищаем текущие пункты меню
            self.items = []
            self.current_selection = 0
            
            # Проверяем существование директории
            if not self.directory:
                self.add_item(MenuItem("Путь к папке станции не указан", lambda: None))
                logger.warning(f"Путь к директории станции не указан для {self.name}")
                return
                
            # Создаем директорию, если она не существует
            if not os.path.exists(self.directory):
                try:
                    logger.info(f"Создаем директорию для станции {self.name}: {self.directory}")
                    os.makedirs(self.directory, exist_ok=True)
                    self.add_item(MenuItem("Папка создана. Добавьте аудиофайлы и вернитесь в меню", lambda: None))
                    return
                except Exception as dir_error:
                    logger.error(f"Ошибка при создании директории {self.directory}: {dir_error}")
                    sentry_sdk.capture_exception(dir_error)
                    self.add_item(MenuItem(f"Ошибка создания папки: {str(dir_error)}", lambda: None))
                    return
            
            # Получаем список аудиофайлов
            audio_files = self._get_audio_files(self.directory)
            
            if not audio_files:
                self.add_item(MenuItem("В папке нет аудиофайлов", lambda: None))
                logger.info(f"Нет аудиофайлов в директории: {self.directory}")
                return
            
            # Добавляем файлы в меню
            for file_path in audio_files:
                file_name = os.path.basename(file_path)
                # Создаем обертку для каждого файла, чтобы избежать проблем с lambda в цикле
                def create_play_action(path=file_path):
                    return lambda: self._play_audio_file(path)
                
                self.add_item(MenuItem(file_name, create_play_action()))
            
            logger.info(f"Загружено {len(audio_files)} аудиофайлов для станции {self.name}")
        except Exception as e:
            logger.error(f"Ошибка при загрузке аудиофайлов для станции {self.name}: {e}")
            sentry_sdk.capture_exception(e)
            # Добавляем сообщение об ошибке
            self.items = []
            self.add_item(MenuItem(f"Ошибка загрузки файлов: {str(e)}", lambda: None))
    
    def _get_audio_files(self, directory):
        """
        Получает список аудиофайлов из указанной директории
        
        Args:
            directory (str): Путь к директории
            
        Returns:
            list: Список путей к аудиофайлам
        """
        try:
            audio_files = []
            
            # Поддерживаемые форматы
            extensions = ['.wav', '.mp3', '.ogg', '.flac']
            
            # Собираем файлы всех поддерживаемых форматов
            for ext in extensions:
                files = glob.glob(os.path.join(directory, f'*{ext}'))
                audio_files.extend(files)
            
            # Сортируем по имени
            audio_files.sort()
            return audio_files
        except Exception as e:
            logger.error(f"Ошибка при получении списка аудиофайлов: {e}")
            sentry_sdk.capture_exception(e)
            return []
            
    def _play_audio_file(self, file_path):
        """
        Воспроизводит выбранный аудиофайл
        
        Args:
            file_path: Путь к аудиофайлу
            
        Returns:
            bool: True если воспроизведение начато успешно
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"Файл не найден: {file_path}")
                return False
            
            # Проверяем наличие необходимых компонентов для воспроизведения
            if not self.menu_manager:
                logger.error("Не найден menu_manager для воспроизведения")
                return False
                
            if not hasattr(self.menu_manager, 'playback_manager'):
                logger.error("Не найден playback_manager для воспроизведения")
                return False
                
            playback_manager = self.menu_manager.playback_manager
            
            # Проверяем наличие необходимых методов
            required_methods = ['set_current_file', 'play_current_file', 'set_completion_callback']
            for method in required_methods:
                if not hasattr(playback_manager, method):
                    logger.error(f"Метод {method} не найден в playback_manager")
                    return False
            
            # Получаем список всех файлов в директории
            audio_files = self._get_audio_files(self.directory)
            if not audio_files:
                logger.error(f"Не удалось получить список файлов для {self.directory}")
                return False
            
            # Находим индекс текущего файла
            try:
                file_index = audio_files.index(file_path)
            except ValueError:
                logger.warning(f"Файл {file_path} не найден в списке, используем первый файл")
                file_index = 0
            
            # Устанавливаем текущий файл и список файлов в playback_manager
            playback_manager.files_list = audio_files
            
            # Запоминаем меню для возврата
            playback_manager.return_to_menu = self
            
            # Устанавливаем обработчик завершения
            def completion_callback(success, message):
                try:
                    logger.info(f"Завершение воспроизведения: success={success}, message={message}")
                    # После завершения воспроизведения возвращаемся в меню станции
                    if self.menu_manager.player_mode_active:
                        self.menu_manager.player_mode_active = False
                        # Возвращаемся в текущее меню
                        self.menu_manager.current_menu = self
                        self.menu_manager.display_current_menu()
                except Exception as e:
                    logger.error(f"Ошибка в обработчике завершения воспроизведения: {e}")
                    sentry_sdk.capture_exception(e)
            
            playback_manager.set_completion_callback(completion_callback)
            
            # Активируем режим проигрывателя
            self.menu_manager.player_mode_active = True
            
            # Запускаем воспроизведение
            logger.info(f"Воспроизведение файла: {file_path}")
            result = playback_manager.set_current_file(file_index)
            if result:
                return playback_manager.play_current_file()
            else:
                logger.error("Не удалось установить текущий файл")
            
            return False
        except Exception as e:
            logger.error(f"Ошибка при воспроизведении файла {file_path}: {e}")
            sentry_sdk.capture_exception(e)
            return False