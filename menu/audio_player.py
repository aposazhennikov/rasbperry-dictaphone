#!/usr/bin/env python3
import os
import time
import threading
import subprocess
import wave
import numpy as np
from pathlib import Path
from pydub import AudioSegment
import sentry_sdk


class AudioPlayer:
    """
    Класс для воспроизведения аудиофайлов с поддержкой различных форматов (WAV, MP3)
    и управлением воспроизведением (пауза, громкость, скорость)
    """
    
    def __init__(self, debug=False):
        """
        Инициализация плеера
        
        Args:
            debug (bool): Режим отладки
        """
        self.debug = debug
        self.current_file = None
        self.is_playing = False
        self.is_paused = False
        self.volume = 100  # Громкость (%)
        self.speed = 1.0   # Скорость воспроизведения
        
        # Текущая позиция и длительность
        self.current_position = 0  # в секундах
        self.duration = 0          # в секундах
        
        # Процесс воспроизведения
        self.playback_process = None
        self.playback_thread = None
        self.stop_playback = False
        
        # Колбэк для обновления времени
        self.time_callback = None
        self.timer_thread = None
        
        # Блокировка для потокобезопасности
        self.lock = threading.Lock()
        
        if self.debug:
            print("AudioPlayer инициализирован")
    
    def load_file(self, file_path):
        """
        Загружает аудиофайл для воспроизведения
        
        Args:
            file_path (str): Путь к аудиофайлу (WAV или MP3)
            
        Returns:
            bool: True, если файл успешно загружен
        """
        try:
            if not os.path.exists(file_path):
                if self.debug:
                    print(f"Файл не найден: {file_path}")
                return False
                
            # Останавливаем текущее воспроизведение, если есть
            if self.is_active():
                self.stop()
                
            self.file_path = file_path
            self.file_ext = os.path.splitext(file_path)[1].lower()
            
            if self.debug:
                print(f"Загружаем файл: {file_path} (расширение: {self.file_ext})")
            
            # Получаем длительность в зависимости от формата
            try:
                if self.file_ext == '.wav':
                    with wave.open(file_path, 'rb') as wf:
                        self.duration = wf.getnframes() / float(wf.getframerate())
                else:  # mp3 и другие форматы через pydub
                    audio = AudioSegment.from_file(file_path)
                    self.duration = len(audio) / 1000.0  # миллисекунды в секунды
                    
                if self.debug:
                    print(f"Длительность файла: {self.duration:.2f} сек")
            except Exception as e:
                error_msg = f"Ошибка при определении длительности файла: {e}"
                print(error_msg)
                sentry_sdk.capture_exception(e)
                self.duration = 0
            
            self.position = 0
            self.is_playing = False
            self.is_paused = False
            self.playback_process = None
            
            return True
        except Exception as e:
            error_msg = f"Ошибка при загрузке файла: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            self.duration = 0
            return False
    
    def play(self):
        """
        Начинает воспроизведение аудиофайла
        
        Returns:
            bool: True, если воспроизведение успешно начато
        """
        try:
            if not hasattr(self, 'file_path') or not self.file_path:
                if self.debug:
                    print("Файл не загружен")
                return False
                
            if self.is_playing:
                if self.debug:
                    print("Воспроизведение уже идёт")
                return True
                
            # Если воспроизведение было на паузе, возобновляем
            if self.is_paused:
                return self.resume()
                
            if self.debug:
                print(f"Начинаем воспроизведение файла: {self.file_path}")
                
            # Останавливаем существующий процесс, если есть
            self._stop_process()
            
            # Запускаем воспроизведение
            cmd = self._get_playback_command()
            
            if self.debug:
                print(f"Команда воспроизведения: {cmd}")
                
            try:
                self.playback_process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE
                )
                
                # Запускаем поток для фонового воспроизведения
                self.playback_thread = threading.Thread(target=self._playback_thread)
                self.playback_thread.daemon = True
                self.playback_thread.start()
                
                # Запускаем таймер
                self._start_timer()
                
                self.is_playing = True
                self.is_paused = False
                
                return True
            except Exception as e:
                error_msg = f"Ошибка при запуске процесса воспроизведения: {e}"
                print(error_msg)
                sentry_sdk.capture_exception(e)
                return False
        except Exception as e:
            error_msg = f"Критическая ошибка при воспроизведении: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def _playback_thread(self):
        """Фоновый поток для воспроизведения файла"""
        try:
            self.is_playing = True
            self.is_paused = False
            
            # Определяем команду в зависимости от формата файла
            file_ext = os.path.splitext(self.current_file)[1].lower()
            
            # Параметры для aplay/mpg123
            if file_ext == '.wav':
                cmd = ["aplay", self.current_file]
                if self.current_position > 0:
                    # aplay не поддерживает начало с середины, нужно обрабатывать отдельно
                    # Если нужно - можно сделать обработку с помощью pydub
                    pass
            elif file_ext in ['.mp3', '.ogg']:
                cmd = ["mpg123", "-q"]
                if self.current_position > 0:
                    start_frame = int(self.current_position * 44100)  # приблизительно
                    cmd.extend(["-k", str(start_frame)])
                cmd.append(self.current_file)
            else:
                if self.debug:
                    print(f"Неподдерживаемый формат для воспроизведения: {file_ext}")
                self.is_playing = False
                return
            
            # Запускаем процесс воспроизведения
            self.playback_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Ожидаем завершения (нормального или по запросу)
            while self.playback_process and not self.stop_playback:
                if self.playback_process.poll() is not None:
                    # Процесс завершился сам
                    break
                
                # Проверяем паузу
                if self.is_paused:
                    if self.playback_process:
                        self.playback_process.terminate()
                        self.playback_process.wait()
                        self.playback_process = None
                    time.sleep(0.1)
                    continue
                
                # Проверяем изменение скорости
                if self.speed != 1.0 and self.playback_process:
                    # aplay/mpg123 не поддерживают изменение скорости напрямую
                    # При изменении скорости нам нужно перезапустить воспроизведение
                    current_pos = self.current_position
                    self.playback_process.terminate()
                    self.playback_process.wait()
                    
                    # Перезапускаем с учетом скорости (это приблизительная реализация)
                    # Для точной реализации нужно использовать более продвинутые библиотеки
                    # например, pygame.mixer или python-vlc
                    if file_ext == '.wav':
                        cmd = ["aplay", self.current_file]
                    elif file_ext in ['.mp3', '.ogg']:
                        cmd = ["mpg123", "-q"]
                        if current_pos > 0:
                            # Корректируем позицию с учетом скорости
                            adjusted_pos = current_pos * self.speed
                            start_frame = int(adjusted_pos * 44100)
                            cmd.extend(["-k", str(start_frame)])
                        cmd.append(self.current_file)
                    
                    self.playback_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                time.sleep(0.1)
            
            # Если был запрос на остановку, останавливаем процесс
            if self.playback_process and self.stop_playback:
                self.playback_process.terminate()
                self.playback_process.wait()
                self.playback_process = None
            
            # Сбрасываем флаги после завершения воспроизведения
            self.is_playing = False
            self.is_paused = False
            
            if self.debug:
                print("Воспроизведение завершено")
                
        except Exception as e:
            if self.debug:
                print(f"Ошибка в потоке воспроизведения: {e}")
            
            # Сбрасываем состояние
            self.is_playing = False
            self.is_paused = False
            if self.playback_process:
                try:
                    self.playback_process.terminate()
                except:
                    pass
    
    def pause(self):
        """
        Приостанавливает воспроизведение
        
        Returns:
            bool: True, если воспроизведение успешно приостановлено
        """
        try:
            if not self.is_playing or self.is_paused:
                return False
                
            if self.debug:
                print("Приостанавливаем воспроизведение")
                
            # Для WAV и MP3 останавливаем процесс
            self._stop_process()
            
            # Запоминаем текущую позицию
            self.is_paused = True
            
            # Останавливаем таймер
            self._stop_timer()
            
            return True
        except Exception as e:
            error_msg = f"Ошибка при постановке на паузу: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def resume(self):
        """
        Возобновляет воспроизведение после паузы
        
        Returns:
            bool: True, если воспроизведение успешно возобновлено
        """
        try:
            if not self.is_paused:
                return False
                
            if self.debug:
                print(f"Возобновляем воспроизведение с позиции {self.position:.2f} сек")
                
            # Запускаем воспроизведение с текущей позиции
            cmd = self._get_playback_command(position=self.position)
            
            try:
                self.playback_process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE
                )
                
                # Запускаем поток для фонового воспроизведения
                self.playback_thread = threading.Thread(target=self._playback_thread)
                self.playback_thread.daemon = True
                self.playback_thread.start()
                
                # Запускаем таймер снова
                self._start_timer()
                
                self.is_paused = False
                
                return True
            except Exception as e:
                error_msg = f"Ошибка при возобновлении воспроизведения: {e}"
                print(error_msg)
                sentry_sdk.capture_exception(e)
                return False
        except Exception as e:
            error_msg = f"Критическая ошибка при возобновлении: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
            
    def stop(self):
        """
        Останавливает воспроизведение
        
        Returns:
            bool: True, если воспроизведение успешно остановлено
        """
        try:
            if not self.is_playing and not self.is_paused:
                return False
                
            if self.debug:
                print("Останавливаем воспроизведение")
                
            # Останавливаем процесс
            self._stop_process()
            
            # Останавливаем таймер
            self._stop_timer()
            
            # Сбрасываем состояние
            self.is_playing = False
            self.is_paused = False
            self.position = 0
            
            return True
        except Exception as e:
            error_msg = f"Ошибка при остановке воспроизведения: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def set_position(self, position):
        """
        Устанавливает позицию воспроизведения
        
        Args:
            position (float): Позиция в секундах
            
        Returns:
            bool: True если позиция успешно установлена, иначе False
        """
        with self.lock:
            if position < 0 or position > self.duration:
                return False
            
            was_playing = self.is_playing and not self.is_paused
            
            # Останавливаем текущее воспроизведение
            if self.is_playing:
                # Устанавливаем флаг остановки для текущего процесса
                self.stop_playback = True
                
                # Останавливаем процесс воспроизведения
                if self.playback_process:
                    try:
                        self.playback_process.terminate()
                        self.playback_process.wait()
                    except:
                        pass
                    self.playback_process = None
            
            # Устанавливаем новую позицию
            self.current_position = position
            
            # Возобновляем воспроизведение, если оно было активно
            if was_playing:
                # Сбрасываем флаг остановки
                self.stop_playback = False
                
                # Запускаем воспроизведение с новой позиции
                file_ext = os.path.splitext(self.current_file)[1].lower()
                
                if file_ext == '.wav':
                    cmd = ["aplay", self.current_file]
                    # TODO: Реализовать точное позиционирование для WAV
                elif file_ext in ['.mp3', '.ogg']:
                    cmd = ["mpg123", "-q"]
                    start_frame = int(self.current_position * 44100)
                    cmd.extend(["-k", str(start_frame)])
                    cmd.append(self.current_file)
                else:
                    return False
                
                # Запускаем новый процесс воспроизведения
                self.playback_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if self.debug:
                print(f"Установлена позиция воспроизведения: {position:.2f} сек")
            
            return True
    
    def fast_forward(self, seconds=10):
        """
        Перемотка вперед на указанное количество секунд
        
        Args:
            seconds (int): Количество секунд для перемотки вперед
            
        Returns:
            bool: True если перемотка выполнена, иначе False
        """
        with self.lock:
            new_position = min(self.current_position + seconds, self.duration)
            return self.set_position(new_position)
    
    def rewind(self, seconds=10):
        """
        Перемотка назад на указанное количество секунд
        
        Args:
            seconds (int): Количество секунд для перемотки назад
            
        Returns:
            bool: True если перемотка выполнена, иначе False
        """
        with self.lock:
            new_position = max(self.current_position - seconds, 0)
            return self.set_position(new_position)
    
    def set_volume(self, volume):
        """
        Устанавливает громкость воспроизведения
        
        Args:
            volume (int): Громкость в процентах (0-100)
            
        Returns:
            bool: True если громкость успешно установлена
        """
        # Ограничиваем значение громкости
        volume = max(0, min(100, volume))
        
        # Устанавливаем новое значение
        self.volume = volume
        
        # Применяем громкость к текущему процессу (если возможно)
        try:
            # Используем amixer для установки громкости системы
            # Это требует прав на управление звуком
            subprocess.run(["amixer", "set", "Master", f"{volume}%"], 
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if self.debug:
                print(f"Установлена громкость: {volume}%")
            
            return True
        except Exception as e:
            if self.debug:
                print(f"Ошибка при установке громкости: {e}")
            return False
    
    def set_speed(self, speed):
        """
        Устанавливает скорость воспроизведения
        
        Args:
            speed (float): Коэффициент скорости (1.0 - нормальная, 2.0 - в два раза быстрее)
            
        Returns:
            bool: True если скорость успешно установлена
        """
        # Ограничиваем значение скорости
        speed = max(0.5, min(2.0, speed))
        
        # Устанавливаем новое значение
        self.speed = speed
        
        if self.debug:
            print(f"Установлена скорость воспроизведения: {speed}x")
        
        return True
    
    def is_active(self):
        """
        Проверяет, активно ли воспроизведение
        
        Returns:
            bool: True если воспроизведение активно (включая паузу)
        """
        return self.is_playing
    
    def is_on_pause(self):
        """
        Проверяет, находится ли воспроизведение на паузе
        
        Returns:
            bool: True если воспроизведение на паузе
        """
        return self.is_playing and self.is_paused
    
    def get_current_position(self):
        """
        Возвращает текущую позицию воспроизведения в секундах
        
        Returns:
            float: Текущая позиция в секундах
        """
        return self.current_position
    
    def get_duration(self):
        """
        Возвращает длительность текущего файла в секундах
        
        Returns:
            float: Длительность в секундах
        """
        return self.duration
    
    def get_formatted_position(self):
        """
        Возвращает отформатированную текущую позицию (MM:SS)
        
        Returns:
            str: Позиция в формате MM:SS
        """
        minutes = int(self.current_position) // 60
        seconds = int(self.current_position) % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def get_formatted_duration(self):
        """
        Возвращает отформатированную длительность (MM:SS)
        
        Returns:
            str: Длительность в формате MM:SS
        """
        minutes = int(self.duration) // 60
        seconds = int(self.duration) % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def get_progress(self):
        """
        Возвращает прогресс воспроизведения в процентах
        
        Returns:
            int: Прогресс (0-100)
        """
        if self.duration == 0:
            return 0
        return int((self.current_position / self.duration) * 100)
    
    def set_time_callback(self, callback):
        """
        Устанавливает функцию обратного вызова для обновления времени
        
        Args:
            callback (callable): Функция, принимающая текущую позицию в секундах
        """
        self.time_callback = callback
    
    def _start_timer(self):
        """Запускает таймер для отслеживания текущей позиции"""
        if self.timer_thread and self.timer_thread.is_alive():
            return
        
        self.stop_timer = False
        self.timer_thread = threading.Thread(target=self._timer_thread)
        self.timer_thread.daemon = True
        self.timer_thread.start()
    
    def _stop_timer(self):
        """Останавливает таймер"""
        self.stop_timer = True
        if self.timer_thread and self.timer_thread.is_alive():
            self.timer_thread.join(1)
    
    def _timer_thread(self):
        """Фоновый поток для отслеживания текущей позиции"""
        last_time = time.time()
        
        while not self.stop_timer:
            # Если воспроизведение активно и не на паузе
            if self.is_playing and not self.is_paused:
                # Рассчитываем приращение времени
                current_time = time.time()
                elapsed = current_time - last_time
                last_time = current_time
                
                # Обновляем текущую позицию с учетом скорости
                self.current_position += elapsed * self.speed
                
                # Если достигли конца файла
                if self.current_position >= self.duration:
                    self.current_position = self.duration
                    
                    # Вызываем колбэк в последний раз
                    if self.time_callback:
                        self.time_callback(self.current_position)
                    
                    # Останавливаем воспроизведение
                    self.stop()
                    break
                
                # Вызываем колбэк для обновления интерфейса
                if self.time_callback:
                    self.time_callback(self.current_position)
            else:
                # Если на паузе, обновляем last_time
                last_time = time.time()
            
            # Спим короткое время
            time.sleep(0.1)
    
    def clean_up(self):
        """Освобождает ресурсы"""
        self.stop()
        self.current_file = None 