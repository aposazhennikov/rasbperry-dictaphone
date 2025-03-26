#!/usr/bin/env python3
import os
import json
import subprocess
import threading
import time
import sentry_sdk

class AudioDeviceManager:
    """Класс для управления аудио устройствами записи"""
    
    def __init__(self, settings_file="/home/aleks/cache_tts/settings.json", debug=False):
        """
        Инициализация менеджера аудио устройств
        
        Args:
            settings_file (str): Путь к файлу настроек
            debug (bool): Режим отладки
        """
        try:
            self.settings_file = settings_file
            self.debug = debug
            self.monitoring_thread = None
            self.stop_monitoring = False
            
            # Колбэк для оповещения об отключении текущего устройства
            self.device_disconnected_callback = None
            
            # Значение по умолчанию для выбранного устройства (встроенный микрофон)
            self.default_device = {
                "card": 0,
                "device": 0,
                "name": "Встроенный микрофон в пульте",
                "is_built_in": True
            }
            
            # Создаем директорию для файла настроек, если её нет
            os.makedirs(os.path.dirname(os.path.abspath(settings_file)), exist_ok=True)
            
            # Загружаем настройки выбранного устройства
            self.load_selected_device()
            
            # Запускаем мониторинг устройств
            self.start_device_monitoring()
            
            if self.debug:
                print("AudioDeviceManager инициализирован")
        except Exception as e:
            error_msg = f"Ошибка при инициализации AudioDeviceManager: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def load_selected_device(self):
        """Загружает информацию о выбранном устройстве из файла настроек"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    
                if "audio_device" in settings:
                    self.selected_device = settings["audio_device"]
                else:
                    # Если настройки аудио устройства отсутствуют, используем встроенный микрофон
                    self.selected_device = self.default_device
                    self.save_selected_device()
            else:
                # Если файл настроек не существует, используем встроенный микрофон
                self.selected_device = self.default_device
                self.save_selected_device()
        except Exception as e:
            sentry_sdk.capture_exception(e)
            # В случае ошибки используем встроенный микрофон
            self.selected_device = self.default_device
    
    def save_selected_device(self):
        """Сохраняет информацию о выбранном устройстве в файл настроек"""
        try:
            # Если файл существует, загружаем текущие настройки
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            else:
                settings = {}
            
            # Обновляем или добавляем настройку аудио устройства
            settings["audio_device"] = self.selected_device
            
            # Сохраняем обновленные настройки
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            sentry_sdk.capture_exception(e)
    
    def get_selected_device(self):
        """
        Возвращает информацию о выбранном устройстве
        
        Returns:
            dict: Словарь с информацией о выбранном устройстве
        """
        return self.selected_device
    
    def get_device_params(self):
        """
        Возвращает параметры устройства для использования с sounddevice
        
        Returns:
            dict: Параметры устройства для sounddevice
        """
        try:
            # Получаем текущий выбранный индекс sounddevice, если он есть
            if "sd_index" in self.selected_device and self.selected_device["sd_index"] is not None:
                sd_index = self.selected_device["sd_index"]
                
                # Проверяем, доступно ли это устройство сейчас
                try:
                    import sounddevice as sd
                    device_list = sd.query_devices()
                    if 0 <= sd_index < len(device_list) and device_list[sd_index]['max_input_channels'] > 0:
                        # Устройство действительно существует и имеет входные каналы
                        return {"device": sd_index}
                except Exception:
                    pass
            
            # Пробуем найти USB микрофон среди доступных устройств sounddevice
            if not self.selected_device.get("is_built_in", False):
                try:
                    import sounddevice as sd
                    device_list = sd.query_devices()
                    
                    # Ищем устройство с "USB" в названии
                    for i, device in enumerate(device_list):
                        if device['max_input_channels'] > 0 and "USB" in device['name']:
                            return {"device": i}
                except Exception:
                    pass
            
            # Иначе используем ALSA формат
            device_id = f"hw:{self.selected_device['card']},{self.selected_device['device']}"
            
            try:
                # Дополнительно пробуем получить устройство по имени
                import sounddevice as sd
                
                # Если это встроенный микрофон, проверяем устройство по умолчанию
                if self.selected_device.get("is_built_in", False):
                    default_device = sd.query_devices(kind='input')
                    if default_device:
                        return {"device": None}  # None означает использовать устройство по умолчанию
            except Exception:
                pass
                
            return {"device": device_id}
        except Exception as e:
            sentry_sdk.capture_exception(e)
            # В случае ошибки возвращаем пустой словарь, чтобы использовалось устройство по умолчанию
            return {}
    
    def get_available_devices(self):
        """
        Получает список доступных микрофонов
        
        Returns:
            list: Список словарей с информацией о доступных устройствах
        """
        try:
            devices = []
            
            # Всегда добавляем встроенный микрофон
            devices.append(self.default_device)
            
            # Получаем информацию о устройствах через sounddevice
            sd_devices = []
            try:
                import sounddevice as sd
                sd_device_list = sd.query_devices()
                for i, device in enumerate(sd_device_list):
                    if device['max_input_channels'] > 0:
                        sd_devices.append({
                            "index": i,
                            "name": device['name'],
                            "channels": device['max_input_channels'],
                            "sample_rate": device.get('default_samplerate', 44100)
                        })
            except Exception as sd_error:
                sentry_sdk.capture_exception(sd_error)
                if self.debug:
                    print(f"Ошибка при получении устройств через sounddevice: {sd_error}")
            
            # Получаем список устройств через arecord -l
            result = subprocess.run(["arecord", "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if result.returncode != 0:
                # Если не удалось получить устройства через arecord, но есть устройства от sounddevice
                if sd_devices:
                    for i, device in enumerate(sd_devices):
                        # Пропускаем устройства без "USB" в названии (кроме встроенного)
                        # и пропускаем устройства с "UACDemoV10" в названии (динамики)
                        if ("USB" in device['name'].upper() and "UACDEMOV10" not in device['name'].upper()):
                            # Добавляем USB-устройство из sounddevice
                            usb_device = {
                                "card": i,  # Используем индекс как номер карты
                                "device": 0,
                                "name": device['name'],
                                "is_built_in": False,
                                "sd_index": i  # Сохраняем индекс для sounddevice
                            }
                            devices.append(usb_device)
                return devices
            
            output = result.stdout
            
            # Парсим вывод arecord -l, без дублирования сообщений
            added_devices = set()  # Множество для отслеживания уже добавленных устройств
            
            for line in output.split('\n'):
                if line.startswith('card '):
                    # Примеры строк:
                    # "card 0: Device [USB Composite Device], device 0: USB Audio [USB Audio]"
                    # "card 1: Device_1 [(LCS) USB Audio Device], device 0: USB Audio [USB Audio]"
                    
                    parts = line.split(':', 2)
                    if len(parts) < 3:
                        continue
                    
                    card_info = parts[1].strip()
                    device_info = parts[2].strip()
                    
                    # Извлекаем номер карты
                    card_number = int(parts[0].replace('card ', ''))
                    
                    # Извлекаем номер устройства
                    device_number = 0  # По умолчанию
                    device_parts = device_info.split(':', 1)
                    if len(device_parts) > 0:
                        try:
                            device_number = int(device_parts[0].replace('device ', ''))
                        except:
                            pass
                    
                    # Извлекаем название устройства
                    device_name = card_info
                    
                    # Создаём уникальный идентификатор устройства для отслеживания дубликатов
                    device_key = f"{card_number}:{device_number}:{device_name}"
                    
                    # Проверяем, было ли уже добавлено это устройство
                    if device_key in added_devices:
                        continue
                    
                    # Проверяем, является ли это устройство встроенным микрофоном в пульте
                    is_built_in = "USB Composite Device" in card_info
                    
                    # Проверяем, является ли это динамиком (не добавляем его в список)
                    if "UACDemoV10" in card_info:
                        continue
                    
                    # Для встроенного микрофона используем специальное название
                    if is_built_in:
                        continue  # Пропускаем, так как он уже добавлен как default_device
                    
                    # Пытаемся найти соответствующий индекс в sounddevice
                    sd_index = None
                    for sd_device in sd_devices:
                        # Если часть названия устройства содержится в названии sounddevice
                        # или название sounddevice содержится в названии устройства
                        if (device_name in sd_device['name'] or sd_device['name'] in device_name or
                            ("USB" in device_name.upper() and "USB" in sd_device['name'].upper())):
                            sd_index = sd_device['index']
                            break
                    
                    # Добавляем устройство в список
                    device = {
                        "card": card_number,
                        "device": device_number,
                        "name": device_name,
                        "is_built_in": is_built_in,
                        "sd_index": sd_index  # Сохраняем индекс для sounddevice, если найден
                    }
                    
                    devices.append(device)
                    # Добавляем устройство в множество добавленных устройств
                    added_devices.add(device_key)
            
            return devices
        except Exception as e:
            sentry_sdk.capture_exception(e)
            if self.debug:
                print(f"Ошибка при получении доступных устройств: {e}")
            # В случае ошибки возвращаем только встроенный микрофон
            return [self.default_device]
    
    def set_device(self, device):
        """
        Устанавливает устройство для записи
        
        Args:
            device (dict): Словарь с информацией об устройстве
            
        Returns:
            bool: True если успешно, иначе False
        """
        try:
            self.selected_device = device
            self.save_selected_device()
            return True
        except Exception as e:
            error_msg = f"Ошибка при установке устройства: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def start_device_monitoring(self):
        """Запускает мониторинг подключения/отключения устройств"""
        try:
            self.stop_monitoring = False
            self.monitoring_thread = threading.Thread(target=self._monitor_devices)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()
            
            if self.debug:
                print("Запущен мониторинг аудио устройств")
        except Exception as e:
            error_msg = f"Ошибка при запуске мониторинга устройств: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def stop_device_monitoring(self):
        """Останавливает мониторинг подключения/отключения устройств"""
        try:
            self.stop_monitoring = True
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(1.0)
                
            if self.debug:
                print("Остановлен мониторинг аудио устройств")
        except Exception as e:
            error_msg = f"Ошибка при остановке мониторинга устройств: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def set_device_disconnected_callback(self, callback):
        """
        Устанавливает функцию обратного вызова, которая будет вызываться при отключении 
        текущего устройства
        
        Args:
            callback (callable): Функция, принимающая два аргумента - старое и новое устройство
        """
        self.device_disconnected_callback = callback
    
    def _monitor_devices(self):
        """Мониторит подключение/отключение аудио устройств"""
        try:
            # Запоминаем текущие устройства без отладочного вывода
            last_devices = self._get_available_devices_quiet()
            last_count = len(last_devices)
            
            # Проверяем наличие выбранного устройства
            selected_device_available = self._is_selected_device_available(last_devices)
            
            # Основной цикл мониторинга устройств
            while not self.stop_monitoring:
                # Получаем список доступных устройств без отладочного вывода
                current_devices = self._get_available_devices_quiet()
                current_count = len(current_devices)
                
                # Проверяем, изменилось ли количество устройств
                if current_count != last_count:
                    # Проверяем доступность выбранного устройства
                    device_available = self._is_selected_device_available(current_devices)
                    
                    # Если выбранное устройство было отключено, переключаемся на встроенный микрофон
                    if selected_device_available and not device_available:
                        # Запоминаем старое устройство
                        old_device = self.selected_device.copy()
                        
                        # Переключаемся на встроенный микрофон
                        self.selected_device = self.default_device
                        self.save_selected_device()
                        
                        # Вызываем колбэк, если он установлен
                        if self.device_disconnected_callback:
                            try:
                                self.device_disconnected_callback(old_device, self.default_device)
                            except Exception as callback_error:
                                sentry_sdk.capture_exception(callback_error)
                    
                    # Обновляем статус доступности выбранного устройства
                    selected_device_available = device_available
                    
                    # Обновляем количество устройств
                    last_count = current_count
                
                # Проверяем каждые 0.5 секунды
                time.sleep(0.5)
        except Exception as e:
            sentry_sdk.capture_exception(e)
    
    def _get_available_devices_quiet(self):
        """
        Тихая версия метода get_available_devices, которая не выводит отладочные сообщения
        
        Returns:
            list: Список словарей с информацией о доступных устройствах
        """
        # Временно отключаем режим отладки
        original_debug = self.debug
        self.debug = False
        
        try:
            # Вызываем обычный метод с отключенной отладкой
            return self.get_available_devices()
        finally:
            # Восстанавливаем режим отладки
            self.debug = original_debug
    
    def _is_selected_device_available(self, available_devices):
        """
        Проверяет, доступно ли выбранное устройство в списке доступных устройств
        
        Args:
            available_devices (list): Список доступных устройств
            
        Returns:
            bool: True если устройство доступно, иначе False
        """
        try:
            # Встроенный микрофон всегда считается доступным
            if self.selected_device.get("is_built_in", False):
                return True
                
            # Получаем параметры выбранного устройства
            selected_card = self.selected_device.get("card")
            selected_device = self.selected_device.get("device")
            selected_name = self.selected_device.get("name", "")
            
            # Проверяем наличие устройства в списке доступных
            for device in available_devices:
                # Проверяем совпадение по card и device
                if device.get("card") == selected_card and device.get("device") == selected_device:
                    return True
                
                # Дополнительно проверяем по имени, если есть USB в названии
                if "USB" in selected_name.upper() and "USB" in device.get("name", "").upper():
                    if (selected_name in device.get("name", "") or 
                        device.get("name", "") in selected_name):
                        return True
                    
            return False
        except Exception as e:
            sentry_sdk.capture_exception(e)
            if self.debug:
                print(f"Ошибка при проверке доступности устройства: {e}")
            # В случае ошибки предполагаем, что устройство недоступно
            return False 