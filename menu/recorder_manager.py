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
        Начинает запись аудио в указанную папку
        
        Args:
            folder (str): Папка для сохранения записи (A, B или C)
            
        Returns:
            bool: True, если запись успешно начата, False в противном случае
        """
        try:
            # Проверяем свободное место перед началом записи
            has_space, free_space = self.recorder.check_disk_space()
            
            # Если мало места, выдаем предупреждение
            if not has_space:
                print("Предупреждение о малом количестве места на диске")
                # Проигрываем системное предупреждение
                self.play_notification(self.low_disk_space_warning)
            
            # 1. Сначала озвучиваем сообщение о начале записи
            message = f"Начата запись в папку {folder}"
            print(f"Воспроизведение сообщения: {message}")
            self.play_notification(message)
            
            # Ждем, чтобы убедиться, что сообщение полностью воспроизведено
            time.sleep(2)
            
            # 2. Проигрываем звуковой сигнал начала записи
            if self.beep_sound_path and os.path.exists(self.beep_sound_path):
                try:
                    print("Воспроизведение сигнала beep...")
                    subprocess.run(["aplay", self.beep_sound_path], check=False)
                    # Небольшая пауза после звукового сигнала
                    time.sleep(0.5)
                except Exception as e:
                    print(f"Ошибка при воспроизведении сигнала: {e}")
            
            # 3. Теперь начинаем запись
            print("Запуск записи...")
            if self.recorder.start_recording(folder):
                print("Запись успешно начата")
                return True
            else:
                # Озвучиваем сообщение об ошибке
                self.play_notification("Не удалось начать запись")
                return False
                
        except Exception as e:
            error_msg = f"Ошибка при начале записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def play_notification(self, message):
        """
        Воспроизводит голосовое уведомление
        
        Args:
            message (str): Текст уведомления
        """
        try:
            if self.tts_manager:
                # Получаем мужской голос из настроек (ru-RU-Standard-D)
                voice_id = "ru-RU-Standard-D"
                print(f"Воспроизведение уведомления голосом: {voice_id}")
                self.tts_manager.speak_text(message, voice_id)
            else:
                # Если TTS недоступен, используем aplay для воспроизведения звука
                print(f"Уведомление: {message}")
        except Exception as e:
            error_msg = f"Ошибка при воспроизведении уведомления: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
            # Запасной вариант - напрямую через aplay
            try:
                # Создаем временный текстовый файл с сообщением
                with open("/tmp/notification.txt", "w") as f:
                    f.write(message)
                # Используем espeak для преобразования текста в речь
                subprocess.run(["espeak", "-f", "/tmp/notification.txt", "-v", "ru"], check=False)
            except Exception as inner_e:
                print(f"Критическая ошибка при воспроизведении уведомления: {inner_e}")
                
    def pause_recording(self):
        """
        Приостанавливает запись
        
        Returns:
            bool: True, если запись успешно приостановлена
        """
        if not self.recorder.is_active() or self.recorder.is_on_pause():
            if self.debug:
                print("Невозможно приостановить запись: запись неактивна или уже на паузе")
            return False
            
        # Сначала приостанавливаем запись
        result = self.recorder.pause_recording()
        
        if result:
            # Затем озвучиваем приостановку
            if self.debug:
                print("Воспроизведение сообщения 'Запись приостановлена'...")
            self.tts_manager.play_speech("Запись приостановлена")
            
            if self.update_callback:
                self.update_callback()
                
        return result
    
    def resume_recording(self):
        """
        Возобновляет запись после паузы
        
        Returns:
            bool: True, если запись успешно возобновлена
        """
        if not self.recorder.is_active() or not self.recorder.is_on_pause():
            if self.debug:
                print("Невозможно возобновить запись: запись неактивна или не на паузе")
            return False
        
        try:
            # Сначала озвучиваем возобновление записи
            if self.debug:
                print("Воспроизведение сообщения 'Запись возобновлена'...")
            
            # Используем subprocess для блокирующего воспроизведения звука
            if hasattr(self.tts_manager, 'get_cached_filename'):
                sound_file = self.tts_manager.get_cached_filename("Запись возобновлена", voice=None)
                if sound_file and os.path.exists(sound_file):
                    if self.debug:
                        print(f"Воспроизведение звукового файла: {sound_file}")
                    subprocess.run(["aplay", "-q", sound_file], 
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    time.sleep(0.5)  # Дополнительная задержка для надежности
                else:
                    # Если файл не найден, используем обычный метод
                    self.tts_manager.play_speech("Запись возобновлена")
                    time.sleep(1.5)  # Ждем, чтобы сообщение точно проиграло
            else:
                # Если метод get_cached_filename отсутствует, используем обычный метод
                self.tts_manager.play_speech("Запись возобновлена")
                time.sleep(1.5)  # Ждем, чтобы сообщение точно проиграло
        except Exception as e:
            if self.debug:
                print(f"Ошибка при воспроизведении сообщения: {e}")
            time.sleep(1)  # На всякий случай подождем
        
        # Воспроизводим звуковой сигнал перед возобновлением записи
        if os.path.exists(self.beep_sound_path):
            try:
                if self.debug:
                    print("Воспроизведение звукового сигнала...")
                subprocess.run(["aplay", "-q", self.beep_sound_path], 
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Добавляем паузу после звукового сигнала перед возобновлением записи
                if self.debug:
                    print(f"Пауза 0.3 секунды после звукового сигнала...")
                time.sleep(0.3)
                
            except Exception as e:
                if self.debug:
                    print(f"Ошибка при воспроизведении звукового сигнала: {e}")
        
        # Теперь возобновляем запись
        if self.debug:
            print("Возобновление записи...")
        result = self.recorder.resume_recording()
        
        if result:
            if self.debug:
                print("Запись успешно возобновлена")
        else:
            if self.debug:
                print("Не удалось возобновить запись")
            
        if result and self.update_callback:
            self.update_callback()
                
        return result
    
    def stop_recording(self):
        """
        Останавливает запись и сохраняет файл
        
        Returns:
            str: Путь к сохраненному файлу или None в случае ошибки
        """
        try:
            if not self.recorder.is_active():
                print("Попытка остановить запись, но запись не активна")
                return None
            
            # Получаем текущую папку для записи
            folder = self.recorder.get_current_folder()
            
            # ЭТАП 1: Озвучиваем завершение записи
            print("Воспроизведение сообщения 'Запись завершается'...")
            try:
                # Используем самый надежный метод воспроизведения
                if hasattr(self.tts_manager, 'play_speech_blocking'):
                    self.tts_manager.play_speech_blocking("Запись завершается", voice_id="ru-RU-Standard-D")
                else:
                    self.play_notification("Запись завершается")
                    time.sleep(1)  # Дополнительная пауза
            except Exception as e:
                print(f"Ошибка при озвучивании завершения записи: {e}")
                # Продолжаем несмотря на ошибку
                
            # ЭТАП 2: Воспроизводим звуковой сигнал остановки
            try:
                print("Воспроизведение звука остановки записи...")
                subprocess.run(["aplay", "/home/aleks/main-sounds/stop.wav"], 
                              check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                time.sleep(0.5)  # Небольшая пауза
            except Exception as e:
                print(f"Ошибка при воспроизведении звука остановки: {e}")
                
            # ЭТАП 3: Останавливаем запись
            print("Останавливаем и сохраняем запись...")
            file_path = self.recorder.stop_recording()
            
            # ЭТАП 4: Обрабатываем результат
            if file_path:
                print(f"Запись успешно сохранена: {file_path}")
                
                # ЭТАП 5: Воспроизводим звук сохранения
                try:
                    print("Воспроизведение звука сохранения...")
                    subprocess.run(["aplay", "/home/aleks/main-sounds/saved.wav"], 
                                  check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    time.sleep(0.5)  # Небольшая пауза
                except Exception as e:
                    print(f"Ошибка при воспроизведении звука сохранения: {e}")
                
                # ЭТАП 6: Озвучиваем подтверждение сохранения
                message = f"Запись сохранена в папке {folder}"
                print(f"Воспроизведение сообщения '{message}'...")
                try:
                    # Используем самый надежный метод воспроизведения
                    if hasattr(self.tts_manager, 'play_speech_blocking'):
                        self.tts_manager.play_speech_blocking(message, voice_id="ru-RU-Standard-D")
                    else:
                        self.play_notification(message)
                        time.sleep(1)  # Дополнительная пауза
                except Exception as e:
                    print(f"Ошибка при озвучивании подтверждения: {e}")
                
                # Обновляем интерфейс
                if self.update_callback:
                    self.update_callback()
                
                return file_path
            else:
                print("Ошибка: Не удалось сохранить запись")
                try:
                    # Используем самый надежный метод воспроизведения
                    if hasattr(self.tts_manager, 'play_speech_blocking'):
                        self.tts_manager.play_speech_blocking("Ошибка при сохранении записи", voice_id="ru-RU-Standard-D")
                    else:
                        self.play_notification("Ошибка при сохранении записи")
                except Exception as e:
                    print(f"Ошибка при озвучивании сообщения об ошибке: {e}")
                return None
                
        except Exception as e:
            error_msg = f"Критическая ошибка при остановке записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
            # Пытаемся вернуть интерфейс в исходное состояние
            if self.update_callback:
                self.update_callback()
                
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