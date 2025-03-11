#!/usr/bin/env python3
import os
import time
import threading
import glob
from datetime import datetime
import sentry_sdk
from pathlib import Path
from .audio_player import AudioPlayer

class PlaybackManager:
    """
    Класс для управления воспроизведением аудиофайлов и интеграции с системой меню.
    Поддерживает навигацию по списку файлов, переключение между записями и удаление.
    """
    
    def __init__(self, tts_manager, base_dir="/home/aleks/records", debug=False):
        """
        Инициализация менеджера воспроизведения
        
        Args:
            tts_manager: Менеджер синтеза речи для голосовых сообщений
            base_dir (str): Базовая директория с записями
            debug (bool): Режим отладки
        """
        try:
            self.tts_manager = tts_manager
            self.base_dir = base_dir
            self.debug = debug
            
            # Создаем плеер
            self.player = AudioPlayer(debug=debug)
            
            # Текущая папка и список файлов
            self.current_folder = None
            self.files_list = []
            self.current_index = -1
            
            # Информация о воспроизведении
            self.playback_info = {
                "active": False,
                "paused": False,
                "current_file": None,
                "position": "00:00",
                "duration": "00:00",
                "progress": 0
            }
            
            # Колбэк для обновления информации в интерфейсе
            self.update_callback = None
            
            # Родительское меню для возврата
            self.return_to_menu = None
            
            # Включить/выключить удаление файлов
            self.allow_delete = True
            
            # Статус подтверждения удаления
            self.confirm_delete_active = False
            self.confirm_delete_selected = "Нет"  # По умолчанию "Нет"
            
            # Состояние кнопок
            self.key_states = {
                "right_pressed": False,  # Для ускоренного воспроизведения
                "left_pressed": False    # Для перемотки назад
            }
            
            if self.debug:
                print("PlaybackManager инициализирован")
        except Exception as e:
            error_msg = f"Ошибка при инициализации PlaybackManager: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def set_update_callback(self, callback):
        """
        Устанавливает функцию обратного вызова для обновления интерфейса
        
        Args:
            callback (callable): Функция, которая будет вызываться при обновлении статуса воспроизведения
        """
        try:
            self.update_callback = callback
            
            # Устанавливаем колбэк для обновления времени в плеере
            self.player.set_time_callback(self._time_callback)
        except Exception as e:
            error_msg = f"Ошибка при установке колбэка обновления: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def _time_callback(self, current_position):
        """
        Обрабатывает обновление времени воспроизведения
        
        Args:
            current_position (float): Текущая позиция в секундах
        """
        try:
            # Обновляем информацию о воспроизведении
            self.playback_info["position"] = self.player.get_formatted_position()
            self.playback_info["progress"] = self.player.get_progress()
            
            # Вызываем колбэк для обновления интерфейса
            if self.update_callback:
                self.update_callback()
        except Exception as e:
            error_msg = f"Ошибка в обработчике таймера: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def load_folder(self, folder, return_to_menu=None):
        """
        Загружает список аудиофайлов из указанной папки
        
        Args:
            folder (str): Папка для загрузки (A, B или C)
            return_to_menu (SubMenu): Меню, в которое нужно вернуться после воспроизведения
            
        Returns:
            bool: True если файлы загружены успешно
        """
        try:
            if self.debug:
                print(f"\n*** ЗАГРУЗКА АУДИОФАЙЛОВ ИЗ ПАПКИ {folder} ***")
                print(f"Возврат в меню: {return_to_menu.name if return_to_menu else 'None'}")
                
            if folder not in ['A', 'B', 'C']:
                if self.debug:
                    print(f"Неверная папка: {folder}")
                return False
                
            # Формируем путь к папке
            folder_path = os.path.join(self.base_dir, folder)
            
            if not os.path.exists(folder_path):
                if self.debug:
                    print(f"Папка не существует: {folder_path}, создаем...")
                os.makedirs(folder_path, exist_ok=True)
                
            # Загружаем список файлов
            audio_files = self._get_audio_files(folder_path)
            
            if not audio_files:
                if self.debug:
                    print(f"В папке {folder} нет аудиофайлов")
                return False
                
            # Сохраняем информацию
            self.current_folder = folder
            self.files_list = audio_files
            self.current_index = 0
            
            # Запоминаем меню для возврата - важно!
            self.return_to_menu = return_to_menu
            
            if self.debug:
                print(f"Загружено {len(audio_files)} файлов из папки {folder}")
                print(f"Меню для возврата: {return_to_menu.name if return_to_menu else 'None'}")
                print(f"Первый файл: {os.path.basename(audio_files[0])}")
                
            return True
        except Exception as e:
            error_msg = f"Ошибка при загрузке папки {folder}: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def _get_audio_files(self, folder_path):
        """
        Получает список аудиофайлов из указанной папки,
        сортированных по дате создания (от новых к старым)
        
        Args:
            folder_path (str): Путь к папке
            
        Returns:
            list: Список путей к аудиофайлам
        """
        try:
            if self.debug:
                print(f"Поиск аудиофайлов в {folder_path}")
                
            audio_files = []
            
            # Поддерживаемые форматы
            extensions = ['.wav', '.mp3', '.ogg']
            
            # Получаем все файлы в папке
            for file in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file)
                
                # Проверяем, что это файл и имеет поддерживаемое расширение
                if os.path.isfile(file_path) and os.path.splitext(file)[1].lower() in extensions:
                    audio_files.append(file_path)
            
            # Сортируем по дате создания (от новых к старым)
            audio_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
            
            if self.debug:
                print(f"Найдено {len(audio_files)} аудиофайлов в {folder_path}")
                if audio_files:
                    print("Список файлов (первые 3):")
                    for i, f in enumerate(audio_files[:3]):
                        mtime = datetime.fromtimestamp(os.path.getmtime(f))
                        print(f"  {i+1}. {os.path.basename(f)} ({mtime.strftime('%d.%m.%Y %H:%M:%S')})")
                
            return audio_files
        except Exception as e:
            error_msg = f"Ошибка при получении списка аудиофайлов: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return []
    
    def get_current_file_info(self):
        """
        Возвращает информацию о текущем файле
        
        Returns:
            dict: Информация о файле или None, если нет файлов
        """
        if not self.files_list or self.current_index < 0 or self.current_index >= len(self.files_list):
            return None
        
        file_path = self.files_list[self.current_index]
        
        # Получаем метаданные файла
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        file_created = datetime.fromtimestamp(os.path.getctime(file_path))
        file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
        
        # Определяем длительность
        duration = 0
        try:
            if self.player.file_path != file_path:
                self.player.load_file(file_path)
            duration = self.player.get_duration()
        except:
            pass
        
        # Форматируем дату и время для чтения
        date_str = file_created.strftime("%d.%m.%Y")
        time_str = file_created.strftime("%H:%M:%S")
        
        # Форматируем длительность
        minutes = int(duration) // 60
        seconds = int(duration) % 60
        duration_str = f"{minutes:02d}:{seconds:02d}"
        
        # Формируем человекоразумное описание
        description = f"Запись от {date_str}, {time_str}"
        
        return {
            "path": file_path,
            "name": file_name,
            "size": file_size,
            "created": file_created,
            "modified": file_modified,
            "duration": duration,
            "duration_str": duration_str,
            "description": description,
            "folder": self.current_folder
        }
    
    def get_file_info(self, index):
        """
        Возвращает информацию о файле по индексу
        
        Args:
            index (int): Индекс файла в списке
            
        Returns:
            dict: Информация о файле или None, если индекс некорректный
        """
        try:
            if not self.files_list or index < 0 or index >= len(self.files_list):
                if self.debug:
                    print(f"Индекс файла за пределами диапазона: {index}, доступно {len(self.files_list)} файлов")
                return None
                
            # Сохраняем текущий индекс
            current_index_backup = self.current_index
            
            # Временно устанавливаем индекс для получения информации
            self.current_index = index
            
            # Получаем информацию о файле
            file_info = self.get_current_file_info()
            
            # Восстанавливаем текущий индекс
            self.current_index = current_index_backup
            
            return file_info
        except Exception as e:
            error_msg = f"Ошибка при получении информации о файле с индексом {index}: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return None
    
    def get_human_readable_filename(self, file_path):
        """
        Возвращает человекочитаемое название файла
        
        Args:
            file_path (str): Путь к файлу
            
        Returns:
            str: Человекочитаемое название
        """
        # Получаем имя файла без пути и расширения
        file_name = os.path.basename(file_path)
        file_base = os.path.splitext(file_name)[0]
        
        # Получаем дату создания
        try:
            file_created = datetime.fromtimestamp(os.path.getmtime(file_path))
            date_str = file_created.strftime("%d.%m.%Y")
            time_str = file_created.strftime("%H:%M")
            
            return f"Запись от {date_str}, {time_str}"
        except:
            # Если не удалось получить дату, возвращаем имя файла
            return file_base
    
    def get_files_count(self):
        """
        Возвращает количество файлов в текущей папке
        
        Returns:
            int: Количество файлов
        """
        return len(self.files_list)
    
    def move_to_next_file(self):
        """
        Переходит к следующему файлу в списке
        
        Returns:
            bool: True если переход выполнен, иначе False
        """
        if not self.files_list:
            return False
        
        # Останавливаем текущее воспроизведение, если оно активно
        if self.player.is_active():
            self.player.stop()
        
        # Переходим к следующему файлу
        self.current_index = (self.current_index + 1) % len(self.files_list)
        
        # Обновляем информацию о файле
        file_info = self.get_current_file_info()
        if file_info:
            # Озвучиваем название файла
            self.tts_manager.play_speech(file_info["description"])
            
            # Обновляем интерфейс
            if self.update_callback:
                self.update_callback()
            
            return True
        
        return False
    
    def move_to_prev_file(self):
        """
        Переходит к предыдущему файлу в списке
        
        Returns:
            bool: True если переход выполнен, иначе False
        """
        if not self.files_list:
            return False
        
        # Останавливаем текущее воспроизведение, если оно активно
        if self.player.is_active():
            self.player.stop()
        
        # Переходим к предыдущему файлу
        self.current_index = (self.current_index - 1) % len(self.files_list)
        
        # Обновляем информацию о файле
        file_info = self.get_current_file_info()
        if file_info:
            # Озвучиваем название файла
            self.tts_manager.play_speech(file_info["description"])
            
            # Обновляем интерфейс
            if self.update_callback:
                self.update_callback()
            
            return True
        
        return False
    
    def play_current_file(self):
        """
        Начинает воспроизведение текущего файла
        
        Returns:
            bool: True если воспроизведение начато, иначе False
        """
        try:
            if not self.files_list or self.current_index < 0 or self.current_index >= len(self.files_list):
                return False
            
            # Получаем путь к файлу
            file_path = self.files_list[self.current_index]
            
            if self.debug:
                print(f"Воспроизведение файла: {file_path}")
                
            # Загружаем файл, если это новый файл
            if self.player.file_path != file_path:
                if self.debug:
                    print(f"Загрузка нового файла: {file_path}")
                if not self.player.load_file(file_path):
                    if self.debug:
                        print(f"Не удалось загрузить файл: {file_path}")
                    return False
            
            # Устанавливаем колбэк завершения воспроизведения
            self.player.set_completion_callback(self._handle_playback_completion)
            
            # Начинаем воспроизведение
            result = self.player.play()
            
            if result:
                if self.debug:
                    print("Воспроизведение успешно начато")
                # Обновляем информацию о воспроизведении
                self.playback_info["active"] = True
                self.playback_info["paused"] = False
                self.playback_info["current_file"] = file_path
                self.playback_info["position"] = self.player.get_formatted_position()
                self.playback_info["duration"] = self.player.get_formatted_duration()
                
                # Обновляем интерфейс
                file_info = self.get_current_file_info()
                if self.update_callback:
                    self.update_callback()
                    
                return True
            else:
                if self.debug:
                    print("Не удалось начать воспроизведение")
                return False
        except Exception as e:
            error_msg = f"Критическая ошибка при воспроизведении: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def _handle_playback_completion(self, success, message):
        """
        Обрабатывает завершение воспроизведения
        
        Args:
            success (bool): True, если воспроизведение завершено успешно
            message (str): Сообщение о завершении
        """
        try:
            if self.debug:
                print(f"Завершение воспроизведения: {message}, успешно: {success}")
            
            # Сбрасываем состояние воспроизведения
            self.playback_info["active"] = False
            self.playback_info["paused"] = False
            
            # Если воспроизведение завершилось успешно, автоматически переходим к следующему файлу
            if success and self.current_index < len(self.files_list) - 1:
                if self.debug:
                    print("Автоматический переход к следующему файлу")
                self.move_to_next_file()
            else:
                # Иначе просто обновляем интерфейс
                if self.update_callback:
                    self.update_callback()
        except Exception as e:
            error_msg = f"Ошибка при обработке завершения воспроизведения: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def toggle_pause(self):
        """
        Приостанавливает/возобновляет воспроизведение
        
        Returns:
            bool: True, если операция успешна
        """
        try:
            if not self.playback_info["active"]:
                if self.debug:
                    print("Невозможно переключить паузу: воспроизведение неактивно")
                return False
                
            # Определяем текущее состояние паузы
            is_paused = self.playback_info["paused"]
            
            if self.debug:
                print(f"Переключение паузы. Текущее состояние: {is_paused}")
                
            # Используем мужской голос для системных сообщений
            voice_id = "ru-RU-Standard-D"
                
            if is_paused:
                # Возобновляем воспроизведение
                if self.debug:
                    print("Возобновление воспроизведения")
                    
                # Озвучиваем возобновление
                if self.tts_manager:
                    try:
                        if hasattr(self.tts_manager, 'play_speech_blocking'):
                            self.tts_manager.play_speech_blocking("Возобновление воспроизведения", voice_id=voice_id)
                        else:
                            self.tts_manager.play_speech("Возобновление воспроизведения", voice_id=voice_id)
                            time.sleep(1)
                    except Exception as e:
                        print(f"Ошибка при озвучивании возобновления: {e}")
                
                # Возобновляем воспроизведение с текущей позиции
                result = self.player.resume()
                
                if result:
                    self.playback_info["paused"] = False
                    
                    # Обновляем интерфейс
                    if self.update_callback:
                        self.update_callback()
                        
                    return True
                else:
                    if self.debug:
                        print("Не удалось возобновить воспроизведение")
                    return False
            else:
                # Приостанавливаем воспроизведение
                if self.debug:
                    print("Приостановка воспроизведения")
                    
                # Озвучиваем паузу
                if self.tts_manager:
                    try:
                        if hasattr(self.tts_manager, 'play_speech_blocking'):
                            self.tts_manager.play_speech_blocking("Пауза", voice_id=voice_id)
                        else:
                            self.tts_manager.play_speech("Пауза", voice_id=voice_id)
                            time.sleep(0.5)
                    except Exception as e:
                        print(f"Ошибка при озвучивании паузы: {e}")
                
                result = self.player.pause()
                
                if result:
                    self.playback_info["paused"] = True
                    
                    # Обновляем интерфейс
                    if self.update_callback:
                        self.update_callback()
                        
                    return True
                else:
                    if self.debug:
                        print("Не удалось приостановить воспроизведение")
                    return False
        except Exception as e:
            error_msg = f"Ошибка при переключении паузы: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def stop_playback(self):
        """
        Останавливает воспроизведение текущего аудиофайла
        
        Returns:
            bool: True если воспроизведение успешно остановлено
        """
        try:
            if self.debug:
                print("\n*** ОСТАНОВКА ВОСПРОИЗВЕДЕНИЯ В PLAYBACK_MANAGER ***")
                
            # Останавливаем воспроизведение
            self.player.stop()
            
            # Обновляем информацию
            self.playback_info["active"] = False
            self.playback_info["paused"] = False
            self.playback_info["position"] = "00:00"
            self.playback_info["progress"] = 0
            
            # Вызываем колбэк для обновления интерфейса
            if self.update_callback:
                self.update_callback()
                
            if self.debug:
                print("Воспроизведение успешно остановлено")
                
            return True
        except Exception as e:
            error_msg = f"Ошибка при остановке воспроизведения: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
            # В случае ошибки всё равно обновляем состояние
            self.playback_info["active"] = False
            self.playback_info["paused"] = False
            
            return False
    
    def set_volume(self, volume):
        """
        Устанавливает громкость воспроизведения
        
        Args:
            volume (int): Громкость в процентах (0-100)
            
        Returns:
            bool: True если громкость успешно установлена
        """
        result = self.player.set_volume(volume)
        
        if result and self.debug:
            print(f"Установлена громкость: {volume}%")
        
        return result
    
    def adjust_volume(self, delta):
        """
        Изменяет громкость на указанное значение
        
        Args:
            delta (int): Изменение громкости (-/+)
            
        Returns:
            int: Новое значение громкости (0-100)
        """
        # Получаем текущую громкость
        current_volume = self.player.volume
        
        # Рассчитываем новую громкость
        new_volume = max(0, min(100, current_volume + delta))
        
        # Устанавливаем новую громкость
        self.player.set_volume(new_volume)
        
        # Озвучиваем новую громкость
        if delta != 0:
            self.tts_manager.play_speech(f"Громкость {new_volume} процентов")
        
        return new_volume
    
    def toggle_fast_playback(self, enable):
        """
        Включает/выключает ускоренное воспроизведение
        
        Args:
            enable (bool): True для включения, False для выключения
            
        Returns:
            bool: True если состояние успешно изменено
        """
        if not self.player.is_active() or self.player.is_on_pause():
            return False
        
        if enable:
            # Включаем ускоренное воспроизведение (2x)
            self.player.set_speed(2.0)
            
            if self.debug:
                print("Включено ускоренное воспроизведение (2x)")
        else:
            # Возвращаем нормальную скорость
            self.player.set_speed(1.0)
            
            if self.debug:
                print("Возвращена нормальная скорость воспроизведения")
        
        return True
    
    def handle_key_press(self, key_code, pressed):
        """
        Обрабатывает нажатие/отпускание клавиши
        
        Args:
            key_code (int): Код клавиши
            pressed (bool): True - нажата, False - отпущена
            
        Returns:
            bool: True если клавиша обработана
        """
        try:
            # Определение всех используемых кодов клавиш
            KEY_SELECT = 353  # Пауза/воспроизведение
            KEY_BACK = 158    # Выход из режима воспроизведения
            KEY_UP = 103      # Увеличение громкости
            KEY_DOWN = 108    # Уменьшение громкости
            KEY_RIGHT = 106   # Перемотка вперед / ускоренное воспроизведение
            KEY_LEFT = 105    # Перемотка назад
            KEY_PAGEUP = 104  # Предыдущий файл
            KEY_PAGEDOWN = 109 # Следующий файл
            KEY_POWER = 116   # Удаление файла
            
            if self.debug:
                print(f"Обработка клавиши {key_code}, pressed={pressed}")
                
            # Обработка однократных нажатий (только при нажатии, не при отпускании)
            if pressed:
                # Пауза/воспроизведение
                if key_code == KEY_SELECT:
                    if self.debug:
                        print("Нажата клавиша PAUSE/PLAY")
                    self.toggle_pause()
                    return True
                
                # Выход из режима воспроизведения
                elif key_code == KEY_BACK:
                    if self.debug:
                        print("Нажата клавиша EXIT")
                    self.stop_playback()
                    return True
                
                # Переключение между файлами
                elif key_code == KEY_PAGEDOWN:
                    if self.debug:
                        print("Нажата клавиша NEXT")
                    self.move_to_next_file()
                    return True
                
                elif key_code == KEY_PAGEUP:
                    if self.debug:
                        print("Нажата клавиша PREV")
                    self.move_to_prev_file()
                    return True
                
                # Управление громкостью
                elif key_code == KEY_UP:
                    if self.debug:
                        print("Нажата клавиша VOL+")
                    self.adjust_volume(10)  # Увеличиваем на 10%
                    return True
                
                elif key_code == KEY_DOWN:
                    if self.debug:
                        print("Нажата клавиша VOL-")
                    self.adjust_volume(-10)  # Уменьшаем на 10%
                    return True
                
                # Удаление файла
                elif key_code == KEY_POWER:
                    if self.debug:
                        print("Нажата клавиша DELETE")
                    self.delete_current_file()
                    return True
            
            # Обработка длительных нажатий (перемотка)
            if key_code == KEY_RIGHT:
                if pressed != self.key_states["right_pressed"]:
                    self.key_states["right_pressed"] = pressed
                    
                    # Включаем/выключаем ускоренное воспроизведение
                    self.toggle_fast_playback(pressed)
                    
                    return True
                    
            elif key_code == KEY_LEFT:
                if pressed != self.key_states["left_pressed"]:
                    self.key_states["left_pressed"] = pressed
                    
                    # Реализация перемотки назад может быть добавлена здесь
                    # В текущей версии мы просто будем перематывать назад на 10 секунд
                    if pressed:
                        self.rewind(10)
                        
                    return True
            
            return False
        except Exception as e:
            error_msg = f"Ошибка при обработке нажатия клавиши в режиме воспроизведения: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def delete_current_file(self):
        """
        Удаляет текущий файл (с подтверждением)
        
        Returns:
            bool: True если процесс удаления начат, иначе False
        """
        try:
            if not self.files_list or self.current_index < 0 or self.current_index >= len(self.files_list):
                if self.debug:
                    print("Невозможно удалить файл: нет текущего файла")
                return False
            
            if not self.allow_delete:
                if self.debug:
                    print("Удаление файлов запрещено")
                return False
            
            # Если уже в режиме подтверждения, выходим
            if self.confirm_delete_active:
                if self.debug:
                    print("Уже в режиме подтверждения удаления")
                return False
            
            # Получаем информацию о файле
            file_info = self.get_current_file_info()
            if not file_info:
                if self.debug:
                    print("Не удалось получить информацию о файле")
                return False
            
            # Приостанавливаем воспроизведение, если оно активно
            was_playing = self.playback_info["active"]
            was_paused = self.playback_info["paused"]
            
            if was_playing and not was_paused:
                if self.debug:
                    print("Приостанавливаем воспроизведение перед удалением")
                self.player.pause()
                self.playback_info["paused"] = True
            
            # Активируем режим подтверждения
            self.confirm_delete_active = True
            self.confirm_delete_selected = "Нет"
            
            # Используем мужской голос для системных сообщений
            voice_id = "ru-RU-Standard-D"
            
            # Озвучиваем запрос на подтверждение
            message = f"Вы точно хотите удалить запись {file_info['description']}?"
            if self.debug:
                print(f"Запрос подтверждения: {message}")
                
            if self.tts_manager:
                try:
                    if hasattr(self.tts_manager, 'play_speech_blocking'):
                        self.tts_manager.play_speech_blocking(message, voice_id=voice_id)
                    else:
                        self.tts_manager.play_speech(message, voice_id=voice_id)
                        time.sleep(1.5)
                except Exception as e:
                    print(f"Ошибка при озвучивании запроса на удаление: {e}")
            
            # Обновляем интерфейс для отображения меню подтверждения
            if self.update_callback:
                self.update_callback()
            
            return True
        except Exception as e:
            error_msg = f"Ошибка при запросе удаления файла: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def confirm_delete(self, confirmed):
        """
        Подтверждает или отменяет удаление файла
        
        Args:
            confirmed (bool): True для подтверждения, False для отмены
            
        Returns:
            bool: True если операция выполнена, иначе False
        """
        if not self.confirm_delete_active:
            return False
        
        # Сбрасываем состояние подтверждения
        self.confirm_delete_active = False
        self.confirm_delete_selected = "Нет" if confirmed else "Да"
        
        if confirmed:
            # Выполняем удаление файла
            return self._execute_delete()
        else:
            # Возобновляем воспроизведение, если оно было активно
            if self.player.is_active() and self.player.is_on_pause():
                self.player.resume()
                
                # Сообщаем об отмене
                self.tts_manager.play_speech("Удаление отменено")
                
                # Обновляем интерфейс
                if self.update_callback:
                    self.update_callback()
            
            return True
    
    def cancel_confirm_delete(self):
        """
        Отменяет процесс подтверждения удаления (при нажатии KEY_BACK)
        
        Returns:
            bool: True если отмена выполнена, иначе False
        """
        return self.confirm_delete(False)
    
    def _execute_delete(self):
        """
        Выполняет фактическое удаление текущего файла
        
        Returns:
            bool: True если файл успешно удален, иначе False
        """
        if not self.files_list or self.current_index < 0 or self.current_index >= len(self.files_list):
            return False
        
        # Получаем путь к файлу
        file_path = self.files_list[self.current_index]
        
        # Останавливаем воспроизведение, если оно активно
        if self.player.is_active():
            self.player.stop()
        
        # Удаляем файл
        try:
            os.remove(file_path)
            
            if self.debug:
                print(f"Файл удален: {file_path}")
            
            # Удаляем файл из списка
            del self.files_list[self.current_index]
            
            # Корректируем текущий индекс
            if not self.files_list:
                self.current_index = -1
            elif self.current_index >= len(self.files_list):
                self.current_index = len(self.files_list) - 1
            
            # Озвучиваем результат
            self.tts_manager.play_speech("Запись удалена")
            
            # Обновляем интерфейс
            if self.update_callback:
                self.update_callback()
            
            return True
        except Exception as e:
            if self.debug:
                print(f"Ошибка при удалении файла: {e}")
            
            # Озвучиваем ошибку
            self.tts_manager.play_speech("Ошибка при удалении записи")
            
            return False
    
    def is_delete_confirmation_active(self):
        """
        Проверяет, активен ли режим подтверждения удаления
        
        Returns:
            bool: True если режим подтверждения активен
        """
        return self.confirm_delete_active
    
    def get_return_menu(self):
        """
        Возвращает меню для возврата
        
        Returns:
            объект меню или None
        """
        return self.return_to_menu
    
    def is_playing(self):
        """
        Проверяет, активно ли воспроизведение в данный момент
        
        Returns:
            bool: True, если воспроизведение активно (даже если на паузе), иначе False
        """
        try:
            return self.playback_info["active"]
        except Exception as e:
            error_msg = f"Ошибка при проверке статуса воспроизведения: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def clean_up(self):
        """Освобождает ресурсы"""
        if self.player:
            self.player.clean_up()
        
        self.files_list = []
        self.current_index = -1
        self.current_folder = None
    
    def set_current_file(self, index):
        """
        Устанавливает текущий файл по индексу
        
        Args:
            index (int): Индекс файла в списке
            
        Returns:
            bool: True, если файл успешно установлен
        """
        try:
            if index < 0 or index >= len(self.files_list):
                if self.debug:
                    print(f"Индекс файла за пределами диапазона: {index}, доступно {len(self.files_list)} файлов")
                return False
                
            self.current_index = index
            
            if self.debug:
                print(f"Установлен текущий файл с индексом {index}: {self.files_list[index]}")
                
            return True
        except Exception as e:
            error_msg = f"Ошибка при установке текущего файла: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False 