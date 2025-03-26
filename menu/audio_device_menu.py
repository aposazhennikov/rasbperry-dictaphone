#!/usr/bin/env python3
import os
import time
import threading
import sentry_sdk
from .audio_device_manager import AudioDeviceManager
from .base_menu import BaseMenu
from .menu_item import MenuItem

class DeviceMenuItem(MenuItem):
    """Класс для представления пункта меню устройства"""
    
    def __init__(self, name, device, action):
        """
        Инициализирует пункт меню устройства
        
        Args:
            name (str): Отображаемое имя пункта меню
            device (dict): Данные устройства 
            action (callable): Функция, вызываемая при выборе пункта
        """
        super().__init__(name, action)
        self.device = device

class AudioDeviceMenu(BaseMenu):
    """Класс для меню выбора аудио устройства"""
    
    def __init__(self, menu_manager, tts_manager, settings_manager, debug=False):
        """
        Инициализация меню выбора аудио устройства
        
        Args:
            menu_manager: Менеджер меню для навигации
            tts_manager: Менеджер TTS для озвучки
            settings_manager: Менеджер настроек
            debug (bool): Режим отладки
        """
        super().__init__("Выбор устройства для записи")
        
        # Добавляем атрибут name для совместимости с MenuManager.display_current_menu
        self.name = "Выбор устройства для записи"
        
        # Добавляем атрибуты для совместимости с MenuManager.display_current_menu
        self.current_selection = 0
        self.items = []
        
        try:
            self.menu_manager = menu_manager
            self.tts_manager = tts_manager
            self.settings_manager = settings_manager
            self.debug = debug
            
            # Создаем менеджер аудио устройств
            self.settings_file = "/home/aleks/cache_tts/settings.json"
            self.audio_device_manager = AudioDeviceManager(settings_file=self.settings_file, debug=debug)
            
            # Текущее выбранное устройство
            self.selected_device = self.audio_device_manager.get_selected_device()
            
            # Список доступных устройств
            self.available_devices = []
            
            # Обновляем список устройств
            self.update_devices()
            
            # Таймер для периодического обновления списка устройств
            self.update_timer = None
            self.stop_update_timer = False
            
            # Запускаем таймер обновления
            self.start_update_timer()
            
            if self.debug:
                print("AudioDeviceMenu инициализирован")
        except Exception as e:
            error_msg = f"Ошибка при инициализации AudioDeviceMenu: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def get_current_item(self):
        """
        Возвращает текущий выбранный пункт меню
        
        Returns:
            MenuItem: Текущий выбранный пункт меню или None
        """
        try:
            if not self.items or self.current_selection >= len(self.items):
                return None
            return self.items[self.current_selection]
        except Exception as e:
            error_msg = f"Ошибка при получении текущего пункта меню: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return None
    
    def move_up(self):
        """Перемещает выделение на предыдущий пункт меню"""
        try:
            if not self.items:
                return
            self.current_selection = (self.current_selection - 1) % len(self.items)
        except Exception as e:
            error_msg = f"Ошибка при перемещении выделения вверх: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def move_down(self):
        """Перемещает выделение на следующий пункт меню"""
        try:
            if not self.items:
                return
            self.current_selection = (self.current_selection + 1) % len(self.items)
        except Exception as e:
            error_msg = f"Ошибка при перемещении выделения вниз: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def update_devices(self):
        """Обновляет список доступных устройств"""
        try:
            # Получаем список доступных устройств
            self.available_devices = self.audio_device_manager.get_available_devices()
            
            # Обновляем структуру меню
            self.update_menu_structure()
            
            if self.debug:
                print(f"Обновлен список устройств: {len(self.available_devices)} устройств")
        except Exception as e:
            error_msg = f"Ошибка при обновлении списка устройств: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def update_menu_structure(self):
        """Обновляет структуру меню на основе доступных устройств"""
        try:
            # Очищаем текущую структуру меню
            self.menu_structure = []
            self.items = []
            
            # Добавляем все доступные устройства
            for i, device in enumerate(self.available_devices):
                device_name = device.get("name", f"Устройство {i}")
                
                # Для встроенного микрофона используем специальное название
                if device.get("is_built_in", False):
                    device_name = "Встроенный микрофон в пульте"
                # Для USB устройств используем упрощенное название
                elif "USB" in device_name:
                    device_name = "USB микрофон"
                
                # Добавляем префикс "✓" для выбранного устройства
                selected = (device.get("card") == self.selected_device.get("card") and 
                           device.get("device") == self.selected_device.get("device"))
                
                menu_text = f"{'✓ ' if selected else ''}{device_name}"
                
                # Создаем объект MenuItem для совместимости с MenuManager
                menu_item = DeviceMenuItem(menu_text, device, lambda d=device: self.select_device(d))
                self.items.append(menu_item)
                
                # Также сохраняем в старом формате для обратной совместимости
                self.menu_structure.append({
                    "text": menu_text,
                    "action": lambda d=device: self.select_device(d),
                    "device": device
                })
            
            if self.debug:
                print(f"Обновлена структура меню, {len(self.menu_structure)} пунктов")
        except Exception as e:
            error_msg = f"Ошибка при обновлении структуры меню: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def select_device(self, device):
        """
        Выбирает устройство для записи
        
        Args:
            device (dict): Словарь с информацией об устройстве
            
        Returns:
            bool: True если успешно, иначе False
        """
        try:
            if self.debug:
                print(f"Выбрано устройство: {device}")
            
            # Запоминаем текущее устройство
            old_device = self.selected_device
            
            # Устанавливаем новое устройство
            result = self.audio_device_manager.set_device(device)
            
            if result:
                # Обновляем локальное выбранное устройство
                self.selected_device = device
                
                # Обновляем меню
                self.update_menu_structure()
                
                # Также обновляем устройство в recorder_manager, если он доступен
                if hasattr(self.menu_manager, 'recorder_manager') and self.menu_manager.recorder_manager:
                    try:
                        # Используем новый метод для обновления устройства в менеджере записи
                        if hasattr(self.menu_manager.recorder_manager, 'update_audio_device'):
                            if self.debug:
                                print(f"Вызываем метод update_audio_device для обновления устройства")
                            self.menu_manager.recorder_manager.update_audio_device(device)
                        else:
                            # Обновляем устройство в текущем менеджере записи
                            self.menu_manager.recorder_manager.audio_device = device
                            
                            # Обновляем устройство в активном рекордере, если он есть
                            if hasattr(self.menu_manager.recorder_manager, 'recorder') and self.menu_manager.recorder_manager.recorder:
                                if self.debug:
                                    print(f"Обновляем устройство в активном рекордере на: {device}")
                                self.menu_manager.recorder_manager.recorder.set_audio_device(device)
                            
                        if self.debug:
                            print(f"Устройство успешно обновлено в менеджере записи")
                    except Exception as recorder_error:
                        print(f"Ошибка при обновлении устройства в менеджере записи: {recorder_error}")
                        sentry_sdk.capture_exception(recorder_error)
                
                # Озвучиваем сообщение о выбранном устройстве
                device_name = device.get("name", "Неизвестное устройство")
                if device.get("is_built_in", False):
                    device_name = "Встроенный микрофон в пульте"
                elif "USB" in device_name:
                    device_name = "USB микрофон"
                
                self.tts_manager.play_speech_blocking(f"Выбран микрофон {device_name}")
                self.tts_manager.play_speech_blocking("Возврат в главное меню")
                
                if self.debug:
                    print(f"Устройство успешно выбрано: {device_name}")
                
                # Возвращаемся в предыдущее меню
                self.menu_manager.go_back()
                
                return True
            else:
                # Озвучиваем сообщение об ошибке
                self.tts_manager.play_speech("Не удалось выбрать устройство")
                
                if self.debug:
                    print("Не удалось установить устройство")
                
                return False
        except Exception as e:
            error_msg = f"Ошибка при выборе устройства: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
            # Озвучиваем сообщение об ошибке
            self.tts_manager.play_speech("Произошла ошибка при выборе устройства")
            
            return False
    
    def start_update_timer(self):
        """Запускает таймер периодического обновления списка устройств"""
        try:
            self.stop_update_timer = False
            self.update_timer = threading.Thread(target=self._update_timer_thread)
            self.update_timer.daemon = True
            self.update_timer.start()
            
            if self.debug:
                print("Запущен таймер обновления списка устройств")
        except Exception as e:
            error_msg = f"Ошибка при запуске таймера обновления: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def stop_update_timer(self):
        """Останавливает таймер периодического обновления списка устройств"""
        try:
            self.stop_update_timer = True
            if self.update_timer and self.update_timer.is_alive():
                self.update_timer.join(1.0)
                
            if self.debug:
                print("Остановлен таймер обновления списка устройств")
        except Exception as e:
            error_msg = f"Ошибка при остановке таймера обновления: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def _update_timer_thread(self):
        """Функция таймера обновления списка устройств в отдельном потоке"""
        try:
            # Запоминаем количество устройств при старте
            last_device_count = len(self.available_devices)
            
            while not self.stop_update_timer:
                # Получаем текущий список устройств
                current_devices = self.audio_device_manager.get_available_devices()
                current_count = len(current_devices)
                
                # Если количество устройств изменилось, обновляем меню
                if current_count != last_device_count:
                    if self.debug:
                        print(f"Изменилось количество устройств: было {last_device_count}, стало {current_count}")
                    
                    # Обновляем список устройств
                    self.available_devices = current_devices
                    self.update_menu_structure()
                    
                    # Обновляем последнее известное количество устройств
                    last_device_count = current_count
                
                # Проверяем каждые 3 секунды
                time.sleep(3)
        except Exception as e:
            error_msg = f"Ошибка в потоке обновления устройств: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def show(self):
        """Показывает меню выбора аудио устройства"""
        try:
            # Обновляем список устройств перед показом меню
            self.update_devices()
            
            # Озвучиваем информацию о текущем выбранном устройстве
            current_device_name = self.selected_device.get("name", "Неизвестное устройство")
            if self.selected_device.get("is_built_in", False):
                current_device_name = "Встроенный микрофон в пульте"
            elif "USB" in current_device_name:
                current_device_name = "USB микрофон"
                
            self.tts_manager.play_speech_blocking(f"Сейчас выбран микрофон: {current_device_name}")
            self.tts_manager.play_speech_blocking("Выбор устройства для записи")
            
            # Если нет доступных устройств, сообщаем об этом
            if not self.menu_structure:
                self.tts_manager.play_speech("Нет доступных устройств для записи")
                time.sleep(2)
                self.menu_manager.go_back()
                return
            
            # Показываем меню
            selected_index = 0
            while True:
                # Обновляем выбранный индекс, если он вышел за пределы меню
                if selected_index >= len(self.menu_structure):
                    selected_index = 0
                
                # Получаем текущий пункт меню
                current_item = self.menu_structure[selected_index]
                
                # Озвучиваем текущий пункт
                self.tts_manager.play_speech(current_item["text"])
                
                # Ждем действия пользователя
                key = self.menu_manager.wait_for_key()
                
                if key == "KEY_UP":
                    # Переход к предыдущему пункту
                    selected_index = (selected_index - 1) % len(self.menu_structure)
                elif key == "KEY_DOWN":
                    # Переход к следующему пункту
                    selected_index = (selected_index + 1) % len(self.menu_structure)
                elif key == "KEY_SELECT":
                    # Выбор текущего пункта
                    current_item["action"]()
                    break
                elif key == "KEY_BACK":
                    # Возврат в предыдущее меню
                    self.menu_manager.go_back()
                    break
        except Exception as e:
            error_msg = f"Ошибка при показе меню выбора аудио устройства: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
            # В случае ошибки возвращаемся в предыдущее меню
            self.menu_manager.go_back() 