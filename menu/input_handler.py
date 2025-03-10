#!/usr/bin/env python3
import time
from evdev import InputDevice, ecodes, list_devices

# Константы клавиш
KEY_UP = 103
KEY_DOWN = 108
KEY_SELECT = 353
KEY_BACK = 158
KEY_LEFT = 105
KEY_RIGHT = 106

class InputHandler:
    """Класс для обработки ввода с пульта"""
    
    def __init__(self, menu_manager, target_device_name="HAOBO Technology USB Composite Device Keyboard"):
        """
        Инициализация обработчика ввода
        
        Args:
            menu_manager: Менеджер меню
            target_device_name (str): Название устройства для поиска
        """
        self.menu_manager = menu_manager
        self.target_device_name = target_device_name
        self.device = None
        self.key_states = {
            KEY_RIGHT: False,
            KEY_LEFT: False
        }
        self.debounce_time = 0.1
        self.last_key_time = 0
    
    def find_device(self):
        """Поиск устройства ввода по имени"""
        devices = [InputDevice(path) for path in list_devices()]
        for device in devices:
            if self.target_device_name in device.name:
                return device
        return None
    
    def initialize(self):
        """Инициализация устройства ввода"""
        self.device = self.find_device()
        if not self.device:
            print(f"Устройство '{self.target_device_name}' не найдено!")
            print("Доступные устройства:")
            for device in [InputDevice(path) for path in list_devices()]:
                print(f"  - {device.name}")
            return False
        
        print(f"Устройство '{self.target_device_name}' найдено!")
        return True
        
    def start_input_loop(self):
        """Запускает цикл обработки ввода"""
        if not self.device:
            if not self.initialize():
                return
        
        try:
            for event in self.device.read_loop():
                if event.type == ecodes.EV_KEY:
                    self.process_key_event(event)
        except KeyboardInterrupt:
            print("\nЗавершение работы...")
        except Exception as e:
            print(f"Ошибка при чтении ввода: {e}")
            
    def process_key_event(self, event):
        """
        Обработка события клавиши
        
        Args:
            event: Событие от устройства ввода
        """
        # Предотвращаем дребезг клавиш
        current_time = time.time()
        if current_time - self.last_key_time < self.debounce_time:
            return
        self.last_key_time = current_time
        
        key_code = event.code
        key_value = event.value  # 1 - нажата, 0 - отпущена
        
        # Добавляем отладочный вывод для диагностики
        if key_value == 1:
            print(f"\n*** Нажата клавиша {key_code} ***")
            
            # Специальная обработка KEY_BACK для остановки записи
            if key_code == KEY_BACK:
                is_recording = self.menu_manager.recording_state.get("active", False)
                print(f"KEY_BACK: запись активна: {is_recording}")
                if is_recording:
                    print("ВЫПОЛНЯЕМ КОМАНДУ ОСТАНОВКИ ЗАПИСИ")
                    self.menu_manager._stop_recording()
                    return
        
        # Получаем текущий экран из display_manager
        current_screen = self.menu_manager.display_manager.current_screen
        
        # Обрабатываем нажатие клавиш
        if key_value == 1:  # Клавиша нажата
            # Проверяем, активна ли запись, независимо от текущего экрана
            if self.menu_manager.recording_state.get("active", False):
                print(f"Запись активна, обрабатываем команды для записи...")
                if key_code == KEY_SELECT:  # KEY_SELECT - Пауза/Возобновить
                    print("Выполняем _toggle_pause_recording")
                    self.menu_manager._toggle_pause_recording()
                    return
            
            # Стандартная обработка для экрана меню, если не в режиме записи
            if key_code == KEY_UP:
                self.menu_manager.move_up()
            elif key_code == KEY_DOWN:
                self.menu_manager.move_down()
            elif key_code == KEY_SELECT:
                self.menu_manager.select_current_item()
            elif key_code == KEY_BACK:
                self.menu_manager.go_back()
            # Дополнительные клавиши можно добавить по необходимости