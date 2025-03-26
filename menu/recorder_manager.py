#!/usr/bin/env python3
import os
import time
import threading
from .audio_recorder import AudioRecorder
from .audio_device_manager import AudioDeviceManager
import subprocess
import sentry_sdk

class RecorderManager:
    """Класс для управления записью аудио и взаимодействия с пользовательским интерфейсом"""
    
    def __init__(self, tts_manager, base_dir="/home/aleks/records", debug=False, beep_sound_path="/home/aleks/main-sounds/beep.wav"):
        """
        Инициализация менеджера записи
        
        Args:
            tts_manager: Менеджер TTS для воспроизведения уведомлений
            base_dir (str): Базовая директория для сохранения записей
            debug (bool): Режим отладки
            beep_sound_path (str): Путь к звуковому файлу сигнала начала записи
        """
        try:
            self.tts_manager = tts_manager
            self.base_dir = base_dir
            self.debug = debug
            self.beep_sound_path = beep_sound_path
            self.settings_manager = None
            
            # Если у tts_manager есть ссылка на settings_manager, используем её
            if hasattr(tts_manager, 'settings_manager'):
                self.settings_manager = tts_manager.settings_manager
            
            # Создаем менеджер аудио устройств
            self.settings_file = "/home/aleks/cache_tts/settings.json"
            self.audio_device_manager = AudioDeviceManager(settings_file=self.settings_file, debug=debug)
            
            # Регистрируем колбэк для отключения устройства
            self.audio_device_manager.set_device_disconnected_callback(self._handle_device_disconnected)
            
            # Получаем выбранное устройство
            self.audio_device = self.audio_device_manager.get_selected_device()
            
            # Создаем рекордер с выбранным устройством
            self.recorder = AudioRecorder(base_dir=base_dir, debug=debug, audio_device=self.audio_device)
            
            # Колбэк для обновления информации о записи
            self.update_callback = None
            
            # Текущее время записи
            self.current_time = 0
            
            # Создаем директории для записей, если их нет
            self._create_directories()
            
            # Системные сообщения
            self.low_disk_space_warning = "Внимание, на устройстве осталось менее 1GB памяти, рекомендуется освободить память устройства"
            self.max_duration_warning = "Порог записи длительность 3 часа достигнут завершаю и сохраняю запись во избежание ошибок"
            
            # Запускаем мониторинг устройства записи
            self.start_device_monitoring()
            
            if self.debug:
                print(f"RecorderManager инициализирован с устройством: {self.audio_device}")
                
            # Регистрируем обработчик для системных сообщений
            self.recorder.set_timer_callback(self._timer_callback)
        except Exception as e:
            error_msg = f"Ошибка при инициализации RecorderManager: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def _create_directories(self):
        """Создает директории для записей"""
        try:
            if not os.path.exists(self.base_dir):
                if self.debug:
                    print(f"Создаём директорию для записей: {self.base_dir}")
                os.makedirs(self.base_dir)
                
            # Создаём поддиректории A, B, C
            for folder in ['A', 'B', 'C']:
                folder_path = os.path.join(self.base_dir, folder)
                if not os.path.exists(folder_path):
                    if self.debug:
                        print(f"Создаём директорию: {folder_path}")
                    os.makedirs(folder_path)
        except Exception as e:
            error_msg = f"Ошибка при создании директорий: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def start_device_monitoring(self):
        """Запускает мониторинг изменений устройства записи"""
        try:
            # Создаем поток для мониторинга
            self.device_monitoring_thread = threading.Thread(target=self._monitor_audio_device)
            self.device_monitoring_thread.daemon = True
            self.device_monitoring_thread.start()
            
            if self.debug:
                print("Запущен мониторинг устройства записи")
        except Exception as e:
            error_msg = f"Ошибка при запуске мониторинга устройства: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def _monitor_audio_device(self):
        """Функция мониторинга изменений устройства записи в отдельном потоке"""
        try:
            # Запоминаем текущее устройство
            current_device_card = self.audio_device.get("card")
            current_device_device = self.audio_device.get("device")
            
            while True:
                # Проверяем текущее устройство
                device = self.audio_device_manager.get_selected_device()
                
                # Если устройство изменилось, обновляем рекордер
                if (device.get("card") != current_device_card or 
                    device.get("device") != current_device_device):
                    
                    if self.debug:
                        print(f"Устройство записи изменилось на: {device}")
                    
                    # Обновляем локальное устройство
                    self.audio_device = device
                    
                    # Если рекордер существует, обновляем устройство
                    if self.recorder:
                        self.recorder.set_audio_device(device)
                    
                    # Обновляем запомненные значения
                    current_device_card = device.get("card")
                    current_device_device = device.get("device")
                
                # Проверяем каждые 0.5 секунды вместо 5 секунд
                time.sleep(0.5)
        except Exception as e:
            error_msg = f"Ошибка в мониторинге устройства записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def set_update_callback(self, callback):
        """
        Устанавливает функцию обратного вызова для обновления информации о записи
        
        Args:
            callback (callable): Функция, которая будет вызываться при обновлении информации
                                о статусе записи, времени и т.д.
        """
        self.update_callback = callback
    
    def _timer_callback(self, time_sec):
        """
        Обработчик обновления таймера записи
        
        Args:
            time_sec (float): Текущее время записи в секундах
        """
        try:
            self.current_time = time_sec
            
            # Форматируем время в удобный вид (MM:SS)
            formatted_time = self.get_formatted_time()
            
            # Вызываем колбэк обновления UI, если он установлен
            if self.update_callback:
                self.update_callback()
            
            # Озвучиваем время записи каждые 3 часа
            if int(time_sec) > 0 and int(time_sec) % 10800 == 0:
                self.announce_recording_time()
                
        except Exception as e:
            error_msg = f"Ошибка в обработчике таймера: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def start_recording(self, folder):
        """
        Начинает запись в указанную папку
        
        Args:
            folder (str): Папка для сохранения записи (A, B или C)
            
        Returns:
            bool: True если запись успешно начата, False в случае ошибки
        """
        try:
            if self.debug:
                print(f"\n*** НАЧАЛО ЗАПИСИ В ПАПКУ {folder} ***")
                
            if folder not in ['A', 'B', 'C']:
                if self.debug:
                    print(f"Неверная папка для записи: {folder}")
                return False
                
            # Проверяем текущее состояние
            if self.recorder and self.recorder.is_active():
                if self.debug:
                    print("Запись уже ведется, нельзя начать новую")
                return False
                
            # Создаем папку, если она не существует
            folder_path = os.path.join(self.base_dir, folder)
            try:
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path, exist_ok=True)
                    if self.debug:
                        print(f"Создана папка: {folder_path}")
            except Exception as dir_error:
                print(f"Ошибка при создании папки {folder_path}: {dir_error}")
                sentry_sdk.capture_exception(dir_error)
                return False
            
            # Проверяем, не изменилось ли устройство
            current_device = self.audio_device_manager.get_selected_device()
            if (current_device.get("card") != self.audio_device.get("card") or 
                current_device.get("device") != self.audio_device.get("device")):
                
                if self.debug:
                    print(f"Устройство записи изменилось, обновляем: {current_device}")
                
                # Обновляем локальное устройство
                self.audio_device = current_device
                
                # Обновляем устройство в рекордере или создаем новый рекордер
                if self.recorder:
                    self.recorder.set_audio_device(current_device)
                else:
                    self.recorder = AudioRecorder(base_dir=self.base_dir, debug=self.debug, audio_device=current_device)
                    self.recorder.set_timer_callback(self._timer_callback)
            
            # Создаем рекордер, если его нет
            if not self.recorder:
                if self.debug:
                    print(f"Создаем новый экземпляр AudioRecorder для {folder_path}")
                self.recorder = AudioRecorder(folder_path, debug=self.debug, audio_device=self.audio_device)
                self.recorder.set_timer_callback(self._timer_callback)
                
            # Озвучиваем начало записи
            voice_id = self.settings_manager.get_voice() if hasattr(self, 'settings_manager') else None
            message = f"Начинаем запись в папку {folder}"
            
            try:
                # Озвучиваем через TTS если доступен
                if self.tts_manager:
                    try:
                        if hasattr(self.tts_manager, 'play_speech_blocking'):
                            if self.debug:
                                print("Воспроизведение сообщения о начале записи (блокирующий режим)...")
                            self.tts_manager.play_speech_blocking(message, voice_id=voice_id)
                            # Увеличиваем паузу для полного завершения воспроизведения
                            if self.debug:
                                print("Ожидание 2 секунды для завершения воспроизведения сообщения...")
                            time.sleep(2.0)
                        else:
                            if self.debug:
                                print("Воспроизведение сообщения о начале записи...")
                            self.tts_manager.play_speech(message)
                            # Увеличиваем паузу для полного завершения воспроизведения
                            if self.debug:
                                print("Ожидание 2 секунды для завершения воспроизведения сообщения...")
                            time.sleep(2.0)
                    except Exception as tts_error:
                        print(f"Ошибка при озвучивании начала записи: {tts_error}")
                        sentry_sdk.capture_exception(tts_error)
                        # Пробуем запасной вариант
                        try:
                            self.play_notification(message)
                            # Увеличиваем паузу для полного завершения воспроизведения
                            if self.debug:
                                print("Ожидание 2 секунды для завершения воспроизведения сообщения...")
                            time.sleep(2.0)
                        except:
                            # Если ничего не помогло, просто продолжаем
                            pass
            except Exception as voice_error:
                print(f"Ошибка при подготовке голосового сообщения: {voice_error}")
                sentry_sdk.capture_exception(voice_error)
                
            # Воспроизводим звуковой сигнал перед началом записи и ждем его завершения
            try:
                self.play_sound_with_volume(self.beep_sound_path)
            except Exception as beep_error:
                print(f"Ошибка при воспроизведении звукового сигнала: {beep_error}")
                sentry_sdk.capture_exception(beep_error)
                
            # Теперь, когда все сообщения воспроизведены, начинаем запись
            if self.debug:
                print(f"Запуск записи в папку {folder}...")
                
            try:
                if self.debug:
                    print(f"Вызываем recorder.start_recording для папки {folder}")
                result = self.recorder.start_recording(folder)
                if self.debug:
                    print(f"Результат start_recording: {result}")
            except Exception as rec_error:
                print(f"Ошибка при вызове recorder.start_recording: {rec_error}")
                sentry_sdk.capture_exception(rec_error)
                return False
                
            if result:
                if self.debug:
                    print("Запись успешно начата")
                    
                # Обновляем интерфейс
                if self.update_callback:
                    try:
                        self.update_callback()
                    except Exception as callback_error:
                        print(f"Ошибка при обновлении интерфейса: {callback_error}")
                        sentry_sdk.capture_exception(callback_error)
                        
                return True
            else:
                if self.debug:
                    print("Не удалось начать запись")
                    
                # Сообщаем об ошибке
                try:
                    self.play_notification("Ошибка при начале записи")
                except:
                    pass
                    
                return False
        except Exception as e:
            error_msg = f"Критическая ошибка при начале записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def play_notification(self, message):
        """
        Воспроизводит уведомление с использованием aplay
        
        Args:
            message (str): Текст сообщения
        """
        try:
            if self.tts_manager:
                self.tts_manager.play_speech(message)
        except Exception as e:
            error_msg = f"Ошибка при воспроизведении уведомления: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def pause_recording(self):
        """
        Приостанавливает запись
        
        Returns:
            bool: True если запись успешно приостановлена, False в случае ошибки
        """
        try:
            if not self.recorder or not self.recorder.is_active():
                if self.debug:
                    print("Нет активной записи для приостановки")
                return False
                
            # Если запись уже на паузе, ничего не делаем
            if self.recorder.is_on_pause():
                if self.debug:
                    print("Запись уже приостановлена")
                return True
                
            # Сначала приостанавливаем запись
            result = self.recorder.pause_recording()
            
            # Затем озвучиваем приостановку
            try:
                message = "Пауза"
                self.play_notification(message)
            except Exception as voice_error:
                print(f"Ошибка при озвучивании приостановки: {voice_error}")
                sentry_sdk.capture_exception(voice_error)
            
            # Обновляем UI
            if self.update_callback:
                self.update_callback()
                
            return result
        except Exception as e:
            error_msg = f"Ошибка при приостановке записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def resume_recording(self):
        """
        Возобновляет запись после паузы
        
        Returns:
            bool: True если запись успешно возобновлена, False в случае ошибки
        """
        try:
            if not self.recorder or not self.recorder.is_active() or not self.recorder.is_on_pause():
                if self.debug:
                    print("Нет приостановленной записи для возобновления")
                return False
                
            # Сначала озвучиваем возобновление записи с блокирующим вызовом
            try:
                message = "Продолжаем запись"
                if hasattr(self.tts_manager, 'play_speech_blocking'):
                    self.tts_manager.play_speech_blocking(message)
                else:
                    self.play_notification(message)
                    # Добавляем паузу, чтобы сообщение успело проиграться
                    time.sleep(1.5)
            except Exception as voice_error:
                print(f"Ошибка при озвучивании возобновления: {voice_error}")
                sentry_sdk.capture_exception(voice_error)
            
            # Затем возобновляем запись
            result = self.recorder.resume_recording()
            
            # Обновляем UI
            if self.update_callback:
                self.update_callback()
                
            return result
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
        try:
            if not self.recorder or not self.recorder.is_active():
                if self.debug:
                    print("Нет активной записи для остановки")
                return None
                
            # Запоминаем папку для озвучивания в сообщении
            folder = self.recorder.get_current_folder() or "Неизвестная папка"
            
            # Сначала останавливаем запись
            saved_file = self.recorder.stop_recording()
            
            # Обновляем UI
            if self.update_callback:
                self.update_callback()
            
            # Затем озвучиваем результат
            try:
                if saved_file:
                    message = f"Запись остановлена и сохранена в папке {folder}"
                    self.play_notification(message)
                else:
                    message = "Не удалось сохранить запись"
                    self.play_notification(message)
            except Exception as voice_error:
                print(f"Ошибка при озвучивании результата: {voice_error}")
                sentry_sdk.capture_exception(voice_error)
                
            return saved_file
        except Exception as e:
            error_msg = f"Ошибка при остановке записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return None
    
    def cancel_recording(self):
        """
        Отменяет запись без сохранения
        
        Returns:
            bool: True если запись успешно отменена, False в случае ошибки
        """
        try:
            if not self.recorder or not self.recorder.is_active():
                return False
                
            # Озвучиваем отмену записи
            try:
                message = "Отмена записи без сохранения"
                self.play_notification(message)
                # Ждем окончания озвучки
                time.sleep(1.5)
            except Exception as voice_error:
                print(f"Ошибка при озвучивании отмены: {voice_error}")
                sentry_sdk.capture_exception(voice_error)
                
            # Отменяем запись
            result = self.recorder.cancel_recording()
            
            # Обновляем UI
            if self.update_callback:
                self.update_callback()
                
            return result
        except Exception as e:
            error_msg = f"Ошибка при отмене записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def is_recording(self):
        """
        Проверяет, ведется ли запись в данный момент
        
        Returns:
            bool: True если запись ведется, False иначе
        """
        return self.recorder and self.recorder.is_active()
    
    def is_paused(self):
        """
        Проверяет, приостановлена ли запись
        
        Returns:
            bool: True если запись приостановлена, False иначе
        """
        return self.recorder and self.recorder.is_active() and self.recorder.is_on_pause()
    
    def get_current_folder(self):
        """
        Возвращает текущую папку записи
        
        Returns:
            str: Имя папки или None если запись не активна
        """
        return self.recorder.get_current_folder() if self.recorder and self.recorder.is_active() else None
    
    def get_current_time(self):
        """
        Возвращает текущее время записи в секундах
        
        Returns:
            float: Время записи в секундах
        """
        return self.current_time
    
    def get_formatted_time(self):
        """
        Возвращает отформатированное время записи в формате MM:SS
        
        Returns:
            str: Время в формате MM:SS
        """
        minutes = int(self.current_time) // 60
        seconds = int(self.current_time) % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def get_status(self):
        """
        Возвращает текущий статус записи
        
        Returns:
            str: Статус записи ("recording", "paused", "stopped")
        """
        if not self.recorder or not self.recorder.is_active():
            return "stopped"
        elif self.recorder.is_on_pause():
            return "paused"
        else:
            return "recording"
    
    def announce_recording_time(self):
        """Озвучивает текущую длительность записи"""
        try:
            time_seconds = int(self.current_time)
            minutes = time_seconds // 60
            seconds = time_seconds % 60
            
            minutes_word = self._get_minutes_word(minutes)
            seconds_word = self._get_seconds_word(seconds)
            
            if minutes > 0:
                message = f"Длительность записи {minutes} {minutes_word} {seconds} {seconds_word}"
            else:
                message = f"Длительность записи {seconds} {seconds_word}"
                
            # Озвучиваем сообщение
            if self.tts_manager:
                self.tts_manager.play_speech(message)
                
            if self.debug:
                print(f"Озвучено время записи: {message}")
                
        except Exception as e:
            error_msg = f"Ошибка при озвучивании времени записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def _get_minutes_word(self, minutes):
        """
        Возвращает правильное склонение слова "минута" для заданного числа
        
        Args:
            minutes (int): Количество минут
            
        Returns:
            str: Правильно склоненное слово
        """
        if minutes % 10 == 1 and minutes % 100 != 11:
            return "минута"
        elif 2 <= minutes % 10 <= 4 and (minutes % 100 < 10 or minutes % 100 >= 20):
            return "минуты"
        else:
            return "минут"
    
    def _get_seconds_word(self, seconds):
        """
        Возвращает правильное склонение слова "секунда" для заданного числа
        
        Args:
            seconds (int): Количество секунд
            
        Returns:
            str: Правильно склоненное слово
        """
        if seconds % 10 == 1 and seconds % 100 != 11:
            return "секунда"
        elif 2 <= seconds % 10 <= 4 and (seconds % 100 < 10 or seconds % 100 >= 20):
            return "секунды"
        else:
            return "секунд"
    
    def play_notification_blocking(self, message):
        """
        Воспроизводит блокирующее уведомление
        
        Args:
            message (str): Текст сообщения
        """
        try:
            if self.tts_manager and hasattr(self.tts_manager, 'play_speech_blocking'):
                self.tts_manager.play_speech_blocking(message)
            else:
                self.play_notification(message)
        except Exception as e:
            error_msg = f"Ошибка при воспроизведении блокирующего уведомления: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def play_sound_with_volume(self, sound_file):
        """
        Воспроизводит звуковой сигнал с учетом системной громкости
        
        Args:
            sound_file (str): Путь к звуковому файлу
            
        Returns:
            bool: True если звук успешно воспроизведен, иначе False
        """
        try:
            if not os.path.exists(sound_file):
                if self.debug:
                    print(f"Звуковой файл не найден: {sound_file}")
                return False
                
            # Получаем текущую громкость системных сообщений
            volume = 100
            if self.settings_manager:
                volume = self.settings_manager.get_system_volume()
            
            # Преобразуем проценты в значение для paplay (0-65536)
            paplay_volume = int(volume * 65536 / 100)
            
            if self.debug:
                print(f"Воспроизведение звука с громкостью {volume}% ({paplay_volume}): {sound_file}")
                
            # Используем paplay для воспроизведения с регулировкой громкости
            subprocess.run(["paplay", "--volume", str(paplay_volume), sound_file], 
                           check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Добавляем небольшую паузу для завершения воспроизведения
            time.sleep(0.5)
            
            return True
        except Exception as e:
            error_msg = f"Ошибка при воспроизведении звукового сигнала: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def update_audio_device(self, device):
        """
        Обновляет устройство для записи непосредственно в менеджере и рекордере
        
        Args:
            device (dict): Словарь с информацией об устройстве
            
        Returns:
            bool: True если успешно, иначе False
        """
        try:
            if self.debug:
                device_name = device.get("name", "Неизвестное устройство")
                if device.get("is_built_in", False) or "USB Composite Device" in device_name:
                    device_name = "Встроенный микрофон в пульте"
                elif "USB" in device_name:
                    if "(LCS)" in device_name:
                        device_name = "Внешний USB микрофон (LCS)"
                    else:
                        device_name = f"USB микрофон ({device_name})"
                print(f"Обновляем устройство записи в RecorderManager: {device_name}")
            
            # Создаем копию устройства, чтобы избежать проблем с изменением исходного объекта
            self.audio_device = device.copy() if device else None
            
            if not self.audio_device:
                # Если устройство не указано, используем устройство по умолчанию (встроенный микрофон)
                self.audio_device = self.audio_device_manager.default_device
                if self.debug:
                    print(f"Устройство не указано, используем устройство по умолчанию: {self.audio_device}")
            
            # Проверяем, активна ли запись и нужно ли перезапустить recorder
            is_active_recording = self.recorder and self.recorder.is_active()
            is_paused = is_active_recording and self.recorder.is_on_pause()
            
            # Если рекордер существует, обновляем устройство в нем
            if self.recorder:
                if self.debug:
                    device_name = self.audio_device.get("name", "Неизвестное устройство")
                    if self.audio_device.get("is_built_in", False):
                        device_name = "Встроенный микрофон в пульте"
                    print(f"Обновляем устройство в существующем рекордере: {device_name}")
                    
                    if is_active_recording:
                        print(f"Запись активна: {is_active_recording}, на паузе: {is_paused}")
                
                # Обновляем устройство в рекордере
                self.recorder.set_audio_device(self.audio_device)
                
                # Если запись активна и на паузе, обновляем флаг для перезапуска стрима при возобновлении
                if is_active_recording and is_paused:
                    if self.debug:
                        print("Установлен флаг need_reset_stream для перезапуска стрима при возобновлении")
            else:
                # Если рекордер не существует, создаем новый с указанным устройством
                if self.debug:
                    print(f"Создаем новый экземпляр AudioRecorder с устройством: {self.audio_device}")
                self.recorder = AudioRecorder(base_dir=self.base_dir, debug=self.debug, audio_device=self.audio_device)
                self.recorder.set_timer_callback(self._timer_callback)
            
            # Проверяем, что устройство обновлено
            if self.debug:
                device_name = self.audio_device.get("name", "Неизвестное устройство")
                if self.audio_device.get("is_built_in", False):
                    device_name = "Встроенный микрофон в пульте"
                print(f"Текущее устройство после обновления: {device_name}")
            
            # Вызываем колбэк обновления, если он установлен
            if self.update_callback and is_active_recording:
                try:
                    self.update_callback()
                except Exception as callback_error:
                    print(f"Ошибка при вызове колбэка обновления: {callback_error}")
                    sentry_sdk.capture_exception(callback_error)
            
            return True
        except Exception as e:
            error_msg = f"Ошибка при обновлении устройства записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def _handle_device_disconnected(self, old_device, new_device):
        """
        Обрабатывает событие отключения текущего устройства записи
        
        Args:
            old_device (dict): Отключенное устройство
            new_device (dict): Новое устройство (обычно встроенный микрофон)
        """
        try:
            # Определяем имена устройств для отображения и озвучивания
            old_device_name = old_device.get("name", "Неизвестное устройство")
            if old_device.get("is_built_in", False) or "USB Composite Device" in old_device_name:
                old_device_name = "Встроенный микрофон в пульте"
            elif "USB" in old_device_name:
                if "(LCS)" in old_device_name:
                    old_device_name = "Внешний USB микрофон"
                else:
                    old_device_name = "USB микрофон"
            
            new_device_name = new_device.get("name", "Неизвестное устройство")
            if new_device.get("is_built_in", False) or "USB Composite Device" in new_device_name:
                new_device_name = "Встроенный микрофон в пульте"
            
            if self.debug:
                print(f"Обработка отключения устройства: {old_device_name} -> {new_device_name}")
            
            # Проверяем, ведется ли запись
            if not self.recorder or not self.recorder.is_active():
                if self.debug:
                    print("Нет активной записи, просто обновляем устройство")
                # Обновляем устройство через метод update_audio_device
                self.update_audio_device(new_device)
                return
            
            # Если запись уже приостановлена, просто обновляем устройство
            if self.recorder.is_on_pause():
                if self.debug:
                    print("Запись уже на паузе, просто обновляем устройство")
                # Обновляем устройство через метод update_audio_device
                self.update_audio_device(new_device)
                return
            
            # Ставим запись на паузу
            if self.debug:
                print("Ставим запись на паузу из-за отключения устройства")
            self.recorder.pause_recording()
            
            # Обновляем устройство через метод update_audio_device
            self.update_audio_device(new_device)
            
            # Обновляем UI
            if self.update_callback:
                self.update_callback()
            
            # Озвучиваем сообщение об отключении устройства
            try:
                message = f"{old_device_name} был отключен, переключаю на Встроенный микрофон в пульте! Для возобновления записи нажмите OK"
                if hasattr(self.tts_manager, 'play_speech_blocking'):
                    self.tts_manager.play_speech_blocking(message)
                else:
                    self.play_notification(message)
                    # Добавляем паузу для завершения озвучивания
                    time.sleep(3.0)
            except Exception as voice_error:
                print(f"Ошибка при озвучивании отключения устройства: {voice_error}")
                sentry_sdk.capture_exception(voice_error)
            
        except Exception as e:
            error_msg = f"Ошибка при обработке отключения устройства: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)