#!/usr/bin/env python3
import sentry_sdk
import subprocess
import threading
import time
from .menu_item import MenuItem, SubMenu

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
            
            while not self.stop_monitoring_flag:
                # Проверяем текущее состояние USB микрофона
                current_usb_state = self.is_usb_microphone_connected()
                
                # Если состояние изменилось
                if current_usb_state != last_usb_state:
                    if self.debug:
                        print(f"Изменение состояния USB микрофона: {last_usb_state} -> {current_usb_state}")
                    
                    # Если USB микрофон был отключен, и он был выбран
                    if not current_usb_state and self.get_microphone() == "usb":
                        if self.debug:
                            print("USB микрофон был отключен, переключаемся на встроенный")
                        
                        # Принудительно переключаемся на встроенный микрофон
                        self.change_microphone("built_in", force=True)
                    
                    # Обновляем отображение меню
                    self._setup_menu_items()
                    
                    # Обновляем последнее состояние
                    last_usb_state = current_usb_state
                
                # Пауза перед следующей проверкой
                time.sleep(1.0)
        except Exception as e:
            error_msg = f"Ошибка в цикле мониторинга микрофонов: {e}"
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
                if self.debug:
                    print(f"Ошибка при выполнении arecord -l: {result.stderr}")
                return False
            
            # Ищем в выводе USB микрофон
            return "(LCS) USB Audio Device" in result.stdout
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