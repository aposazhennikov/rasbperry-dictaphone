#!/usr/bin/env python3
import sentry_sdk
import subprocess
import threading
import time
from .menu_item import MenuItem, SubMenu
from .event_bus import EventBus, EVENT_USB_MIC_DISCONNECTED, EVENT_RECORDING_SAVED

class MicrophoneSelector:
    """Класс для выбора микрофона в настройках"""
    
    def __init__(self, menu_manager, settings_manager, debug=False):
        """
        Инициализация селектора микрофона
        
        Args:
            menu_manager: Ссылка на менеджер меню для обновления интерфейса
            settings_manager: Ссылка на менеджер настроек для сохранения выбора
            debug (bool): Режим отладки
        """
        try:
            self.menu_manager = menu_manager
            self.settings_manager = settings_manager
            self.debug = debug
            
            # Создаем подменю для выбора микрофона
            self.microphone_menu = SubMenu("Выбор микрофона")
            
            # Запускаем мониторинг микрофонов
            self.start_monitoring()
            
            # Добавляем пункты меню
            self._setup_menu_items()
            
            if self.debug:
                print("MicrophoneSelector инициализирован")
        except Exception as e:
            error_msg = f"Ошибка при инициализации MicrophoneSelector: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def start_monitoring(self):
        """Запускает мониторинг микрофонов"""
        try:
            # Создаем и запускаем поток для мониторинга микрофонов
            self.stop_monitoring_flag = False
            self.monitor_thread = threading.Thread(target=self._monitor_loop)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            
            if self.debug:
                print("Мониторинг микрофонов запущен")
        except Exception as e:
            error_msg = f"Ошибка при запуске мониторинга микрофонов: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def stop_monitoring(self):
        """Останавливает мониторинг микрофонов"""
        try:
            self.stop_monitoring_flag = True
            if hasattr(self, 'monitor_thread') and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=1.0)
                
            if self.debug:
                print("Мониторинг микрофонов остановлен")
        except Exception as e:
            error_msg = f"Ошибка при остановке мониторинга микрофонов: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def _monitor_loop(self):
        """Цикл мониторинга микрофонов"""
        try:
            last_usb_state = self.is_usb_microphone_connected()
            
            # Получаем экземпляр EventBus
            event_bus = EventBus.get_instance()
            if self.debug:
                event_bus.set_debug(self.debug)
            
            # Подписываемся на события завершения записи
            event_bus.subscribe(EVENT_RECORDING_SAVED, self._handle_recording_saved)
            
            # Флаг для отслеживания, что мы ожидаем сохранения записи
            self.waiting_for_recording_save = False
            
            while not self.stop_monitoring_flag:
                # Проверяем текущее состояние USB микрофона
                current_usb_state = self.is_usb_microphone_connected()
                
                # Если состояние изменилось
                if current_usb_state != last_usb_state:
                    # Логируем изменение состояния в Sentry
                    sentry_sdk.add_breadcrumb(
                        category="microphone_monitoring",
                        message=f"Изменение состояния USB микрофона: {last_usb_state} -> {current_usb_state}",
                        level="info"
                    )
                    
                    if self.debug:
                        print(f"Изменение состояния USB микрофона: {last_usb_state} -> {current_usb_state}")
                    
                    # Если USB микрофон был отключен, и он был выбран
                    if not current_usb_state and self.get_microphone() == "usb":
                        # Логируем событие отключения микрофона во время использования
                        sentry_sdk.add_breadcrumb(
                            category="microphone_monitoring",
                            message="USB микрофон был отключен во время использования",
                            level="warning"
                        )
                        
                        if self.debug:
                            print("USB микрофон был отключен, и он был выбран")
                        
                        # Публикуем событие отключения USB микрофона
                        # Другие компоненты (RecorderManager) могут подписаться на это событие
                        try:
                            event_bus.publish(
                                EVENT_USB_MIC_DISCONNECTED,
                                microphone_selector=self
                            )
                            
                            # Логируем успешную публикацию события
                            sentry_sdk.add_breadcrumb(
                                category="microphone_monitoring",
                                message="Успешно опубликовано событие EVENT_USB_MIC_DISCONNECTED",
                                level="info"
                            )
                        except Exception as event_publish_error:
                            error_msg = f"Ошибка при публикации события отключения USB микрофона: {event_publish_error}"
                            print(error_msg)
                            sentry_sdk.capture_exception(event_publish_error)
                        
                        # Устанавливаем флаг ожидания сохранения записи
                        # Теперь мы не будем сразу переключать микрофон и возвращаться в главное меню
                        # Это произойдет только после получения события о сохранении записи
                        self.waiting_for_recording_save = True
                        
                        # Если запись не активна, сразу переключаемся на встроенный микрофон
                        # RecorderManager должен сам определить, была ли активна запись
                        if not self.waiting_for_recording_save:
                            try:
                                self._switch_to_built_in_microphone()
                            except Exception as switch_error:
                                error_msg = f"Ошибка при переключении на встроенный микрофон: {switch_error}"
                                print(error_msg)
                                sentry_sdk.capture_exception(switch_error)
                    
                    # Обновляем отображение меню
                    try:
                        self._setup_menu_items()
                    except Exception as menu_update_error:
                        error_msg = f"Ошибка при обновлении меню после изменения состояния микрофона: {menu_update_error}"
                        print(error_msg)
                        sentry_sdk.capture_exception(menu_update_error)
                    
                    # Обновляем последнее состояние
                    last_usb_state = current_usb_state
                
                # Пауза перед следующей проверкой
                time.sleep(1.0)
                
            # Отписываемся от событий при завершении цикла
            event_bus.unsubscribe(EVENT_RECORDING_SAVED, self._handle_recording_saved)
                
        except Exception as e:
            error_msg = f"Ошибка в цикле мониторинга микрофонов: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def _handle_recording_saved(self, **kwargs):
        """
        Обработчик события сохранения записи
        
        Args:
            **kwargs: Параметры события
        """
        try:
            # Логируем получение события
            sentry_sdk.add_breadcrumb(
                category="microphone_monitoring",
                message=f"Получено событие о завершении записи с параметрами: {kwargs}",
                level="info"
            )
            
            if self.debug:
                print("MicrophoneSelector: Получено событие о завершении записи")
            
            # Сбрасываем флаг ожидания сохранения
            self.waiting_for_recording_save = False
            
            # Переключаемся на встроенный микрофон и возвращаемся в главное меню
            self._switch_to_built_in_microphone()
            
            # Логируем успешное завершение обработки события
            sentry_sdk.add_breadcrumb(
                category="microphone_monitoring",
                message="Успешно обработано событие завершения записи",
                level="info"
            )
            
        except Exception as e:
            error_msg = f"Ошибка при обработке события сохранения записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def _switch_to_built_in_microphone(self):
        """
        Переключение на встроенный микрофон и возврат в главное меню
        """
        try:
            # Логируем начало процесса переключения
            sentry_sdk.add_breadcrumb(
                category="microphone_monitoring",
                message="Начало переключения на встроенный микрофон после отключения USB микрофона",
                level="info"
            )
            
            if self.debug:
                print("Переключение на встроенный микрофон после отключения USB микрофона")
            
            # Принудительно переключаемся на встроенный микрофон
            self.change_microphone("built_in", force=True)
            
            # Логируем успешное переключение
            sentry_sdk.add_breadcrumb(
                category="microphone_monitoring",
                message="Успешное переключение на встроенный микрофон",
                level="info"
            )
            
        except Exception as e:
            error_msg = f"Ошибка при переключении на встроенный микрофон: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def is_usb_microphone_connected(self):
        """
        Проверяет, подключен ли USB микрофон
        
        Returns:
            bool: True если USB микрофон подключен, иначе False
        """
        try:
            # Запускаем команду arecord -l для получения списка устройств
            result = subprocess.run(["arecord", "-l"], capture_output=True, text=True)
            
            # Проверяем результат выполнения команды
            if result.returncode != 0:
                # Логируем ошибку выполнения команды
                sentry_sdk.add_breadcrumb(
                    category="microphone_monitoring",
                    message=f"Ошибка при выполнении arecord -l: {result.stderr}",
                    level="error"
                )
                
                if self.debug:
                    print(f"Ошибка при выполнении arecord -l: {result.stderr}")
                return False
            
            # Ищем в выводе USB микрофон
            is_connected = "(LCS) USB Audio Device" in result.stdout
            
            # Не логируем каждый успешный вызов, чтобы не засорять логи
            return is_connected
        except Exception as e:
            error_msg = f"Ошибка при проверке подключения USB микрофона: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def _setup_menu_items(self):
        """Настраивает пункты меню для выбора микрофона"""
        try:
            # Очищаем текущие пункты меню
            self.microphone_menu.items = []
            
            # Сбрасываем индекс текущего выбора, чтобы избежать ошибки "list index out of range"
            self.microphone_menu.current_selection = 0
            
            # Получаем текущий выбранный микрофон
            current_microphone = self.get_microphone()
            
            # Добавляем пункты меню для каждого типа микрофона
            for mic_id, mic_desc in self.get_available_microphones().items():
                # Создаем обертку для избежания проблем с lambda в цикле
                def create_microphone_action(mic_id=mic_id):
                    return lambda: self.change_microphone(mic_id)
                
                # Добавляем индикатор текущего выбора
                display_name = f"{mic_desc}"
                if mic_id == current_microphone:
                    display_name = f"{mic_desc} ✓"
                
                self.microphone_menu.add_item(MenuItem(
                    display_name,
                    create_microphone_action()
                ))
            
            if self.debug:
                print(f"Настроено меню выбора микрофона: {len(self.microphone_menu.items)} пунктов")
        except Exception as e:
            error_msg = f"Ошибка при настройке пунктов меню микрофона: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def get_menu(self):
        """
        Возвращает подменю для выбора микрофона
        
        Returns:
            SubMenu: Подменю выбора микрофона
        """
        return self.microphone_menu
    
    def get_available_microphones(self):
        """
        Возвращает словарь доступных микрофонов
        
        Returns:
            dict: Словарь {id_микрофона: описание}
        """
        try:
            # Встроенный микрофон всегда доступен
            available_mics = {
                "built_in": "Встроенный микрофон в пульте"
            }
            
            # Проверяем, подключен ли USB микрофон
            if self.is_usb_microphone_connected():
                available_mics["usb"] = "USB микрофон"
            
            return available_mics
        except Exception as e:
            error_msg = f"Ошибка при получении списка доступных микрофонов: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            # В случае ошибки возвращаем только встроенный микрофон
            return {
                "built_in": "Встроенный микрофон в пульте"
            }
    
    def get_microphone(self):
        """
        Возвращает идентификатор текущего выбранного микрофона
        
        Returns:
            str: Идентификатор микрофона
        """
        try:
            # Получаем значение из настроек, по умолчанию используем встроенный микрофон
            return self.settings_manager.settings.get("microphone", "built_in")
        except Exception as e:
            error_msg = f"Ошибка при получении текущего микрофона: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return "built_in"  # По умолчанию используем встроенный микрофон
    
    def change_microphone(self, microphone_id, force=False):
        """
        Изменяет текущий выбранный микрофон
        
        Args:
            microphone_id (str): Идентификатор микрофона
            force (bool): Принудительное изменение, без проверки доступности
            
        Returns:
            None: Метод больше не возвращает строку, а напрямую отображает сообщение
        """
        try:
            # Логируем начало процесса
            sentry_sdk.add_breadcrumb(
                category="microphone",
                message=f"MicrophoneSelector: Начало смены микрофона на {microphone_id}, force={force}",
                level="info"
            )
            print(f"[MICROPHONE] Запрос на изменение микрофона: {microphone_id}, force={force}")
            
            # Проверяем, существует ли микрофон в доступных
            available_microphones = self.get_available_microphones()
            
            # Если пытаемся выбрать USB микрофон, проверяем, подключен ли он
            if microphone_id == "usb" and not force:
                # Если USB микрофон недоступен, выдаем сообщение и возвращаемся
                if not self.is_usb_microphone_connected():
                    error_msg = "USB микрофон сейчас не подключен."
                    print(f"[MICROPHONE WARNING] {error_msg}")
                    
                    # Отображаем сообщение на экране
                    if hasattr(self.menu_manager, "display_manager"):
                        self.menu_manager.display_manager.display_message(error_msg)
                    
                    # Озвучиваем сообщение
                    if hasattr(self.menu_manager, "tts_manager"):
                        self.menu_manager.tts_manager.play_speech(
                            error_msg, 
                            voice_id=self.menu_manager.settings_manager.get_voice()
                        )
                    
                    # Задержка перед возвратом в главное меню
                    import time
                    time.sleep(5.0)
                    
                    # Возвращаемся в главное меню
                    if hasattr(self.menu_manager, "go_to_main_menu"):
                        self.menu_manager.go_to_main_menu()
                    elif hasattr(self.menu_manager, "go_back"):
                        # Возможно, нужно вернуться несколько раз
                        while self.menu_manager.current_menu != self.menu_manager.root_menu:
                            self.menu_manager.go_back()
                    
                    return None
            
            # Если не принудительное изменение, и микрофон не в списке доступных
            if not force and microphone_id not in available_microphones:
                error_msg = f"Ошибка при выборе микрофона: недоступен"
                print(f"[MICROPHONE ERROR] {error_msg}")
                sentry_sdk.capture_message(error_msg, level="error")
                
                # Отображаем сообщение на экране
                if hasattr(self.menu_manager, "display_manager"):
                    self.menu_manager.display_manager.display_message(error_msg)
                
                # Озвучиваем сообщение
                if hasattr(self.menu_manager, "tts_manager"):
                    self.menu_manager.tts_manager.play_speech(
                        error_msg, 
                        voice_id=self.menu_manager.settings_manager.get_voice()
                    )
                
                return None
            
            # Запоминаем старое значение для возможного восстановления
            old_microphone = self.get_microphone()
            
            # Если текущий микрофон совпадает с запрашиваемым, ничего не делаем
            if old_microphone == microphone_id and not force:
                print(f"[MICROPHONE] Микрофон {microphone_id} уже выбран, изменений не требуется")
                mic_desc = available_microphones.get(microphone_id, "Неизвестный микрофон")
                success_message = f"Выбран {mic_desc}."
                
                # Отображаем сообщение на экране
                if hasattr(self.menu_manager, "display_manager"):
                    self.menu_manager.display_manager.display_message(success_message)
                
                # Озвучиваем сообщение
                if hasattr(self.menu_manager, "tts_manager"):
                    self.menu_manager.tts_manager.play_speech(
                        success_message, 
                        voice_id=self.menu_manager.settings_manager.get_voice()
                    )
                
                # Задержка перед возвратом в главное меню для завершения воспроизведения
                import time
                time.sleep(3.0)
                
                # Возвращаемся в главное меню
                if hasattr(self.menu_manager, "go_to_main_menu"):
                    self.menu_manager.go_to_main_menu()
                elif hasattr(self.menu_manager, "go_back"):
                    # Возможно, нужно вернуться несколько раз
                    while self.menu_manager.current_menu != self.menu_manager.root_menu:
                        self.menu_manager.go_back()
                
                return None
            
            # Устанавливаем новое значение
            self.settings_manager.settings["microphone"] = microphone_id
            
            # Сохраняем настройки
            try:
                self.settings_manager.save_settings()
                print(f"[MICROPHONE] Настройки сохранены в файл")
            except Exception as save_error:
                error_msg = f"Ошибка при сохранении настроек: {save_error}"
                print(f"[MICROPHONE ERROR] {error_msg}")
                sentry_sdk.capture_exception(save_error)
                # Восстанавливаем старое значение
                self.settings_manager.settings["microphone"] = old_microphone
                
                # Отображаем сообщение об ошибке
                if hasattr(self.menu_manager, "display_manager"):
                    self.menu_manager.display_manager.display_message(error_msg)
                
                # Озвучиваем сообщение об ошибке
                if hasattr(self.menu_manager, "tts_manager"):
                    self.menu_manager.tts_manager.play_speech(
                        error_msg, 
                        voice_id=self.menu_manager.settings_manager.get_voice()
                    )
                
                return None
            
            # Обновляем пункты меню для отображения нового выбора
            self._setup_menu_items()
            
            # Подготавливаем сообщение об успешном изменении
            mic_desc = available_microphones.get(microphone_id, "Неизвестный микрофон")
            success_message = f"Выбран {mic_desc}."
            
            # Отображаем сообщение на экране
            if hasattr(self.menu_manager, "display_manager"):
                self.menu_manager.display_manager.display_message(success_message)
            
            # Озвучиваем сообщение
            if hasattr(self.menu_manager, "tts_manager"):
                self.menu_manager.tts_manager.play_speech(
                    success_message, 
                    voice_id=self.menu_manager.settings_manager.get_voice()
                )
            
            # Задержка для завершения воспроизведения
            import time
            time.sleep(3.0)
            
            # Возвращаемся в главное меню
            if hasattr(self.menu_manager, "go_to_main_menu"):
                self.menu_manager.go_to_main_menu()
            elif hasattr(self.menu_manager, "go_back"):
                # Возможно, нужно вернуться несколько раз
                while self.menu_manager.current_menu != self.menu_manager.root_menu:
                    self.menu_manager.go_back()
            
            # Логируем успешное изменение
            sentry_sdk.add_breadcrumb(
                category="microphone",
                message=f"MicrophoneSelector: Микрофон успешно изменен с {old_microphone} на {microphone_id}",
                level="info"
            )
            
            return None
        except Exception as e:
            error_msg = f"Критическая ошибка при изменении микрофона: {e}"
            print(f"[MICROPHONE CRITICAL ERROR] {error_msg}")
            sentry_sdk.capture_exception(e)
            
            # Отображаем сообщение об ошибке
            if hasattr(self.menu_manager, "display_manager"):
                self.menu_manager.display_manager.display_message(error_msg)
            
            # Озвучиваем сообщение об ошибке
            if hasattr(self.menu_manager, "tts_manager"):
                self.menu_manager.tts_manager.play_speech(
                    error_msg, 
                    voice_id=self.menu_manager.settings_manager.get_voice()
                )
            
            return None
    
    def __del__(self):
        """Деструктор класса"""
        try:
            # Останавливаем мониторинг при удалении объекта
            self.stop_monitoring()
        except Exception as e:
            error_msg = f"Ошибка при остановке мониторинга микрофонов: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e) 