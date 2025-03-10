#!/usr/bin/env python3
import os
import time
import threading
from .audio_recorder import AudioRecorder
import subprocess

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
        
        if self.debug:
            print("RecorderManager инициализирован")
    
    def _create_directories(self):
        """Создает директории для записей"""
        if not os.path.exists(self.base_dir):
            if self.debug:
                print(f"Создаем директорию для записей: {self.base_dir}")
            os.makedirs(self.base_dir)
        
        # Создаем поддиректории A, B, C
        for folder in ['A', 'B', 'C']:
            folder_path = os.path.join(self.base_dir, folder)
            if not os.path.exists(folder_path):
                if self.debug:
                    print(f"Создаем директорию: {folder_path}")
                os.makedirs(folder_path)
    
    def set_update_callback(self, callback):
        """
        Устанавливает функцию обратного вызова для обновления интерфейса
        
        Args:
            callback (callable): Функция, которая будет вызываться при обновлении статуса записи
        """
        self.update_callback = callback
        
        # Устанавливаем колбэк для обновления времени в рекордере
        self.recorder.set_timer_callback(self._timer_callback)
    
    def _timer_callback(self, elapsed_time):
        """
        Обрабатывает обновление времени записи
        
        Args:
            elapsed_time (float): Прошедшее время в секундах
        """
        self.current_time = elapsed_time
        
        # Вызываем колбэк для обновления интерфейса, если он установлен
        if self.update_callback:
            self.update_callback()
    
    def start_recording(self, folder):
        """
        Начинает запись в указанную папку
        
        Args:
            folder (str): Папка для записи ('A', 'B' или 'C')
            
        Returns:
            bool: True, если запись успешно начата
        """
        # Проверяем, что папка существует
        folder_path = os.path.join(self.base_dir, folder)
        if not os.path.exists(folder_path):
            if self.debug:
                print(f"Создаем директорию {folder_path}")
            os.makedirs(folder_path)
        
        # Сначала озвучиваем начало записи
        if self.debug:
            print("Подготовка к записи...")
        self.tts_manager.play_speech(f"Запись началась")
        
        # Ждем короткое время
        time.sleep(0.5)
        
        # Воспроизводим звуковой сигнал
        if os.path.exists(self.beep_sound_path):
            # Используем subprocess для воспроизведения звука напрямую
            try:
                if self.debug:
                    print("Воспроизведение звукового сигнала...")
                subprocess.run(["aplay", "-q", self.beep_sound_path], 
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Добавляем паузу после звукового сигнала перед началом записи
                if self.debug:
                    print(f"Пауза 0.3 секунды после звукового сигнала...")
                time.sleep(0.3)
                
                if self.debug:
                    print("Сигнал завершен, начинаем запись...")
            except Exception as e:
                if self.debug:
                    print(f"Ошибка при воспроизведении звукового сигнала: {e}")
        else:
            if self.debug:
                print(f"Файл звукового сигнала не найден: {self.beep_sound_path}")
        
        # Запускаем запись
        result = self.recorder.start_recording(folder)
        
        # Немедленно обновляем информацию
        if result and self.update_callback:
            if self.debug:
                print("Запись началась, обновляем интерфейс...")
            self.update_callback()
        
        return result
    
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
        if not self.recorder.is_active():
            if self.debug:
                print("Невозможно остановить запись: запись не активна")
            return None
            
        if self.debug:
            print("\n>> ОСТАНОВКА ЗАПИСИ В RECORDER_MANAGER <<")
        
        # Сохраняем папку до остановки
        folder = self.recorder.get_current_folder()
        
        # Проверяем, находится ли запись на паузе
        was_paused = self.recorder.is_on_pause()
        if was_paused and self.debug:
            print("Запись была на паузе перед остановкой")
        
        try:
            # Останавливаем запись и получаем путь к файлу
            if self.debug:
                print("Вызов recorder.stop_recording()...")
            file_path = self.recorder.stop_recording()
            
            if not file_path:
                if self.debug:
                    print("Ошибка: файл не был сохранен")
                return None
            
            if self.debug:
                print(f"Запись успешно сохранена в файл: {file_path}")
            
            # Воспроизводим звуковые уведомления напрямую через aplay
            try:
                if self.debug:
                    print("Воспроизведение звуковых уведомлений...")
                
                # Уведомление о том, что запись остановлена с блокирующим вызовом
                print("Воспроизведение первого сообщения: 'Запись остановлена'")
                
                # Блокирующий вызов для первого сообщения
                if hasattr(self.tts_manager, 'play_speech_blocking'):
                    self.tts_manager.play_speech_blocking("Запись остановлена")
                else:
                    self.tts_manager.play_speech("Запись остановлена")
                    # Даем время на проигрывание первого сообщения
                    time.sleep(1.0)
                
                # Небольшая задержка между сообщениями для естественности
                delay = 0.5
                if self.debug:
                    print(f"Небольшая пауза {delay} секунд между сообщениями...")
                time.sleep(delay)
                
                # Озвучиваем сообщение о сохранении
                saved_message = f"Запись сохранена в папку {folder}"
                print(f"Воспроизведение второго сообщения: '{saved_message}'")
                
                # Блокирующий вызов для второго сообщения
                if hasattr(self.tts_manager, 'play_speech_blocking'):
                    self.tts_manager.play_speech_blocking(saved_message)
                else:
                    self.tts_manager.play_speech(saved_message)
                    # Даем время для полного проигрывания второго сообщения
                    time.sleep(1.5)
                
                # Минимальная задержка перед возвратом управления
                time.sleep(0.5)
                
                if self.debug:
                    print("Завершено воспроизведение всех сообщений")
                    
            except Exception as e:
                if self.debug:
                    print(f"Ошибка при воспроизведении уведомлений: {e}")
                # Запасной вариант с увеличенными задержками
                try:
                    self.tts_manager.play_speech("Запись остановлена")
                    time.sleep(2.5)  # Большая задержка для надежности
                    self.tts_manager.play_speech(f"Запись сохранена в папку {folder}")
                    time.sleep(3.0)  # Увеличенная задержка после второго сообщения
                except:
                    if self.debug:
                        print("Критическая ошибка при воспроизведении резервных сообщений")
            
            # Обратный вызов для обновления интерфейса
            if self.update_callback:
                self.update_callback()
                
            return file_path
                
        except Exception as e:
            if self.debug:
                print(f"КРИТИЧЕСКАЯ ОШИБКА при остановке записи: {e}")
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