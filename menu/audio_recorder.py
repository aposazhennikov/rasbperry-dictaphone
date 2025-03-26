#!/usr/bin/env python3
import os
import time
import threading
import datetime
import numpy as np
import sounddevice as sd
import soundfile as sf
import subprocess
import shutil
import sentry_sdk

class AudioRecorder:
    """Класс для записи аудио с микрофона, использующий sounddevice"""
    
    # Константы для настроек записи
    RATE = 44100  # Значение по умолчанию
    CHANNELS = 1
    
    # Список стандартных частот дискретизации в порядке предпочтения
    STANDARD_RATES = [44100, 48000, 32000, 22050, 16000, 8000]
    
    # Максимальная длительность записи в секундах (3 часа)
    MAX_RECORDING_DURATION = 3 * 60 * 60
    
    # Минимальное требуемое свободное место в байтах (1 GB)
    MIN_FREE_SPACE = 1 * 1024 * 1024 * 1024
    
    def __init__(self, base_dir="/home/aleks/records", debug=False, audio_device=None):
        """
        Инициализация рекордера
        
        Args:
            base_dir (str): Базовая директория для сохранения записей
            debug (bool): Режим отладки
            audio_device (dict): Информация об устройстве для записи
        """
        self.base_dir = base_dir
        self.debug = debug
        self.audio_data = []
        self.is_recording = False
        self.is_paused = False
        self.start_time = None
        self.pause_start_time = None
        self.total_pause_time = 0
        self.current_folder = None
        self.lock = threading.Lock()
        self.timer_callback = None
        self.timer_thread = None
        self.stop_timer = False
        self.output_file = None
        self.stream = None
        self.recording_thread = None
        self.save_and_stop = False  # Новый флаг для корректного сохранения при остановке
        
        # Устройство для записи
        self.audio_device = audio_device
        
        # Создаем базовую директорию, если она не существует
        self._create_base_directories()
        
    def _create_base_directories(self):
        """Создает базовые директории для записей, если они не существуют"""
        try:
            # Создаем базовую директорию, если она не существует
            os.makedirs(self.base_dir, exist_ok=True)
            
            # Создаем стандартные директории для категорий
            standard_folders = ["Заметки", "Идеи", "Важное", "Работа", "Личное"]
            for folder in standard_folders:
                folder_path = os.path.join(self.base_dir, folder)
                os.makedirs(folder_path, exist_ok=True)
        except Exception as e:
            sentry_sdk.capture_exception(e)
    
    def check_disk_space(self):
        """
        Проверяет наличие свободного места на диске
        
        Returns:
            tuple: (bool, int) - (достаточно ли места, свободное место в байтах)
        """
        try:
            # Для Linux
            disk_usage = shutil.disk_usage('/')
            free_space = disk_usage.free
            return free_space >= self.MIN_FREE_SPACE, free_space
        except Exception as e:
            sentry_sdk.capture_exception(e)
            # В случае ошибки считаем, что места достаточно
            return True, None
    
    def set_audio_device(self, device):
        """
        Устанавливает устройство для записи
        
        Args:
            device (dict): Словарь с информацией об устройстве
        """
        try:
            self.audio_device = device
        except Exception as e:
            sentry_sdk.capture_exception(e)
    
    def start_recording(self, folder):
        """
        Начинает запись аудио в указанную папку
        
        Args:
            folder (str): Папка для сохранения записи
            
        Returns:
            bool: True, если запись успешно начата, False в противном случае
        """
        with self.lock:
            if self.is_recording:
                return False
            
            try:
                # Проверяем наличие свободного места
                has_space, free_space = self.check_disk_space()
                if not has_space:
                    # Запись все равно начнем, обработчик сам отобразит предупреждение
                    pass
                
                self.current_folder = folder
                self.is_paused = False
                self.total_pause_time = 0
                self.audio_data = []
                
                # Генерируем имя файла для записи
                filename = self._generate_filename()
                folder_path = os.path.join(self.base_dir, folder)
                self.output_file = os.path.join(folder_path, filename)
                
                # Устанавливаем флаги записи
                self.is_recording = True
                self.start_time = time.time()
                self.stop_timer = False
                
                # Запускаем запись в отдельном потоке
                self.recording_thread = threading.Thread(target=self._record_audio)
                self.recording_thread.daemon = True
                self.recording_thread.start()
                
                # Запускаем таймер в отдельном потоке
                self.timer_thread = threading.Thread(target=self._update_timer)
                self.timer_thread.daemon = True
                self.timer_thread.start()
                
                # Запускаем монитор длительности записи
                self.duration_monitor_thread = threading.Thread(target=self._monitor_recording_duration)
                self.duration_monitor_thread.daemon = True
                self.duration_monitor_thread.start()
                
                return True
            except Exception as e:
                sentry_sdk.capture_exception(e)
                self._clean_up()
                return False
                
    def _monitor_recording_duration(self):
        """Мониторит длительность записи и автоматически останавливает при превышении максимальной длительности"""
        try:
            while self.is_recording:
                elapsed_time = self.get_elapsed_time()
                
                # Если превышена максимальная длительность записи
                if elapsed_time >= self.MAX_RECORDING_DURATION:
                    # Останавливаем запись
                    self.auto_stop_recording()
                    break
                    
                # Проверяем каждую секунду
                time.sleep(1)
        except Exception as e:
            sentry_sdk.capture_exception(e)
    
    def auto_stop_recording(self):
        """
        Автоматически останавливает запись при достижении максимальной длительности
        
        Returns:
            str: Путь к сохраненному файлу или None в случае ошибки
        """
        # Используем существующий метод stop_recording, но в другом потоке
        threading.Thread(target=self.stop_recording).start()
        
        # Возвращаем None, так как путь будет возвращен в методе stop_recording
        return None
    
    def _get_supported_sample_rate(self, device_id):
        """
        Определяет поддерживаемую устройством частоту дискретизации
        
        Args:
            device_id (str): Идентификатор устройства
            
        Returns:
            int: Поддерживаемая частота дискретизации
        """
        try:
            # Пробуем получить информацию об устройстве
            device_info = sd.query_devices(device_id, 'input')
            if self.debug:
                print(f"Информация об устройстве: {device_info}")
            
            # Проверяем, есть ли информация о поддерживаемых частотах
            if 'default_samplerate' in device_info:
                default_rate = int(device_info['default_samplerate'])
                if self.debug:
                    print(f"Используем стандартную частоту устройства: {default_rate} Гц")
                return default_rate
            
            # Если нет информации, пробуем стандартные частоты
            for rate in self.STANDARD_RATES:
                try:
                    if self.debug:
                        print(f"Пробуем частоту дискретизации: {rate} Гц")
                    # Проверяем работоспособность частоты, открывая тестовый стрим
                    test_stream = sd.InputStream(samplerate=rate, channels=self.CHANNELS, device=device_id)
                    test_stream.close()
                    if self.debug:
                        print(f"Частота {rate} Гц поддерживается устройством")
                    return rate
                except Exception as e:
                    if self.debug:
                        print(f"Частота {rate} Гц не поддерживается: {e}")
                    continue
            
            # Если ни одна из стандартных частот не подходит, возвращаем минимальную
            if self.debug:
                print(f"Ни одна из стандартных частот не поддерживается, используем 8000 Гц")
            return 8000
        except Exception as e:
            error_msg = f"Ошибка при определении поддерживаемой частоты: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            # В случае ошибки используем самую низкую стандартную частоту
            return 8000
    
    def _record_audio(self):
        """Записывает аудио в отдельном потоке"""
        try:
            def callback(indata, frames, time, status):
                if not self.is_paused and self.is_recording:
                    try:
                        self.audio_data.append(indata.copy())
                    except Exception as e:
                        sentry_sdk.capture_exception(e)
            
            # Подготавливаем параметры устройства для записи
            device_params = {}
            sample_rate = self.RATE
            
            # ПРИНУДИТЕЛЬНОЕ ИСПОЛЬЗОВАНИЕ USB МИКРОФОНА
            if self.audio_device and not self.audio_device.get("is_built_in", True):
                try:
                    import sounddevice as sd
                    
                    # Вариант 1: Пробуем использовать sd_index
                    if "sd_index" in self.audio_device and self.audio_device["sd_index"] is not None:
                        sd_index = self.audio_device["sd_index"]
                        device_info = sd.query_devices(sd_index)
                        if device_info and device_info['max_input_channels'] > 0:
                            device_params["device"] = sd_index
                            sample_rate = int(device_info.get("default_samplerate", self.RATE))
                    
                    # Вариант 2: Если sd_index нет или не работает, ищем по имени
                    if "device" not in device_params:
                        for i, device in enumerate(sd.query_devices()):
                            if device['max_input_channels'] > 0 and (
                                "USB" in device['name'] or 
                                (self.audio_device.get('name') and self.audio_device['name'] in device['name'])
                            ):
                                device_params["device"] = i
                                sample_rate = int(device.get("default_samplerate", self.RATE))
                                break
                    
                    # Вариант 3: Если предыдущие не сработали, используем ALSA hw путь
                    if "device" not in device_params:
                        try:
                            card_num = self.audio_device['card']
                            device_num = self.audio_device['device']
                            device_id = f"hw:{card_num},{device_num}"
                            device_params["device"] = device_id
                        except Exception:
                            pass
                            
                except Exception:
                    # Если все попытки не удались, используем ALSA hw путь
                    try:
                        card_num = self.audio_device['card']
                        device_num = self.audio_device['device']
                        device_id = f"hw:{card_num},{device_num}"
                        device_params["device"] = device_id
                    except Exception:
                        pass
            # Для встроенного микрофона
            elif self.audio_device:
                try:
                    device_id = f"hw:{self.audio_device['card']},{self.audio_device['device']}"
                    device_params["device"] = device_id
                except Exception:
                    pass
            
            # Запускаем поток записи
            with sd.InputStream(samplerate=sample_rate, channels=self.CHANNELS, callback=callback, **device_params):
                # Продолжаем запись пока флаг is_recording установлен
                while self.is_recording:
                    time.sleep(0.1)
            
            # Сохраняем запись при необходимости
            if self.save_and_stop:
                try:
                    if self.audio_data and len(self.audio_data) > 0:
                        audio_data_concat = np.concatenate(self.audio_data)
                        sf.write(self.output_file, audio_data_concat, sample_rate)
                        
                        # Проверяем, что файл создан
                        if os.path.exists(self.output_file):
                            return self.output_file
                        else:
                            return None
                    else:
                        return None
                except Exception as e:
                    sentry_sdk.capture_exception(e)
                    return None
            return None
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return None
    
    def pause_recording(self):
        """
        Приостанавливает запись
        
        Returns:
            bool: True, если запись успешно приостановлена, иначе False
        """
        with self.lock:
            if not self.is_recording or self.is_paused:
                return False
                
            try:
                # Устанавливаем флаг паузы и время паузы
                self.is_paused = True
                self.pause_start_time = time.time()
                
                return True
            except Exception as e:
                sentry_sdk.capture_exception(e)
                return False
    
    def resume_recording(self):
        """
        Возобновляет запись после паузы
        
        Returns:
            bool: True, если запись успешно возобновлена, иначе False
        """
        with self.lock:
            if not self.is_recording or not self.is_paused:
                return False
                
            try:
                # Обновляем общее время паузы
                if self.pause_start_time:
                    self.total_pause_time += time.time() - self.pause_start_time
                    self.pause_start_time = None
                
                # Снимаем флаг паузы
                self.is_paused = False
                
                return True
            except Exception as e:
                sentry_sdk.capture_exception(e)
                return False
    
    def stop_recording(self):
        """
        Останавливает запись и сохраняет аудиофайл
        
        Returns:
            str: Путь к сохраненному файлу или None в случае ошибки
        """
        with self.lock:
            if not self.is_recording:
                return None
            
            try:
                # Устанавливаем флаг для сохранения перед остановкой
                self.save_and_stop = True
                
                # Останавливаем запись
                self.is_recording = False
                self.is_paused = False
                self.stop_timer = True
                
                # Ждем завершения потока записи и сохранения файла
                if self.recording_thread and self.recording_thread.is_alive():
                    self.recording_thread.join(10.0)  # Ждем не более 10 секунд
                
                # Проверяем, был ли файл создан
                if os.path.exists(self.output_file):
                    return self.output_file
                else:
                    return None
            except Exception as e:
                sentry_sdk.capture_exception(e)
                return None
            finally:
                self.save_and_stop = False  # Сбрасываем флаг
                self._clean_up()
    
    def cancel_recording(self):
        """
        Отменяет запись без сохранения
        
        Returns:
            bool: True, если запись успешно отменена, иначе False
        """
        with self.lock:
            if not self.is_recording:
                return False
                
            try:
                # Останавливаем запись
                self.is_recording = False
                self.stop_timer = True
                
                # Очищаем ресурсы
                self._clean_up()
                
                return True
            except Exception as e:
                sentry_sdk.capture_exception(e)
                return False
    
    def get_elapsed_time(self):
        """
        Возвращает время записи в секундах (без учета пауз)
        
        Returns:
            float: Время записи в секундах
        """
        try:
            if not self.start_time:
                return 0
                
            elapsed = time.time() - self.start_time
            
            # Вычитаем общее время паузы
            elapsed -= self.total_pause_time
            
            # Если запись на паузе, вычитаем текущее время паузы
            if self.is_paused and self.pause_start_time:
                elapsed -= (time.time() - self.pause_start_time)
                
            return max(0, elapsed)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return 0
    
    def set_timer_callback(self, callback):
        """
        Устанавливает функцию обратного вызова для обновления таймера
        
        Args:
            callback (callable): Функция, которая будет вызываться с текущим временем записи
        """
        self.timer_callback = callback
    
    def _update_timer(self):
        """Обновляет таймер записи в отдельном потоке"""
        try:
            while not self.stop_timer and self.is_recording:
                if self.timer_callback:
                    elapsed_time = self.get_elapsed_time()
                    self.timer_callback(elapsed_time)
                
                time.sleep(0.1)
        except Exception as e:
            sentry_sdk.capture_exception(e)
    
    def _generate_filename(self):
        """
        Генерирует имя файла для записи на основе текущей даты и времени
        
        Returns:
            str: Имя файла в формате 'YYYY-MM-DD_HH-MM-SS.wav'
        """
        now = datetime.datetime.now()
        return now.strftime("%Y-%m-%d_%H-%M-%S.wav")
    
    def _clean_up(self):
        """Очищает ресурсы после записи"""
        self.audio_data = []
        self.is_recording = False
        self.is_paused = False
        self.start_time = None
        self.pause_start_time = None
        self.total_pause_time = 0
    
    def is_active(self):
        """
        Проверяет, активна ли запись
        
        Returns:
            bool: True, если запись активна, иначе False
        """
        return self.is_recording
    
    def is_on_pause(self):
        """
        Проверяет, приостановлена ли запись
        
        Returns:
            bool: True, если запись приостановлена, иначе False
        """
        return self.is_paused
    
    def get_current_folder(self):
        """
        Возвращает текущую папку для записи
        
        Returns:
            str: Имя папки или None, если запись не активна
        """
        return self.current_folder if self.is_recording else None 