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
        Загружает список файлов из указанной папки
        
        Args:
            folder (str): Имя папки ('A', 'B' или 'C')
            return_to_menu: Меню, в которое нужно вернуться после завершения
            
        Returns:
            bool: True если папка успешно загружена, иначе False
        """
        folder_path = os.path.join(self.base_dir, folder)
        
        if not os.path.exists(folder_path):
            if self.debug:
                print(f"Папка не найдена: {folder_path}")
            return False
        
        # Сохраняем текущую папку и меню возврата
        self.current_folder = folder
        self.return_to_menu = return_to_menu
        
        # Получаем список файлов
        self.files_list = self._get_audio_files(folder_path)
        
        # Сортируем по дате создания (от новых к старым)
        self.files_list.sort(key=lambda f: os.path.getmtime(f), reverse=True)
        
        # Сбрасываем текущий индекс
        self.current_index = 0 if self.files_list else -1
        
        if self.debug:
            print(f"Загружены файлы из папки {folder}: {len(self.files_list)} файлов")
            
        return len(self.files_list) > 0
    
    def _get_audio_files(self, folder_path):
        """
        Получает список аудиофайлов из указанной папки
        
        Args:
            folder_path (str): Путь к папке
            
        Returns:
            list: Список путей к аудиофайлам
        """
        audio_files = []
        
        # Проверяем существование папки
        if not os.path.exists(folder_path):
            return audio_files
        
        # Получаем список файлов
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            
            # Проверяем, что это файл и имеет поддерживаемое расширение
            if os.path.isfile(file_path) and file.lower().endswith(('.wav', '.mp3', '.ogg')):
                audio_files.append(file_path)
        
        return audio_files
    
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
            if self.player.current_file != file_path:
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
        if not self.files_list or self.current_index < 0 or self.current_index >= len(self.files_list):
            return False
        
        # Получаем путь к файлу
        file_path = self.files_list[self.current_index]
        
        # Загружаем файл, если это новый файл
        if self.player.current_file != file_path:
            if not self.player.load_file(file_path):
                if self.debug:
                    print(f"Не удалось загрузить файл: {file_path}")
                return False
        
        # Начинаем воспроизведение
        result = self.player.play()
        
        if result:
            # Обновляем информацию о воспроизведении
            self.playback_info["active"] = True
            self.playback_info["paused"] = False
            self.playback_info["current_file"] = file_path
            self.playback_info["position"] = self.player.get_formatted_position()
            self.playback_info["duration"] = self.player.get_formatted_duration()
            self.playback_info["progress"] = self.player.get_progress()
            
            # Озвучиваем начало воспроизведения
            file_info = self.get_current_file_info()
            if file_info:
                self.tts_manager.play_speech(f"Воспроизведение {file_info['description']}")
            
            # Обновляем интерфейс
            if self.update_callback:
                self.update_callback()
        
        return result
    
    def toggle_pause(self):
        """
        Переключает паузу воспроизведения
        
        Returns:
            bool: True если состояние успешно изменено, иначе False
        """
        if not self.player.is_active():
            return False
        
        if self.player.is_on_pause():
            # Возобновляем воспроизведение
            result = self.player.resume()
            if result:
                self.playback_info["paused"] = False
                
                # Озвучиваем возобновление воспроизведения
                self.tts_manager.play_speech("Воспроизведение возобновлено")
        else:
            # Приостанавливаем воспроизведение
            result = self.player.pause()
            if result:
                self.playback_info["paused"] = True
                
                # Озвучиваем приостановку воспроизведения
                self.tts_manager.play_speech("Воспроизведение приостановлено")
        
        # Обновляем интерфейс
        if self.update_callback:
            self.update_callback()
        
        return result
    
    def stop_playback(self):
        """
        Останавливает воспроизведение
        
        Returns:
            bool: True если воспроизведение успешно остановлено, иначе False
        """
        if not self.player.is_active():
            return False
        
        result = self.player.stop()
        
        if result:
            # Сбрасываем информацию о воспроизведении
            self.playback_info["active"] = False
            self.playback_info["paused"] = False
            self.playback_info["position"] = "00:00"
            self.playback_info["progress"] = 0
            
            # Озвучиваем остановку воспроизведения
            self.tts_manager.play_speech("Воспроизведение остановлено")
            
            # Обновляем интерфейс
            if self.update_callback:
                self.update_callback()
        
        return result
    
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
        # Коды клавиш могут отличаться в зависимости от системы
        KEY_RIGHT = 106  # Перемотка вперед / ускоренное воспроизведение
        KEY_LEFT = 105   # Перемотка назад
        
        if key_code == KEY_RIGHT:
            if pressed != self.key_states["right_pressed"]:
                self.key_states["right_pressed"] = pressed
                
                # Включаем/выключаем ускоренное воспроизведение
                self.toggle_fast_playback(pressed)
                
                return True
                
        elif key_code == KEY_LEFT:
            if pressed != self.key_states["left_pressed"]:
                self.key_states["left_pressed"] = pressed
                
                # Если нажата, выполняем перемотку назад
                if pressed:
                    self.player.rewind(10)  # Перемотка на 10 секунд назад
                    
                    if self.debug:
                        print("Перемотка назад на 10 секунд")
                
                return True
        
        return False
    
    def delete_current_file(self):
        """
        Удаляет текущий файл (с подтверждением)
        
        Returns:
            bool: True если процесс удаления начат, иначе False
        """
        if not self.files_list or self.current_index < 0 or self.current_index >= len(self.files_list):
            return False
        
        if not self.allow_delete:
            if self.debug:
                print("Удаление файлов запрещено")
            return False
        
        # Если уже в режиме подтверждения, выходим
        if self.confirm_delete_active:
            return False
        
        # Получаем информацию о файле
        file_info = self.get_current_file_info()
        if not file_info:
            return False
        
        # Приостанавливаем воспроизведение, если оно активно
        was_playing = self.player.is_active()
        was_paused = self.player.is_on_pause()
        
        if was_playing and not was_paused:
            self.player.pause()
        
        # Активируем режим подтверждения
        self.confirm_delete_active = True
        self.confirm_delete_selected = "Нет"
        
        # Озвучиваем запрос на подтверждение
        self.tts_manager.play_speech(f"Вы точно хотите удалить запись {file_info['description']}?")
        
        # Обновляем интерфейс
        if self.update_callback:
            self.update_callback()
        
        return True
    
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