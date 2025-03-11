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
        self.file_path = None       # Путь к текущему файлу
        self.is_playing = False     # Флаг активного воспроизведения
        self.is_paused = False      # Флаг паузы
        self.volume = 100           # Громкость (%)
        self.speed = 1.0            # Скорость воспроизведения
        
        # Текущая позиция и длительность
        self.position = 0           # Позиция в секундах
        self.duration = 0           # Длительность в секундах
        
        # Процесс воспроизведения
        self.playback_process = None
        self.playback_thread = None
        self.stop_playback = False
        
        # Колбэк для обновления времени
        self.time_callback = None
        self.timer_thread = None
        self.timer_running = False
        
        # Колбэк для оповещения о завершении воспроизведения
        self.completion_callback = None
        
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
                    try:
                        with wave.open(file_path, 'rb') as wf:
                            self.duration = wf.getnframes() / float(wf.getframerate())
                    except Exception as wav_error:
                        # Если не удалось открыть как WAV, пробуем через pydub
                        if self.debug:
                            print(f"Ошибка при открытии WAV файла: {wav_error}, пробуем через pydub")
                        try:
                            audio = AudioSegment.from_file(file_path)
                            self.duration = len(audio) / 1000.0  # миллисекунды в секунды
                        except Exception as pydub_error:
                            # Если и это не сработало, устанавливаем примерную длительность
                            if self.debug:
                                print(f"Ошибка при открытии через pydub: {pydub_error}, устанавливаем примерную длительность")
                            # Получаем размер файла и примерно оцениваем длительность
                            file_size = os.path.getsize(file_path)
                            # Примерно 172KB на секунду для WAV 44.1kHz, 16-bit, stereo
                            self.duration = file_size / (172 * 1024)
                else:  # mp3 и другие форматы через pydub
                    try:
                        audio = AudioSegment.from_file(file_path)
                        self.duration = len(audio) / 1000.0  # миллисекунды в секунды
                    except Exception as e:
                        if self.debug:
                            print(f"Ошибка при определении длительности MP3: {e}, устанавливаем примерную длительность")
                        # Получаем размер файла и примерно оцениваем длительность
                        file_size = os.path.getsize(file_path)
                        # Примерно 16KB на секунду для MP3 128kbps
                        self.duration = file_size / (16 * 1024)
                    
                if self.debug:
                    print(f"Длительность файла: {self.duration:.2f} сек")
            except Exception as e:
                error_msg = f"Ошибка при определении длительности файла: {e}"
                print(error_msg)
                sentry_sdk.capture_exception(e)
                # Устанавливаем примерную длительность
                file_size = os.path.getsize(file_path)
                if self.file_ext == '.wav':
                    self.duration = file_size / (172 * 1024)  # Примерно для WAV
                else:
                    self.duration = file_size / (16 * 1024)   # Примерно для MP3
                if self.debug:
                    print(f"Установлена примерная длительность: {self.duration:.2f} сек")
            
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
            if not self.file_path:
                if self.debug:
                    print("Нет загруженного файла для воспроизведения")
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
            
            if not cmd:
                if self.debug:
                    print("Не удалось получить команду воспроизведения")
                return False
                
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
                
                # Запускаем таймер для отслеживания позиции
                self._start_timer()
                
                # Устанавливаем флаги
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
        """
        Поток для воспроизведения аудиофайла
        """
        try:
            if self.debug:
                print(f"Запуск потока воспроизведения для {self.file_path}")
                
            # Устанавливаем флаг остановки
            self.stop_playback = False
            
            # Начинаем воспроизведение
            self.is_playing = True
            
            # Ждем завершения воспроизведения
            exit_code = None
            try:
                exit_code = self.playback_process.wait()
            except Exception as e:
                print(f"Ошибка при ожидании завершения процесса: {e}")
                sentry_sdk.capture_exception(e)
                exit_code = -1
                
            # Проверяем, не была ли это принудительная остановка
            if self.stop_playback:
                if self.debug:
                    print("Воспроизведение было остановлено принудительно")
                
                # Если установлен колбэк завершения, вызываем его с флагом ошибки
                if self.completion_callback:
                    try:
                        self.completion_callback(False, "Воспроизведение остановлено пользователем")
                    except Exception as e:
                        print(f"Ошибка в колбэке завершения: {e}")
                        sentry_sdk.capture_exception(e)
                        
                # Обновляем состояние
                self.is_playing = False
                return
                
            if exit_code == 0:
                if self.debug:
                    print("Воспроизведение завершено успешно")
                    
                # Сбрасываем состояние
                self.is_playing = False
                self.position = 0
                
                # Если установлен колбэк завершения, вызываем его
                if self.completion_callback:
                    try:
                        self.completion_callback(True, "Воспроизведение завершено успешно")
                    except Exception as e:
                        print(f"Ошибка в колбэке завершения: {e}")
                        sentry_sdk.capture_exception(e)
            else:
                if self.debug:
                    print(f"Воспроизведение завершено с ошибкой, код: {exit_code}")
                    
                # Сбрасываем состояние
                self.is_playing = False
                
                # Если установлен колбэк завершения, вызываем его с флагом ошибки
                if self.completion_callback:
                    try:
                        self.completion_callback(False, f"Ошибка воспроизведения, код: {exit_code}")
                    except Exception as e:
                        print(f"Ошибка в колбэке завершения: {e}")
                        sentry_sdk.capture_exception(e)
        except Exception as e:
            error_msg = f"Критическая ошибка в потоке воспроизведения: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
            # Сбрасываем состояние
            self.is_playing = False
            self.playback_process = None
            
            # Вызываем колбэк с ошибкой
            if self.completion_callback:
                try:
                    self.completion_callback(False, f"Критическая ошибка: {e}")
                except Exception as callback_error:
                    print(f"Ошибка в колбэке завершения: {callback_error}")
                    sentry_sdk.capture_exception(callback_error)
    
    def pause(self):
        """
        Приостанавливает воспроизведение
        
        Returns:
            bool: True, если воспроизведение успешно приостановлено
        """
        try:
            if self.debug:
                print("\n*** ПАУЗА ВОСПРОИЗВЕДЕНИЯ В AUDIO_PLAYER ***")
                
            if not self.is_playing or self.is_paused:
                if self.debug:
                    print("Воспроизведение уже на паузе или остановлено")
                return False
                
            if self.debug:
                print("Приостанавливаем воспроизведение")
                
            # Запоминаем текущую позицию до установки флагов
            current_position = self.position
            
            # Устанавливаем флаги состояния до остановки процессов
            self.is_paused = True
            self.is_playing = False
            self.stop_playback = True
                
            # Останавливаем таймер
            self._stop_timer()
            
            # Используем новый улучшенный метод для остановки всех процессов
            self._stop_process()
            
            # Очищаем потоки воспроизведения
            if self.playback_thread and self.playback_thread.is_alive():
                try:
                    if self.debug:
                        print("Ожидаем завершения потока воспроизведения для паузы")
                    # Ограничиваем время ожидания
                    self.playback_thread.join(timeout=0.3)
                    if self.playback_thread.is_alive():
                        if self.debug:
                            print("Поток воспроизведения не завершился в течение таймаута")
                except Exception as e:
                    print(f"Ошибка при ожидании завершения потока для паузы: {e}")
                    sentry_sdk.capture_exception(e)
                finally:
                    # Явно обнуляем ссылку на поток
                    self.playback_thread = None
            
            # Восстанавливаем запомненную позицию, она могла измениться во время остановки
            self.position = current_position
            
            # Дополнительная проверка и очистка аудиопроцессов, если что-то осталось
            if os.name == 'posix':
                try:
                    # Останавливаем все процессы aplay и mpg123 
                    # Перенаправляем stderr в /dev/null чтобы не видеть ошибки, если процессов нет
                    os.system("pkill -9 aplay 2>/dev/null")
                    os.system("pkill -9 mpg123 2>/dev/null")
                    if self.debug:
                        print("Выполнена финальная проверка остановки аудиопроцессов")
                except Exception as e:
                    if self.debug:
                        print(f"Ошибка при финальной очистке: {e}")
            
            if self.debug:
                print(f"Воспроизведение успешно приостановлено на позиции {self.position:.2f} сек")
                
            return True
        except Exception as e:
            print(f"Критическая ошибка при постановке на паузу: {e}")
            sentry_sdk.capture_exception(e)
            
            # В случае ошибки всё равно пытаемся остановить воспроизведение
            self.is_paused = True
            self.is_playing = False
            self.playback_process = None
            self.playback_thread = None
            self._stop_timer()
            
            # Финальная попытка убить аудиопроцессы
            try:
                os.system("pkill -9 aplay 2>/dev/null")
                os.system("pkill -9 mpg123 2>/dev/null")
            except:
                pass
            
            return True  # Возвращаем True, чтобы интерфейс думал, что пауза успешна
    
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
            if self.debug:
                print("\n*** ОСТАНОВКА ВОСПРОИЗВЕДЕНИЯ В AUDIO_PLAYER ***")
                
            if not self.is_playing and not self.is_paused:
                if self.debug:
                    print("Воспроизведение уже остановлено")
                return True
            
            # Сбрасываем состояние до вызова остановки процессов,
            # чтобы избежать race condition при запуске новых потоков
            self.is_playing = False
            self.is_paused = False
            self.position = 0
            self.stop_playback = True
                
            if self.debug:
                print("Останавливаем воспроизведение")
                
            # Останавливаем таймер
            self._stop_timer()
            
            # Принудительно останавливаем процесс и все дочерние процессы
            self._stop_process()
            
            # Ждем завершения потока воспроизведения
            if self.playback_thread and self.playback_thread.is_alive():
                try:
                    if self.debug:
                        print("Ожидаем завершения потока воспроизведения")
                    # Ограничиваем время ожидания
                    self.playback_thread.join(timeout=0.3)
                    if self.playback_thread.is_alive():
                        if self.debug:
                            print("Поток не завершился в течение таймаута")
                except Exception as e:
                    print(f"Ошибка при ожидании завершения потока: {e}")
                    sentry_sdk.capture_exception(e)
                finally:
                    # Явно устанавливаем None
                    self.playback_thread = None
            
            # Дополнительно проверяем, не остались ли активные процессы
            # Эта часть будет выполнена, только если _stop_process не справился
            # с остановкой всех процессов
            if os.name == 'posix':  # Linux
                try:
                    # Останавливаем все процессы aplay и mpg123
                    os.system("pkill -9 aplay 2>/dev/null")
                    os.system("pkill -9 mpg123 2>/dev/null")
                    if self.debug:
                        print("Выполнена дополнительная очистка аудиопроцессов")
                except Exception as e:
                    if self.debug:
                        print(f"Ошибка при дополнительной очистке: {e}")
            
            if self.debug:
                print("Воспроизведение полностью остановлено")
            
            return True
        except Exception as e:
            error_msg = f"Ошибка при остановке воспроизведения: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
            # В случае ошибки все равно сбрасываем состояние
            self.is_playing = False
            self.is_paused = False
            self.position = 0
            self.stop_playback = False
            self.playback_process = None
            self.playback_thread = None
            
            # В любом случае пытаемся убить процессы аудио
            try:
                os.system("pkill -9 aplay 2>/dev/null")
                os.system("pkill -9 mpg123 2>/dev/null")
            except:
                pass
            
            return True  # Возвращаем True, чтобы система думала, что остановка прошла успешно
    
    def _stop_process(self):
        """
        Останавливает текущий процесс воспроизведения, если он активен
        """
        if not self.playback_process:
            return
            
        # Записываем process ID для последующего поиска и уничтожения дочерних процессов
        if self.playback_process:
            try:
                parent_pid = self.playback_process.pid
                if self.debug:
                    print(f"Останавливаем процесс воспроизведения (PID: {parent_pid})")
                
                # Пытаемся найти дочерние процессы по родительскому ID
                try:
                    # Запрашиваем список всех процессов с родительским ID
                    if os.name == 'posix':  # Linux
                        child_pids = []
                        try:
                            import psutil
                            # Используем psutil для поиска дочерних процессов
                            parent = psutil.Process(parent_pid)
                            children = parent.children(recursive=True)
                            child_pids = [child.pid for child in children]
                            if self.debug and child_pids:
                                print(f"Найдены дочерние процессы: {child_pids}")
                        except ImportError:
                            # Если psutil не установлен, пробуем через pgrep
                            try:
                                result = subprocess.check_output(['pgrep', '-P', str(parent_pid)])
                                child_pids = [int(pid) for pid in result.decode('utf-8').strip().split('\n') if pid]
                                if self.debug and child_pids:
                                    print(f"Найдены дочерние процессы через pgrep: {child_pids}")
                            except:
                                if self.debug:
                                    print("Не удалось найти дочерние процессы через pgrep")
                                pass
                except Exception as e:
                    if self.debug:
                        print(f"Ошибка при поиске дочерних процессов: {e}")
                
                # Сначала останавливаем дочерние процессы, если они есть
                for pid in child_pids:
                    try:
                        if self.debug:
                            print(f"Останавливаем дочерний процесс {pid}")
                        # Посылаем сигнал завершения
                        os.kill(pid, 9)  # SIGKILL
                    except Exception as e:
                        if self.debug:
                            print(f"Ошибка при остановке дочернего процесса {pid}: {e}")
                
                # Теперь останавливаем основной процесс
                self.playback_process.terminate()
                try:
                    self.playback_process.wait(timeout=0.3)
                except subprocess.TimeoutExpired:
                    # Если процесс не завершается добровольно, применяем силу
                    if self.debug:
                        print("Процесс не завершился по TERMINATE, применяем KILL")
                    self.playback_process.kill()
                    try:
                        self.playback_process.wait(timeout=0.3)
                    except:
                        pass
                
                # Проверяем, действительно ли процесс остановлен
                if self.playback_process.poll() is None:
                    if self.debug:
                        print("Процесс все еще активен после kill(), применяем системный kill")
                    # В крайнем случае используем системный вызов kill
                    try:
                        os.kill(parent_pid, 9)  # SIGKILL
                    except:
                        pass
                
                # Убиваем аудиопроцессы напрямую через системные команды
                try:
                    # Убиваем aplay процессы
                    os.system("pkill -9 aplay")
                    # Убиваем mpg123 процессы
                    os.system("pkill -9 mpg123")
                    if self.debug:
                        print("Выполнена системная очистка аудиопроцессов")
                except Exception as e:
                    if self.debug:
                        print(f"Ошибка при системной очистке: {e}")
            except Exception as e:
                print(f"Ошибка при остановке процесса: {e}")
                sentry_sdk.capture_exception(e)
            finally:
                self.playback_process = None
                if self.debug:
                    print("Процесс очищен")
    
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
            self.position = position
            
            # Возобновляем воспроизведение, если оно было активно
            if was_playing:
                # Сбрасываем флаг остановки
                self.stop_playback = False
                
                # Запускаем воспроизведение с новой позиции
                file_ext = os.path.splitext(self.file_path)[1].lower()
                
                if file_ext == '.wav':
                    cmd = ["aplay", self.file_path]
                    # TODO: Реализовать точное позиционирование для WAV
                elif file_ext in ['.mp3', '.ogg']:
                    cmd = ["mpg123", "-q"]
                    start_frame = int(self.position * 44100)
                    cmd.extend(["-k", str(start_frame)])
                    cmd.append(self.file_path)
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
        try:
            if not self.is_playing and not self.is_paused:
                return False
                
            # Рассчитываем новую позицию
            new_position = self.position + seconds
            
            # Ограничиваем позицию длительностью файла
            if new_position > self.duration:
                new_position = self.duration
                
            # Устанавливаем новую позицию
            return self.set_position(new_position)
        except Exception as e:
            error_msg = f"Ошибка при перемотке вперед: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def rewind(self, seconds=10):
        """
        Перемотка назад на указанное количество секунд
        
        Args:
            seconds (int): Количество секунд для перемотки назад
            
        Returns:
            bool: True если перемотка выполнена, иначе False
        """
        try:
            if not self.is_playing and not self.is_paused:
                return False
                
            # Рассчитываем новую позицию
            new_position = self.position - seconds
            
            # Ограничиваем позицию не меньше 0
            if new_position < 0:
                new_position = 0
                
            # Устанавливаем новую позицию
            return self.set_position(new_position)
        except Exception as e:
            error_msg = f"Ошибка при перемотке назад: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def set_volume(self, volume):
        """
        Устанавливает громкость воспроизведения
        
        Args:
            volume (int): Громкость от 0 до 100
            
        Returns:
            bool: True в случае успеха
        """
        try:
            if volume < 0:
                volume = 0
            elif volume > 100:
                volume = 100
                
            self.volume = volume
            
            # Для Linux устанавливаем системную громкость с помощью amixer
            if os.name == 'posix':
                try:
                    # Устанавливаем громкость для PCM и Master
                    volume_cmd = ["amixer", "sset", "PCM", f"{volume}%"]
                    subprocess.run(volume_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    
                    # Также устанавливаем для Master
                    volume_cmd = ["amixer", "sset", "Master", f"{volume}%"]
                    subprocess.run(volume_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    
                    if self.debug:
                        print(f"Громкость установлена на {volume}%")
                except Exception as cmd_error:
                    print(f"Ошибка при установке громкости: {cmd_error}")
                    sentry_sdk.capture_exception(cmd_error)
                    # Продолжаем выполнение, так как устанавливаем внутреннюю громкость в любом случае
            
            return True
        except Exception as e:
            error_msg = f"Ошибка при установке громкости: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def set_speed(self, speed):
        """
        Устанавливает скорость воспроизведения
        
        Args:
            speed (float): Скорость воспроизведения (0.5-2.0)
            
        Returns:
            bool: True в случае успеха
        """
        try:
            # Ограничиваем скорость в разумных пределах
            if speed < 0.5:
                speed = 0.5
            elif speed > 2.0:
                speed = 2.0
                
            if self.debug:
                print(f"Установка скорости воспроизведения: {speed}")
                
            self.speed = speed
            return True
        except Exception as e:
            error_msg = f"Ошибка при установке скорости: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
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
        return self.position
    
    def get_duration(self):
        """
        Возвращает длительность текущего файла в секундах
        
        Returns:
            float: Длительность в секундах
        """
        return self.duration
    
    def get_formatted_position(self):
        """
        Возвращает текущую позицию в формате MM:SS
        
        Returns:
            str: Строка в формате MM:SS
        """
        try:
            minutes = int(self.position) // 60
            seconds = int(self.position) % 60
            return f"{minutes:02d}:{seconds:02d}"
        except Exception as e:
            print(f"Ошибка при форматировании позиции: {e}")
            sentry_sdk.capture_exception(e)
            return "00:00"
    
    def get_formatted_duration(self):
        """
        Возвращает длительность в формате MM:SS
        
        Returns:
            str: Строка в формате MM:SS
        """
        try:
            minutes = int(self.duration) // 60
            seconds = int(self.duration) % 60
            return f"{minutes:02d}:{seconds:02d}"
        except Exception as e:
            print(f"Ошибка при форматировании длительности: {e}")
            sentry_sdk.capture_exception(e)
            return "00:00"
    
    def get_progress(self):
        """
        Возвращает прогресс воспроизведения в процентах
        
        Returns:
            int: Процент воспроизведения (0-100)
        """
        try:
            if self.duration <= 0:
                return 0
                
            # Вычисляем процент
            progress = (self.position / self.duration) * 100
            
            # Ограничиваем значение от 0 до 100
            if progress < 0:
                progress = 0
            elif progress > 100:
                progress = 100
                
            return int(progress)
        except Exception as e:
            print(f"Ошибка при получении прогресса: {e}")
            sentry_sdk.capture_exception(e)
            return 0
    
    def set_time_callback(self, callback):
        """
        Устанавливает функцию обратного вызова для обновления времени
        
        Args:
            callback (callable): Функция, принимающая текущую позицию в секундах
        """
        self.time_callback = callback
    
    def _start_timer(self):
        """
        Запускает таймер для обновления позиции и отправки колбэков
        """
        try:
            if self.timer_thread and self.timer_thread.is_alive():
                if self.debug:
                    print("Таймер уже запущен")
                return
                
            if self.debug:
                print("Запуск таймера обновления позиции")
                
            # Устанавливаем флаг для работы таймера
            self.stop_timer = False
            
            # Запускаем поток таймера
            self.timer_thread = threading.Thread(target=self._timer_thread, daemon=True)
            self.timer_thread.start()
        except Exception as e:
            error_msg = f"Ошибка при запуске таймера: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
            # Очищаем ссылку на поток
            self.timer_thread = None
    
    def _stop_timer(self):
        """
        Останавливает таймер обновления позиции
        """
        try:
            # Устанавливаем флаг остановки
            self.stop_timer = True
            
            # Ждем завершения потока, если он активен
            if self.timer_thread and self.timer_thread.is_alive():
                if self.debug:
                    print("Ожидаем завершения таймера...")
                try:
                    self.timer_thread.join(timeout=0.5)
                    if self.timer_thread.is_alive():
                        if self.debug:
                            print("Не удалось дождаться завершения таймера")
                except Exception as thread_error:
                    print(f"Ошибка при ожидании завершения таймера: {thread_error}")
                    sentry_sdk.capture_exception(thread_error)
                    
            # Очищаем ссылку на поток в любом случае
            self.timer_thread = None
            
            if self.debug:
                print("Таймер остановлен")
        except Exception as e:
            error_msg = f"Ошибка при остановке таймера: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
            # В случае ошибки все равно очищаем ссылку
            self.timer_thread = None
    
    def _timer_thread(self):
        """
        Поток для обновления текущей позиции воспроизведения
        """
        try:
            if self.debug:
                print("Запущен поток таймера")
                
            # Время последнего обновления
            last_update = time.time()
            
            # Интервал обновления в секундах
            update_interval = 0.1
            
            # Пока флаг остановки не установлен
            while not self.stop_timer:
                try:
                    # Если воспроизведение не запущено или на паузе, ждем
                    if not self.is_playing or self.is_paused:
                        time.sleep(update_interval)
                        continue
                        
                    # Вычисляем прошедшее время
                    current_time = time.time()
                    elapsed = current_time - last_update
                    last_update = current_time
                    
                    # Учитываем скорость воспроизведения
                    adjusted_elapsed = elapsed * self.speed
                    
                    # Обновляем позицию
                    self.position += adjusted_elapsed
                    
                    # Проверяем, не превышает ли позиция длительность файла
                    if self.duration > 0 and self.position > self.duration:
                        if self.debug:
                            print(f"Достигнут конец файла: {self.position:.2f} > {self.duration:.2f}")
                        self.position = self.duration
                    
                    # Вызываем колбэк для обновления времени в UI
                    if self.time_callback:
                        try:
                            self.time_callback(self.position)
                        except Exception as callback_error:
                            print(f"Ошибка в колбэке обновления времени: {callback_error}")
                            sentry_sdk.capture_exception(callback_error)
                            # Отключаем колбэк, чтобы не было постоянных ошибок
                            self.time_callback = None
                        
                    # Ожидаем перед следующим обновлением
                    time.sleep(update_interval)
                    
                except Exception as loop_error:
                    print(f"Ошибка в цикле таймера: {loop_error}")
                    sentry_sdk.capture_exception(loop_error)
                    # Продолжаем выполнение цикла несмотря на ошибку
                    time.sleep(update_interval)
                    
            if self.debug:
                print("Поток таймера завершен")
                
        except Exception as e:
            error_msg = f"Критическая ошибка в потоке таймера: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def clean_up(self):
        """
        Освобождает ресурсы при завершении работы
        """
        try:
            if self.debug:
                print("Выполняется очистка ресурсов аудиоплеера")
                
            # Останавливаем воспроизведение
            self.stop()
            
            # Останавливаем таймер
            self._stop_timer()
            
            # Убеждаемся, что все процессы завершены
            if os.name == 'posix':
                try:
                    # Для надежности пытаемся убить аудиопроцессы напрямую
                    os.system("pkill -9 aplay 2>/dev/null")
                    os.system("pkill -9 mpg123 2>/dev/null")
                except:
                    pass
                    
            if self.debug:
                print("Ресурсы аудиоплеера успешно освобождены")
        except Exception as e:
            error_msg = f"Ошибка при очистке ресурсов аудиоплеера: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def _get_playback_command(self, position=None):
        """
        Формирует команду для воспроизведения аудиофайла в зависимости от формата
        
        Args:
            position (float, optional): Позиция в секундах, с которой начать воспроизведение
            
        Returns:
            list: Список аргументов для subprocess.Popen
        """
        try:
            if not self.file_path or not os.path.exists(self.file_path):
                if self.debug:
                    print(f"Файл не существует: {self.file_path}")
                return None
                
            # Определяем команду в зависимости от формата файла
            file_ext = os.path.splitext(self.file_path)[1].lower()
            
            # Если позиция не указана, используем текущую
            if position is None:
                position = self.position
                
            if self.debug:
                print(f"Формирование команды воспроизведения для {file_ext}, позиция: {position:.2f} сек")
            
            # Параметры для aplay/mpg123
            if file_ext == '.wav':
                cmd = ["aplay", self.file_path]
                if position > 0:
                    # aplay не поддерживает начало с середины, нужно обрабатывать отдельно
                    # Для WAV файлов можно использовать sox для обрезки
                    if self.debug:
                        print(f"WAV: позиция {position:.2f} сек не поддерживается напрямую")
                    # Можно реализовать через временный файл и sox, если нужно
            elif file_ext in ['.mp3', '.ogg']:
                cmd = ["mpg123", "-q"]
                if position > 0:
                    start_frame = int(position * 44100)  # приблизительно
                    cmd.extend(["-k", str(start_frame)])
                    if self.debug:
                        print(f"MP3: начало с фрейма {start_frame} (позиция {position:.2f} сек)")
                cmd.append(self.file_path)
            else:
                if self.debug:
                    print(f"Неподдерживаемый формат для воспроизведения: {file_ext}")
                return None
                
            return cmd
        except Exception as e:
            error_msg = f"Ошибка при формировании команды воспроизведения: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return None
    
    def set_completion_callback(self, callback):
        """
        Устанавливает функцию обратного вызова для оповещения о завершении воспроизведения
        
        Args:
            callback (callable): Функция, которая будет вызвана при завершении воспроизведения
        """
        self.completion_callback = callback
        if self.debug:
            print("Установлен колбэк завершения воспроизведения") 