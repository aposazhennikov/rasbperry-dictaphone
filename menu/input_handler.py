#!/usr/bin/env python3
import time
from evdev import InputDevice, ecodes, list_devices
import sentry_sdk

# Константы клавиш
KEY_UP = 103
KEY_DOWN = 108
KEY_SELECT = 353
KEY_BACK = 158
KEY_LEFT = 105
KEY_RIGHT = 106
KEY_POWER = 116   # Клавиша питания для удаления файлов
KEY_PAGEUP = 104  # Клавиша Page Up для перехода к предыдущему файлу
KEY_PAGEDOWN = 109  # Клавиша Page Down для перехода к следующему файлу
KEY_VOLUMEUP = 115  # Клавиша Volume Up
KEY_VOLUMEDOWN = 114  # Клавиша Volume Down

class InputHandler:
    """Класс для обработки ввода с пульта"""
    
    def __init__(self, menu_manager, target_device_name="HAOBO Technology USB Composite Device Keyboard"):
        """
        Инициализация обработчика ввода
        
        Args:
            menu_manager: Менеджер меню для обработки команд
            target_device_name (str): Название целевого устройства ввода
        """
        try:
            self.menu_manager = menu_manager
            self.target_device_name = target_device_name
            self.device = None
            self.running = False
            self.debug = menu_manager.debug
            
            # Состояние клавиш для отслеживания удержания
            self.key_states = {
                KEY_LEFT: {"pressed": False, "time": 0},
                KEY_RIGHT: {"pressed": False, "time": 0}
            }
            
            if self.debug:
                print("InputHandler инициализирован")
        except Exception as e:
            error_msg = f"Ошибка при инициализации InputHandler: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def find_device(self):
        """
        Ищет целевое устройство ввода по имени
        
        Returns:
            InputDevice: Найденное устройство или None
        """
        try:
            devices = [InputDevice(path) for path in list_devices()]
            for device in devices:
                if self.target_device_name in device.name:
                    if self.debug:
                        print(f"Найдено устройство: {device.name} ({device.path})")
                    return device
            
            if self.debug:
                print(f"Устройство {self.target_device_name} не найдено")
                available_devices = ", ".join([device.name for device in devices])
                print(f"Доступные устройства: {available_devices}")
                
            return None
        except Exception as e:
            error_msg = f"Ошибка при поиске устройства ввода: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return None
    
    def initialize(self):
        """
        Инициализирует устройство ввода
        
        Returns:
            bool: True, если инициализация успешна
        """
        try:
            self.device = self.find_device()
            if not self.device:
                return False
                
            if self.debug:
                print("Устройство ввода инициализировано")
                
            return True
        except Exception as e:
            error_msg = f"Ошибка при инициализации устройства ввода: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
            
    def start_input_loop(self):
        """Запускает цикл обработки событий ввода"""
        try:
            if not self.device:
                if not self.initialize():
                    print("Не удалось инициализировать устройство ввода")
                    return
            
            self.running = True
            
            if self.debug:
                print("Запущен цикл обработки ввода")
            
            for event in self.device.read_loop():
                if not self.running:
                    break
                    
                self.handle_event(event)
        except Exception as e:
            error_msg = f"Ошибка в цикле обработки ввода: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
    def handle_event(self, event):
        """
        Обрабатывает событие от устройства ввода
        
        Args:
            event: Событие от устройства
        """
        try:
            if event.type == ecodes.EV_KEY:
                key_code = event.code
                key_id = self._get_key_id(key_code)
                
                if self.debug:
                    print(f"\nСобытие клавиши: {key_id} (код: {key_code}), значение: {event.value}")
                
                # Обработка нажатия
                if event.value == 1:  # Нажатие
                    # Сначала проверяем, не нужно ли передать событие в PlaybackManager
                    playback_manager = getattr(self.menu_manager, 'playback_manager', None)
                    if playback_manager and playback_manager.is_playing():
                        if key_code in [KEY_LEFT, KEY_RIGHT, KEY_VOLUMEUP, KEY_VOLUMEDOWN]:
                            if self.debug:
                                print(f"Передача нажатия {key_id} в PlaybackManager")
                            playback_manager.handle_key_press(key_code, True)
                            return
                    
                    # Если не обработано PlaybackManager, передаем в MenuManager
                    self.menu_manager.handle_button_press(key_id)
                    
                # Обработка отпускания
                elif event.value == 0:  # Отпускание
                    # Сначала проверяем PlaybackManager
                    playback_manager = getattr(self.menu_manager, 'playback_manager', None)
                    if playback_manager and playback_manager.is_playing():
                        if key_code in [KEY_LEFT, KEY_RIGHT]:
                            if self.debug:
                                print(f"Передача отпускания {key_id} в PlaybackManager")
                            playback_manager.handle_key_press(key_code, False)
                            return
                    
                    # Если не обработано PlaybackManager, обрабатываем стандартно
                    self._handle_key_release(key_code)
                    
        except Exception as e:
            error_msg = f"Ошибка при обработке события: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
    def _handle_key_press(self, key_code):
        """Обрабатывает нажатие клавиши"""
        try:
            # Преобразуем код клавиши в строковый идентификатор
            key_id = self._get_key_id(key_code)
            if self.debug:
                print(f"Обработка нажатия клавиши: {key_id} (код: {key_code})")
            
            # Используем новый универсальный метод обработки нажатий
            # Он сам определит, в каком режиме находится система (меню, аудиоплеер или запись)
            handled = self.menu_manager.handle_button_press(key_id)
            
            if self.debug:
                if handled:
                    print(f"Клавиша {key_id} успешно обработана")
                else:
                    print(f"Клавиша {key_id} не обработана")
            
            # Запоминаем состояние и время для клавиш, которые можно удерживать
            if key_code in self.key_states:
                self.key_states[key_code]["pressed"] = True
                self.key_states[key_code]["time"] = time.time()
                
        except Exception as e:
            error_msg = f"Ошибка при обработке нажатия клавиши: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
    def _handle_key_release(self, key_code):
        """Обрабатывает отпускание клавиши"""
        try:
            # Обработка отпускания для режима воспроизведения
            playback_manager = getattr(self.menu_manager, 'playback_manager', None)
            if playback_manager and playback_manager.is_playing():
                playback_manager.handle_key_press(key_code, False)
                
            # Сбрасываем состояние клавиш
            if key_code in self.key_states:
                self.key_states[key_code]["pressed"] = False
        except Exception as e:
            error_msg = f"Ошибка при обработке отпускания клавиши: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
    def _get_key_id(self, key_code):
        """
        Преобразует код клавиши в строковый идентификатор
        
        Args:
            key_code (int): Код клавиши
        
        Returns:
            str: Строковый идентификатор клавиши
        """
        key_map = {
            KEY_UP: "KEY_UP",
            KEY_DOWN: "KEY_DOWN",
            KEY_LEFT: "KEY_LEFT",
            KEY_RIGHT: "KEY_RIGHT",
            KEY_SELECT: "KEY_SELECT",
            KEY_BACK: "KEY_BACK",
            KEY_POWER: "KEY_POWER",
            KEY_PAGEUP: "KEY_PAGEUP",
            KEY_PAGEDOWN: "KEY_PAGEDOWN",
            KEY_VOLUMEUP: "KEY_VOLUMEUP",
            KEY_VOLUMEDOWN: "KEY_VOLUMEDOWN",
            49: "KEY_1",  # Клавиша 1
            50: "KEY_2",  # Клавиша 2
            51: "KEY_3",  # Клавиша 3
            52: "KEY_4",  # Клавиша 4
            53: "KEY_5",  # Клавиша 5
        }
        
        return key_map.get(key_code, f"UNKNOWN_{key_code}")