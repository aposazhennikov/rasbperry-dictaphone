#!/usr/bin/env python3
import os
import sys
import time
import importlib
import sentry_sdk
import logging
from pathlib import Path
from .tts_manager import TTSManager
from .display_manager import DisplayManager
from .recorder_manager import RecorderManager
from .playback_manager import PlaybackManager
from .settings_manager import SettingsManager
from .audio_recorder import AudioRecorder
from .menu_item import MenuItem, SubMenu, Menu
from .external_storage_menu import ExternalStorageMenu
from .base_menu import BaseMenu
from .bulk_delete_manager import BulkDeleteManager
from .radio_menu import RadioMenu
from .microphone_selector import MicrophoneSelector

# Настройка логирования
logger = logging.getLogger("menu_manager")

class MenuManager:
    """Класс для управления иерархическим меню"""
    
    def __init__(self, tts_enabled=True, cache_dir="/home/aleks/cache_tts", debug=False, use_wav=True, settings_manager=None, records_dir="/home/aleks/records"):
        """
        Инициализация менеджера меню
        
        Args:
            tts_enabled (bool): Включить озвучку
            cache_dir (str): Директория для кэширования звуков
            debug (bool): Режим отладки
            use_wav (bool): Использовать WAV вместо MP3
            settings_manager: Менеджер настроек
            records_dir (str): Директория для записей
        """
        self.root_menu = None
        self.current_menu = None
        self.tts_enabled = tts_enabled
        self.debug = debug
        self.use_wav = use_wav
        self.cache_dir = cache_dir
        self.records_dir = records_dir
        
        # Флаг режима аудиоплеера - когда True, все команды идут в аудиоплеер, а не в меню
        self.player_mode_active = False
        
        # Инициализация менеджера настроек
        self.settings_manager = settings_manager
        
        # Инициализация менеджера синтеза речи
        if tts_enabled:
            self.tts_manager = TTSManager(
                cache_dir=cache_dir,
                debug=debug,
                use_wav=use_wav,
                settings_manager=settings_manager
            )
        else:
            self.tts_manager = None
        
        # Инициализация менеджера записи
        self.recorder_manager = RecorderManager(
            tts_manager=self.tts_manager,
            base_dir=self.records_dir,
            debug=self.debug,
            settings_manager=settings_manager
        )
        
        # Инициализация менеджера воспроизведения
        self.playback_manager = PlaybackManager(
            tts_manager=self.tts_manager,
            base_dir=self.records_dir,
            debug=self.debug
        )
        
        # Инициализация менеджера массового удаления
        self.bulk_delete_manager = BulkDeleteManager(
            menu_manager=self,
            records_dir=self.records_dir,
            debug=self.debug
        )
        
        # Состояние записи
        self.recording_state = {
            "active": False,
            "paused": False,
            "folder": None,
            "elapsed_time": 0,
            "formatted_time": "00:00:00",
            "max_duration_handled": False
        }
        
        # Состояние воспроизведения
        self.playback_state = {
            "active": False,
            "paused": False,
            "folder": None,
            "current_file": None,
            "position": "00:00:00",
            "duration": "00:00:00",
            "progress": 0
        }
        
        # Регистрируем обратный вызов для обновления информации о записи
        self.recorder_manager.set_update_callback(self._update_recording_info)
        
        # Регистрируем обратный вызов для обновления информации о воспроизведении
        self.playback_manager.set_update_callback(self._update_playback_info)
        
        # Инициализация менеджера отображения
        self.display_manager = DisplayManager(self)
        
        # Меню, из которого был запущен аудиоплеер (для возврата по KEY_BACK)
        self.source_menu = None
        
        # Флаг для предотвращения двойного озвучивания громкости
        self._volume_announced = False
        
        # Создаем структуру меню
        self.create_menu_structure()
    
    def set_root_menu(self, menu):
        """
        Устанавливает корневое меню
        
        Args:
            menu (SubMenu): Корневое меню
        """
        self.root_menu = menu
        self.current_menu = menu
    
    def display_current_menu(self):
        """Отображает текущее меню и озвучивает его название"""
        try:
            if not self.current_menu:
                return
                
            # Получаем человеко-читаемое имя меню
            menu_name = self.current_menu.name
            
            # Отладочная информация
            if self.debug:
                print(f"\n--- ОТОБРАЖЕНИЕ МЕНЮ: {menu_name} ---")
                print(f"Количество пунктов: {len(self.current_menu.items)}")
                print(f"Текущий выбранный пункт: {self.current_menu.current_selection}")
                
            # Обновляем отображение меню
            if self.display_manager:
                try:
                    self.display_manager.display_menu(self.current_menu)
                except Exception as display_error:
                    print(f"Ошибка при обновлении дисплея: {display_error}")
                    sentry_sdk.capture_exception(display_error)
            
            # Больше не озвучиваем название меню при входе в него
            # Сразу переходим к озвучиванию текущего пункта меню
            self.announce_current_menu_item()
        except Exception as e:
            error_msg = f"Ошибка при отображении меню: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def move_up(self):
        """
        Перемещает выделение меню вверх
        
        Returns:
            bool: True если навигация выполнена успешно
        """
        try:
            if not self.current_menu:
                return False
                
            if self.debug:
                print("Навигация: ВВЕРХ")
                
            # Перемещаем указатель вверх
            old_index = self.current_menu.current_selection
            self.current_menu.move_up()
            new_index = self.current_menu.current_selection
            
            # Если индекс изменился, считаем навигацию успешной
            if old_index != new_index:
                if self.debug:
                    print(f"Переход с пункта {old_index} на {new_index}")
                    
                # Обновляем отображение
                if self.display_manager:
                    try:
                        self.display_manager.display_menu(self.current_menu)
                    except Exception as display_error:
                        print(f"Ошибка при обновлении дисплея: {display_error}")
                        sentry_sdk.capture_exception(display_error)
                
                # Озвучиваем новый пункт используя announce_current_menu_item
                if self.tts_enabled:
                    self.announce_current_menu_item()
                
                return True
            else:
                if self.debug:
                    print("Навигация вверх не изменила выбранный пункт")
                return False
        except Exception as e:
            error_msg = f"Ошибка при навигации вверх: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def move_down(self):
        """
        Перемещает выделение меню вниз
        
        Returns:
            bool: True если навигация выполнена успешно
        """
        try:
            if not self.current_menu:
                return False
                
            if self.debug:
                print("Навигация: ВНИЗ")
                
            # Перемещаем указатель вниз
            old_index = self.current_menu.current_selection
            self.current_menu.move_down()
            new_index = self.current_menu.current_selection
            
            # Если индекс изменился, считаем навигацию успешной
            if old_index != new_index:
                if self.debug:
                    print(f"Переход с пункта {old_index} на {new_index}")
                    
                # Обновляем отображение
                if self.display_manager:
                    try:
                        self.display_manager.display_menu(self.current_menu)
                    except Exception as display_error:
                        print(f"Ошибка при обновлении дисплея: {display_error}")
                        sentry_sdk.capture_exception(display_error)
                
                # Озвучиваем новый пункт используя announce_current_menu_item
                if self.tts_enabled:
                    self.announce_current_menu_item()
                
                return True
            else:
                if self.debug:
                    print("Навигация вниз не изменила выбранный пункт")
                return False
        except Exception as e:
            error_msg = f"Ошибка при навигации вниз: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def _get_voice_id_for_menu_item(self, menu_item_name):
        """
        Получает идентификатор голоса для заданного названия пункта меню
        
        Args:
            menu_item_name (str): Название пункта меню
            
        Returns:
            str: Идентификатор голоса или None, если соответствие не найдено
        """
        # Получаем словарь голосов
        voices_dict = self.settings_manager.get_available_voices()
        
        # Ищем соответствие между названием пункта меню и голосом
        for voice_id, voice_desc in voices_dict.items():
            if voice_desc == menu_item_name:
                return voice_id
                
        return None
    
    def select_current_item(self):
        """Выбирает текущий пункт меню"""
        if not self.current_menu:
            return
            
        # Получаем текущий выбранный пункт меню
        item = self.current_menu.get_current_item()
        if not item:
            return
            
        # Вызываем метод select у выбранного пункта
        result = item.select()
        
        # Если результат - подменю или наследник BaseMenu, переключаемся на него
        if isinstance(result, SubMenu) or isinstance(result, BaseMenu):
            self.current_menu = result
            
            # Вызываем метод on_enter для нового меню, если он существует
            if hasattr(self.current_menu, 'on_enter') and callable(self.current_menu.on_enter):
                self.current_menu.on_enter()
                
            self.display_current_menu()
        elif result is not None:
            # Если результат не None и не подменю, 
            # показываем сообщение с результатом и озвучиваем его
            self.display_manager.display_message(str(result))
            
            if self.tts_enabled:
                # Получаем текущий голос из настроек
                voice = self.settings_manager.get_voice()
                self.tts_manager.play_speech(str(result), voice_id=voice)
                
            self.display_current_menu()
        # Если возвращен None, и это пункт "Назад", возвращаемся в родительское меню
        elif result is None and hasattr(item, 'name') and item.name.lower() in ["назад", "back"]:
            if self.current_menu and self.current_menu.parent:
                self.current_menu = self.current_menu.parent
                
                # Вызываем метод on_enter для родительского меню, если он существует
                if hasattr(self.current_menu, 'on_enter') and callable(self.current_menu.on_enter):
                    self.current_menu.on_enter()
                    
                self.display_current_menu()
    
    def go_back(self) -> None:
        """
        Возврат к предыдущему меню.
        """
        try:
            # Проверяем, есть ли у текущего меню родительское меню
            if hasattr(self.current_menu, 'parent') and self.current_menu.parent:
                # Если есть родительское меню, переходим к нему
                parent = self.current_menu.parent
                logger.info(f"Возврат в родительское меню: {getattr(parent, 'name', str(parent))}")
                
                # Переходим к родительскому меню
                self.current_menu = parent
                
                # Если родительское меню имеет метод on_enter, вызываем его
                if hasattr(parent, 'on_enter') and callable(parent.on_enter):
                    parent.on_enter()
                
                # Отображаем родительское меню
                self.display_current_menu()
            else:
                # Если нет родительского меню, переходим в главное меню
                logger.info("Возврат в главное меню (родительское меню не найдено)")
                self.current_menu = self.root_menu
                self.display_current_menu()
                
                # Обновляем сообщение перед возвратом в главное меню
                self.tts_manager.play_speech(
                    "Возврат в главное меню", 
                    voice_id=self.settings_manager.get_voice()
                )
        except Exception as e:
            logger.error(f"Ошибка при возврате к предыдущему меню: {e}")
            sentry_sdk.capture_exception(e)
            # В случае ошибки возвращаемся в главное меню
            self.current_menu = self.root_menu
            self.display_current_menu()
    
    def handle_key_back(self) -> None:
        """
        Обработка нажатия кнопки "Назад".
        """
        try:
            logger.info("Обработка нажатия кнопки: KEY_BACK")
            
            # Проверяем текущий режим
            if self.current_mode == self.MODE_MENU:
                logger.info("Текущий режим: МЕНЮ")
                
                # Проверяем активна ли запись и воспроизведение
                is_recording = self.recorder.is_recording() if hasattr(self, 'recorder') else False
                is_playing = self.player.is_playing if hasattr(self, 'player') else False
                logger.info(f"Запись активна: {is_recording}, Воспроизведение активно: {is_playing}")
                
                # Если запись активна, останавливаем её
                if is_recording:
                    self.recorder.stop_recording()
                    return
                
                # Если воспроизведение активно, останавливаем его
                if is_playing:
                    self.player.stop()
                    return
                
                # Возвращаемся в предыдущее меню
                if hasattr(self.current_menu, 'parent') and self.current_menu.parent:
                    logger.info("Подготовка к возврату в родительское меню")
                    parent_name = getattr(self.current_menu.parent, 'name', "предыдущее меню")
                    self.tts_manager.play_speech("Возврат в", voice_id=self.settings_manager.get_voice())
                    time.sleep(0.1)  # Небольшая пауза между сообщениями
                    self.tts_manager.play_speech(parent_name, voice_id=self.settings_manager.get_voice())
                else:
                    logger.info("Подготовка к возврату в главное меню")
                    self.tts_manager.play_speech("Возврат в", voice_id=self.settings_manager.get_voice())
                    time.sleep(0.1)  # Небольшая пауза между сообщениями
                    self.tts_manager.play_speech("главное меню", voice_id=self.settings_manager.get_voice())
                    
                # Выполняем возврат
                self.go_back()
            else:
                logger.info(f"Текущий режим: {self.current_mode}")
                # Другие режимы обрабатываются в соответствующих классах
                
        except Exception as e:
            logger.error(f"Ошибка при обработке кнопки KEY_BACK: {e}")
            sentry_sdk.capture_exception(e)
            # В случае ошибки возвращаемся в главное меню
            self.current_menu = self.root_menu
            self.display_current_menu()
    
    def pre_generate_all_speech(self, voices=None):
        """
        Предварительно генерирует все звуки для меню
        
        Args:
            voices (list, optional): Список голосов для предварительной генерации
        """
        if not self.tts_enabled or not self.root_menu:
            return
        
        # Если голоса не указаны, используем все доступные голоса
        if voices is None:
            voices = list(self.settings_manager.get_available_voices().keys())
        
        # Собираем все тексты для озвучки
        speech_texts = set()
        
        def collect_speech_texts(menu):
            # Добавляем только тексты пунктов меню, не озвучиваем название самого меню
            for item in menu.items:
                speech_texts.add(item.get_speech_text())
                if isinstance(item, SubMenu):
                    collect_speech_texts(item)
        
        # Начинаем с корневого меню
        collect_speech_texts(self.root_menu)
        
        # Добавляем системные сообщения для возврата
        speech_texts.add("Возврат в")
        speech_texts.add("главное меню")
        speech_texts.add("предыдущее меню")
        speech_texts.add("Голос успешно изменен")
        speech_texts.add("Диктофон готов к работе")  # Добавляем сообщение о готовности
        
        # Добавляем сообщения для диктофона
        speech_texts.add("Запись началась")
        speech_texts.add("Запись приостановлена")
        speech_texts.add("Запись возобновлена")
        speech_texts.add("Запись остановлена")
        speech_texts.add("Запись сохранена в папку")  # Первая часть сообщения
        speech_texts.add("Запись отменена")
        speech_texts.add("Выберите папку для записи")
        speech_texts.add("Папка A")
        speech_texts.add("Папка B")
        speech_texts.add("Папка C")
        
        # Добавляем сообщения для информации о файлах в папках
        speech_texts.add("В папке")  # Первая часть сообщения
        speech_texts.add("нет записей")  # Третья часть сообщения
        
        # Добавляем слова для формирования сообщений о количестве файлов
        for count in range(0, 100):  # Поддержка до 99 файлов
            speech_texts.add(str(count))
        speech_texts.add("файл")
        speech_texts.add("файла")
        speech_texts.add("файлов")
        
        # Добавляем слово "Папка" для навигации по файлам на флешке
        speech_texts.add("Папка")
        
        # Добавляем сообщения для воспроизведения
        speech_texts.add("Воспроизведение")
        speech_texts.add("Пауза")
        speech_texts.add("Прослушано")
        speech_texts.add("Переключаю вперед на запись")
        speech_texts.add("Переключаю назад на запись")
        speech_texts.add("Ошибка при переключении трека")
        speech_texts.add("Запись успешно удалена")
        speech_texts.add("Ошибка при удалении записи")
        
        # Добавляем сообщения для удаления файлов
        speech_texts.add("Вы точно хотите удалить эту запись")
        speech_texts.add("Запись успешно удалена")
        speech_texts.add("Ошибка при удалении записи")
        
        # Добавляем сообщения для массового удаления записей
        speech_texts.add("Массовое удаление записей")
        speech_texts.add("Удалить записи из всех папок")
        speech_texts.add("Вы действительно хотите удалить все записи из папки")
        speech_texts.add("Вы точно хотите удалить все записи из всех папок")
        speech_texts.add("Финальное подтверждение удаления всех записей")
        speech_texts.add("Количество записей")
        speech_texts.add("В папке нет записей")
        speech_texts.add("Нет записей во всех папках")
        speech_texts.add("Ошибка при удалении записей из папки")
        speech_texts.add("Ошибка при удалении записей из всех папок")
        speech_texts.add("запись")
        speech_texts.add("записи")
        speech_texts.add("записей")
        
        # Добавляем сообщения для внешнего носителя
        speech_texts.add("Недостаточно места на флешке")
        speech_texts.add("Копирование успешно завершено")
        speech_texts.add("Возврат в режим внешнего носителя")
        speech_texts.add("Произошла ошибка при копировании файлов")
        speech_texts.add("Флешка была отключена")
        speech_texts.add("Директория с записями не найдена")
        speech_texts.add("Скопировать все аудиозаписи из всех папок")
        speech_texts.add("Скопировать все аудиозаписи из папки")
        
        # Добавляем сообщения для настроек громкости (теперь отдельно)
        speech_texts.add("Установлен уровень громкости")
        speech_texts.add("Уровень громкости")
        speech_texts.add("Сейчас установлен уровень громкости")
        
        # Добавляем числовые значения для уровней громкости
        for level in range(0, 7):
            speech_texts.add(f"{level}")
        
        # Попытка добавить имена записей диктофона из папок A, B, C
        try:
            # Путь к папке с записями
            records_dir = self.records_dir
            if os.path.exists(records_dir):
                # Папки для диктофона
                folders = ["A", "B", "C"]
                for folder in folders:
                    folder_path = os.path.join(records_dir, folder)
                    if os.path.exists(folder_path):
                        # Получаем список файлов в папке
                        files = [f for f in os.listdir(folder_path) if f.endswith(('.wav', '.mp3'))]
                        for file in files:
                            file_path = os.path.join(folder_path, file)
                            # Получаем человекочитаемое название файла
                            if hasattr(self, 'playback_manager') and self.playback_manager:
                                readable_name = self.playback_manager.get_human_readable_filename(file_path)
                                speech_texts.add(readable_name)
        except Exception as e:
            print(f"Ошибка при получении имен файлов из папок диктофона: {e}")
            sentry_sdk.capture_exception(e)
        
        # Попытка добавить имена файлов с подключенного внешнего носителя
        try:
            # Проверяем подключенные USB-устройства
            if hasattr(self, 'external_storage_menu') and self.external_storage_menu:
                mounted_devices = self.external_storage_menu.get_mounted_devices()
                for device_info in mounted_devices:
                    mount_point = device_info.get('mount_point')
                    if mount_point and os.path.exists(mount_point):
                        # Получаем список аудиофайлов на флешке
                        for root, dirs, files in os.walk(mount_point):
                            for file in files:
                                if file.endswith(('.wav', '.mp3')):
                                    file_path = os.path.join(root, file)
                                    # Получаем человекочитаемое название файла
                                    if hasattr(self, 'playback_manager') and self.playback_manager:
                                        readable_name = self.playback_manager.get_human_readable_filename(file_path)
                                        speech_texts.add(readable_name)
        except Exception as e:
            print(f"Ошибка при получении имен файлов с внешнего носителя: {e}")
            sentry_sdk.capture_exception(e)
        
        # Предварительно генерируем все звуки для всех голосов
        self.tts_manager.pre_generate_menu_items(speech_texts, voices=voices)
    
    def change_voice(self, voice_id):
        """
        Изменяет голос озвучки
        
        Args:
            voice_id (str): Идентификатор голоса
            
        Returns:
            str: Сообщение о результате операции
        """
        try:
            # Логируем начало процесса
            sentry_sdk.add_breadcrumb(
                category="voice",
                message=f"Начало процесса изменения голоса на {voice_id}",
                level="info"
            )
            print(f"[VOICE] Запрос на изменение голоса: {voice_id}")
            
            # Проверяем, доступен ли TTS
            if not self.tts_enabled:
                sentry_sdk.capture_message("Попытка изменить голос при отключенной озвучке", level="warning")
                return "Озвучка отключена"
            
            # Отладочная информация
            current_voice = self.settings_manager.get_voice()
            sentry_sdk.add_breadcrumb(
                category="voice",
                message=f"Текущий голос: {current_voice}",
                level="info"
            )
            print(f"[VOICE] Текущий голос в настройках: {current_voice}")
            
            # Проверяем, не выбран ли уже этот голос
            if current_voice == voice_id:
                sentry_sdk.add_breadcrumb(
                    category="voice",
                    message=f"Голос {voice_id} уже выбран",
                    level="info"
                )
                print(f"[VOICE] Голос {voice_id} уже выбран, никаких изменений не требуется")
                message = "Этот голос уже выбран"
                self.tts_manager.play_speech(message, voice_id=voice_id)
                return message
            
            # Проверяем существование голоса в доступных
            available_voices = self.settings_manager.get_available_voices()
            sentry_sdk.add_breadcrumb(
                category="voice",
                message=f"Доступные голоса: {available_voices}",
                level="info"
            )
            print(f"[VOICE] Доступные голоса: {available_voices}")
            
            if voice_id not in available_voices:
                error_msg = f"Голос {voice_id} не найден в списке доступных голосов"
                print(f"[VOICE ERROR] {error_msg}")
                sentry_sdk.capture_message(error_msg, level="error")
                return "Ошибка: выбранный голос недоступен"
            
            # Изменяем голос в настройках
            print(f"[VOICE] Вызов settings_manager.set_voice({voice_id})")
            if not self.settings_manager.set_voice(voice_id):
                error_msg = f"Не удалось установить голос {voice_id} в настройках"
                print(f"[VOICE ERROR] {error_msg}")
                sentry_sdk.capture_message(error_msg, level="error")
                return "Ошибка при изменении голоса в настройках"
            
            # Проверяем результат установки голоса в настройках
            new_settings_voice = self.settings_manager.get_voice()
            sentry_sdk.add_breadcrumb(
                category="voice",
                message=f"Голос в настройках после установки: {new_settings_voice}",
                level="info"
            )
            print(f"[VOICE] Голос в настройках после установки: {new_settings_voice}")
            
            # Изменяем голос в TTS менеджере
            try:
                print(f"[VOICE] Вызов tts_manager.set_voice({voice_id})")
                result = self.tts_manager.set_voice(voice_id)
                sentry_sdk.add_breadcrumb(
                    category="voice",
                    message=f"Результат установки голоса в TTS: {result}",
                    level="info"
                )
                print(f"[VOICE] Результат установки голоса в TTS: {result}")
                
                if not result:
                    error_msg = f"Не удалось установить голос {voice_id} в TTS менеджере"
                    print(f"[VOICE ERROR] {error_msg}")
                    sentry_sdk.capture_message(error_msg, level="error")
                    return "Ошибка при изменении голоса в TTS системе"
            except Exception as tts_error:
                error_msg = f"Ошибка при установке голоса {voice_id} в TTS менеджере: {str(tts_error)}"
                print(f"[VOICE ERROR] {error_msg}")
                sentry_sdk.capture_exception(tts_error)
                return "Ошибка при изменении голоса в TTS системе"
            
            # Проверяем текущий голос в TTS после установки
            tts_current_voice = getattr(self.tts_manager, 'voice', 'неизвестно')
            sentry_sdk.add_breadcrumb(
                category="voice",
                message=f"Текущий голос в TTS после установки: {tts_current_voice}",
                level="info"
            )
            print(f"[VOICE] Текущий голос в TTS после установки: {tts_current_voice}")
            
            # Важно! Перестраиваем структуру меню, чтобы обновить голоса во всех пунктах
            try:
                # Сохраняем текущее меню и его состояние
                current_menu_path = []
                temp_menu = self.current_menu
                while temp_menu and temp_menu != self.root_menu:
                    # Ищем индекс текущего меню в родительском
                    if temp_menu.parent:
                        for i, item in enumerate(temp_menu.parent.items):
                            if item is temp_menu:
                                current_menu_path.insert(0, i)
                                break
                    temp_menu = temp_menu.parent
                
                current_index = self.current_menu.current_selection
                sentry_sdk.add_breadcrumb(
                    category="voice",
                    message=f"Сохранение состояния меню перед обновлением: путь {current_menu_path}, индекс {current_index}",
                    level="info"
                )
                print(f"[VOICE] Сохранение состояния меню перед обновлением: путь {current_menu_path}, индекс {current_index}")
                
                # Пересоздаем структуру меню
                self.create_menu_structure()
                sentry_sdk.add_breadcrumb(
                    category="voice",
                    message="Структура меню успешно пересоздана",
                    level="info"
                )
                print(f"[VOICE] Структура меню успешно пересоздана")
                
                # Восстанавливаем положение в меню
                temp_menu = self.root_menu
                for menu_index in current_menu_path:
                    if 0 <= menu_index < len(temp_menu.items):
                        item = temp_menu.items[menu_index]
                        if isinstance(item, SubMenu):
                            temp_menu = item
                        else:
                            # Если это не подменю, прерываем восстановление
                            break
                
                # Устанавливаем текущее меню и выбранный пункт
                self.current_menu = temp_menu
                if 0 <= current_index < len(self.current_menu.items):
                    self.current_menu.current_selection = current_index
                
                sentry_sdk.add_breadcrumb(
                    category="voice",
                    message=f"Состояние меню восстановлено: {self.current_menu.name}, индекс {self.current_menu.current_selection}",
                    level="info"
                )
                print(f"[VOICE] Состояние меню восстановлено: {self.current_menu.name}, индекс {self.current_menu.current_selection}")
                
            except Exception as menu_error:
                error_msg = f"Ошибка при обновлении структуры меню: {str(menu_error)}"
                print(f"[VOICE ERROR] {error_msg}")
                sentry_sdk.capture_exception(menu_error)
                # Продолжаем выполнение, это не критическая ошибка
            
            # Пробуем тестовую озвучку с новым голосом
            message = "Голос успешно изменен"
            
            try:
                print(f"[VOICE] Пробуем тестовую озвучку с голосом {voice_id}")
                # Явно передаем идентификатор голоса для корректной озвучки
                result = self.tts_manager.play_speech(message, voice_id=voice_id)
                sentry_sdk.add_breadcrumb(
                    category="voice",
                    message=f"Результат тестовой озвучки: {result}",
                    level="info"
                )
                print(f"[VOICE] Результат тестовой озвучки: {result}")
                
                if not result:
                    error_msg = f"Не удалось выполнить тестовую озвучку с голосом {voice_id}"
                    print(f"[VOICE ERROR] {error_msg}")
                    sentry_sdk.capture_message(error_msg, level="error")
                    return "Ошибка при проверке нового голоса"
            except Exception as speech_error:
                error_msg = f"Ошибка при тестовой озвучке с голосом {voice_id}: {str(speech_error)}"
                print(f"[VOICE ERROR] {error_msg}")
                sentry_sdk.capture_exception(speech_error)
                return "Ошибка при проверке нового голоса"
            
            # Обновляем отображение текущего меню
            self.display_current_menu()
            
            # Финальная проверка
            final_voice = self.settings_manager.get_voice()
            sentry_sdk.add_breadcrumb(
                category="voice",
                message=f"Финальная проверка голоса: {final_voice}",
                level="info"
            )
            print(f"[VOICE] Финальная проверка голоса в настройках: {final_voice}")
            
            # Отправляем в Sentry информацию об успешной смене голоса
            sentry_sdk.capture_message(
                f"Голос успешно изменен с {current_voice} на {final_voice}",
                level="info"
            )
            
            return message
            
        except Exception as e:
            error_msg = f"Критическая ошибка при смене голоса на {voice_id}: {str(e)}"
            print(f"[VOICE CRITICAL ERROR] {error_msg}")
            sentry_sdk.capture_exception(e)
            return "Критическая ошибка при изменении голоса"
        
    def create_menu_structure(self):
        """Создает структуру меню согласно заданной схеме"""
        # Создаем корневое (главное) меню
        main_menu = SubMenu("Главное меню")
        
        # Меню режима диктофона
        dictaphone_menu = SubMenu("Режим диктофона", parent=main_menu)
        main_menu.add_item(MenuItem("Режим диктофона", lambda: dictaphone_menu))
        
        # Добавляем подменю для диктофона
        dictaphone_menu.add_item(MenuItem("Создать новую запись", lambda: self._show_folder_selection_menu()))
        dictaphone_menu.add_item(MenuItem("Воспроизвести запись", lambda: self._show_play_record_menu()))
        dictaphone_menu.add_item(MenuItem("Массовое удаление записей", lambda: self._show_delete_record_menu()))
        
        # Добавляем подменю для режима звонка
        call_menu = SubMenu("Режим звонка", parent=main_menu)
        main_menu.add_item(MenuItem("Режим звонка", lambda: call_menu))
        
        # - Принять звонок
        accept_call_menu = SubMenu("Принять звонок", parent=call_menu)
        call_menu.add_item(accept_call_menu)
        
        # -- Подтверждение входящего вызова
        incoming_call_menu = SubMenu("Входящий вызов", parent=accept_call_menu)
        accept_call_menu.add_item(incoming_call_menu)
        
        # --- Подтверждение
        incoming_call_menu.add_item(MenuItem("Да", lambda: "Звонок принят"))
        incoming_call_menu.add_item(MenuItem("Нет", lambda: "Звонок отклонен"))
        
        # - Совершить звонок
        make_call_menu = SubMenu("Совершить звонок", parent=call_menu)
        call_menu.add_item(make_call_menu)
        
        # -- Избранные контакты
        favorites_menu = SubMenu("Избранные контакты", parent=make_call_menu)
        make_call_menu.add_item(favorites_menu)
        
        # --- Контакты
        favorites_menu.add_item(MenuItem("NAME1", lambda: "Звонок NAME1"))
        favorites_menu.add_item(MenuItem("NAME2", lambda: "Звонок NAME2"))
        favorites_menu.add_item(MenuItem("Удалить избранный контакт", lambda: "Удаление контакта"))
        favorites_menu.add_item(MenuItem("Добавить избранный контакт", lambda: "Добавление контакта"))
        
        # -- Последние набранные
        recent_menu = SubMenu("Последние набранные", parent=make_call_menu)
        make_call_menu.add_item(recent_menu)
        
        # --- Контакты
        recent_menu.add_item(MenuItem("NAME", lambda: "Звонок NAME (последний)"))
        
        # Добавляем подменю для режима радио
        radio_menu = RadioMenu(parent=main_menu, menu_manager=self)
        main_menu.add_item(MenuItem("Радио", lambda: radio_menu))
        
        # Добавляем подменю для внешних носителей
        external_storage = ExternalStorageMenu(
            settings_manager=self.settings_manager, 
            debug=self.debug, 
            menu_manager=self
        )
        main_menu.add_item(MenuItem("Внешний носитель", lambda: external_storage))
        
        # Добавляем подменю для настроек
        settings_menu = SubMenu("Настройки", parent=main_menu)
        main_menu.add_item(MenuItem("Настройки", lambda: settings_menu))
        
        # - Подменю выбора голоса
        voice_menu = SubMenu("Выбор голоса", parent=settings_menu)
        settings_menu.add_item(voice_menu)
        
        # -- Добавляем доступные голоса
        available_voices = self.settings_manager.get_available_voices()
        if self.debug:
            print("Создание пунктов меню выбора голоса:")
            
        for voice_id, voice_desc in available_voices.items():
            if self.debug:
                print(f"  Добавление пункта: {voice_desc} -> {voice_id}")
                
            # Создаем обертку для каждого голоса, чтобы избежать проблем с lambda в цикле
            def create_voice_action(voice_id=voice_id):
                return lambda: self.change_voice(voice_id)
                
            voice_menu.add_item(MenuItem(
                voice_desc, 
                create_voice_action()
            ))

        # - Подменю выбора микрофона
        try:
            # Создаем селектор микрофона
            microphone_selector = MicrophoneSelector(
                menu_manager=self,
                settings_manager=self.settings_manager,
                debug=self.debug
            )
            
            # Получаем подменю от селектора и добавляем его в настройки
            microphone_menu = microphone_selector.get_menu()
            microphone_menu.parent = settings_menu
            settings_menu.add_item(microphone_menu)
            
            if self.debug:
                print("Подменю выбора микрофона добавлено в настройки")
        except Exception as e:
            error_msg = f"Ошибка при добавлении меню выбора микрофона: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
                
        # - Подменю управления громкостью системных сообщений
        volume_menu = SubMenu("Громкость системных сообщений", parent=settings_menu)
        # Добавляем обработчик входа в меню для озвучивания текущей громкости
        volume_menu.on_enter = lambda: self._announce_current_volume()
        settings_menu.add_item(volume_menu)
        
        # -- Добавляем пункты управления громкостью (7 уровней от 0 до 6)
        for level in range(7):
            volume_item = MenuItem(
                f"Уровень громкости {level}",
                lambda lvl=level: self.change_system_volume(lvl)
            )
            # Добавляем обработчик наведения курсора
            volume_item.on_focus = lambda lvl=level: self.preview_system_volume(lvl)
            volume_menu.add_item(volume_item)
        
        # Устанавливаем главное меню как корневое
        self.set_root_menu(main_menu)
        
        # Предварительно генерируем озвучку если включен TTS
        if self.tts_enabled:
            self.pre_generate_all_speech([self.tts_manager.voice])  # Генерируем только для текущего голоса
    
    def get_debug_info(self):
        """
        Возвращает отладочную информацию для текущего состояния меню
        
        Returns:
            dict: Словарь с отладочной информацией
        """
        debug_info = {
            "current_menu": self.current_menu.name if self.current_menu else "None",
            "menu_items": [item.name for item in self.current_menu.items] if self.current_menu else [],
            "current_index": getattr(self.current_menu, 'current_selection', 0)
        }
        
        # Добавляем информацию от TTS менеджера, если он доступен
        if hasattr(self, 'tts_manager') and self.tts_manager:
            debug_info["tts"] = self.tts_manager.get_debug_info()
            
            # Если используется Google Cloud TTS, добавляем специфичную информацию
            if hasattr(self.tts_manager, 'tts_engine') and self.tts_manager.tts_engine == "google_cloud":
                if hasattr(self.tts_manager, 'google_tts_manager') and self.tts_manager.google_tts_manager:
                    try:
                        google_tts_metrics = self.tts_manager.google_tts_manager.get_usage_info()
                        
                        # Форматируем метрики для удобства чтения
                        debug_info["google_cloud_tts"] = {
                            "total_requests": google_tts_metrics["total_requests"],
                            "today_requests": google_tts_metrics["today_requests"],
                            "total_chars": f"{google_tts_metrics['total_chars']:,}",
                            "monthly_chars_used": f"{google_tts_metrics['monthly_chars_used']:,}",
                            "remaining_free_chars": f"{google_tts_metrics['remaining_free_chars']:,}",
                            "voice_type": google_tts_metrics["voice_type"],
                            "price_per_million": f"${google_tts_metrics['price_per_million']:.2f}",
                            "estimated_cost": f"${google_tts_metrics['estimated_cost']:.2f}",
                            "last_update": google_tts_metrics["last_update"]
                        }
                    except Exception as e:
                        debug_info["google_cloud_tts_error"] = str(e)
        
        return debug_info

    def _update_recording_info(self):
        """Обновляет информацию о записи"""
        try:
            if not self.recorder_manager or not self.display_manager:
                return
            
            # Получаем текущий статус записи
            is_recording = self.recorder_manager.is_recording()
            is_paused = self.recorder_manager.is_paused()
            
            # Обновляем состояние записи
            self.recording_state["active"] = is_recording
            self.recording_state["paused"] = is_paused
            
            if is_recording:
                # Получаем текущую папку
                self.recording_state["folder"] = self.recorder_manager.get_current_folder()
                
                # Получаем текущее время записи
                current_time = self.recorder_manager.get_current_time()
                formatted_time = self.recorder_manager.get_formatted_time()
                
                self.recording_state["elapsed_time"] = current_time
                self.recording_state["formatted_time"] = formatted_time
                
                # Проверяем, не достигнут ли максимальный порог записи
                if current_time >= AudioRecorder.MAX_RECORDING_DURATION:
                    self._handle_max_duration_reached()
                
                # Отображаем экран записи
                status = "Paused" if is_paused else "Recording"
                self.display_manager.display_recording_screen(
                    status=status,
                    time=formatted_time,
                    folder=self.recording_state["folder"]
                )
        except Exception as e:
            error_msg = f"Ошибка при обновлении информации о записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def _handle_max_duration_reached(self):
        """Обрабатывает ситуацию, когда достигнут максимальный порог записи"""
        try:
            if self.recording_state["max_duration_handled"]:
                return  # Уже обработано
                
            print("Достигнут максимальный порог записи (3 часа)")
            self.recording_state["max_duration_handled"] = True
            
            # Останавливаем запись
            self._stop_recording()
            
            # Отображаем сообщение
            self.display_manager.display_message(
                message="Достигнут максимальный порог записи 3 часа. Запись автоматически завершена.",
                title="Автоматическая остановка"
            )
            
            # Задержка, чтобы пользователь успел прочитать сообщение
            time.sleep(3)
            
            # Возвращаемся к основному меню
            if self.current_menu and self.current_menu.parent:
                self.current_menu = self.current_menu.parent
                self.display_current_menu()
                
        except Exception as e:
            error_msg = f"Ошибка при обработке превышения длительности записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def _start_recording(self, folder):
        """
        Начинает запись в указанную папку
        
        Args:
            folder (str): Папка для записи (A, B или C)
        """
        try:
            print(f"\n*** НАЧАЛО ЗАПИСИ В ПАПКУ {folder} ***")
            
            # Сбрасываем состояние записи
            self.recording_state = {
                "active": False,
                "paused": False,
                "folder": folder,
                "elapsed_time": 0,
                "formatted_time": "00:00:00",
                "max_duration_handled": False
            }
            
            # Начинаем запись
            if self.recorder_manager.start_recording(folder):
                print("Запись успешно начата")
                
                # Отображаем экран записи
                self.display_manager.display_recording_screen(
                    status="Recording",
                    time="00:00:00",
                    folder=folder
                )
                
                # Обновляем состояние записи
                self.recording_state["active"] = True
            else:
                print("Ошибка при начале записи")
                # Возвращаемся в меню выбора папки
                self.display_current_menu()
        except Exception as e:
            error_msg = f"Ошибка при начале записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
            # Возвращаемся в меню выбора папки
            self.display_current_menu()
    
    def _toggle_pause_recording(self):
        """Переключает паузу записи"""
        if not self.recording_state["active"]:
            print("Попытка поставить на паузу, но запись не активна")
            return
        
        try:
            print(f"Переключаем паузу. Текущее состояние паузы: {self.recording_state['paused']}")
            
            if self.recording_state["paused"]:
                # Возобновляем запись
                print("Возобновляем запись...")
                result = self.recorder_manager.resume_recording()
                if result:
                    print("Запись успешно возобновлена")
                    # Обновляем состояние паузы
                    self.recording_state["paused"] = False
                    
                    # Обновляем отображение экрана записи
                    self.display_manager.display_recording_screen(
                        status="Recording",
                        time=self.recording_state["formatted_time"],
                        folder=self.recording_state["folder"]
                    )
                else:
                    print("ОШИБКА: Не удалось возобновить запись!")
            else:
                # Приостанавливаем запись
                print("Приостанавливаем запись...")
                result = self.recorder_manager.pause_recording()
                if result:
                    print("Запись успешно приостановлена")
                    # Обновляем состояние паузы
                    self.recording_state["paused"] = True
                    
                    # Обновляем отображение экрана записи
                    self.display_manager.display_recording_screen(
                        status="Paused",
                        time=self.recording_state["formatted_time"],
                        folder=self.recording_state["folder"]
                    )
                else:
                    print("ОШИБКА: Не удалось приостановить запись!")
            
            # Отображаем текущий статус записи (для информации)
            print(f"Статус записи: активна={self.recording_state['active']}, "
                f"на паузе={self.recording_state['paused']}, "
                f"папка={self.recording_state['folder']}, "
                f"время={self.recording_state['formatted_time']}")
                
        except Exception as e:
            print(f"КРИТИЧЕСКАЯ ОШИБКА при переключении паузы: {e}")
            sentry_sdk.capture_exception(e)
    
    def _stop_recording(self):
        """Останавливает запись и сохраняет файл"""
        if not self.recording_state["active"]:
            print("Попытка остановить запись, но запись не активна")
            return
        
        print("\n*** ОСТАНОВКА ЗАПИСИ ***")
        folder = self.recording_state["folder"]
        parent_menu = None
        
        try:
            # Запоминаем родительское меню перед тем как остановить запись
            if hasattr(self, 'current_menu') and self.current_menu and hasattr(self.current_menu, 'parent'):
                parent_menu = self.current_menu.parent
                print(f"Запоминаем родительское меню: {parent_menu.name if parent_menu else 'None'}")
            
            # Останавливаем запись
            print("Вызываем recorder_manager.stop_recording()...")
            file_path = self.recorder_manager.stop_recording()
            
            print(f"Результат stop_recording: {file_path}")
            
            # Сбрасываем состояние записи
            self.recording_state["active"] = False
            self.recording_state["paused"] = False
            
            # Даже если файл не сохранился, все равно озвучиваем что-то
            if not file_path:
                print("ОШИБКА: Не удалось сохранить запись!")
            else:
                print(f"Запись сохранена в файл: {file_path}")
            
            # Значительная задержка для полного воспроизведения всех сообщений
            # Сообщения "Запись завершается" и "Запись сохранена в папке X" должны воспроизвестись полностью
            print("Ожидание окончания воспроизведения системных сообщений (3 секунды)...")
            time.sleep(2)
            
            # Возвращаемся в родительское меню
            if parent_menu:
                print(f"Возвращаемся в родительское меню: {parent_menu.name}")
                self.current_menu = parent_menu
            else:
                print("Родительское меню не найдено, возвращаемся в корневое меню")
                self.current_menu = self.root_menu
            
            # Отображаем меню
            self.display_current_menu()
            
        except Exception as e:
            print(f"КРИТИЧЕСКАЯ ОШИБКА при остановке записи: {e}")
            sentry_sdk.capture_exception(e)
            
            # В случае ошибки все равно пытаемся вернуться в меню
            try:
                # Даем время для завершения аудио сообщений
                time.sleep(3)
                
                if parent_menu:
                    self.current_menu = parent_menu
                else:
                    self.current_menu = self.root_menu
                self.display_current_menu()
            except Exception as menu_e:
                print(f"Ошибка при возврате в меню: {menu_e}")
    
    def _show_folder_selection_menu(self):
        """Показывает меню выбора папки для записи"""
        try:
            # Создаем временное подменю для выбора папки
            folder_menu = SubMenu("Выберите папку для записи", parent=self.current_menu)
            
            # Получаем количество файлов в каждой папке
            files_in_a = self.playback_manager.count_files_in_folder("A")
            files_in_b = self.playback_manager.count_files_in_folder("B")
            files_in_c = self.playback_manager.count_files_in_folder("C")
            
            # Добавляем пункты меню для папок с указанием количества файлов
            folder_a_item = MenuItem(
                f"Папка A [{files_in_a} {self._get_files_word(files_in_a)}]", 
                action=lambda: self._start_recording("A"),
                speech_text="Папка A"  # Только название папки для озвучки
            )
            folder_menu.add_item(folder_a_item)
            
            folder_b_item = MenuItem(
                f"Папка B [{files_in_b} {self._get_files_word(files_in_b)}]", 
                action=lambda: self._start_recording("B"),
                speech_text="Папка B"  # Только название папки для озвучки
            )
            folder_menu.add_item(folder_b_item)
            
            folder_c_item = MenuItem(
                f"Папка C [{files_in_c} {self._get_files_word(files_in_c)}]", 
                action=lambda: self._start_recording("C"),
                speech_text="Папка C"  # Только название папки для озвучки
            )
            folder_menu.add_item(folder_c_item)
            
            # Переключаемся на меню выбора папки
            self.current_menu = folder_menu
            self.display_current_menu()
        except Exception as e:
            error_msg = f"Ошибка при отображении меню выбора папки: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def _show_calendar_menu(self):
        # Implementation of _show_calendar_menu method
        pass

    def _show_play_record_menu(self):
        """Показывает меню воспроизведения записей"""
        try:
            # Создаем временное подменю для выбора папки
            play_menu = SubMenu("Выберите папку для воспроизведения", parent=self.current_menu)
            
            # Получаем количество файлов в каждой папке
            files_in_a = self.playback_manager.count_files_in_folder("A")
            files_in_b = self.playback_manager.count_files_in_folder("B")
            files_in_c = self.playback_manager.count_files_in_folder("C")
            
            # Добавляем пункты меню для папок с указанием количества файлов
            folder_a_item = MenuItem(
                f"Папка A [{files_in_a} {self._get_files_word(files_in_a)}]",
                action=lambda: self._show_play_files_menu("A"),
                speech_text="Папка A"  # Только название папки для озвучки
            )
            play_menu.add_item(folder_a_item)
            
            folder_b_item = MenuItem(
                f"Папка B [{files_in_b} {self._get_files_word(files_in_b)}]",
                action=lambda: self._show_play_files_menu("B"),
                speech_text="Папка B"  # Только название папки для озвучки
            )
            play_menu.add_item(folder_b_item)
            
            folder_c_item = MenuItem(
                f"Папка C [{files_in_c} {self._get_files_word(files_in_c)}]",
                action=lambda: self._show_play_files_menu("C"),
                speech_text="Папка C"  # Только название папки для озвучки
            )
            play_menu.add_item(folder_c_item)
            
            # Переключаемся на меню выбора папки
            self.current_menu = play_menu
            self.display_current_menu()
        except Exception as e:
            error_msg = f"Ошибка при отображении меню воспроизведения: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def _show_delete_record_menu(self):
        """Показывает меню массового удаления записей"""
        try:
            # Используем BulkDeleteManager для отображения меню удаления
            self.bulk_delete_manager.show_delete_menu()
        except Exception as e:
            error_msg = f"Ошибка при отображении меню удаления: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)

    def _update_playback_info(self):
        """Обновляет информацию о текущем воспроизведении"""
        try:
            # Получаем информацию о воспроизведении
            player_info = self.playback_manager.playback_info
            
            # Обновляем состояние воспроизведения
            self.playback_state["active"] = player_info["active"]
            self.playback_state["paused"] = player_info["paused"]
            self.playback_state["position"] = player_info["position"]
            self.playback_state["duration"] = player_info["duration"]
            self.playback_state["progress"] = player_info["progress"]
            
            # Получаем информацию о текущем файле
            file_info = self.playback_manager.get_current_file_info()
            if file_info:
                self.playback_state["current_file"] = file_info["description"]
                self.playback_state["folder"] = file_info["folder"]
            
            # Проверяем, активен ли режим подтверждения удаления
            if self.playback_manager.is_delete_confirmation_active():
                # Отображаем экран подтверждения удаления
                self.display_manager.display_delete_confirmation(
                    file_name=self.playback_state["current_file"],
                    selected_option=self.playback_manager.confirm_delete_selected
                )
                
                if self.debug:
                    print(f"Отображение экрана подтверждения удаления: " +
                        f"файл={self.playback_state['current_file']}, " +
                        f"выбрано={self.playback_manager.confirm_delete_selected}")
            
            # Обновляем экран воспроизведения, если воспроизведение активно и не активен режим подтверждения
            elif self.playback_state["active"]:
                status = "Paused" if self.playback_state["paused"] else "Playing"
                self.display_manager.display_playback_screen(
                    status=status,
                    time=f"{self.playback_state['position']} / {self.playback_state['duration']}",
                    progress=self.playback_state["progress"],
                    file_name=self.playback_state["current_file"],
                    folder=self.playback_state["folder"]
                )
                
                if self.debug:
                    print(f"Обновление информации о воспроизведении: " +
                        f"активно={self.playback_state['active']}, " +
                        f"пауза={self.playback_state['paused']}, " +
                        f"время={self.playback_state['position']} / {self.playback_state['duration']}, " +
                        f"файл={self.playback_state['current_file']}")
        except Exception as e:
            error_msg = f"Ошибка при обновлении информации о воспроизведении: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def _show_play_files_menu(self, folder, start_with_file=None):
        """
        Показывает меню со списком файлов для воспроизведения
        
        Args:
            folder (str): Папка для поиска файлов
            start_with_file (int, optional): Индекс файла для немедленного воспроизведения
        """
        try:
            print(f"\n*** ЗАГРУЗКА ФАЙЛОВ ИЗ ПАПКИ {folder} ***")
            
            # Запоминаем текущее меню перед загрузкой файлов
            parent_menu = self.current_menu
            
            # Загружаем файлы из папки
            if self.playback_manager.load_folder(folder, return_to_menu=parent_menu):
                # Получаем количество файлов
                files_count = self.playback_manager.get_files_count()
                
                # Создаем подменю для файлов
                files_menu = SubMenu(f"Записи в папке {os.path.basename(folder)}")
                
                # Добавляем файлы в меню
                for i in range(files_count):
                    file_info = self.playback_manager.get_file_info(i)
                    if file_info:
                        # Используем человеко-читаемое имя файла
                        file_item = MenuItem(file_info["description"], lambda idx=i: self._play_file(idx))
                        files_menu.add_item(file_item)
                
                # Устанавливаем текущее меню
                self.current_menu = files_menu
                
                print(f"Загружено {files_count} файлов из папки {folder}")
                
                # Если указан индекс файла для воспроизведения, запускаем его сразу
                if start_with_file is not None and 0 <= start_with_file < files_count:
                    # Устанавливаем текущий выбранный пункт меню
                    self.current_menu.current_selection = start_with_file
                    # Запускаем воспроизведение
                    self._play_file(start_with_file)
                    return
                
                # Отображаем меню файлов
                self.display_current_menu()
                return
            else:
                print(f"В папке {folder} нет файлов")
                
                # Создаем сообщение
                folder_name = os.path.basename(folder)
                
                # Отображаем сообщение на экране
                self.display_manager.display_message(f"В папке {folder_name} нет записей", title="Пустая папка")
                
                if self.tts_enabled:
                    # Получаем текущий голос из настроек
                    voice = self.settings_manager.get_voice()
                    self.tts_manager.play_speech("В папке", voice_id=voice)
                    time.sleep(0.1)  # Небольшая пауза между сообщениями
                    self.tts_manager.play_speech(folder_name, voice_id=voice)
                    time.sleep(0.1)  # Небольшая пауза между сообщениями
                    self.tts_manager.play_speech("нет записей", voice_id=voice)
                
                # Возвращаемся в предыдущее меню
                time.sleep(2)
                self.display_current_menu()
                return
        except Exception as e:
            error_msg = f"Ошибка при показе меню файлов: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return
    
    def _play_file(self, file_index):
        """Начинает воспроизведение выбранного файла"""
        try:
            print("\n*** ВОСПРОИЗВЕДЕНИЕ ФАЙЛА ***")
            print(f"Индекс файла: {file_index}")
            
            # Запоминаем меню, из которого запущен аудиоплеер
            self.source_menu = self.current_menu
            if self.debug and self.source_menu:
                print(f"Запоминаем исходное меню: {self.source_menu.name}")
            
            # Активируем режим аудиоплеера
            self.player_mode_active = True
            
            if self.debug:
                print("РЕЖИМ АУДИОПЛЕЕРА АКТИВИРОВАН")
            
            # Устанавливаем текущий индекс файла
            if self.playback_manager.set_current_file(file_index):
                # Получаем информацию о файле
                file_info = self.playback_manager.get_current_file_info()
                
                # Используем простое сообщение "Воспроизведение" вместо полного названия записи
                if file_info and self.tts_enabled:
                    # Озвучиваем простое сообщение перед воспроизведением
                    voice = self.settings_manager.get_voice()
                    message = "Воспроизведение"
                    
                    if self.debug:
                        print(f"Озвучивание сообщения перед воспроизведением: {message}")
                        print(f"Не озвучиваем полное название: {file_info['description']}")
                    
                    # Используем блокирующее воспроизведение, чтобы сообщение прозвучало полностью
                    message_played = False
                    try:
                        if hasattr(self.tts_manager, 'play_speech_blocking'):
                            print("Использую блокирующее воспроизведение сообщения...")
                            self.tts_manager.play_speech_blocking(message, voice_id=voice)
                            message_played = True
                        else:
                            print("Использую стандартное воспроизведение сообщения...")
                            self.tts_manager.play_speech(message, voice_id=voice)
                            message_played = True
                    except Exception as e:
                        print(f"Ошибка при озвучивании перед воспроизведением: {e}")
                        sentry_sdk.capture_exception(e)
                    
                    # Уменьшаем паузу до 1.5 секунд
                    if message_played:
                        print("Ожидание 1.5 секунды для завершения воспроизведения сообщения...")
                        time.sleep(1.5)
                
                # Теперь начинаем воспроизведение
                print("Начинаем воспроизведение файла...")
                result = self.playback_manager.play_current_file()
                if result:
                    print("Воспроизведение успешно начато")
                else:
                    print("ОШИБКА: Не удалось начать воспроизведение")
                    # Если не удалось начать воспроизведение, деактивируем режим плеера
                    self.player_mode_active = False
            else:
                print(f"ОШИБКА: Не удалось установить текущий файл с индексом {file_index}")
                # Если не удалось установить файл, деактивируем режим плеера
                self.player_mode_active = False
                
        except Exception as e:
            print(f"КРИТИЧЕСКАЯ ОШИБКА при воспроизведении файла: {e}")
            sentry_sdk.capture_exception(e)
            # В случае ошибки деактивируем режим плеера
            self.player_mode_active = False
    
    def _toggle_pause_playback(self):
        """Переключает паузу воспроизведения"""
        if not self.playback_state["active"]:
            if self.debug:
                print("Попытка поставить на паузу, но воспроизведение не активно")
            return False
        
        try:
            print("\n*** ПЕРЕКЛЮЧЕНИЕ ПАУЗЫ ВОСПРОИЗВЕДЕНИЯ ***")
            
            # Проверяем состояние воспроизведения и паузы
            is_paused = self.playback_state["paused"]
            
            if self.debug:
                print(f"Переключаем паузу воспроизведения. Текущее состояние паузы: {is_paused}")
            
            # Пробуем несколько способов переключения паузы
            toggle_success = False
            
            # 1. Пробуем через playback_manager.toggle_pause()
            try:
                if self.debug:
                    print("ПОПЫТКА 1: Переключение через playback_manager.toggle_pause()")
                success = self.playback_manager.toggle_pause()
                if success:
                    toggle_success = True
                    if self.debug:
                        print("ПОПЫТКА 1: Успешно")
                else:
                    if self.debug:
                        print("ПОПЫТКА 1: Не удалось")
            except Exception as e:
                print(f"Ошибка при переключении паузы через playback_manager: {e}")
                sentry_sdk.capture_exception(e)
            
            # 2. Если не сработало, пробуем напрямую через AudioPlayer
            if not toggle_success and hasattr(self.playback_manager, 'player'):
                try:
                    if self.debug:
                        print("ПОПЫТКА 2: Переключение напрямую через player.pause() или player.resume()")
                    
                    player = self.playback_manager.player
                    if is_paused:
                        # Возобновляем воспроизведение
                        if hasattr(player, 'resume'):
                            if self.debug:
                                print("Вызываем player.resume()")
                            result = player.resume()
                            if result:
                                self.playback_state["paused"] = False
                                toggle_success = True
                                if self.debug:
                                    print("ПОПЫТКА 2: Успешное возобновление")
                    else:
                        # Ставим на паузу
                        if hasattr(player, 'pause'):
                            if self.debug:
                                print("Вызываем player.pause()")
                            result = player.pause()
                            if result:
                                self.playback_state["paused"] = True
                                toggle_success = True
                                if self.debug:
                                    print("ПОПЫТКА 2: Успешная постановка на паузу")
                except Exception as e:
                    print(f"Ошибка при прямом переключении паузы: {e}")
                    sentry_sdk.capture_exception(e)
            
            # 3. Если предыдущие попытки не сработали, принудительно меняем состояние
            if not toggle_success:
                try:
                    if self.debug:
                        print("ПОПЫТКА 3: Принудительное переключение состояния")
                    
                    # Инвертируем состояние паузы
                    new_paused_state = not is_paused
                    self.playback_state["paused"] = new_paused_state
                    
                    # Вызываем соответствующие методы AudioPlayer в зависимости от нового состояния
                    if hasattr(self.playback_manager, 'player'):
                        player = self.playback_manager.player
                        if new_paused_state:
                            # Ставим на паузу
                            if hasattr(player, 'pause'):
                                player.pause()
                        else:
                            # Возобновляем
                            if hasattr(player, 'resume'):
                                player.resume()
                    
                    toggle_success = True
                    if self.debug:
                        print(f"ПОПЫТКА 3: Успешно принудительно установили состояние паузы: {new_paused_state}")
                except Exception as e:
                    print(f"Ошибка при принудительном переключении паузы: {e}")
                    sentry_sdk.capture_exception(e)
            
            # Проверяем успешность операции и выводим системное сообщение при необходимости
            if toggle_success:
                # Получаем текущее состояние паузы после всех операций
                current_paused_state = self.playback_state["paused"]
                
                if self.debug:
                    print(f"Итоговое состояние паузы: {current_paused_state}")
                
                # Логика паузы уже обработана в PlaybackManager, включая озвучивание
                # Не дублируем озвучивание здесь, так как это делает PlaybackManager
                if current_paused_state:
                    if self.debug:
                        print("Воспроизведение на паузе")
                else:
                    # Воспроизведение возобновлено
                    if self.debug:
                        print("Воспроизведение возобновлено")
            else:
                if self.debug:
                    print("ОШИБКА: Не удалось переключить паузу воспроизведения всеми доступными способами")
            
            # Отображаем текущий статус воспроизведения
            if self.debug:
                print(f"Статус воспроизведения: активно={self.playback_state['active']}, " +
                      f"на паузе={self.playback_state['paused']}, " +
                      f"время={self.playback_state['position']} / {self.playback_state['duration']}")
            
            # Возвращаем результат операции
            return toggle_success
        
        except Exception as e:
            if self.debug:
                print(f"КРИТИЧЕСКАЯ ОШИБКА при переключении паузы воспроизведения: {e}")
            sentry_sdk.capture_exception(e)
            return False
    
    def _stop_playback(self):
        """Останавливает воспроизведение и возвращается в меню"""
        try:
            if not self.playback_state["active"] and not self.player_mode_active:
                if self.debug:
                    print("Попытка остановить воспроизведение, но оно не активно и режим плеера не включен")
                return False
                
            print("\n*** ОСТАНОВКА ВОСПРОИЗВЕДЕНИЯ ***")
            sentry_sdk.add_breadcrumb(
                category='playback',
                message='Остановка воспроизведения и переход к исходному меню',
                level='info'
            )
            
            # Деактивируем режим аудиоплеера в ПЕРВУЮ ОЧЕРЕДЬ,
            # чтобы предотвратить повторную обработку кнопок в режиме плеера
            old_mode = self.player_mode_active
            self.player_mode_active = False
            if self.debug:
                print(f"РЕЖИМ АУДИОПЛЕЕРА ДЕАКТИВИРОВАН (предыдущее значение: {old_mode})")
            
            # Определяем меню для возврата
            return_menu = None
            
            # Приоритетно используем source_menu - меню, из которого был запущен аудиоплеер
            if hasattr(self, 'source_menu') and self.source_menu:
                menu_name = getattr(self.source_menu, 'name', str(self.source_menu))
                print(f"Используем сохраненное исходное меню для возврата: {menu_name}")
                sentry_sdk.add_breadcrumb(
                    category='playback',
                    message=f'Возврат к исходному меню: {menu_name}',
                    level='info'
                )
                return_menu = self.source_menu
            else:
                # Если source_menu не определено, пробуем получить его из playback_manager
                files_menu = self.playback_manager.get_return_menu()
                
                # Проверяем корректность меню возврата
                if files_menu and hasattr(files_menu, 'name'):
                    menu_name = files_menu.name
                    if self.debug:
                        print(f"Возврат к меню со списком записей: {menu_name}")
                    sentry_sdk.add_breadcrumb(
                        category='playback',
                        message=f'Возврат к меню из playback_manager: {menu_name}',
                        level='info'
                    )
                    return_menu = files_menu
                else:
                    # Если у нас нет правильного меню со списком записей, попробуем найти его
                    folder = None
                    if self.playback_state["folder"]:
                        folder = self.playback_state["folder"]
                    elif self.playback_manager.current_folder:
                        folder = self.playback_manager.current_folder
                    
                    if folder and self.current_menu and hasattr(self.current_menu, 'parent'):
                        if self.debug:
                            print(f"Пытаемся найти меню с записями для папки {folder}")
                        
                        # Находим правильное меню для возврата
                        for menu in self.current_menu.parent.submenus:
                            if hasattr(menu, 'name') and menu.name and folder in menu.name:
                                return_menu = menu
                                if self.debug:
                                    print(f"Найдено меню записей: {menu.name}")
                                sentry_sdk.add_breadcrumb(
                                    category='playback',
                                    message=f'Найдено подходящее меню для возврата: {menu.name}',
                                    level='info'
                                )
                                break
            
            # Запоминаем имя меню для озвучивания
            menu_name = "списку записей"
            if return_menu and hasattr(return_menu, 'name') and return_menu.name:
                menu_name = return_menu.name
            
            if self.debug:
                print(f"Меню для возврата: {menu_name}")
            
            # Останавливаем воспроизведение ПЕРЕД озвучиванием сообщения
            # чтобы избежать проблем с перекрытием звуков
            print("Останавливаем воспроизведение...")
            
            # Дополнительная проверка, что playback_manager существует и доступен
            if not hasattr(self, 'playback_manager') or not self.playback_manager:
                if self.debug:
                    print("ОШИБКА: playback_manager не найден")
                sentry_sdk.capture_message("playback_manager не найден при остановке воспроизведения", level="error")
                return False
                
            # Принудительная остановка воспроизведения
            stop_result = self.playback_manager.stop_playback()
            if not stop_result and self.debug:
                print("ОШИБКА: stop_playback вернул False, возможно, воспроизведение не было остановлено")
                sentry_sdk.capture_message("stop_playback вернул False при остановке воспроизведения", level="warning")
            
            # Проверяем, что воспроизведение точно остановлено
            if self.playback_state["active"]:
                if self.debug:
                    print("ОШИБКА: После вызова stop_playback флаг active остался True, делаем дополнительную остановку")
                    sentry_sdk.capture_message("Флаг active остался True после остановки, делаем дополнительную остановку", level="warning")
                # Повторная попытка остановки
                self.playback_manager.stop_playback()
                # Принудительно сбрасываем состояние
                self.playback_state["active"] = False
                self.playback_state["paused"] = False
            
            # Даем время для полной остановки воспроизведения
            time.sleep(0.5)
            
            # Озвучиваем сообщение о возврате блокирующим методом
            if self.tts_enabled:
                try:
                    # Получаем текущий голос из настроек
                    voice = self.settings_manager.get_voice()
                    
                    # Формируем сообщение о возврате
                    message = f"Возврат к {menu_name}"
                    
                    if self.debug:
                        print(f"Озвучивание перед возвратом: {message}, голос: {voice}")
                    
                    # Используем блокирующее озвучивание
                    self.tts_manager.play_speech_blocking(message, voice_id=voice)
                except Exception as e:
                    print(f"Ошибка при озвучивании перед переходом: {e}")
                    sentry_sdk.capture_exception(e)
            
            # Выполняем переход в меню
            if return_menu:
                old_menu = self.current_menu
                self.current_menu = return_menu
                if self.debug:
                    old_name = getattr(old_menu, 'name', str(old_menu)) if old_menu else "None"
                    new_name = getattr(return_menu, 'name', str(return_menu))
                    print(f"Переход в меню: {old_name} -> {new_name}")
                    sentry_sdk.add_breadcrumb(
                        category='navigation',
                        message=f'Переход в меню после остановки воспроизведения: {old_name} -> {new_name}',
                        level='info'
                    )
            else:
                # Если не удалось найти меню с записями, возвращаемся к родительскому меню
                parent_menu = None
                if self.current_menu and hasattr(self.current_menu, 'parent'):
                    parent_menu = self.current_menu.parent
                
                if parent_menu:
                    old_menu = self.current_menu
                    self.current_menu = parent_menu
                    if self.debug:
                        old_name = getattr(old_menu, 'name', str(old_menu)) if old_menu else "None"
                        new_name = getattr(parent_menu, 'name', str(parent_menu))
                        print(f"Переход в родительское меню: {old_name} -> {new_name}")
                        sentry_sdk.add_breadcrumb(
                            category='navigation',
                            message=f'Переход в родительское меню: {old_name} -> {new_name}',
                            level='info'
                        )
                else:
                    # Если нет родительского меню, возвращаемся в корневое
                    old_menu = self.current_menu
                    self.current_menu = self.root_menu
                    if self.debug:
                        old_name = getattr(old_menu, 'name', str(old_menu)) if old_menu else "None"
                        new_name = getattr(self.root_menu, 'name', str(self.root_menu))
                        print(f"Переход в корневое меню: {old_name} -> {new_name}")
                        sentry_sdk.add_breadcrumb(
                            category='navigation',
                            message=f'Переход в корневое меню: {old_name} -> {new_name}',
                            level='info'
                        )
            
            # Сбрасываем source_menu
            if hasattr(self, 'source_menu'):
                self.source_menu = None
                
            # Отображаем меню
            self.display_current_menu()
            
            # Возвращаем True если операция успешна
            return True
                
        except Exception as e:
            print(f"КРИТИЧЕСКАЯ ОШИБКА при остановке воспроизведения: {e}")
            sentry_sdk.capture_exception(e)
            
            # В случае ошибки пытаемся вернуться в главное меню
            try:
                self.current_menu = self.root_menu
                self.display_current_menu()
            except Exception as menu_e:
                print(f"Не удалось вернуться в главное меню после ошибки: {menu_e}")
                sentry_sdk.capture_exception(menu_e)
                
            return False
    
    def _delete_current_file(self):
        """Удаляет текущий воспроизводимый файл"""
        if not self.player_mode_active:  # Проверяем только режим плеера, а не активность воспроизведения
            if self.debug:
                print("Попытка удалить файл, но режим плеера не активен")
            return
        
        # Инициируем процесс удаления
        self.playback_manager.delete_current_file()
    
    def _confirm_delete(self, confirmed):
        """
        Подтверждает или отменяет удаление файла
        
        Args:
            confirmed (bool): True для подтверждения, False для отмены
        """
        try:
            # Добавляем хлебные крошки для отслеживания в Sentry
            sentry_sdk.add_breadcrumb(
                category='delete',
                message=f'Начало процесса подтверждения удаления (confirmed={confirmed})',
                level='info'
            )
            
            if self.debug:
                print(f"\n*** ПОДТВЕРЖДЕНИЕ/ОТМЕНА УДАЛЕНИЯ: {confirmed} ***")
                print(f"Состояние до: player_mode={self.player_mode_active}, playback_active={self.playback_state['active']}")
            
            # Проверяем, активен ли режим подтверждения удаления
            if not self.playback_manager.is_delete_confirmation_active():
                error_msg = "Попытка подтвердить/отменить удаление, когда режим подтверждения не активен"
                if self.debug:
                    print(f"ОШИБКА: {error_msg}")
                sentry_sdk.capture_message(error_msg, level='warning')
                return
            
            # Сохраняем текущую папку перед удалением
            current_folder = self.playback_manager.current_folder
            if self.debug:
                print(f"Текущая папка перед удалением: {current_folder}")
            
            # Подтверждаем или отменяем удаление
            try:
                result = self.playback_manager.confirm_delete(confirmed)
                sentry_sdk.add_breadcrumb(
                    category='delete',
                    message=f'Результат confirm_delete: {result}',
                    level='info'
                )
                
                # Если файл был удален, обновляем список файлов и создаем новое меню
                if confirmed and result:
                    if self.debug:
                        print("Файл удален, обновляем список файлов")
                    
                    try:
                        # Добавляем задержку для гарантированного воспроизведения сообщения об удалении
                        time.sleep(2.0)
                        
                        # Проверяем, был ли удален файл с флешки
                        if result == "usb_deleted":
                            if self.debug:
                                print("Удален файл с флешки, выходим из режима плеера")
                                
                            # Деактивируем режим плеера
                            self.player_mode_active = False
                            self.playback_state["active"] = False
                            self.playback_state["paused"] = False
                            
                            # Возвращаемся в родительское меню (меню флешки)
                            if self.current_menu and self.current_menu.parent:
                                self.current_menu = self.current_menu.parent
                                
                                # Если это меню внешнего накопителя, перезагружаем его
                                if hasattr(self.current_menu, 'on_enter'):
                                    try:
                                        self.current_menu.on_enter()
                                    except Exception as reload_e:
                                        print(f"Ошибка при перезагрузке меню флешки: {reload_e}")
                                        
                                # Отображаем обновленное меню
                                self.display_current_menu()
                            return
                        
                        # Создаем новое меню с обновленным списком файлов
                        files_menu = SubMenu(f"Записи в папке {current_folder}")
                        
                        # Перезагружаем список файлов для текущей папки
                        if self.playback_manager.load_folder(current_folder, return_to_menu=files_menu):
                            # Получаем обновленный список файлов
                            files_count = self.playback_manager.get_files_count()
                            
                            if self.debug:
                                print(f"Найдено {files_count} файлов после удаления")
                            
                            # Добавляем файлы в новое меню
                            for i in range(files_count):
                                file_info = self.playback_manager.get_file_info(i)
                                if file_info:
                                    file_item = MenuItem(file_info["description"], 
                                                       lambda idx=i: self._play_file(idx))
                                    files_menu.add_item(file_item)
                            
                            # Устанавливаем родительское меню
                            if self.current_menu and self.current_menu.parent:
                                files_menu.parent = self.current_menu.parent
                            
                            # Переключаемся на обновленное меню
                            self.current_menu = files_menu
                            
                            # Деактивируем режим плеера
                            self.player_mode_active = False
                            
                            # Отображаем обновленное меню
                            self.display_current_menu()
                            
                            sentry_sdk.add_breadcrumb(
                                category='delete',
                                message='Список файлов успешно обновлен после удаления',
                                level='info',
                                data={'files_count': files_count}
                            )
                        else:
                            if self.debug:
                                print(f"Папка {current_folder} пуста после удаления")
                            
                            # Если папка пуста, показываем сообщение
                            message = f"В папке {current_folder} нет записей"
                            self.display_manager.display_message(message)
                            
                            if self.tts_enabled:
                                voice = self.settings_manager.get_voice()
                                self.tts_manager.play_speech(message, voice_id=voice)
                            
                            # Возвращаемся в родительское меню
                            if self.current_menu and self.current_menu.parent:
                                self.current_menu = self.current_menu.parent
                                self.display_current_menu()
                    
                    except Exception as update_error:
                        error_msg = f"Ошибка при обновлении списка файлов: {str(update_error)}"
                        print(f"ОШИБКА: {error_msg}")
                        sentry_sdk.capture_exception(update_error)
                
            except Exception as delete_error:
                error_msg = f"Ошибка при подтверждении/отмене удаления в playback_manager: {str(delete_error)}"
                print(f"ОШИБКА: {error_msg}")
                sentry_sdk.capture_exception(delete_error)
                raise
            
            # Если отменили удаление - гарантируем, что мы остаемся в режиме воспроизведения
            if not confirmed:
                # Гарантируем, что режим аудиоплеера активен
                self.player_mode_active = True
                
                # Обновляем состояние воспроизведения
                self.playback_state["active"] = True
                self.playback_state["paused"] = False
                
                if self.debug:
                    print(f"Отмена удаления: принудительно устанавливаем режим воспроизведения")
                    print(f"Состояние после: player_mode={self.player_mode_active}, playback_active={self.playback_state['active']}")
                
                sentry_sdk.add_breadcrumb(
                    category='delete',
                    message='Отмена удаления: восстановление режима воспроизведения',
                    level='info',
                    data={
                        'player_mode_active': self.player_mode_active,
                        'playback_active': self.playback_state['active'],
                        'playback_paused': self.playback_state['paused']
                    }
                )
        
        except Exception as e:
            error_msg = f"Критическая ошибка при подтверждении/отмене удаления: {str(e)}"
            print(f"КРИТИЧЕСКАЯ ОШИБКА: {error_msg}")
            
            # Отправляем ошибку в Sentry с дополнительным контекстом
            with sentry_sdk.push_scope() as scope:
                scope.set_extra('confirmed', confirmed)
                scope.set_extra('player_mode_active', self.player_mode_active)
                scope.set_extra('playback_state', self.playback_state)
                sentry_sdk.capture_exception(e)
            
            # В случае ошибки, если это была отмена удаления,
            # все равно пытаемся восстановить режим воспроизведения
            if not confirmed:
                try:
                    self.player_mode_active = True
                    self.playback_state["active"] = True
                    self.playback_state["paused"] = False
                    sentry_sdk.capture_message(
                        "Аварийное восстановление режима воспроизведения после ошибки",
                        level='warning'
                    )
                except Exception as recovery_error:
                    sentry_sdk.capture_exception(recovery_error)
    
    def _next_file(self):
        """Переходит к следующему файлу в списке"""
        if not self.playback_state["active"]:
            return
        
        # Переходим к следующему файлу
        self.playback_manager.move_to_next_file()
    
    def _prev_file(self):
        """Переходит к предыдущему файлу в списке"""
        if not self.playback_state["active"]:
            return
        
        # Переходим к предыдущему файлу
        self.playback_manager.move_to_prev_file()
    
    def _adjust_volume(self, delta):
        """
        Изменяет громкость воспроизведения
        
        Args:
            delta (int): Изменение громкости (-/+)
        """
        if not self.playback_state["active"]:
            return
        
        # Изменяем громкость
        self.playback_manager.adjust_volume(delta)

    def _get_voice_id_by_description(self, voice_description):
        """
        Находит идентификатор голоса по его описанию
        
        Args:
            voice_description (str): Описание голоса (например, "Мужской голос 2")
            
        Returns:
            str: Идентификатор голоса или None, если не найден
        """
        try:
            # Получаем словарь голосов
            voices_dict = self.settings_manager.get_available_voices()
            
            # Ищем голос по описанию
            for voice_id, description in voices_dict.items():
                if description == voice_description:
                    if self.debug:
                        print(f"Найден идентификатор {voice_id} для описания '{voice_description}'")
                    return voice_id
                    
            if self.debug:
                print(f"Идентификатор для описания '{voice_description}' не найден")
            return None
            
        except Exception as e:
            error_msg = f"Ошибка при поиске идентификатора голоса: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return None

    def _force_kill_playback_processes(self):
        """Принудительно завершает все процессы воспроизведения"""
        try:
            print("Принудительное завершение всех процессов воспроизведения")
            
            # Останавливаем воспроизведение через playback_manager
            if hasattr(self, 'playback_manager') and self.playback_manager:
                try:
                    # Останавливаем воспроизведение стандартным методом
                    self.playback_manager.stop_playback()
                    
                    # Если есть audio_player, используем его метод stop
                    if hasattr(self.playback_manager, 'audio_player') and self.playback_manager.audio_player:
                        self.playback_manager.audio_player.stop()
                        
                        # Если у audio_player есть процесс, пытаемся завершить его
                        if hasattr(self.playback_manager.audio_player, 'process') and self.playback_manager.audio_player.process:
                            try:
                                process = self.playback_manager.audio_player.process
                                if process.poll() is None:  # Процесс еще запущен
                                    process.terminate()
                                    process.wait(timeout=0.5)  # Ждем завершения не более 0.5 сек
                                    
                                    # Если процесс все еще жив, используем kill
                                    if process.poll() is None:
                                        process.kill()
                                        process.wait(timeout=0.5)
                            except Exception as proc_e:
                                print(f"Ошибка при завершении процесса воспроизведения: {proc_e}")
                except Exception as player_e:
                    print(f"Ошибка при остановке через playback_manager: {player_e}")
                    sentry_sdk.capture_exception(player_e)
            
            # Сбрасываем состояние воспроизведения
            self.playback_state["active"] = False
            self.playback_state["paused"] = False
            
            return True
        except Exception as e:
            print(f"Критическая ошибка при принудительном завершении процессов: {e}")
            sentry_sdk.capture_exception(e)
            return False

    # Добавляем новый метод для обработки нажатий кнопок с учетом режима
    def handle_button_press(self, button_id):
        """
        Обрабатывает нажатие кнопки пульта с учетом текущего режима (меню или аудиоплеер)
        
        Args:
            button_id (str): Идентификатор нажатой кнопки
            
        Returns:
            bool: True если кнопка была обработана
        """
        try:
            # Специальная обработка для кнопки BACK в режиме аудиоплеера
            # Чтобы эта кнопка всегда имела высший приоритет
            if button_id == "KEY_BACK" and (self.player_mode_active or self.playback_state["active"]):
                print("\n*** ПРИНУДИТЕЛЬНАЯ ОСТАНОВКА ВОСПРОИЗВЕДЕНИЯ ПО KEY_BACK ***")
                print(f"Текущий режим: player_mode_active={self.player_mode_active}, playback_active={self.playback_state['active']}")
                sentry_sdk.add_breadcrumb(
                    category='playback',
                    message=f'Принудительная остановка воспроизведения по KEY_BACK (player_active={self.player_mode_active}, playback_active={self.playback_state["active"]})',
                    level='info'
                )
                
                # 1. Принудительно деактивируем режим аудиоплеера
                old_mode = self.player_mode_active
                self.player_mode_active = False
                print(f"Деактивация режима аудиоплеера (был: {old_mode})")
                
                # 2. Принудительно останавливаем все процессы воспроизведения
                stop_result = self._force_kill_playback_processes()
                if not stop_result:
                    print("Ошибка при принудительной остановке воспроизведения")
                    sentry_sdk.capture_message("Ошибка при принудительной остановке воспроизведения", level="error")
                
                # 3. Определяем меню для возврата
                return_menu = None
                
                # Приоритетно используем source_menu - меню, из которого был запущен аудиоплеер
                if hasattr(self, 'source_menu') and self.source_menu:
                    menu_name = getattr(self.source_menu, 'name', str(self.source_menu))
                    print(f"Используем сохраненное исходное меню для возврата: {menu_name}")
                    return_menu = self.source_menu
                else:
                    # Если source_menu не определено, пробуем получить его из playback_manager
                    if hasattr(self, 'playback_manager') and self.playback_manager:
                        files_menu = self.playback_manager.get_return_menu()
                        
                        # Проверяем корректность меню возврата
                        if files_menu and hasattr(files_menu, 'name'):
                            menu_name = files_menu.name
                            print(f"Используем меню из playback_manager для возврата: {menu_name}")
                            return_menu = files_menu
                
                # 4. Сбрасываем состояние воспроизведения
                self.playback_state["active"] = False
                self.playback_state["paused"] = False
                
                # 5. Выполняем возврат в меню
                if return_menu:
                    old_menu = self.current_menu
                    self.current_menu = return_menu
                    old_name = getattr(old_menu, 'name', str(old_menu)) if old_menu else "None"
                    new_name = getattr(return_menu, 'name', str(return_menu))
                    print(f"Переход в меню: {old_name} -> {new_name}")
                    
                    # 5.1 Сбрасываем source_menu
                    self.source_menu = None
                    
                    # 5.2 Отображаем меню
                    self.display_current_menu()
                    return True
                else:
                    # Если не удалось найти меню для возврата, используем стандартный метод _stop_playback
                    print("Не удалось определить меню для возврата, используем стандартный метод")
                    return self._stop_playback()
            
            # Обработка в зависимости от текущего режима
            # Получаем информацию о текущем режиме
            is_player_mode = self.player_mode_active
            is_recording = self.recording_state["active"]
            is_playing = self.playback_state["active"]
            
            if self.debug:
                print(f"Обработка нажатия кнопки: {button_id}")
                print(f"Текущий режим: {'АУДИОПЛЕЕР' if is_player_mode else 'МЕНЮ'}")
                print(f"Запись активна: {is_recording}, Воспроизведение активно: {is_playing}")
            
            # Проверяем, активен ли режим подтверждения удаления
            if self.playback_manager.is_delete_confirmation_active():
                # Обработка кнопок в режиме подтверждения удаления
                if button_id == "KEY_UP" or button_id == "KEY_DOWN":
                    # Переключение между "Да" и "Нет"
                    current_selection = self.playback_manager.confirm_delete_selected
                    self.playback_manager.confirm_delete_selected = "Да" if current_selection == "Нет" else "Нет"
                    
                    # Озвучиваем текущий выбор без лишних сообщений
                    voice_id = "ru-RU-Standard-D"
                    self.tts_manager.play_speech(self.playback_manager.confirm_delete_selected, voice_id=voice_id)
                    
                    # Обновляем экран
                    self._update_playback_info()
                    return True
                
                elif button_id == "KEY_SELECT":
                    # Подтверждаем выбор
                    confirmed = self.playback_manager.confirm_delete_selected == "Да"
                    self._confirm_delete(confirmed)
                    
                    # Если отменили удаление (выбрали "Нет"), гарантируем, что остаемся в режиме воспроизведения
                    if not confirmed:
                        self.player_mode_active = True
                        self.playback_state["active"] = True
                    
                    return True
                
                elif button_id == "KEY_BACK" or button_id == "KEY_POWER":
                    # Отменяем удаление
                    self._confirm_delete(False)
                    
                    # Гарантируем, что остаемся в режиме воспроизведения
                    self.player_mode_active = True
                    self.playback_state["active"] = True
                    
                    return True
                
                # В режиме подтверждения удаления все другие кнопки игнорируем
                return True
            
            # В режиме аудиоплеера обрабатываем кнопки по-особому
            elif self.player_mode_active:
                # Обработка кнопок в режиме аудиоплеера
                if button_id == "KEY_PAGEUP":
                    # Уменьшаем громкость
                    if self.debug:
                        print("Нажата клавиша PAGE_UP (уменьшение громкости)")
                    self.playback_manager.adjust_volume(-10)
                    return True
                    
                elif button_id == "KEY_PAGEDOWN":
                    # Увеличиваем громкость
                    if self.debug:
                        print("Нажата клавиша PAGE_DOWN (увеличение громкости)")
                    self.playback_manager.adjust_volume(10)
                    return True
                    
                elif button_id == "KEY_VOLUMEUP" or button_id == "KEY_VOLUMEDOWN" or button_id == "KEY_LEFT" or button_id == "KEY_RIGHT":
                    # Передаем управление в PlaybackManager
                    try:
                        # Получаем код клавиши из строкового идентификатора
                        key_codes = {
                            "KEY_LEFT": 105,
                            "KEY_RIGHT": 106,
                            "KEY_VOLUMEUP": 115,
                            "KEY_VOLUMEDOWN": 114
                        }
                        key_code = key_codes.get(button_id)
                        if key_code:
                            if self.debug:
                                print(f"Передача управления в PlaybackManager: {button_id}")
                            self.playback_manager.handle_key_press(key_code, True)
                            return True
                    except Exception as e:
                        error_msg = f"Ошибка при обработке кнопки {button_id}: {e}"
                        print(f"ОШИБКА: {error_msg}")
                        sentry_sdk.capture_exception(e)
                    return True
                    
                elif button_id == "KEY_SELECT":
                    # Пауза/продолжить воспроизведение
                    self._toggle_pause_playback()
                    return True
                    
                elif button_id == "KEY_BACK":
                    # Этот блок кода не должен выполняться из-за приоритетной обработки выше,
                    # но оставляем для надежности
                    if self.debug:
                        print("Вызов _stop_playback из стандартного обработчика KEY_BACK")
                    self._stop_playback()
                    return True
                
                elif button_id == "KEY_POWER":
                    # Удаление текущего файла
                    self._delete_current_file()
                    return True
                
                # Все остальные кнопки игнорируем в режиме аудиоплеера
                return True
            
            # В режиме записи тоже особая обработка
            elif is_recording:
                # Код обработки кнопок в режиме записи
                if button_id == "KEY_SELECT":
                    # Пауза/продолжить запись
                    self._toggle_pause_recording()
                    return True
                    
                elif button_id == "KEY_BACK":
                    # Остановка записи
                    self._stop_recording()
                    return True
                
                # Игнорируем все остальные кнопки в режиме записи
                return True
            
            # Обычный режим меню
            else:
                # Стандартная навигация по меню
                if button_id == "KEY_UP":
                    return self.move_up()
                    
                elif button_id == "KEY_DOWN":
                    return self.move_down()
                    
                elif button_id == "KEY_SELECT":
                    self.select_current_item()
                    return True
                    
                elif button_id == "KEY_BACK":
                    self.go_back()
                    return True
            
            # Если дошли сюда, значит кнопка не была обработана
            return False
            
        except Exception as e:
            error_msg = f"Ошибка при обработке нажатия кнопки {button_id}: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False

    def _get_files_word(self, count):
        """
        Возвращает правильную форму слова "файл" в зависимости от числа
        
        Args:
            count (int): Количество файлов
            
        Returns:
            str: Правильная форма слова
        """
        if count % 100 in (11, 12, 13, 14):
            return "файлов"
        elif count % 10 == 1:
            return "файл"
        elif count % 10 in (2, 3, 4):
            return "файла"
        else:
            return "файлов"

    def _announce_current_volume(self):
        """Озвучивает текущий уровень громкости"""
        try:
            # Проверяем, был ли уже озвучен уровень громкости
            if hasattr(self, '_volume_announced') and self._volume_announced:
                if self.debug:
                    print("Уровень громкости уже был озвучен")
                return
            
            # Получаем текущую громкость из настроек
            volume = self.settings_manager.get_system_volume()
            level = (volume - 40) // 10  # Преобразуем проценты обратно в уровень
            
            if self.debug:
                print(f"Озвучивание текущего уровня громкости: {level} (соответствует {volume}%)")
            
            # Озвучиваем текущий уровень громкости
            self.tts_manager.play_speech_blocking(f"Сейчас установлен уровень громкости {level}")
            
            # Устанавливаем флаг, что сообщение было озвучено
            self._volume_announced = True
            
        except Exception as e:
            error_msg = f"Ошибка при озвучивании текущей громкости: {e}"
            print(f"[MENU ERROR] {error_msg}")
            sentry_sdk.capture_exception(e)

    def change_system_volume(self, level=None):
        """
        Изменяет уровень громкости системы
        
        Args:
            level (int, optional): Уровень громкости от 0 до 6
        """
        try:
            # Если уровень не указан, запрашиваем его
            if level is None:
                if self.debug:
                    print("Запрос уровня громкости...")
                
                # Получаем текущую громкость из настроек
                current_volume = self.settings_manager.get_system_volume()
                current_level = (current_volume - 40) // 10  # Преобразуем проценты обратно в уровень
                
                # Показываем текущую громкость
                if self.debug:
                    print(f"Текущий уровень громкости: {current_level} (соответствует {current_volume}%)")
                    
                if self.tts_enabled:
                    voice_id = self.settings_manager.get_voice()
                    self.tts_manager.play_speech_blocking(f"Установлен уровень громкости {current_level}")
                
                # Запрашиваем новый уровень громкости
                level_str = input("Введите уровень громкости (0-6): ")
                try:
                    level = int(level_str)
                except:
                    print("Введен некорректный уровень громкости")
                    return
            
            # Проверяем, что уровень в допустимом диапазоне
            if not (0 <= level <= 6):
                print(f"[MENU ERROR] Некорректный уровень громкости: {level}")
                return
                
            # Преобразуем уровень в проценты (40% - 100%)
            volume = 40 + (level * 10)  # 0->40%, 1->50%, ..., 6->100%
            
            # Сохраняем новую громкость в настройках
            self.settings_manager.set_system_volume(volume)
            
            # Воспроизводим подтверждающее сообщение
            self.tts_manager.speak_text(f"Установлен уровень громкости {level}")
            
        except Exception as e:
            error_msg = f"Ошибка при изменении громкости: {e}"
            print(f"[MENU ERROR] {error_msg}")
            sentry_sdk.capture_exception(e)

    def preview_system_volume(self, level):
        """
        Воспроизводит тестовое сообщение с указанной громкостью
        
        Args:
            level (int): Уровень громкости от 0 до 6
        """
        try:
            # Сохраняем текущую громкость
            current_volume = self.settings_manager.get_system_volume()
            
            # Преобразуем уровень в проценты (40% - 100%)
            volume = 40 + (level * 10)  # 0->40%, 1->50%, ..., 6->100%
            
            # Временно устанавливаем новую громкость в настройках
            self.settings_manager.set_system_volume(volume)
            
            # Временно устанавливаем новую громкость в TTS менеджере
            if hasattr(self.tts_manager, 'set_volume'):
                self.tts_manager.set_volume(volume)
            
            # Воспроизводим тестовое сообщение
            self.tts_manager.speak_text(f"Уровень громкости {level}")
            
            # Восстанавливаем исходную громкость в настройках
            self.settings_manager.set_system_volume(current_volume)
            
            # Восстанавливаем исходную громкость в TTS менеджере
            if hasattr(self.tts_manager, 'set_volume'):
                self.tts_manager.set_volume(current_volume)
            
        except Exception as e:
            error_msg = f"Ошибка при предпросмотре громкости: {e}"
            print(f"[MENU ERROR] {error_msg}")
            sentry_sdk.capture_exception(e)

    def show_settings_menu(self):
        """Показывает меню настроек"""
        try:
            while True:
                self.clear_screen()
                print("\n=== Настройки ===\n")
                print("1. Выбор голоса")
                print("2. Выбор движка TTS")
                print("3. Управление громкостью")
                print("0. Назад")
                
                choice = input("\nВыберите пункт меню: ")
                
                if choice == "1":
                    self.change_voice()
                elif choice == "2":
                    self.change_tts_engine()
                elif choice == "3":
                    self.change_system_volume()
                elif choice == "0":
                    break
                else:
                    print("\nНеверный выбор. Попробуйте снова.")
                    time.sleep(1)
        except Exception as e:
            error_msg = f"Ошибка в меню настроек: {e}"
            print(f"\n[MENU ERROR] {error_msg}")
            sentry_sdk.capture_exception(e)
            sentry_sdk.capture_message(error_msg, level="error")
            time.sleep(2)
    
    def clear_screen(self):
        """Очищает экран консоли"""
        try:
            # Для Windows
            if os.name == 'nt':
                os.system('cls')
            # Для Unix/Linux/MacOS
            else:
                os.system('clear')
        except Exception as e:
            if self.debug:
                print(f"Ошибка при очистке экрана: {e}")
            # Если не удалось очистить экран, печатаем пустые строки
            print("\n" * 100)

    def process_key_event(self, key_code, key_value):
        """
        Обработка события клавиатуры
        
        Args:
            key_code (int): Код клавиши
            key_value (int): Значение (0 - отпущена, 1 - нажата, 2 - удерживается)
            
        Returns:
            bool: True если событие обработано
        """
        try:
            # Пропускаем события отпускания клавиш и повторы
            if key_value == 0:
                # Для клавиши SELECT мы обрабатываем событие отпускания
                if key_code != self.KEY_SELECT:
                    return False
            
            # ... остальной код метода ...
            
        except Exception as e:
            error_msg = f"Ошибка при обработке события клавиши: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
            
    # Удаляем дублирующий метод select() из этого места файла
    # Метод process_key_event будет использовать select_current_item() вместо него

    def announce_current_menu_item(self):
        """Озвучивает текущий выбранный пункт меню"""
        try:
            if not self.current_menu or not self.tts_enabled:
                return
                
            current_item = self.current_menu.get_current_item()
            if not current_item:
                return
                
            # Получаем текст для озвучки
            item_speech_text = current_item.get_speech_text()
            
            # Получаем текущий голос из настроек
            voice_id = self.settings_manager.get_voice()
            
            if self.debug:
                print(f"Озвучиваем текущий пункт: {item_speech_text}, голос: {voice_id}")
            
            # Проверяем, является ли элемент папкой на флешке
            is_folder = hasattr(current_item, 'is_folder') and callable(current_item.is_folder) and current_item.is_folder()
            
            # Проверяем, является ли элемент папкой диктофона (A, B, C)
            is_recorder_folder = item_speech_text in ["Папка A", "Папка B", "Папка C"]
            
            if is_folder or is_recorder_folder:
                # Если это папка, сначала озвучиваем слово "Папка"
                if hasattr(self.tts_manager, 'play_speech_blocking'):
                    self.tts_manager.play_speech_blocking("Папка", voice_id=voice_id)
                else:
                    self.tts_manager.play_speech("Папка", voice_id=voice_id)
                    time.sleep(0.5)  # Более длинная пауза для гарантированного воспроизведения
                
                time.sleep(0.1)  # Небольшая пауза между сообщениями
                
                # Затем озвучиваем имя папки
                folder_name = item_speech_text
                if is_recorder_folder:
                    # Для папок диктофона извлекаем только букву (A, B, C)
                    folder_name = item_speech_text[-1]  # Последний символ - буква папки
                
                # Озвучиваем имя папки
                if hasattr(self.tts_manager, 'play_speech_blocking'):
                    self.tts_manager.play_speech_blocking(folder_name, voice_id=voice_id)
                else:
                    self.tts_manager.play_speech(folder_name, voice_id=voice_id)
                    time.sleep(0.5)  # Пауза для гарантированного воспроизведения
            else:
                # Обычное озвучивание для не-папок
                self.tts_manager.play_speech(item_speech_text, voice_id=voice_id)
            
            # Для пунктов меню папок диктофона (A, B, C) озвучиваем количество файлов
            # Для папок на флешке (is_folder) НЕ озвучиваем количество файлов
            if not is_folder and (is_recorder_folder or item_speech_text in ["A", "B", "C"]) and hasattr(self, 'playback_manager'):
                # Определяем букву папки
                if is_recorder_folder:
                    folder_letter = item_speech_text[-1]  # Последний символ в "Папка X"
                else:
                    folder_letter = item_speech_text  # Используем непосредственно название папки
                
                # Получаем количество файлов
                files_count = self.playback_manager.count_files_in_folder(folder_letter)
                
                # Формируем текст о количестве файлов
                files_text = f"{files_count} {self._get_files_word(files_count)}"
                
                # Озвучиваем с небольшой паузой
                time.sleep(0.2)  # Пауза между сообщениями
                
                if hasattr(self.tts_manager, 'play_speech_blocking'):
                    self.tts_manager.play_speech_blocking(files_text, voice_id=voice_id)
                else:
                    self.tts_manager.play_speech(files_text, voice_id=voice_id)
                    time.sleep(1.0)  # Более длинная пауза для гарантированного воспроизведения
                
        except Exception as e:
            error_msg = f"Ошибка при озвучивании пункта меню: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)

    def pre_generate_missing_speech(self, voices=None):
        """
        Предварительно генерирует только отсутствующие звуки для меню
        
        Args:
            voices (list, optional): Список голосов для предварительной генерации
        """
        if not self.tts_enabled or not self.root_menu:
            return
        
        # Если голоса не указаны, используем все доступные голоса
        if voices is None:
            voices = list(self.settings_manager.get_available_voices().keys())
        
        # Собираем все тексты для озвучки
        speech_texts = set()
        
        def collect_speech_texts(menu):
            # Добавляем только тексты пунктов меню, не озвучиваем название самого меню
            for item in menu.items:
                speech_texts.add(item.get_speech_text())
                if isinstance(item, SubMenu):
                    collect_speech_texts(item)
        
        # Начинаем с корневого меню
        collect_speech_texts(self.root_menu)
        
        # Добавляем системные сообщения для возврата
        speech_texts.add("Возврат в")
        speech_texts.add("главное меню")
        speech_texts.add("предыдущее меню")
        speech_texts.add("Голос успешно изменен")
        
        # Добавляем сообщения для диктофона
        speech_texts.add("Запись началась")
        speech_texts.add("Запись приостановлена")
        speech_texts.add("Запись возобновлена")
        speech_texts.add("Запись остановлена")
        speech_texts.add("Запись сохранена в папку")  # Первая часть сообщения
        speech_texts.add("Запись отменена")
        speech_texts.add("Выберите папку для записи")
        speech_texts.add("Папка A")
        speech_texts.add("Папка B")
        speech_texts.add("Папка C")
        
        # Добавляем фразы для количества файлов
        for i in range(1, 101):  # От 1 до 100
            if i % 10 == 1 and i != 11:
                speech_texts.add(f"{i} файл")
            elif i % 10 in [2, 3, 4] and i not in [12, 13, 14]:
                speech_texts.add(f"{i} файла")
            else:
                speech_texts.add(f"{i} файлов")
        
        # Добавляем сообщения для массового удаления записей
        speech_texts.add("Массовое удаление записей")
        speech_texts.add("Удалить записи из всех папок")
        speech_texts.add("Вы действительно хотите удалить все записи из папки")
        speech_texts.add("Вы точно хотите удалить все записи из всех папок")
        speech_texts.add("Финальное подтверждение удаления всех записей")
        speech_texts.add("Количество записей")
        speech_texts.add("В папке нет записей")
        speech_texts.add("Нет записей во всех папках")
        speech_texts.add("Ошибка при удалении записей из папки")
        speech_texts.add("Ошибка при удалении записей из всех папок")
        speech_texts.add("запись")
        speech_texts.add("записи")
        speech_texts.add("записей")
        
        # Добавляем сообщения для информации о файлах в папках
        speech_texts.add("В папке")  # Первая часть сообщения
        speech_texts.add("нет записей")  # Третья часть сообщения
        
        # Добавляем слова для формирования сообщений о количестве файлов
        for count in range(0, 100):  # Поддержка до 99 файлов
            speech_texts.add(str(count))
        speech_texts.add("файл")
        speech_texts.add("файла")
        speech_texts.add("файлов")
        
        # Добавляем слово "Папка" для навигации по файлам на флешке
        speech_texts.add("Папка")
        
        # Добавляем сообщения для воспроизведения
        speech_texts.add("Воспроизведение")
        speech_texts.add("Пауза")
        speech_texts.add("Прослушано")
        speech_texts.add("Переключаю вперед на запись")
        speech_texts.add("Переключаю назад на запись")
        speech_texts.add("Ошибка при переключении трека")
        speech_texts.add("Запись успешно удалена")
        speech_texts.add("Ошибка при удалении записи")
        
        # Добавляем сообщения для удаления файлов
        speech_texts.add("Вы точно хотите удалить эту запись")
        speech_texts.add("Запись успешно удалена")
        speech_texts.add("Ошибка при удалении записи")
        
        # Добавляем сообщения для внешнего носителя
        speech_texts.add("Недостаточно места на флешке")
        speech_texts.add("Копирование успешно завершено")
        speech_texts.add("Возврат в режим внешнего носителя")
        speech_texts.add("Произошла ошибка при копировании файлов")
        speech_texts.add("Флешка была отключена")
        speech_texts.add("Директория с записями не найдена")
        speech_texts.add("Скопировать все аудиозаписи из всех папок")
        speech_texts.add("Скопировать все аудиозаписи из папки")
        
        # Добавляем сообщения для настроек громкости (теперь отдельно)
        speech_texts.add("Установлен уровень громкости")
        speech_texts.add("Уровень громкости")
        speech_texts.add("Сейчас установлен уровень громкости")
        
        # Добавляем числовые значения для уровней громкости
        for level in range(0, 7):
            speech_texts.add(f"{level}")
        
        # Попытка добавить имена записей диктофона из папок A, B, C
        try:
            # Путь к папке с записями
            records_dir = self.records_dir
            if os.path.exists(records_dir):
                # Папки для диктофона
                folders = ["A", "B", "C"]
                for folder in folders:
                    folder_path = os.path.join(records_dir, folder)
                    if os.path.exists(folder_path):
                        # Получаем список файлов в папке
                        files = [f for f in os.listdir(folder_path) if f.endswith(('.wav', '.mp3'))]
                        for file in files:
                            file_path = os.path.join(folder_path, file)
                            # Получаем человекочитаемое название файла
                            if hasattr(self, 'playback_manager') and self.playback_manager:
                                readable_name = self.playback_manager.get_human_readable_filename(file_path)
                                speech_texts.add(readable_name)
        except Exception as e:
            print(f"Ошибка при получении имен файлов из папок диктофона: {e}")
            sentry_sdk.capture_exception(e)
        
        # Предварительно генерируем только отсутствующие звуки для всех голосов
        self.tts_manager.pre_generate_missing_menu_items(speech_texts, voices=voices)