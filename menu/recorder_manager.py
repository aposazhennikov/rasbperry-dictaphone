#!/usr/bin/env python3
import os
import time
import threading
from .audio_recorder import AudioRecorder
import subprocess
import sentry_sdk

class RecorderManager:
    """Класс для управления записью аудио и взаимодействия с пользовательским интерфейсом"""
    
    def __init__(self, tts_manager, base_dir="/home/aleks/records", debug=False, beep_sound_path="/home/aleks/main-sounds/beep.wav"):
        """
        Инициализация менеджера записи
        
        Args:
            tts_manager: Менеджер синтеза речи для голосовых сообщений
            base_dir (str): Базовая директория для сохранения записей
            debug (bool): Режим отладки
            beep_sound_path (str): Путь к звуковому файлу для сигнала начала записи
        """
        self.tts_manager = tts_manager
        self.base_dir = base_dir
        self.debug = debug
        self.beep_sound_path = beep_sound_path
        self.recorder = AudioRecorder(base_dir=base_dir, debug=debug)
        
        # Колбэк для обновления информации о записи
        self.update_callback = None
        
        # Текущее время записи
        self.current_time = 0
        
        # Создаем директории для записей, если их нет
        self._create_directories()
        
        # Системные сообщения
        self.low_disk_space_warning = "Внимание, на устройстве осталось менее 1GB памяти, рекомендуется освободить память устройства"
        self.max_duration_warning = "Порог записи длительность 3 часа достигнут завершаю и сохраняю запись во избежание ошибок"
        
        if self.debug:
            print("RecorderManager инициализирован")
            
        # Регистрируем обработчик для системных сообщений
        self.recorder.set_timer_callback(self._timer_callback)
    
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
                
            # Создаем рекордер, если его нет
            if not self.recorder:
                if self.debug:
                    print(f"Создаем новый экземпляр AudioRecorder для {folder_path}")
                self.recorder = AudioRecorder(folder_path, debug=self.debug)
                
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
                if os.path.exists(self.beep_sound_path):
                    if self.debug:
                        print("Воспроизведение звукового сигнала...")
                    subprocess.run(["aplay", self.beep_sound_path], 
                                  check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    # Убедимся, что звук проиграл до конца
                    time.sleep(0.5)
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
            
        Returns:
            bool: True если успешно, False в случае ошибки
        """
        try:
            if self.debug:
                print(f"Воспроизведение уведомления: {message}")
                
            if not message:
                return False
                
            # Если TTS доступен, пытаемся использовать его
            if self.tts_manager:
                try:
                    # Используем текущий голос, если есть доступ к настройкам
                    voice_id = self.settings_manager.get_voice() if hasattr(self, 'settings_manager') else None
                    
                    self.tts_manager.speak_text(message, voice_id)
                    return True
                except Exception as tts_error:
                    print(f"Ошибка при использовании TTS: {tts_error}")
                    sentry_sdk.capture_exception(tts_error)
                    # Продолжаем выполнение, попробуем aplay
            
            # Если TTS недоступен, используем aplay для воспроизведения звука
            try:
                subprocess.run(["aplay", "/home/aleks/main-sounds/beep.wav"], 
                               check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return True
            except Exception as sound_error:
                print(f"Ошибка при воспроизведении звука: {sound_error}")
                sentry_sdk.capture_exception(sound_error)
                return False
        except Exception as e:
            error_msg = f"Ошибка при воспроизведении уведомления: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def pause_recording(self):
        """
        Приостанавливает запись
        
        Returns:
            bool: True если успешно приостановлено, False в случае ошибки
        """
        try:
            if self.debug:
                print("\n*** ПАУЗА ЗАПИСИ ***")
                
            # Проверяем, есть ли рекордер и идет ли запись
            if not self.recorder or not self.recorder.is_active():
                if self.debug:
                    print("Нет активной записи, нечего приостанавливать")
                return False
                
            if self.recorder.is_on_pause():
                if self.debug:
                    print("Запись уже на паузе")
                return True
                
            if self.debug:
                print("Приостанавливаем запись")
                
            # Приостанавливаем запись ПЕРЕД воспроизведением звуков
            result = self.recorder.pause_recording()
            
            if result:
                # Воспроизводим звуковой сигнал паузы ПОСЛЕ приостановки записи
                try:
                    subprocess.run(["aplay", "/home/aleks/main-sounds/pause.wav"], 
                                   check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    time.sleep(0.3)  # Небольшая пауза после сигнала
                except Exception as sound_error:
                    print(f"Ошибка при воспроизведении звука паузы: {sound_error}")
                    sentry_sdk.capture_exception(sound_error)
                
                # Озвучиваем паузу, если TTS доступен
                if self.tts_manager:
                    try:
                        self.tts_manager.play_speech("Запись приостановлена")
                    except Exception as tts_error:
                        print(f"Ошибка при озвучивании паузы: {tts_error}")
                        sentry_sdk.capture_exception(tts_error)
                
                # Обновляем интерфейс
                if self.update_callback:
                    try:
                        self.update_callback()
                    except Exception as callback_error:
                        print(f"Ошибка при обновлении интерфейса: {callback_error}")
                        sentry_sdk.capture_exception(callback_error)
                
                return True
            else:
                print("Не удалось приостановить запись")
                return False
        except Exception as e:
            error_msg = f"Ошибка при приостановке записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def resume_recording(self):
        """
        Возобновляет приостановленную запись
        
        Returns:
            bool: True если успешно возобновлено, False в случае ошибки
        """
        try:
            if self.debug:
                print("\n*** ВОЗОБНОВЛЕНИЕ ЗАПИСИ ***")
                
            # Проверяем, есть ли рекордер и приостановлена ли запись
            if not self.recorder or not self.recorder.is_active() or not self.recorder.is_on_pause():
                if self.debug:
                    print("Нет приостановленной записи, нечего возобновлять")
                return False
                
            if self.debug:
                print("Подготовка к возобновлению записи")
                
            # ВАЖНО: сначала воспроизводим все звуки и сообщения, затем долгая пауза, и только потом возобновление записи
            message_played = False
            
            try:
                # Пытаемся найти звуковой файл в кэше TTS
                sound_file = None
                if hasattr(self.tts_manager, 'get_cached_filename'):
                    sound_file = self.tts_manager.get_cached_filename("Запись возобновлена", voice=None)
                    
                # Если файл существует, воспроизводим его
                if sound_file and os.path.exists(sound_file):
                    try:
                        if self.debug:
                            print(f"Воспроизведение звукового файла: {sound_file}")
                        subprocess.run(["aplay", sound_file], 
                                      check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        message_played = True
                    except Exception as sound_error:
                        print(f"Ошибка при воспроизведении звука возобновления: {sound_error}")
                        sentry_sdk.capture_exception(sound_error)
                else:
                    # Иначе пытаемся озвучить текст через TTS
                    if self.tts_manager:
                        try:
                            if self.debug:
                                print("Воспроизведение сообщения 'Запись возобновлена'")
                            self.tts_manager.play_speech("Запись возобновлена")
                            message_played = True
                        except Exception as tts_error:
                            print(f"Ошибка при озвучивании возобновления: {tts_error}")
                            sentry_sdk.capture_exception(tts_error)
                            # Пробуем запасной вариант
                            try:
                                self.play_notification("Запись возобновлена")
                                message_played = True
                            except:
                                # Ничего не делаем, все методы уже не работают
                                pass
            except Exception as notification_error:
                print(f"Ошибка при уведомлении о возобновлении: {notification_error}")
                sentry_sdk.capture_exception(notification_error)
            
            # Если сообщение было воспроизведено, делаем более длинную паузу для завершения воспроизведения
            if message_played:
                if self.debug:
                    print("Ожидание 3 секунды для завершения воспроизведения сообщения...")
                time.sleep(3.0)  # Длинная пауза для полного завершения воспроизведения
            
            # Теперь, когда все звуки закончились, возобновляем запись
            if self.debug:
                print("Возобновление записи...")
            result = self.recorder.resume_recording()
            
            if result:
                # Обновляем интерфейс
                if self.update_callback:
                    try:
                        self.update_callback()
                    except Exception as callback_error:
                        print(f"Ошибка при обновлении интерфейса: {callback_error}")
                        sentry_sdk.capture_exception(callback_error)
                
                return True
            else:
                print("Не удалось возобновить запись")
                return False
        except Exception as e:
            error_msg = f"Ошибка при возобновлении записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def stop_recording(self):
        """
        Останавливает запись и сохраняет файл
        
        Returns:
            str: Путь к сохраненному файлу или None в случае ошибки
        """
        try:
            if self.debug:
                print("\n*** ОСТАНОВКА ЗАПИСИ ***")
                
            # Проверяем, есть ли рекордер и идет ли запись
            if not self.recorder or not self.recorder.is_active():
                if self.debug:
                    print("Нет активной записи, нечего останавливать")
                return None
                
            # Получаем текущую папку для озвучивания в сообщении
            folder = self.recorder.get_current_folder()
            
            # ЭТАП 1: Останавливаем запись СРАЗУ - ДО всех звуков и уведомлений!
            print("Останавливаем и сохраняем запись...")
            file_path = self.recorder.stop_recording()
            
            # ЭТАП 2: После остановки записи воспроизводим звуковой сигнал
            try:
                print("Воспроизведение звука остановки записи...")
                subprocess.run(["aplay", "/home/aleks/main-sounds/stop.wav"], 
                              check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                time.sleep(0.5)  # Небольшая пауза
            except Exception as e:
                print(f"Ошибка при воспроизведении звука остановки: {e}")
                sentry_sdk.capture_exception(e)
            
            # ЭТАП 3: Обрабатываем результат
            if file_path:
                print(f"Запись успешно сохранена: {file_path}")
                
                # ЭТАП 4: Воспроизводим звук сохранения
                try:
                    print("Воспроизведение звука сохранения...")
                    subprocess.run(["aplay", "/home/aleks/main-sounds/saved.wav"], 
                                  check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    time.sleep(0.5)  # Небольшая пауза
                except Exception as e:
                    print(f"Ошибка при воспроизведении звука сохранения: {e}")
                    sentry_sdk.capture_exception(e)
                
                # ЭТАП 5: Озвучиваем подтверждение сохранения
                print(f"Воспроизведение сообщения о сохранении...")
                try:
                    # Получаем текущий голос из настроек
                    voice = self.settings_manager.get_voice() if hasattr(self, 'settings_manager') else None
                    
                    # Используем самый надежный метод воспроизведения
                    if hasattr(self.tts_manager, 'play_speech_blocking'):
                        self.tts_manager.play_speech_blocking("Запись сохранена в папке", voice_id=voice)
                        time.sleep(0.1)  # Небольшая пауза между сообщениями
                        self.tts_manager.play_speech_blocking(folder, voice_id=voice)
                    else:
                        self.play_notification("Запись сохранена в папке")
                        time.sleep(0.1)  # Небольшая пауза между сообщениями
                        self.play_notification(folder)
                        time.sleep(1)  # Дополнительная пауза
                except Exception as e:
                    print(f"Ошибка при озвучивании подтверждения: {e}")
                    sentry_sdk.capture_exception(e)
                
                # Обновляем интерфейс
                if self.update_callback:
                    try:
                        self.update_callback()
                    except Exception as e:
                        print(f"Ошибка при обновлении интерфейса: {e}")
                        sentry_sdk.capture_exception(e)
                
                return file_path
            else:
                print("Ошибка: Не удалось сохранить запись")
                try:
                    # Получаем текущий голос из настроек
                    voice = self.settings_manager.get_voice() if hasattr(self, 'settings_manager') else None
                    
                    # Используем самый надежный метод воспроизведения
                    if hasattr(self.tts_manager, 'play_speech_blocking'):
                        self.tts_manager.play_speech_blocking("Ошибка при сохранении записи", voice_id=voice)
                    else:
                        self.play_notification("Ошибка при сохранении записи")
                        time.sleep(1)  # Пауза для воспроизведения
                except Exception as e:
                    print(f"Ошибка при озвучивании ошибки сохранения: {e}")
                    sentry_sdk.capture_exception(e)
                
                return None
        except Exception as e:
            error_msg = f"Критическая ошибка при остановке записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
            # В случае критической ошибки все равно пытаемся остановить запись без обработки результата
            try:
                self.recorder.stop_recording()
            except:
                pass
                
            return None
    
    def cancel_recording(self):
        """
        Отменяет запись без сохранения
        
        Returns:
            bool: True, если запись успешно отменена
        """
        if not self.recorder.is_active():
            return False
            
        result = self.recorder.cancel_recording()
        
        if result:
            self.tts_manager.play_speech("Запись отменена")
            
            if self.update_callback:
                self.update_callback()
                
        return result
    
    def is_recording(self):
        """
        Проверяет, идет ли запись в данный момент
        
        Returns:
            bool: True, если запись активна
        """
        return self.recorder.is_active()
    
    def is_paused(self):
        """
        Проверяет, находится ли запись на паузе
        
        Returns:
            bool: True, если запись на паузе
        """
        return self.recorder.is_on_pause()
    
    def get_current_folder(self):
        """
        Возвращает текущую папку записи
        
        Returns:
            str: Имя папки или None, если запись не активна
        """
        return self.recorder.get_current_folder()
    
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
        seconds = int(self.current_time)
        minutes = seconds // 60
        seconds %= 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def get_status(self):
        """
        Возвращает статус записи
        
        Returns:
            dict: Словарь с информацией о статусе записи
        """
        return {
            'is_recording': self.is_recording(),
            'is_paused': self.is_paused(),
            'current_folder': self.get_current_folder(),
            'time': self.get_current_time(),
            'formatted_time': self.get_formatted_time()
        }
    
    def announce_recording_time(self):
        """
        Озвучивает текущее время записи
        
        Returns:
            bool: True если время было объявлено, False если запись неактивна
        """
        if not self.is_recording():
            return False
            
        minutes = int(self.current_time) // 60
        seconds = int(self.current_time) % 60
        
        # Формируем сообщение о времени
        if minutes > 0:
            if seconds > 0:
                time_text = f"Записано {minutes} {self._get_minutes_word(minutes)} {seconds} {self._get_seconds_word(seconds)}"
            else:
                time_text = f"Записано {minutes} {self._get_minutes_word(minutes)}"
        else:
            time_text = f"Записано {seconds} {self._get_seconds_word(seconds)}"
        
        # Озвучиваем время
        self.tts_manager.play_speech(time_text)
        return True
    
    def _get_minutes_word(self, minutes):
        """
        Возвращает правильное склонение слова "минута" для числа minutes
        
        Args:
            minutes (int): Количество минут
            
        Returns:
            str: Правильное склонение слова "минута"
        """
        if minutes % 10 == 1 and minutes % 100 != 11:
            return "минута"
        elif 2 <= minutes % 10 <= 4 and (minutes % 100 < 10 or minutes % 100 >= 20):
            return "минуты"
        else:
            return "минут"
    
    def _get_seconds_word(self, seconds):
        """
        Возвращает правильное склонение слова "секунда" для числа seconds
        
        Args:
            seconds (int): Количество секунд
            
        Returns:
            str: Правильное склонение слова "секунда"
        """
        if seconds % 10 == 1 and seconds % 100 != 11:
            return "секунда"
        elif 2 <= seconds % 10 <= 4 and (seconds % 100 < 10 or seconds % 100 >= 20):
            return "секунды"
        else:
            return "секунд"
    
    def play_notification_blocking(self, message):
        """
        Воспроизводит голосовое уведомление в блокирующем режиме
        
        Args:
            message (str): Текст уведомления
        """
        try:
            if self.tts_manager:
                # Получаем мужской голос
                voice_id = "ru-RU-Standard-D"
                print(f"Блокирующее воспроизведение уведомления голосом {voice_id}: {message}")
                
                # Пытаемся найти звуковой файл для этого сообщения
                if hasattr(self.tts_manager, 'get_cached_filename'):
                    sound_file = self.tts_manager.get_cached_filename(message, voice=voice_id)
                    if sound_file and os.path.exists(sound_file):
                        # Используем aplay для гарантированного воспроизведения
                        subprocess.run(["aplay", sound_file], 
                                      check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        # Дополнительная пауза после воспроизведения
                        time.sleep(0.3)
                        return
                
                # Если файл не найден или возникла ошибка, используем стандартный метод
                self.tts_manager.play_speech_blocking(message, voice_id=voice_id)
            else:
                # Если TTS недоступен, просто выводим сообщение
                print(f"Уведомление (без TTS): {message}")
                time.sleep(1)  # Имитация паузы для воспроизведения
        except Exception as e:
            error_msg = f"Ошибка при блокирующем воспроизведении уведомления: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)