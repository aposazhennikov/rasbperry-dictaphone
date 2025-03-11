#!/usr/bin/env python3
import os
import time
import sentry_sdk
from pathlib import Path
from .tts_manager import TTSManager
from .display_manager import DisplayManager
from .recorder_manager import RecorderManager
from .playback_manager import PlaybackManager
from .settings_manager import SettingsManager
from .audio_recorder import AudioRecorder
from .menu_item import MenuItem, SubMenu, Menu

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
            debug=self.debug
        )
        
        # Инициализация менеджера воспроизведения
        self.playback_manager = PlaybackManager(
            tts_manager=self.tts_manager,
            base_dir=self.records_dir,
            debug=self.debug
        )
        
        # Состояние записи
        self.recording_state = {
            "active": False,
            "paused": False,
            "folder": None,
            "elapsed_time": 0,
            "formatted_time": "00:00",
            "max_duration_handled": False
        }
        
        # Состояние воспроизведения
        self.playback_state = {
            "active": False,
            "paused": False,
            "folder": None,
            "current_file": None,
            "position": "00:00",
            "duration": "00:00",
            "progress": 0
        }
        
        # Регистрируем обратный вызов для обновления информации о записи
        self.recorder_manager.set_update_callback(self._update_recording_info)
        
        # Регистрируем обратный вызов для обновления информации о воспроизведении
        self.playback_manager.set_update_callback(self._update_playback_info)
        
        # Инициализация менеджера отображения
        self.display_manager = DisplayManager(self)
    
    def set_root_menu(self, menu):
        """
        Устанавливает корневое меню
        
        Args:
            menu (SubMenu): Корневое меню
        """
        self.root_menu = menu
        self.current_menu = menu
    
    def display_current_menu(self):
        """
        Отображает текущее меню и озвучивает его название
        """
        try:
            if not self.current_menu:
                if self.debug:
                    print("Ошибка: нет текущего меню для отображения")
                return
                
            if self.debug:
                print(f"\n--- ОТОБРАЖЕНИЕ МЕНЮ: {self.current_menu.name} ---")
                print(f"Текущее меню содержит {len(self.current_menu.items)} пунктов")
                
            # Отображаем меню на экране, если есть дисплей
            if self.display_manager:
                try:
                    self.display_manager.display_menu(self.current_menu)
                except Exception as display_error:
                    print(f"Ошибка при отображении меню на дисплее: {display_error}")
                    sentry_sdk.capture_exception(display_error)
            
            # Озвучиваем название меню, если включен TTS
            if self.tts_enabled:
                try:
                    voice = self._get_voice_id_for_menu_item(self.current_menu.name)
                    if self.debug:
                        print(f"Озвучиваем название меню: {self.current_menu.name}, голос: {voice}")
                    self.tts_manager.play_speech(f"Меню {self.current_menu.name}", voice_id=voice)
                except Exception as tts_error:
                    print(f"Ошибка при озвучивании названия меню: {tts_error}")
                    sentry_sdk.capture_exception(tts_error)
            
            # Озвучиваем текущий выбранный пункт, если есть
            if self.current_menu.items and len(self.current_menu.items) > 0:
                try:
                    current_index = self.current_menu.current_selection
                    if current_index >= 0 and current_index < len(self.current_menu.items):
                        current_item = self.current_menu.items[current_index]
                        if self.tts_enabled:
                            try:
                                # Пытаемся получить специальный голос для пункта меню
                                voice_id = self._get_voice_id_for_menu_item(current_item.name)
                                if self.debug:
                                    print(f"Озвучиваем текущий пункт: {current_item.name}, голос: {voice_id}")
                                    
                                self.tts_manager.play_speech(current_item.get_speech_text(), voice_id=voice_id)
                            except Exception as item_tts_error:
                                print(f"Ошибка при озвучивании пункта меню: {item_tts_error}")
                                sentry_sdk.capture_exception(item_tts_error)
                                # Пробуем запасной вариант с обычным голосом
                                try:
                                    voice = self.tts_manager.voice
                                    self.tts_manager.play_speech(current_item.get_speech_text(), voice_id=voice)
                                except:
                                    # Если и это не сработало, пропускаем
                                    pass
                except Exception as item_error:
                    print(f"Ошибка при работе с текущим пунктом меню: {item_error}")
                    sentry_sdk.capture_exception(item_error)
        except Exception as e:
            error_msg = f"Критическая ошибка при отображении меню: {e}"
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
                
                # Озвучиваем новый пункт
                if self.tts_enabled and new_index >= 0 and new_index < len(self.current_menu.items):
                    try:
                        current_item = self.current_menu.items[new_index]
                        
                        # Пытаемся получить специальный голос для пункта меню
                        voice_id = self._get_voice_id_for_menu_item(current_item.name)
                        if self.debug:
                            print(f"Озвучиваем новый пункт: {current_item.name}, голос: {voice_id}")
                            
                        self.tts_manager.play_speech(current_item.get_speech_text(), voice_id=voice_id)
                    except Exception as tts_error:
                        print(f"Ошибка при озвучивании пункта меню: {tts_error}")
                        sentry_sdk.capture_exception(tts_error)
                        
                        # Пробуем запасной вариант с обычным голосом
                        try:
                            voice = self.tts_manager.voice
                            self.tts_manager.play_speech(current_item.get_speech_text(), voice_id=voice)
                        except:
                            # Если и это не сработало, пропускаем
                            pass
                
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
                
                # Озвучиваем новый пункт
                if self.tts_enabled and new_index >= 0 and new_index < len(self.current_menu.items):
                    try:
                        current_item = self.current_menu.items[new_index]
                        
                        # Пытаемся получить специальный голос для пункта меню
                        voice_id = self._get_voice_id_for_menu_item(current_item.name)
                        if self.debug:
                            print(f"Озвучиваем новый пункт: {current_item.name}, голос: {voice_id}")
                            
                        self.tts_manager.play_speech(current_item.get_speech_text(), voice_id=voice_id)
                    except Exception as tts_error:
                        print(f"Ошибка при озвучивании пункта меню: {tts_error}")
                        sentry_sdk.capture_exception(tts_error)
                        
                        # Пробуем запасной вариант с обычным голосом
                        try:
                            voice = self.tts_manager.voice
                            self.tts_manager.play_speech(current_item.get_speech_text(), voice_id=voice)
                        except:
                            # Если и это не сработало, пропускаем
                            pass
                
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
        
        # Если результат - подменю, переключаемся на него
        if isinstance(result, SubMenu):
            self.current_menu = result
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
    
    def go_back(self):
        """Возвращается в родительское меню"""
        # Сохраняем текущее меню перед переходом
        previous_menu = self.current_menu
        
        if self.current_menu and self.current_menu.parent:
            # Формируем сообщение заранее
            message = f"Возврат в {self.current_menu.parent.name}"
            print(f"Подготовка к возврату в родительское меню: {message}")
            
            # Сначала озвучиваем сообщение в блокирующем режиме 
            if self.tts_enabled:
                # Получаем текущий голос из настроек
                voice = self.settings_manager.get_voice()
                
                # Используем блокирующее озвучивание
                try:
                    print(f"Озвучивание сообщения перед возвратом: {message}")
                    if hasattr(self.tts_manager, 'play_speech_blocking'):
                        self.tts_manager.play_speech_blocking(message, voice_id=voice)
                    else:
                        self.tts_manager.play_speech(message, voice_id=voice)
                        # Если блокирующий метод недоступен, добавляем паузу
                        time.sleep(1.5)
                except Exception as e:
                    print(f"Ошибка при озвучивании перед переходом: {e}")
                    # Небольшая пауза для стабильности
                    time.sleep(0.5)
            
            # Теперь выполняем переход между меню
            self.current_menu = self.current_menu.parent
            print(f"Переход в родительское меню: {self.current_menu.name}")
            
            # Отображаем меню после перехода
            self.display_current_menu()
                
        elif self.current_menu != self.root_menu:
            # Если нет родительского меню, но текущее меню не корневое,
            # возвращаемся в корневое меню
            
            # Формируем сообщение
            message = "Возврат в главное меню"
            print(f"Подготовка к возврату в главное меню")
            
            # Сначала озвучиваем сообщение в блокирующем режиме
            if self.tts_enabled:
                # Получаем текущий голос из настроек
                voice = self.settings_manager.get_voice()
                
                # Используем блокирующее озвучивание
                try:
                    print(f"Озвучивание сообщения перед возвратом: {message}")
                    if hasattr(self.tts_manager, 'play_speech_blocking'):
                        self.tts_manager.play_speech_blocking(message, voice_id=voice)
                    else:
                        self.tts_manager.play_speech(message, voice_id=voice)
                        # Если блокирующий метод недоступен, добавляем паузу
                        time.sleep(1.5)
                except Exception as e:
                    print(f"Ошибка при озвучивании перед переходом: {e}")
                    # Небольшая пауза для стабильности
                    time.sleep(0.5)
            
            # Теперь выполняем переход
            self.current_menu = self.root_menu
            print(f"Переход в главное меню")
            
            # Отображаем меню после перехода
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
            # Добавляем название меню
            speech_texts.add(menu.get_speech_text())
            speech_texts.add(f"Меню {menu.name}")
            
            # Добавляем все пункты меню
            for item in menu.items:
                speech_texts.add(item.get_speech_text())
                if isinstance(item, SubMenu):
                    collect_speech_texts(item)
        
        # Начинаем с корневого меню
        collect_speech_texts(self.root_menu)
        
        # Добавляем системные сообщения
        speech_texts.add("Возврат в главное меню")
        speech_texts.add("Голос успешно изменен")
        
        # Предварительно генерируем все звуки для всех голосов
        self.tts_manager.pre_generate_menu_items(speech_texts, voices=voices)
    
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
            # Добавляем название меню
            speech_texts.add(menu.get_speech_text())
            speech_texts.add(f"Меню {menu.name}")
            
            # Добавляем все пункты меню
            for item in menu.items:
                speech_texts.add(item.get_speech_text())
                if isinstance(item, SubMenu):
                    collect_speech_texts(item)
        
        # Начинаем с корневого меню
        collect_speech_texts(self.root_menu)
        
        # Добавляем системные сообщения
        speech_texts.add("Возврат в главное меню")
        speech_texts.add("Голос успешно изменен")
        
        # Добавляем сообщения для диктофона
        speech_texts.add("Запись началась")
        speech_texts.add("Запись приостановлена")
        speech_texts.add("Запись возобновлена")
        speech_texts.add("Запись остановлена")
        speech_texts.add("Запись сохранена в папку")
        speech_texts.add("Запись отменена")
        speech_texts.add("Выберите папку для записи")
        speech_texts.add("Папка A")
        speech_texts.add("Папка B")
        speech_texts.add("Папка C")
        
        # Предварительно генерируем только отсутствующие звуки для всех голосов
        self.tts_manager.pre_generate_missing_menu_items(speech_texts, voices=voices)
    
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
        dictaphone_menu.add_item(MenuItem("Календарь", lambda: self._show_calendar_menu()))
        dictaphone_menu.add_item(MenuItem("Воспроизвести запись", lambda: self._show_play_record_menu()))
        dictaphone_menu.add_item(MenuItem("Удалить запись", lambda: self._show_delete_record_menu()))
        
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
        radio_menu = SubMenu("Режим управления радио", parent=main_menu)
        main_menu.add_item(MenuItem("Режим управления радио", lambda: radio_menu))
        
        # Добавляем радиостанции
        for station in ["Юмор", "Наука", "Политика", "Трошин", "Шаов", "Природа"]:
            station_menu = SubMenu(f"Радиостанция {station}", parent=radio_menu)
            radio_menu.add_item(station_menu)
            
            # Добавляем пункты управления для каждой радиостанции
            station_menu.add_item(MenuItem("Что сейчас звучит?", lambda s=station: f"Сейчас на {s} звучит: ..."))
            station_menu.add_item(MenuItem("Начать текущую композицию с начала", lambda s=station: f"Перезапуск композиции на {s}"))
            station_menu.add_item(MenuItem("Переключить на предыдущую композицию", lambda s=station: f"Предыдущая композиция на {s}"))
            station_menu.add_item(MenuItem("Переключить на следующую композицию", lambda s=station: f"Следующая композиция на {s}"))
        
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
        
        # Добавляем подменю для подтверждения удаления
        confirm_delete_menu = SubMenu("Подтверждение удаления", parent=settings_menu)
        settings_menu.add_item(confirm_delete_menu)
        
        # -- Варианты подтверждения
        confirm_delete_menu.add_item(MenuItem("Да", lambda: "Удаление подтверждено"))
        confirm_delete_menu.add_item(MenuItem("Нет", lambda: "Удаление отменено"))
        
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
                "formatted_time": "00:00",
                "max_duration_handled": False
            }
            
            # Начинаем запись
            if self.recorder_manager.start_recording(folder):
                print("Запись успешно начата")
                
                # Отображаем экран записи
                self.display_manager.display_recording_screen(
                    status="Recording",
                    time="00:00",
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
        # Создаем временное подменю для выбора папки
        folder_menu = SubMenu("Выберите папку для записи", parent=self.current_menu)
        
        # Добавляем пункты меню для папок
        folder_menu.add_item(MenuItem("Папка A", action=lambda: self._start_recording("A")))
        folder_menu.add_item(MenuItem("Папка B", action=lambda: self._start_recording("B")))
        folder_menu.add_item(MenuItem("Папка C", action=lambda: self._start_recording("C")))
        
        # Переключаемся на меню выбора папки
        self.current_menu = folder_menu
        self.display_current_menu()
    
    def _show_calendar_menu(self):
        # Implementation of _show_calendar_menu method
        pass

    def _show_play_record_menu(self):
        """Показывает меню воспроизведения записей"""
        # Создаем временное подменю для выбора папки
        play_menu = SubMenu("Выберите папку для воспроизведения", parent=self.current_menu)
        
        # Добавляем пункты меню для папок
        play_menu.add_item(MenuItem("Папка A", action=lambda: self._show_play_files_menu("A")))
        play_menu.add_item(MenuItem("Папка B", action=lambda: self._show_play_files_menu("B")))
        play_menu.add_item(MenuItem("Папка C", action=lambda: self._show_play_files_menu("C")))
        
        # Переключаемся на меню выбора папки
        self.current_menu = play_menu
        self.display_current_menu()
    
    def _show_delete_record_menu(self):
        # Implementation of _show_delete_record_menu method
        pass

    def _update_playback_info(self):
        """Обновляет информацию о текущем воспроизведении"""
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
        
        # Обновляем экран воспроизведения, если воспроизведение активно
        if self.playback_state["active"]:
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
    
    def _show_play_files_menu(self, folder):
        """
        Показывает меню со списком файлов для воспроизведения
        
        Args:
            folder (str): Папка для поиска файлов (A, B или C)
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
                files_menu = SubMenu(f"Записи в папке {folder}")
                
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
                
                # Отображаем меню файлов
                self.display_current_menu()
            else:
                print(f"В папке {folder} нет файлов")
                
                # Создаем сообщение
                message = f"В папке {folder} нет записей"
                
                # Отображаем и озвучиваем сообщение
                self.display_manager.display_message(message, title="Пустая папка")
                
                if self.tts_enabled:
                    # Получаем текущий голос из настроек
                    voice = self.settings_manager.get_voice()
                    self.tts_manager.play_speech(message, voice_id=voice)
                    
                # Возвращаемся в предыдущее меню
                time.sleep(2)
                self.display_current_menu()
        except Exception as e:
            error_msg = f"Ошибка при показе меню файлов: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
            # В случае ошибки возвращаемся к текущему меню
            self.display_current_menu()
    
    def _play_file(self, file_index):
        """Начинает воспроизведение выбранного файла"""
        try:
            print("\n*** ВОСПРОИЗВЕДЕНИЕ ФАЙЛА ***")
            print(f"Индекс файла: {file_index}")
            
            # Устанавливаем текущий индекс файла
            if self.playback_manager.set_current_file(file_index):
                # Получаем информацию о файле для озвучивания
                file_info = self.playback_manager.get_current_file_info()
                if file_info and self.tts_enabled:
                    # Озвучиваем простое сообщение перед воспроизведением
                    voice = self.settings_manager.get_voice()
                    message = "Воспроизведение"
                    print(f"Озвучивание сообщения перед воспроизведением: {message}")
                    
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
            else:
                print(f"ОШИБКА: Не удалось установить текущий файл с индексом {file_index}")
                
        except Exception as e:
            print(f"КРИТИЧЕСКАЯ ОШИБКА при воспроизведении файла: {e}")
            sentry_sdk.capture_exception(e)
    
    def _toggle_pause_playback(self):
        """Переключает паузу воспроизведения"""
        if not self.playback_state["active"]:
            if self.debug:
                print("Попытка поставить на паузу, но воспроизведение не активно")
            return
        
        try:
            if self.debug:
                print(f"Переключаем паузу воспроизведения. Текущее состояние: {self.playback_state['paused']}")
            
            # Переключаем паузу
            self.playback_manager.toggle_pause()
            
            # Отображаем текущий статус воспроизведения
            if self.debug:
                print(f"Статус воспроизведения: активно={self.playback_state['active']}, " +
                      f"на паузе={self.playback_state['paused']}, " +
                      f"время={self.playback_state['position']} / {self.playback_state['duration']}")
                
        except Exception as e:
            if self.debug:
                print(f"КРИТИЧЕСКАЯ ОШИБКА при переключении паузы воспроизведения: {e}")
    
    def _stop_playback(self):
        """Останавливает воспроизведение и возвращается в меню"""
        try:
            if not self.playback_state["active"]:
                if self.debug:
                    print("Попытка остановить воспроизведение, но оно не активно")
                return
                
            print("\n*** ОСТАНОВКА ВОСПРОИЗВЕДЕНИЯ ***")
            
            # Получаем информацию о меню возврата до остановки воспроизведения
            return_menu = self.playback_manager.get_return_menu()
            
            # Запоминаем имя меню для озвучивания
            menu_name = return_menu.name if return_menu else "меню выбора папки"
            
            if self.debug:
                print(f"Меню для возврата: {menu_name}")
            
            # Озвучиваем сообщение о возврате блокирующим методом
            if self.tts_enabled:
                try:
                    # Получаем текущий голос из настроек
                    voice = self.settings_manager.get_voice()
                    
                    # Формируем сообщение о возврате
                    message = f"Возврат в {menu_name}"
                    
                    if self.debug:
                        print(f"Озвучивание перед возвратом: {message}, голос: {voice}")
                    
                    # Используем блокирующее озвучивание
                    self.tts_manager.play_speech_blocking(message, voice_id=voice)
                except Exception as e:
                    print(f"Ошибка при озвучивании перед переходом: {e}")
                    sentry_sdk.capture_exception(e)
            
            # Останавливаем воспроизведение с задержкой
            print("Останавливаем воспроизведение...")
            self.playback_manager.stop_playback()
            
            # Даем время для полной остановки воспроизведения
            time.sleep(0.5)
            
            # Выполняем переход в меню
            if return_menu:
                self.current_menu = return_menu
                if self.debug:
                    print(f"Переход в возвратное меню: {return_menu.name}")
            else:
                # Если нет родительского меню, возвращаемся в корневое
                self.current_menu = self.root_menu
                if self.debug:
                    print("Переход в корневое меню")
            
            # Отображаем меню
            self.display_current_menu()
                
        except Exception as e:
            print(f"КРИТИЧЕСКАЯ ОШИБКА при остановке воспроизведения: {e}")
            sentry_sdk.capture_exception(e)
            
            # В случае ошибки все равно пытаемся отобразить текущее меню
            self.display_current_menu()
    
    def _delete_current_file(self):
        """Удаляет текущий воспроизводимый файл"""
        if not self.playback_state["active"]:
            if self.debug:
                print("Попытка удалить файл, но воспроизведение не активно")
            return
        
        # Инициируем процесс удаления
        self.playback_manager.delete_current_file()
    
    def _confirm_delete(self, confirmed):
        """
        Подтверждает или отменяет удаление файла
        
        Args:
            confirmed (bool): True для подтверждения, False для отмены
        """
        if not self.playback_manager.is_delete_confirmation_active():
            return
        
        # Подтверждаем или отменяем удаление
        self.playback_manager.confirm_delete(confirmed)
    
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