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
    
    # Удаляем статическую карту устройств микрофонов, теперь они будут определяться динамически
    # Константы для настроек записи
    RATE = 44100
    CHANNELS = 1
    
    # Максимальная длительность записи в секундах (3 часа)
    MAX_RECORDING_DURATION = 3 * 60 * 60
    
    # Минимальное требуемое свободное место в байтах (1 GB)
    MIN_FREE_SPACE = 1 * 1024 * 1024 * 1024
    
    # Маркеры для определения микрофонов
    BUILT_IN_MIC_MARKER = "USB Composite Device"  # Маркер встроенного микрофона
    USB_MIC_MARKER = "(LCS) USB Audio Device"     # Маркер USB микрофона
    
    def __init__(self, base_dir="/home/aleks/records", debug=False, settings_manager=None):
        """
        Инициализация рекордера
        
        Args:
            base_dir (str): Базовая директория для сохранения записей
            debug (bool): Режим отладки
            settings_manager: Ссылка на менеджер настроек для получения настроек микрофона
        """
        self.base_dir = base_dir
        self.debug = debug
        self.settings_manager = settings_manager
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
        
        # Создаем базовую директорию, если она не существует
        self._create_base_directories()
        
        if self.debug:
            print("AudioRecorder инициализирован")
        
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
                
            if self.debug:
                print(f"Созданы базовые директории в {self.base_dir}")
        except Exception as e:
            error_msg = f"Ошибка при создании базовых директорий: {e}"
            print(error_msg)
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
            
            if self.debug:
                print(f"Свободное место на диске: {free_space / (1024*1024*1024):.2f} GB")
                
            return free_space >= self.MIN_FREE_SPACE, free_space
        except Exception as e:
            error_msg = f"Ошибка при проверке свободного места: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            # В случае ошибки считаем, что места достаточно
            return True, None
    
    def start_recording(self, folder):
        """
        Начинает запись аудио в указанную папку
        
        Args:
            folder (str): Папка для сохранения записи (A, B или C)
            
        Returns:
            bool: True, если запись успешно начата, False в противном случае
        """
        with self.lock:
            if self.is_recording:
                if self.debug:
                    print("Запись уже идёт")
                return False
            
            try:
                # Проверяем наличие свободного места
                has_space, free_space = self.check_disk_space()
                if not has_space:
                    warning_msg = f"Недостаточно свободного места на диске: {free_space / (1024*1024*1024):.2f} GB"
                    print(warning_msg)
                    # Если метод вернул False, обработчик должен отобразить предупреждение
                    # но запись все равно начнем
                
                self.current_folder = folder
                self.is_paused = False
                self.total_pause_time = 0
                self.audio_data = []
                
                # Генерируем имя файла для записи
                filename = self._generate_filename()
                folder_path = os.path.join(self.base_dir, folder)
                self.output_file = os.path.join(folder_path, filename)
                
                if self.debug:
                    print(f"Начинаем запись в файл: {self.output_file}")
                
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
                
                if self.debug:
                    print(f"Запись начата в папку {folder}")
                
                return True
            except Exception as e:
                error_msg = f"Ошибка при начале записи: {e}"
                print(error_msg)
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
                    warning_msg = f"Достигнут максимальный порог записи {self.MAX_RECORDING_DURATION / 3600:.1f} часа"
                    print(warning_msg)
                    
                    # Останавливаем запись
                    self.auto_stop_recording()
                    break
                    
                # Проверяем каждую секунду
                time.sleep(1)
        except Exception as e:
            error_msg = f"Ошибка в мониторе длительности записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def auto_stop_recording(self):
        """
        Автоматически останавливает запись при достижении максимальной длительности
        
        Returns:
            str: Путь к сохраненному файлу или None в случае ошибки
        """
        print("Автоматическая остановка записи из-за превышения максимальной длительности")
        # Используем существующий метод stop_recording, но в другом потоке
        threading.Thread(target=self.stop_recording).start()
        
        # Возвращаем None, так как путь будет возвращен в методе stop_recording
        return None
    
    def _record_audio(self):
        """Записывает аудио в отдельном потоке"""
        try:
            def callback(indata, frames, time, status):
                if not self.is_paused and self.is_recording:
                    try:
                        self.audio_data.append(indata.copy())
                        if status and self.debug:
                            print(f"Статус записи: {status}")
                    except Exception as e:
                        error_msg = f"Ошибка при сохранении аудиоданных: {e}"
                        print(error_msg)
                        sentry_sdk.capture_exception(e)
            
            # Получаем ID устройства микрофона из настроек
            device_id = self._get_selected_microphone_device()
            
            # Определяем поддерживаемую частоту дискретизации для устройства
            sample_rate = self._get_supported_sample_rate(device_id)
            
            # Определяем количество каналов для устройства
            channels = self._get_supported_channels(device_id)
            
            if self.debug:
                print(f"Запуск записи с микрофона device_id={device_id}, sample_rate={sample_rate}, channels={channels}")
            
            # Запускаем поток записи с выбранным микрофоном, частотой дискретизации и количеством каналов
            with sd.InputStream(samplerate=sample_rate, channels=channels, callback=callback, device=device_id):
                while self.is_recording:
                    time.sleep(0.1)
            
            if self.debug:
                print("Поток записи завершен нормально")
                
        except Exception as e:
            error_msg = f"Ошибка в потоке записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            self.is_recording = False
    
    def _get_selected_microphone_device(self):
        """
        Определяет ID устройства микрофона на основе настроек.
        Использует непосредственно идентификаторы sounddevice.
        
        Returns:
            int or str: ID устройства для sounddevice
        """
        try:
            # Получаем список устройств sounddevice
            if self.debug:
                print("Получение списка устройств ввода sounddevice:")
                for i, device in enumerate(sd.query_devices()):
                    print(f"Device {i}: {device['name']} - {device}")
            
            # Если нет менеджера настроек, используем встроенный микрофон по умолчанию
            if not self.settings_manager:
                if self.debug:
                    print("Нет доступа к настройкам, используем встроенный микрофон по умолчанию")
                return self._find_sounddevice_mic(self.BUILT_IN_MIC_MARKER)
            
            # Получаем настройку микрофона
            microphone_setting = self.settings_manager.get_microphone()
            
            if self.debug:
                print(f"Настройка микрофона из settings.json: {microphone_setting}")
            
            # Если выбран USB микрофон
            if microphone_setting == "usb":
                # Находим USB микрофон в списке устройств sounddevice
                usb_mic_id = self._find_sounddevice_mic(self.USB_MIC_MARKER)
                
                # Если найден, используем его
                if usb_mic_id is not None:
                    if self.debug:
                        print(f"Найден USB микрофон, используем device_id={usb_mic_id}")
                    return usb_mic_id
                
                # Если USB микрофон не найден, используем встроенный
                if self.debug:
                    print("USB микрофон выбран в настройках, но не подключен. Используем встроенный микрофон.")
                return self._find_sounddevice_mic(self.BUILT_IN_MIC_MARKER)
            
            # Если выбран встроенный микрофон
            return self._find_sounddevice_mic(self.BUILT_IN_MIC_MARKER)
            
        except Exception as e:
            error_msg = f"Ошибка при определении устройства микрофона: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            # По умолчанию используем устройство по умолчанию
            return None  # None означает использовать устройство по умолчанию
    
    def _find_sounddevice_mic(self, marker):
        """
        Находит микрофон в списке устройств sounddevice по маркеру
        
        Args:
            marker (str): Маркер для поиска в названии устройства
            
        Returns:
            int or str: ID устройства для sounddevice или None, если не найдено
        """
        try:
            # Получаем все устройства
            devices = sd.query_devices()
            
            # Ищем входное устройство с совпадающим маркером
            for i, device in enumerate(devices):
                # Проверяем, что это входное устройство
                if device.get('max_input_channels', 0) > 0:
                    # Проверяем, содержит ли имя устройства маркер
                    device_name = device.get('name', '')
                    if marker in device_name:
                        if self.debug:
                            print(f"Найден микрофон с маркером '{marker}': device_id={i}, name={device_name}")
                        return i  # Возвращаем индекс устройства
            
            # Если не нашли устройство с маркером, ищем любое входное устройство
            for i, device in enumerate(devices):
                if device.get('max_input_channels', 0) > 0:
                    if self.debug:
                        print(f"Используем первое доступное входное устройство: device_id={i}, name={device.get('name', '')}")
                    return i
            
            # Если не нашли ни одного входного устройства, возвращаем устройство по умолчанию
            if self.debug:
                print(f"Не найдено входных устройств, используем устройство по умолчанию")
            return None  # None означает использовать устройство по умолчанию
        except Exception as e:
            error_msg = f"Ошибка при поиске микрофона: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return None
    
    def _check_usb_microphone_connected(self):
        """
        Проверяет, подключен ли USB микрофон
        
        Returns:
            bool: True если USB микрофон подключен, иначе False
        """
        return self._find_sounddevice_mic(self.USB_MIC_MARKER) is not None
    
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
                
                if self.debug:
                    print(f"Запись приостановлена. Время записи: {self.get_elapsed_time():.1f} сек")
                    
                return True
            except Exception as e:
                error_msg = f"Ошибка при приостановке записи: {e}"
                print(error_msg)
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
                # Обновляем общее время на паузе
                pause_duration = time.time() - self.pause_start_time
                self.total_pause_time += pause_duration
                
                # Сбрасываем флаг паузы
                self.is_paused = False
                
                if self.debug:
                    print(f"Запись возобновлена. Пауза длилась {pause_duration:.1f} сек")
                    
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
                if self.debug:
                    print("Невозможно остановить запись: запись не активна")
                return None
                
            try:
                if self.debug:
                    print("Останавливаем запись...")
                
                # Останавливаем запись
                self.is_recording = False
                
                # Ждем завершения потока записи
                if self.recording_thread and self.recording_thread.is_alive():
                    self.recording_thread.join(timeout=2)
                
                # Останавливаем таймер
                self.stop_timer = True
                if self.timer_thread and self.timer_thread.is_alive():
                    self.timer_thread.join(timeout=1)
                
                # Если нет данных для сохранения
                if not self.audio_data:
                    warning_msg = "Нет данных для сохранения"
                    print(warning_msg)
                    
                    return None
                
                try:
                    # Создаем директорию для сохранения, если она не существует
                    os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
                    
                    # Объединяем все части записи
                    if self.debug:
                        print(f"Сохраняем запись в файл: {self.output_file}")
                        print(f"Количество блоков данных: {len(self.audio_data)}")
                    
                    data = np.concatenate(self.audio_data, axis=0)
                    
                    # Проверяем свободное место перед сохранением
                    required_space = data.nbytes + 1024*1024  # Размер данных + 1MB запаса
                    has_space, free_space = self.check_disk_space()
                    
                    if free_space and free_space < required_space:
                        warning_msg = f"Критически мало места на диске: {free_space / (1024*1024*1024):.2f} GB. Требуется {required_space / (1024*1024*1024):.2f} GB"
                        print(warning_msg)
                        sentry_sdk.capture_message(warning_msg, level="warning")
                    
                    # Получаем фактическую частоту дискретизации и количество каналов из устройства
                    device_id = self._get_selected_microphone_device()
                    rate = self._get_supported_sample_rate(device_id)
                    
                    # Преобразуем многоканальные данные в моно для сохранения, если нужно
                    if data.shape[1] > 1:
                        if self.debug:
                            print(f"Преобразуем {data.shape[1]} каналов в моно для сохранения")
                        # Усредняем все каналы для получения моно
                        data = np.mean(data, axis=1, keepdims=True)
                    
                    # Записываем файл с правильной частотой дискретизации
                    sf.write(self.output_file, data, rate)
                    
                    if self.debug:
                        print(f"Запись успешно сохранена в файл: {self.output_file} с частотой {rate} Гц")
                    
                    # Возвращаем путь к сохраненному файлу
                    saved_file = self.output_file
                    
                    # Очищаем ресурсы
                    self._clean_up()
                    
                    return saved_file
                    
                except OSError as e:
                    error_msg = f"Ошибка ввода-вывода при сохранении файла: {e}"
                    print(error_msg)
                    sentry_sdk.capture_exception(e)
                    self._clean_up()
                    return None
                    
            except Exception as e:
                error_msg = f"Ошибка при остановке и сохранении записи: {e}"
                print(error_msg)
                sentry_sdk.capture_exception(e)
                self._clean_up()
                return None
    
    def cancel_recording(self):
        """
        Отменяет запись без сохранения
        
        Returns:
            bool: True, если запись успешно отменена
        """
        with self.lock:
            if not self.is_recording:
                return False
                
            try:
                if self.debug:
                    print("Отменяем запись без сохранения")
                
                # Останавливаем запись
                self.is_recording = False
                
                # Ждем завершения потока записи
                if self.recording_thread and self.recording_thread.is_alive():
                    self.recording_thread.join(timeout=2)
                
                # Останавливаем таймер
                self.stop_timer = True
                if self.timer_thread and self.timer_thread.is_alive():
                    self.timer_thread.join(timeout=1)
                
                # Очищаем ресурсы
                self._clean_up()
                
                return True
            except Exception as e:
                error_msg = f"Ошибка при отмене записи: {e}"
                print(error_msg)
                sentry_sdk.capture_exception(e)
                self._clean_up()
                return False
    
    def get_elapsed_time(self):
        """
        Возвращает прошедшее время записи с учетом пауз
        
        Returns:
            float: Время записи в секундах
        """
        if not self.is_recording:
            return 0
            
        current_time = time.time()
        
        if self.is_paused:
            # Если на паузе, считаем время до начала паузы
            elapsed = self.pause_start_time - self.start_time - self.total_pause_time
        else:
            # Иначе считаем текущее время
            elapsed = current_time - self.start_time - self.total_pause_time
            
        return max(0, elapsed)
    
    def set_timer_callback(self, callback):
        """
        Устанавливает функцию обратного вызова для обновления времени
        
        Args:
            callback (callable): Функция, принимающая один аргумент (время в секундах)
        """
        self.timer_callback = callback
    
    def _update_timer(self):
        """Обновляет таймер и вызывает callback"""
        last_time = 0
        
        while self.is_recording and not self.stop_timer:
            current_time = self.get_elapsed_time()
            
            # Вызываем callback только если время изменилось
            if int(current_time) != int(last_time) and self.timer_callback:
                self.timer_callback(current_time)
                last_time = current_time
                
            time.sleep(0.1)
    
    def _generate_filename(self):
        """
        Генерирует имя файла для записи на основе текущей даты и времени
        
        Returns:
            str: Имя файла
        """
        now = datetime.datetime.now()
        return f"record_{now.strftime('%Y-%m-%d_%H-%M-%S')}.wav"
    
    def _clean_up(self):
        """Освобождает ресурсы"""
        self.is_recording = False
        self.is_paused = False
        self.audio_data = []
        self.output_file = None
        self.current_folder = None
    
    def is_active(self):
        """
        Проверяет, активна ли запись
        
        Returns:
            bool: True, если запись активна
        """
        return self.is_recording
    
    def is_on_pause(self):
        """
        Проверяет, находится ли запись на паузе
        
        Returns:
            bool: True, если запись на паузе
        """
        return self.is_recording and self.is_paused
    
    def get_current_folder(self):
        """
        Возвращает текущую папку записи
        
        Returns:
            str: Имя папки или None, если запись не активна
        """
        return self.current_folder if self.is_recording else None
    
    def _get_supported_sample_rate(self, device_id):
        """
        Определяет поддерживаемую частоту дискретизации для устройства
        
        Args:
            device_id (int): ID устройства
            
        Returns:
            int: Поддерживаемая частота дискретизации
        """
        try:
            # Стандартные частоты дискретизации для проверки
            standard_rates = [48000, 44100, 32000, 22050, 16000, 8000]
            
            # Получаем информацию об устройстве
            device_info = sd.query_devices(device_id, 'input')
            
            if self.debug:
                print(f"Информация об устройстве {device_id}:")
                print(device_info)
            
            # Если устройство имеет информацию о доступных частотах дискретизации
            if 'default_samplerate' in device_info:
                default_rate = device_info['default_samplerate']
                if self.debug:
                    print(f"Устройство {device_id} имеет частоту дискретизации по умолчанию: {default_rate}")
                return int(default_rate)
            
            # Пробуем стандартные частоты дискретизации
            for rate in standard_rates:
                try:
                    # Проверяем возможность открытия устройства с данной частотой
                    sd.check_input_settings(device=device_id, samplerate=rate, channels=self.CHANNELS)
                    if self.debug:
                        print(f"Устройство {device_id} поддерживает частоту {rate} Гц")
                    return rate
                except Exception as check_error:
                    if self.debug:
                        print(f"Устройство {device_id} не поддерживает частоту {rate} Гц: {check_error}")
                    continue
            
            # Если ни одна из стандартных частот не подходит, пробуем любую возможную
            try:
                test_stream = sd.InputStream(device=device_id, channels=self.CHANNELS)
                rate = int(test_stream.samplerate)
                test_stream.close()
                if self.debug:
                    print(f"Использую доступную частоту {rate} Гц для устройства {device_id}")
                return rate
            except Exception as stream_error:
                if self.debug:
                    print(f"Не удалось определить частоту для устройства {device_id}: {stream_error}")
            
            # Если все методы не сработали, возвращаем стандартную частоту и надеемся на лучшее
            if self.debug:
                print(f"Использую стандартную частоту 48000 Гц для устройства {device_id}")
            return 48000
            
        except Exception as e:
            error_msg = f"Ошибка при определении частоты дискретизации: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            # Возвращаем 48000 как наиболее безопасную частоту
            return 48000
    
    def _get_supported_channels(self, device_id):
        """
        Определяет поддерживаемое количество каналов для устройства
        
        Args:
            device_id (int): ID устройства
            
        Returns:
            int: Поддерживаемое количество каналов
        """
        try:
            # Получаем информацию об устройстве
            device_info = sd.query_devices(device_id, 'input')
            
            if self.debug:
                print(f"Получение информации о каналах для устройства {device_id}:")
                print(f"Устройство: {device_info}")
            
            # Проверяем, имеет ли устройство информацию о каналах
            if 'max_input_channels' in device_info:
                channels = device_info['max_input_channels']
                if self.debug:
                    print(f"Устройство {device_id} поддерживает {channels} каналов")
                # Убедимся, что количество каналов не менее 1
                return max(1, int(channels))
            
            # Если не удалось определить количество каналов, используем значение по умолчанию
            if self.debug:
                print(f"Не удалось определить количество каналов для устройства {device_id}, используем CHANNELS={self.CHANNELS}")
            return self.CHANNELS
            
        except Exception as e:
            error_msg = f"Ошибка при определении количества каналов: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            # Возвращаем стандартное значение в случае ошибки
            return self.CHANNELS 