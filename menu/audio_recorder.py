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
            if self.debug:
                device_name = device.get("name", "Неизвестное устройство")
                if device.get("is_built_in", False) or "USB Composite Device" in device_name:
                    device_name = "Встроенный микрофон в пульте"
                print(f"Устанавливаем устройство записи: {device_name}")
            
            # Создаем копию устройства для избежания проблем с изменением исходного объекта
            self.audio_device = device.copy() if device else None
            
            # Если запись активна и на паузе, нужно будет перезапустить стрим при возобновлении
            if self.is_recording and self.is_paused:
                self.need_reset_stream = True
        except Exception as e:
            error_msg = f"Ошибка при установке устройства для записи: {e}"
            print(error_msg)
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
            device_id (str или int): Идентификатор устройства
            
        Returns:
            int: Поддерживаемая частота дискретизации
        """
        try:
            # Импортируем sounddevice в начале функции, чтобы он был доступен во всей функции
            import sounddevice as sd
            
            # Если device_id - числовой индекс sounddevice
            if isinstance(device_id, int) or (isinstance(device_id, str) and device_id.isdigit()):
                try:
                    device_info = sd.query_devices(int(device_id))
                    if self.debug:
                        print(f"Информация об устройстве (по индексу {device_id}): {device_info}")
                    
                    if 'default_samplerate' in device_info:
                        default_rate = int(device_info['default_samplerate'])
                        if self.debug:
                            print(f"Используем стандартную частоту устройства: {default_rate} Гц")
                        return default_rate
                except Exception as sd_error:
                    if self.debug:
                        print(f"Ошибка при получении информации по индексу {device_id}: {sd_error}")
                    # Продолжаем с другими методами
            
            # Пробуем получить информацию об устройстве
            try:
                device_info = sd.query_devices(device_id, 'input')
                if self.debug:
                    print(f"Информация об устройстве: {device_info}")
                
                # Проверяем, есть ли информация о поддерживаемых частотах
                if 'default_samplerate' in device_info:
                    default_rate = int(device_info['default_samplerate'])
                    if self.debug:
                        print(f"Используем стандартную частоту устройства: {default_rate} Гц")
                    return default_rate
            except Exception as e:
                if self.debug:
                    print(f"Ошибка при получении информации об устройстве {device_id}: {e}")
                # Продолжаем с перебором стандартных частот
            
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
            
            # Если устройство - None, значит используется устройство по умолчанию
            if device_id is None:
                try:
                    # Получаем устройство по умолчанию и его частоту
                    device_info = sd.query_devices(kind='input')
                    if 'default_samplerate' in device_info:
                        default_rate = int(device_info['default_samplerate'])
                        if self.debug:
                            print(f"Используем частоту устройства по умолчанию: {default_rate} Гц")
                        return default_rate
                except Exception as default_error:
                    if self.debug:
                        print(f"Ошибка при получении частоты устройства по умолчанию: {default_error}")
            
            # Если всё не сработало, используем стандартную частоту
            if self.debug:
                print(f"Используем стандартную частоту 44100 Гц")
            return 44100
        except Exception as e:
            error_msg = f"Ошибка при определении поддерживаемой частоты: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            # В случае ошибки используем самую распространенную частоту
            return 44100
    
    def _record_audio(self):
        """Записывает аудио в отдельном потоке"""
        try:
            # Импортируем sounddevice в начале функции, чтобы он был доступен во всей функции
            import sounddevice as sd
            
            def callback(indata, frames, time, status):
                if not self.is_paused and self.is_recording:
                    try:
                        self.audio_data.append(indata.copy())
                    except Exception as e:
                        sentry_sdk.capture_exception(e)
            
            # Определяем параметры устройства
            device_id = None
            device_name = None
            
            # Если указано устройство, определяем его ID для sounddevice
            if self.audio_device:
                # Проверяем, есть ли sd_index в устройстве
                if "sd_index" in self.audio_device and self.audio_device["sd_index"] is not None:
                    device_id = self.audio_device["sd_index"]
                    if self.debug:
                        print(f"Используем индекс sounddevice: {device_id}")
                else:
                    # Пробуем найти устройство по имени с помощью sounddevice
                    try:
                        device_list = sd.query_devices()
                        device_name = self.audio_device.get("name", "")
                        card_num = self.audio_device.get("card")
                        is_built_in = self.audio_device.get("is_built_in", False)
                        
                        # Для внешних USB устройств ищем по фрагментам имени
                        if not is_built_in and "USB" in device_name.upper():
                            for i, device in enumerate(device_list):
                                if (device['max_input_channels'] > 0 and 
                                    ("USB" in device['name'].upper()) and
                                    (device_name in device['name'] or 
                                     any(keyword in device['name'] for keyword in ["LCS", "USB Audio Device"]))):
                                    device_id = i
                                    if self.debug:
                                        print(f"Найдено USB устройство по имени: {device['name']}, индекс: {i}")
                                    break
                        
                        # Для встроенного микрофона ищем по ключевым словам
                        if (is_built_in or "USB Composite Device" in device_name) and device_id is None:
                            # Если это встроенный микрофон, ищем устройство с "USB Composite Device" или первое доступное
                            for i, device in enumerate(device_list):
                                if device['max_input_channels'] > 0:
                                    if "USB Composite Device" in device['name'] or "USB Audio" in device['name']:
                                        device_id = i
                                        if self.debug:
                                            print(f"Найден встроенный микрофон: {device['name']}, индекс: {i}")
                                        break
                    except Exception as find_error:
                        if self.debug:
                            print(f"Ошибка при поиске устройства по имени: {find_error}")
                        sentry_sdk.capture_exception(find_error)
                    
                    # Если всё ещё не найдено, используем формат ALSA
                    if device_id is None:
                        device_id = f"hw:{self.audio_device['card']},{self.audio_device['device']}"
                        if self.debug:
                            print(f"Используем ALSA устройство: {device_id}")
                
                # Сохраняем имя устройства для логов
                device_name = self.audio_device.get("name", "Неизвестное устройство")
                if self.audio_device.get("is_built_in", False) or "USB Composite Device" in device_name:
                    device_name = "Встроенный микрофон в пульте"
                elif "USB" in device_name:
                    if "(LCS)" in device_name:
                        device_name = "Внешний USB микрофон (LCS)"
                    else:
                        device_name = f"USB микрофон ({device_name})"
            
            if self.debug:
                print(f"Выбранное устройство для записи: {device_name}, ID: {device_id}")
                print(f"Текущий статус: recording={self.is_recording}, paused={self.is_paused}")
            
            # Если мы перезапускаем стрим из-за смены устройства во время паузы,
            # автоматически снимаем флаг паузы
            was_paused = self.is_paused
            if was_paused and hasattr(self, 'need_reset_stream') and self.need_reset_stream:
                if self.debug:
                    print("Автоматическое снятие флага паузы после перезапуска стрима")
                self.is_paused = False
            
            # Определяем поддерживаемую частоту дискретизации
            sample_rate = self._get_supported_sample_rate(device_id)
            
            if self.debug:
                print(f"Начинаем запись аудио с устройства {device_name} (ID: {device_id}) с частотой {sample_rate} Гц")
            
            # Пробуем создать стрим с указанными параметрами
            try:
                # Настраиваем sounddevice
                self.stream = sd.InputStream(
                    samplerate=sample_rate,
                    channels=self.CHANNELS,
                    callback=callback,
                    device=device_id
                )
                
                # Запускаем стрим
                with self.stream:
                    if self.debug:
                        print("Стрим запущен успешно")
                        
                    # Устанавливаем текущую частоту дискретизации
                    self.RATE = sample_rate
                    
                    # Если мы перезапустили стрим во время паузы и автоматически сняли эту паузу,
                    # возвращаем флаг паузы обратно, чтобы пользователь мог продолжить с этого состояния
                    if was_paused:
                        if self.debug:
                            print("Восстановление флага паузы после инициализации стрима")
                        self.is_paused = True
                    
                    # Ждем, пока запись не будет остановлена или установлен флаг save_and_stop
                    while self.is_recording and not self.save_and_stop:
                        time.sleep(0.1)
                    
                    # Если установлен флаг save_and_stop, сохраняем запись и выходим
                    if self.save_and_stop:
                        if self.debug:
                            print("Завершаем запись и сохраняем файл")
                            
                        self._save_recording()
                        
                        # Сбрасываем флаги
                        self.is_recording = False
                        self.is_paused = False
                        self.save_and_stop = False
            except Exception as stream_error:
                error_msg = f"Ошибка при создании стрима для записи: {stream_error}"
                print(error_msg)
                sentry_sdk.capture_exception(stream_error)
                
                # Пробуем с устройством по умолчанию
                try:
                    if self.debug:
                        print("Пробуем использовать устройство по умолчанию")
                    
                    # Создаем стрим с устройством по умолчанию
                    self.stream = sd.InputStream(
                        samplerate=sample_rate,
                        channels=self.CHANNELS,
                        callback=callback
                    )
                    
                    # Запускаем стрим
                    with self.stream:
                        if self.debug:
                            print("Стрим с устройством по умолчанию запущен")
                            
                        # Устанавливаем текущую частоту дискретизации
                        self.RATE = sample_rate
                        
                        # Ждем, пока запись не будет остановлена или установлен флаг save_and_stop
                        while self.is_recording and not self.save_and_stop:
                            time.sleep(0.1)
                        
                        # Если установлен флаг save_and_stop, сохраняем запись и выходим
                        if self.save_and_stop:
                            if self.debug:
                                print("Завершаем запись и сохраняем файл")
                                
                            self._save_recording()
                            
                            # Сбрасываем флаги
                            self.is_recording = False
                            self.is_paused = False
                            self.save_and_stop = False
                except Exception as default_stream_error:
                    error_msg = f"Ошибка при создании стрима с устройством по умолчанию: {default_stream_error}"
                    print(error_msg)
                    sentry_sdk.capture_exception(default_stream_error)
                    
                    # Уведомляем о проблеме
                    self.is_recording = False
                    self.is_paused = False
                
        except Exception as e:
            error_msg = f"Критическая ошибка в потоке записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
            # Сбрасываем флаги записи в случае ошибки
            self.is_recording = False
            self.is_paused = False
    
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
        Возобновляет приостановленную запись
        
        Returns:
            bool: True если запись успешно возобновлена, False в противном случае
        """
        with self.lock:
            if not self.is_recording or not self.is_paused:
                return False
            
            try:
                # Если нужно перезапустить стрим из-за смены устройства
                need_reset = getattr(self, 'need_reset_stream', False)
                
                if need_reset:
                    if self.debug:
                        print("Перезапускаем стрим из-за смены устройства")
                    
                    # Останавливаем текущий стрим, если он существует
                    if self.stream:
                        try:
                            self.stream.stop()
                            self.stream.close()
                        except Exception as stop_error:
                            if self.debug:
                                print(f"Ошибка при остановке стрима: {stop_error}")
                            # Продолжаем даже при ошибке
                    
                    # Проверяем, что аудио устройство установлено
                    if not self.audio_device:
                        if self.debug:
                            print("Аудио устройство не установлено, используем устройство по умолчанию")
                        # Можно установить устройство по умолчанию или вернуть ошибку
                    
                    # Создаем новый поток записи
                    self.recording_thread = threading.Thread(target=self._record_audio)
                    self.recording_thread.daemon = True
                    self.recording_thread.start()
                    
                    # Сбрасываем флаг перезапуска
                    self.need_reset_stream = False
                    
                    # Поскольку поток записи теперь перезапущен,
                    # не нужно снимать флаг паузы здесь, это сделает _record_audio
                    
                    # Рассчитываем время на паузе
                    if self.pause_start_time:
                        pause_time = time.time() - self.pause_start_time
                        self.total_pause_time += pause_time
                        self.pause_start_time = None
                    
                    # Просто возвращаем успех, actual unpausing будет выполнено в новом потоке
                    return True
                else:
                    # Стандартное возобновление записи
                    # Рассчитываем время на паузе
                    if self.pause_start_time:
                        pause_time = time.time() - self.pause_start_time
                        self.total_pause_time += pause_time
                        self.pause_start_time = None
                    
                    self.is_paused = False
                    
                    return True
            except Exception as e:
                error_msg = f"Ошибка при возобновлении записи: {e}"
                print(error_msg)
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
    
    def _save_recording(self):
        """Сохраняет записанные данные в файл"""
        try:
            if not self.audio_data or len(self.audio_data) == 0:
                if self.debug:
                    print("Нет данных для сохранения")
                return None
            
            if self.debug:
                print(f"Сохраняем запись в файл: {self.output_file}")
            
            # Объединяем все части записи
            audio_data_concat = np.concatenate(self.audio_data)
            
            # Сохраняем в файл с текущей частотой дискретизации
            sf.write(self.output_file, audio_data_concat, self.RATE)
            
            # Проверяем, что файл создан
            if os.path.exists(self.output_file):
                if self.debug:
                    print(f"Запись успешно сохранена: {self.output_file}")
                return self.output_file
            else:
                if self.debug:
                    print(f"Ошибка: файл не был создан")
                return None
        except Exception as e:
            error_msg = f"Ошибка при сохранении записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return None 