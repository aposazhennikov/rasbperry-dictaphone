#!/usr/bin/env python3
from .menu_item import MenuItem, SubMenu
from .display_manager import DisplayManager
from .tts_manager import TTSManager

class MenuManager:
    """Класс для управления иерархическим меню"""
    
    def __init__(self, tts_enabled=True, cache_dir="/home/aleks/cache_tts", debug=False, use_wav=True):
        """
        Инициализация менеджера меню
        
        Args:
            tts_enabled (bool): Включена ли озвучка
            cache_dir (str): Директория для кэширования звуковых файлов
            debug (bool): Режим отладки
            use_wav (bool): Использовать WAV вместо MP3 для более быстрого воспроизведения
        """
        self.root_menu = None
        self.current_menu = None
        self.tts_enabled = tts_enabled
        self.debug = debug
        self.use_wav = use_wav
        
        # Инициализация менеджеров
        self.display_manager = DisplayManager(self)
        
        # Инициализация менеджера TTS
        if self.tts_enabled:
            self.tts_manager = TTSManager(cache_dir=cache_dir, debug=debug, use_wav=use_wav)
    
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
            self.tts_manager.play_speech(f"Меню {self.current_menu.name}")
    
    def move_up(self):
        """Перемещение вверх по текущему меню"""
        if self.current_menu:
            self.current_menu.move_up()
            self.display_current_menu()
            
            # Озвучиваем текущий выбранный пункт
            if self.tts_enabled:
                current_item = self.current_menu.get_current_item()
                if current_item:
                    self.tts_manager.play_speech(current_item.get_speech_text())
    
    def move_down(self):
        """Перемещение вниз по текущему меню"""
        if self.current_menu:
            self.current_menu.move_down()
            self.display_current_menu()
            
            # Озвучиваем текущий выбранный пункт
            if self.tts_enabled:
                current_item = self.current_menu.get_current_item()
                if current_item:
                    self.tts_manager.play_speech(current_item.get_speech_text())
    
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
                self.tts_manager.play_speech(str(result))
                
            self.display_current_menu()
    
    def go_back(self):
        """Возвращается в родительское меню"""
        if self.current_menu and self.current_menu.parent:
            self.current_menu = self.current_menu.parent
            self.display_current_menu()
            
            # Озвучиваем возврат
            if self.tts_enabled:
                self.tts_manager.play_speech(f"Возврат в {self.current_menu.name}")
                
        elif self.current_menu != self.root_menu:
            # Если нет родительского меню, но текущее меню не корневое,
            # возвращаемся в корневое меню
            self.current_menu = self.root_menu
            self.display_current_menu()
            
            # Озвучиваем возврат в главное меню
            if self.tts_enabled:
                self.tts_manager.play_speech("Возврат в главное меню")
    
    def pre_generate_all_speech(self):
        """Предварительно генерирует все звуки для меню"""
        if not self.tts_enabled or not self.root_menu:
            return
        
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
        
        # Предварительно генерируем все звуки
        self.tts_manager.pre_generate_menu_items(speech_texts)
        
    def create_menu_structure(self):
        """Создает структуру меню согласно заданной схеме"""
        # Создаем главное меню
        main_menu = SubMenu("Главное меню")
        
        # Добавляем подменю для режима диктофона
        dictaphone_menu = SubMenu("Режим диктофона")
        main_menu.add_item(dictaphone_menu)
        
        # Наполняем подменю режима диктофона
        # - Создать новую запись
        create_record_menu = SubMenu("Создать новую запись")
        dictaphone_menu.add_item(create_record_menu)
        
        # -- Папки для записи
        create_record_menu.add_item(MenuItem("Папка A", lambda: "Запись в папку A"))
        create_record_menu.add_item(MenuItem("Папка B", lambda: "Запись в папку B"))
        create_record_menu.add_item(MenuItem("Папка C", lambda: "Запись в папку C"))
        
        # - Календарь
        calendar_menu = SubMenu("Календарь")
        dictaphone_menu.add_item(calendar_menu)
        
        # -- Годы (пример)
        calendar_menu.add_item(MenuItem("2023", lambda: "Выбран 2023 год"))
        calendar_menu.add_item(MenuItem("2024", lambda: "Выбран 2024 год"))
        calendar_menu.add_item(MenuItem("2025", lambda: "Выбран 2025 год"))
        
        # - Воспроизвести запись
        play_record_menu = SubMenu("Воспроизвести уже имеющуюся запись")
        dictaphone_menu.add_item(play_record_menu)
        
        # -- Папки с записями
        play_record_menu.add_item(MenuItem("Папка A", lambda: "Воспроизведение из папки A"))
        play_record_menu.add_item(MenuItem("Папка B", lambda: "Воспроизведение из папки B"))
        play_record_menu.add_item(MenuItem("Папка C", lambda: "Воспроизведение из папки C"))
        
        # - Удалить запись
        delete_record_menu = SubMenu("Удалить запись")
        dictaphone_menu.add_item(delete_record_menu)
        
        # -- Папки с записями для удаления
        delete_record_menu.add_item(MenuItem("Папка A", lambda: "Удаление из папки A"))
        delete_record_menu.add_item(MenuItem("Папка B", lambda: "Удаление из папки B"))
        delete_record_menu.add_item(MenuItem("Папка C", lambda: "Удаление из папки C"))
        
        # Добавляем подменю для режима звонка
        call_menu = SubMenu("Режим звонка")
        main_menu.add_item(call_menu)
        
        # - Принять звонок
        accept_call_menu = SubMenu("Принять звонок")
        call_menu.add_item(accept_call_menu)
        
        # -- Подтверждение входящего вызова
        incoming_call_menu = SubMenu("Входящий вызов")
        accept_call_menu.add_item(incoming_call_menu)
        
        # --- Подтверждение
        incoming_call_menu.add_item(MenuItem("Да", lambda: "Звонок принят"))
        incoming_call_menu.add_item(MenuItem("Нет", lambda: "Звонок отклонен"))
        
        # - Совершить звонок
        make_call_menu = SubMenu("Совершить звонок")
        call_menu.add_item(make_call_menu)
        
        # -- Избранные контакты
        favorites_menu = SubMenu("Избранные контакты")
        make_call_menu.add_item(favorites_menu)
        
        # --- Контакты
        favorites_menu.add_item(MenuItem("NAME1", lambda: "Звонок NAME1"))
        favorites_menu.add_item(MenuItem("NAME2", lambda: "Звонок NAME2"))
        favorites_menu.add_item(MenuItem("Удалить избранный контакт", lambda: "Удаление контакта"))
        favorites_menu.add_item(MenuItem("Добавить избранный контакт", lambda: "Добавление контакта"))
        
        # -- Последние набранные
        recent_menu = SubMenu("Последние набранные")
        make_call_menu.add_item(recent_menu)
        
        # --- Контакты
        recent_menu.add_item(MenuItem("NAME", lambda: "Звонок NAME (последний)"))
        
        # Добавляем подменю для режима радио
        radio_menu = SubMenu("Режим управления радио")
        main_menu.add_item(radio_menu)
        
        # Добавляем радиостанции
        for station in ["Юмор", "Наука", "Политика", "Трошин", "Шаов", "Природа"]:
            station_menu = SubMenu(f"Радиостанция {station}")
            radio_menu.add_item(station_menu)
            
            # Добавляем пункты управления для каждой радиостанции
            station_menu.add_item(MenuItem("Что сейчас звучит?", lambda s=station: f"Сейчас на {s} звучит: ..."))
            station_menu.add_item(MenuItem("Начать текущую композицию с начала", lambda s=station: f"Перезапуск композиции на {s}"))
            station_menu.add_item(MenuItem("Переключить на предыдущую композицию", lambda s=station: f"Предыдущая композиция на {s}"))
            station_menu.add_item(MenuItem("Переключить на следующую композицию", lambda s=station: f"Следующая композиция на {s}"))
        
        # Добавляем подменю для подтверждения удаления
        confirm_delete_menu = SubMenu("Подтверждение удаления")
        main_menu.add_item(confirm_delete_menu)
        
        # Добавляем пункты подтверждения
        confirm_delete_menu.add_item(MenuItem("Да", lambda: "Подтверждено удаление"))
        confirm_delete_menu.add_item(MenuItem("Нет", lambda: "Отменено удаление"))
        
        # Устанавливаем главное меню как корневое
        self.set_root_menu(main_menu)
        
        # Предварительно генерируем все звуки для меню
        if self.tts_enabled:
            self.pre_generate_all_speech()
        
        return main_menu

    def get_debug_info(self):
        """
        Возвращает отладочную информацию
        
        Returns:
            dict: Информация о состоянии меню и озвучки
        """
        info = {
            "current_menu": self.current_menu.name if self.current_menu else "None",
            "tts_enabled": self.tts_enabled,
            "tts_stats": None
        }
        
        if self.tts_enabled:
            info["tts_stats"] = self.tts_manager.get_debug_info()
            
        return info