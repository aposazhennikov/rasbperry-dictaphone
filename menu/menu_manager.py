#!/usr/bin/env python3
from .menu_item import MenuItem, SubMenu
from .display_manager import DisplayManager
from .tts_manager import TTSManager
from .settings_manager import SettingsManager
from .recorder_manager import RecorderManager
import time
import subprocess

class MenuManager:
    """Класс для управления иерархическим меню"""
    
    def __init__(self, tts_enabled=True, cache_dir="/home/aleks/cache_tts", debug=False, use_wav=True, settings_manager=None, records_dir="/home/aleks/records"):
        """
        Инициализация менеджера меню
        
        Args:
            tts_enabled (bool): Включена ли озвучка
            cache_dir (str): Директория для кэширования звуковых файлов
            debug (bool): Режим отладки
            use_wav (bool): Использовать WAV вместо MP3 для более быстрого воспроизведения
            settings_manager (SettingsManager): Менеджер настроек (если None, будет создан новый)
            records_dir (str): Директория для сохранения аудиозаписей
        """
        self.root_menu = None
        self.current_menu = None
        self.tts_enabled = tts_enabled
        self.debug = debug
        self.use_wav = use_wav
        self.cache_dir = cache_dir
        self.records_dir = records_dir
        
        # Инициализация менеджера настроек
        if settings_manager:
            self.settings_manager = settings_manager
        else:
            self.settings_manager = SettingsManager(settings_dir=cache_dir)
        
        # Инициализация менеджеров
        self.display_manager = DisplayManager(self)
        
        # Инициализация менеджера TTS с голосом из настроек
        if self.tts_enabled:
            voice = self.settings_manager.get_voice()
            self.tts_manager = TTSManager(
                cache_dir=cache_dir, 
                debug=debug, 
                use_wav=use_wav,
                voice=voice,
                settings_manager=self.settings_manager
            )
            if self.debug:
                print(f"TTS менеджер инициализирован с голосом {voice}")
                print(f"TTS движок: {self.settings_manager.get_tts_engine()}")
        else:
            self.tts_manager = None
        
        # Инициализация менеджера записи
        self.recorder_manager = RecorderManager(
            tts_manager=self.tts_manager,
            base_dir=self.records_dir,
            debug=self.debug
        )
        
        # Состояние записи
        self.recording_state = {
            "active": False,
            "paused": False,
            "folder": None,
            "time": 0,
            "time_formatted": "00:00"
        }
        
        # Регистрируем обратный вызов для обновления информации о записи
        self.recorder_manager.set_update_callback(self._update_recording_info)
    
    def set_root_menu(self, menu):
        """
        Устанавливает корневое меню
        
        Args:
            menu (SubMenu): Корневое меню
        """
        self.root_menu = menu
        self.current_menu = menu
    
    def display_current_menu(self):
        """Отображает текущее меню"""
        self.display_manager.display_menu()
        
        # Озвучиваем название текущего меню
        if self.tts_enabled and self.current_menu:
            # Получаем текущий голос из настроек
            voice = self.settings_manager.get_voice()
            
            # Название меню всегда озвучиваем текущим голосом
            self.tts_manager.play_speech(f"Меню {self.current_menu.name}", voice=voice)
    
    def move_up(self):
        """Перемещение вверх по текущему меню"""
        if self.current_menu:
            self.current_menu.move_up()
            self.display_current_menu()
            
            # Озвучиваем текущий выбранный пункт
            if self.tts_enabled:
                current_item = self.current_menu.get_current_item()
                if current_item:
                    # Особая обработка для меню выбора голоса
                    if self.current_menu.name == "Выбор голоса":
                        # Находим голос, соответствующий текущему пункту меню
                        voice_id = self._get_voice_id_for_menu_item(current_item.name)
                        if voice_id:
                            # Озвучиваем этот пункт с соответствующим голосом
                            self.tts_manager.play_speech(current_item.get_speech_text(), voice=voice_id)
                        else:
                            # Если не нашли соответствующий голос, используем текущий
                            voice = self.settings_manager.get_voice()
                            self.tts_manager.play_speech(current_item.get_speech_text(), voice=voice)
                    else:
                        # Для всех остальных меню используем текущий голос
                        voice = self.settings_manager.get_voice()
                        self.tts_manager.play_speech(current_item.get_speech_text(), voice=voice)
    
    def move_down(self):
        """Перемещение вниз по текущему меню"""
        if self.current_menu:
            self.current_menu.move_down()
            self.display_current_menu()
            
            # Озвучиваем текущий выбранный пункт
            if self.tts_enabled:
                current_item = self.current_menu.get_current_item()
                if current_item:
                    # Особая обработка для меню выбора голоса
                    if self.current_menu.name == "Выбор голоса":
                        # Находим голос, соответствующий текущему пункту меню
                        voice_id = self._get_voice_id_for_menu_item(current_item.name)
                        if voice_id:
                            # Озвучиваем этот пункт с соответствующим голосом
                            self.tts_manager.play_speech(current_item.get_speech_text(), voice=voice_id)
                        else:
                            # Если не нашли соответствующий голос, используем текущий
                            voice = self.settings_manager.get_voice()
                            self.tts_manager.play_speech(current_item.get_speech_text(), voice=voice)
                    else:
                        # Для всех остальных меню используем текущий голос
                        voice = self.settings_manager.get_voice()
                        self.tts_manager.play_speech(current_item.get_speech_text(), voice=voice)
    
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
                self.tts_manager.play_speech(str(result), voice=voice)
                
            self.display_current_menu()
    
    def go_back(self):
        """Возвращается в родительское меню"""
        if self.current_menu and self.current_menu.parent:
            self.current_menu = self.current_menu.parent
            self.display_current_menu()
            
            # Озвучиваем возврат
            if self.tts_enabled:
                # Получаем текущий голос из настроек
                voice = self.settings_manager.get_voice()
                self.tts_manager.play_speech(f"Возврат в {self.current_menu.name}", voice=voice)
                
        elif self.current_menu != self.root_menu:
            # Если нет родительского меню, но текущее меню не корневое,
            # возвращаемся в корневое меню
            self.current_menu = self.root_menu
            self.display_current_menu()
            
            # Озвучиваем возврат в главное меню
            if self.tts_enabled:
                # Получаем текущий голос из настроек
                voice = self.settings_manager.get_voice()
                self.tts_manager.play_speech("Возврат в главное меню", voice=voice)
    
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
        # Проверяем, доступен ли TTS
        if not self.tts_enabled:
            return "Озвучка отключена"
            
        # Отладочная информация
        if self.debug:
            print(f"\nИзменение голоса на: {voice_id}")
            print(f"Предыдущий голос: {self.settings_manager.get_voice()}")
            
        # Проверяем, не выбран ли уже этот голос
        if self.settings_manager.get_voice() == voice_id:
            if self.debug:
                print(f"Голос {voice_id} уже выбран")
            message = "Этот голос уже выбран"
            self.tts_manager.play_speech(message, voice=voice_id)
            return message
            
        # Изменяем голос в настройках
        if self.settings_manager.set_voice(voice_id):
            # Изменяем голос в TTS менеджере
            self.tts_manager.set_voice(voice_id)
            
            # Пробуем тестовую озвучку с новым голосом
            message = "Голос успешно изменен"
            
            # Явно передаем идентификатор голоса для корректной озвучки
            self.tts_manager.play_speech(message, voice=voice_id)
            
            # Отладочная информация
            if self.debug:
                print(f"Текущий голос в настройках: {self.settings_manager.get_voice()}")
                print(f"Текущий голос в TTS менеджере: {self.tts_manager.voice}")
            
            return message
        else:
            return "Ошибка при изменении голоса"
        
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
                
            voice_menu.add_item(MenuItem(
                voice_desc, 
                lambda voice=voice_id: self.change_voice(voice)
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
            "current_index": getattr(self.current_menu, 'current_index', 0)
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
        """Обновляет информацию о текущей записи"""
        if self.recorder_manager.is_recording():
            self.recording_state["active"] = True
            self.recording_state["paused"] = self.recorder_manager.is_paused()
            self.recording_state["folder"] = self.recorder_manager.get_current_folder()
            self.recording_state["time"] = self.recorder_manager.get_current_time()
            self.recording_state["time_formatted"] = self.recorder_manager.get_formatted_time()
            
            # Всегда обновляем экран записи, если запись активна
            self.display_manager.display_recording_screen(
                status="Paused" if self.recording_state["paused"] else "Recording",
                time=self.recording_state["time_formatted"],
                folder=self.recording_state["folder"]
            )
            
            if self.debug:
                print(f"Обновление информации о записи: активна={self.recording_state['active']}, " +
                      f"пауза={self.recording_state['paused']}, " +
                      f"время={self.recording_state['time_formatted']}, " +
                      f"папка={self.recording_state['folder']}")
        else:
            # Сбрасываем состояние записи, если запись неактивна
            old_state = self.recording_state.get("active", False)
            self.recording_state["active"] = False
            self.recording_state["paused"] = False
            
            # Если запись была активна, но теперь неактивна, выводим информацию
            if old_state and self.debug:
                print("Запись остановлена, сбрасываем состояние")
    
    def _start_recording(self, folder):
        """
        Начинает запись в указанную папку
        
        Args:
            folder (str): Папка для записи ('A', 'B' или 'C')
        """
        # Показываем экран записи сразу, чтобы пользователь понимал что происходит
        self.display_manager.display_recording_screen(
            status="Initializing...",
            time="00:00",
            folder=folder
        )
        
        # Начинаем запись
        print(f"Начинаем запись в папку {folder}...")
        success = self.recorder_manager.start_recording(folder)
        
        if success:
            # Обновляем состояние записи
            self.recording_state["active"] = True
            self.recording_state["paused"] = False
            self.recording_state["folder"] = folder
            
            # Обновляем экран записи
            self._update_recording_info()
        else:
            print("Не удалось начать запись!")
            # Возвращаемся в предыдущее меню в случае неудачи
            if self.current_menu.parent:
                self.current_menu = self.current_menu.parent
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
                else:
                    print("ОШИБКА: Не удалось возобновить запись!")
            else:
                # Приостанавливаем запись
                print("Приостанавливаем запись...")
                result = self.recorder_manager.pause_recording()
                if result:
                    print("Запись успешно приостановлена")
                else:
                    print("ОШИБКА: Не удалось приостановить запись!")
            
            # Отображаем текущий статус записи (для информации)
            print(f"Статус записи: активна={self.recording_state['active']}, "
                f"на паузе={self.recording_state['paused']}, "
                f"папка={self.recording_state['folder']}, "
                f"время={self.recording_state['time']}")
                
        except Exception as e:
            print(f"КРИТИЧЕСКАЯ ОШИБКА при переключении паузы: {e}")
    
    def _stop_recording(self):
        """Останавливает запись и сохраняет файл"""
        if not self.recording_state["active"]:
            print("Попытка остановить запись, но запись не активна")
            return
        
        print("\n*** ОСТАНОВКА ЗАПИСИ ***")
        folder = self.recording_state["folder"]
        
        try:
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
                # Озвучивание ошибки уже происходит в recorder_manager.stop_recording()
            else:
                print(f"Запись сохранена в файл: {file_path}")
                # Озвучивание успеха уже происходит в recorder_manager.stop_recording()
            
            # Важная задержка перед переключением в меню!
            # Даем время для полного воспроизведения всех голосовых сообщений
            print("Небольшая задержка перед возвратом в меню...")
            time.sleep(0.5)
            
            # Переходим к родительскому меню (независимо от результата)
            if self.current_menu and self.current_menu.parent:
                print("Возвращаемся в родительское меню...")
                self.current_menu = self.current_menu.parent
                self.display_current_menu()
            else:
                print("Нет родительского меню, остаемся на текущем экране")
                self.display_current_menu()
                
        except Exception as e:
            print(f"КРИТИЧЕСКАЯ ОШИБКА в _stop_recording: {e}")
            
            # Даже в случае ошибки даем небольшое время для воспроизведения
            time.sleep(0.5)
            
            # В случае ошибки тоже возвращаемся в родительское меню
            if self.current_menu and self.current_menu.parent:
                print("Возвращаемся в родительское меню после ошибки...")
                self.current_menu = self.current_menu.parent
                self.display_current_menu()
    
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
        # Implementation of _show_play_record_menu method
        pass

    def _show_delete_record_menu(self):
        # Implementation of _show_delete_record_menu method
        pass