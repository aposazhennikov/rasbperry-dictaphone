#!/usr/bin/env python3
import os
import time
import glob
import sentry_sdk
from pathlib import Path
from .menu_item import MenuItem, SubMenu

class BulkDeleteManager:
    """
    Класс для управления массовым удалением аудиозаписей из папок диктофона.
    """
    
    def __init__(self, menu_manager, records_dir="/home/aleks/records", debug=False):
        """
        Инициализация менеджера массового удаления
        
        Args:
            menu_manager: Менеджер меню для взаимодействия с общим интерфейсом
            records_dir (str): Базовая директория с записями
            debug (bool): Режим отладки
        """
        try:
            self.menu_manager = menu_manager
            self.records_dir = records_dir
            self.debug = debug
            
            if self.debug:
                print("BulkDeleteManager инициализирован")
        except Exception as e:
            error_msg = f"Ошибка при инициализации BulkDeleteManager: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def show_delete_menu(self):
        """Показывает меню массового удаления записей"""
        try:
            # Получаем доступ к необходимым компонентам из менеджера меню
            playback_manager = self.menu_manager.playback_manager
            settings_manager = self.menu_manager.settings_manager
            tts_manager = self.menu_manager.tts_manager
            display_manager = self.menu_manager.display_manager
            tts_enabled = self.menu_manager.tts_enabled
            
            # Создаем временное подменю для выбора папки
            delete_menu = SubMenu("Массовое удаление записей", parent=self.menu_manager.current_menu)
            
            # Получаем количество файлов в каждой папке
            files_in_a = playback_manager.count_files_in_folder("A")
            files_in_b = playback_manager.count_files_in_folder("B")
            files_in_c = playback_manager.count_files_in_folder("C")
            
            # Добавляем пункты меню для папок с указанием количества файлов
            folder_a_item = MenuItem(
                f"Папка A [{files_in_a} {self._get_files_word(files_in_a)}]",
                action=lambda: self.confirm_delete_folder("A", files_in_a),
                speech_text="Папка A"  # Только название папки для озвучки
            )
            delete_menu.add_item(folder_a_item)
            
            folder_b_item = MenuItem(
                f"Папка B [{files_in_b} {self._get_files_word(files_in_b)}]",
                action=lambda: self.confirm_delete_folder("B", files_in_b),
                speech_text="Папка B"  # Только название папки для озвучки
            )
            delete_menu.add_item(folder_b_item)
            
            folder_c_item = MenuItem(
                f"Папка C [{files_in_c} {self._get_files_word(files_in_c)}]",
                action=lambda: self.confirm_delete_folder("C", files_in_c),
                speech_text="Папка C"  # Только название папки для озвучки
            )
            delete_menu.add_item(folder_c_item)
            
            # Добавляем пункт для удаления записей из всех папок
            total_files = files_in_a + files_in_b + files_in_c
            all_folders_item = MenuItem(
                f"Удалить записи из всех папок [{total_files} {self._get_files_word(total_files)}]",
                action=lambda: self.confirm_delete_all_folders(files_in_a, files_in_b, files_in_c),
                speech_text="Удалить записи из всех папок"
            )
            delete_menu.add_item(all_folders_item)
            
            # Переключаемся на меню выбора папки
            self.menu_manager.current_menu = delete_menu
            self.menu_manager.display_current_menu()
        except Exception as e:
            error_msg = f"Ошибка при отображении меню удаления: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def confirm_delete_folder(self, folder, files_count):
        """
        Показывает меню подтверждения удаления всех записей из папки
        
        Args:
            folder (str): Буква папки (A, B, C)
            files_count (int): Количество файлов в папке
        """
        try:
            # Получаем доступ к необходимым компонентам из менеджера меню
            settings_manager = self.menu_manager.settings_manager
            tts_manager = self.menu_manager.tts_manager
            display_manager = self.menu_manager.display_manager
            tts_enabled = self.menu_manager.tts_enabled
            
            if files_count == 0:
                # Если в папке нет файлов, показываем сообщение и не удаляем
                if self.debug:
                    print(f"В папке {folder} нет записей для удаления")
                
                # Отображаем сообщение на экране
                display_manager.display_message(f"В папке {folder} нет записей", title="Пустая папка")
                
                if tts_enabled:
                    # Получаем текущий голос из настроек
                    voice = settings_manager.get_voice()
                    tts_manager.play_speech_blocking("В папке", voice_id=voice)
                    time.sleep(0.1)  # Небольшая пауза между сообщениями
                    tts_manager.play_speech_blocking(folder, voice_id=voice)
                    time.sleep(0.1)  # Небольшая пауза между сообщениями
                    tts_manager.play_speech_blocking("нет записей", voice_id=voice)
                
                # Возвращаемся к меню удаления через 2 секунды
                time.sleep(2)
                self.menu_manager.display_current_menu()
                return
            
            # Создаем подменю для подтверждения удаления
            confirm_menu = SubMenu(f"Подтверждение удаления из папки {folder}", parent=self.menu_manager.current_menu)
            
            # Информация для озвучки
            folder_speech = folder  # Буква папки
            files_speech = f"{files_count} {self._get_files_word(files_count)}"  # Количество файлов
            
            # Добавляем пункты меню подтверждения
            # ВАЖНО: пункт "Нет" должен быть первым
            no_item = MenuItem(
                "Нет",
                action=lambda: self.return_to_dictaphone_menu(),
                speech_text="Нет"
            )
            confirm_menu.add_item(no_item)
            
            yes_item = MenuItem(
                "Да",
                action=lambda: self.execute_delete_folder(folder),
                speech_text="Да"
            )
            confirm_menu.add_item(yes_item)
            
            # Переключаемся на меню подтверждения
            self.menu_manager.current_menu = confirm_menu
            
            # Отображаем сообщение подтверждения на экране
            message = f"Вы действительно хотите удалить все записи из папки {folder}? Количество записей - {files_count}"
            display_manager.display_message(message, title="Подтверждение удаления")
            
            # Озвучиваем сообщение
            if tts_enabled:
                try:
                    voice = settings_manager.get_voice()
                    # Используем мужской голос для системных сообщений
                    system_voice = "ru-RU-Standard-D"
                    
                    tts_manager.play_speech_blocking("Вы действительно хотите удалить все записи из папки", voice_id=system_voice)
                    time.sleep(0.1)  # Небольшая пауза между сообщениями
                    tts_manager.play_speech_blocking(folder_speech, voice_id=system_voice)
                    time.sleep(0.1)  # Небольшая пауза между сообщениями
                    tts_manager.play_speech_blocking("Количество записей", voice_id=system_voice)
                    time.sleep(0.1)  # Небольшая пауза между сообщениями
                    tts_manager.play_speech_blocking(files_speech, voice_id=system_voice)
                except Exception as voice_error:
                    print(f"Ошибка при озвучивании подтверждения удаления: {voice_error}")
                    sentry_sdk.capture_exception(voice_error)
            
            # Отображаем меню подтверждения
            self.menu_manager.display_current_menu()
        except Exception as e:
            error_msg = f"Ошибка при отображении подтверждения удаления папки: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def confirm_delete_all_folders(self, files_in_a, files_in_b, files_in_c):
        """
        Показывает меню подтверждения удаления всех записей из всех папок
        
        Args:
            files_in_a (int): Количество файлов в папке A
            files_in_b (int): Количество файлов в папке B
            files_in_c (int): Количество файлов в папке C
        """
        try:
            # Получаем доступ к необходимым компонентам из менеджера меню
            settings_manager = self.menu_manager.settings_manager
            tts_manager = self.menu_manager.tts_manager
            display_manager = self.menu_manager.display_manager
            tts_enabled = self.menu_manager.tts_enabled
            
            total_files = files_in_a + files_in_b + files_in_c
            
            if total_files == 0:
                # Если нет файлов во всех папках, показываем сообщение и не удаляем
                if self.debug:
                    print("Нет записей для удаления во всех папках")
                
                # Отображаем сообщение на экране
                display_manager.display_message("Нет записей во всех папках", title="Пустые папки")
                
                if tts_enabled:
                    # Получаем текущий голос из настроек
                    voice = settings_manager.get_voice()
                    tts_manager.play_speech_blocking("Нет записей во всех папках", voice_id=voice)
                
                # Возвращаемся к меню удаления через 2 секунды
                time.sleep(2)
                self.menu_manager.display_current_menu()
                return
            
            # Создаем подменю для подтверждения удаления
            confirm_menu = SubMenu("Подтверждение удаления из всех папок", parent=self.menu_manager.current_menu)
            
            # Информация для озвучки
            files_speech = f"{total_files} {self._get_files_word(total_files)}"  # Общее количество файлов
            
            # Добавляем пункты меню подтверждения
            # ВАЖНО: пункт "Нет" должен быть первым
            no_item = MenuItem(
                "Нет",
                action=lambda: self.return_to_dictaphone_menu(),
                speech_text="Нет"
            )
            confirm_menu.add_item(no_item)
            
            yes_item = MenuItem(
                "Да",
                action=lambda: self.show_final_confirmation_all_folders(),
                speech_text="Да"
            )
            confirm_menu.add_item(yes_item)
            
            # Переключаемся на меню подтверждения
            self.menu_manager.current_menu = confirm_menu
            
            # Отображаем сообщение подтверждения на экране
            details = f"A: {files_in_a}, B: {files_in_b}, C: {files_in_c}"
            message = f"Вы точно хотите удалить все записи из всех папок?\nВсего: {total_files} ({details})"
            display_manager.display_message(message, title="Подтверждение удаления")
            
            # Озвучиваем сообщение
            if tts_enabled:
                try:
                    # Используем мужской голос для системных сообщений
                    system_voice = "ru-RU-Standard-D"
                    
                    tts_manager.play_speech_blocking("Вы точно хотите удалить все записи из всех папок", voice_id=system_voice)
                    time.sleep(0.1)  # Небольшая пауза между сообщениями
                    tts_manager.play_speech_blocking("Количество записей", voice_id=system_voice)
                    time.sleep(0.1)  # Небольшая пауза между сообщениями
                    tts_manager.play_speech_blocking(files_speech, voice_id=system_voice)
                except Exception as voice_error:
                    print(f"Ошибка при озвучивании подтверждения удаления: {voice_error}")
                    sentry_sdk.capture_exception(voice_error)
            
            # Отображаем меню подтверждения
            self.menu_manager.display_current_menu()
        except Exception as e:
            error_msg = f"Ошибка при отображении подтверждения удаления всех папок: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def show_final_confirmation_all_folders(self):
        """Показывает финальное подтверждение удаления записей из всех папок"""
        try:
            # Получаем доступ к необходимым компонентам из менеджера меню
            settings_manager = self.menu_manager.settings_manager
            tts_manager = self.menu_manager.tts_manager
            display_manager = self.menu_manager.display_manager
            tts_enabled = self.menu_manager.tts_enabled
            
            # Создаем подменю для финального подтверждения
            final_confirm_menu = SubMenu("Финальное подтверждение удаления", parent=self.menu_manager.current_menu)
            
            # Добавляем пункты меню подтверждения
            # ВАЖНО: пункт "Нет" должен быть первым
            no_item = MenuItem(
                "Нет",
                action=lambda: self.return_to_dictaphone_menu(),
                speech_text="Нет"
            )
            final_confirm_menu.add_item(no_item)
            
            yes_item = MenuItem(
                "Да",
                action=lambda: self.execute_delete_all_folders(),
                speech_text="Да"
            )
            final_confirm_menu.add_item(yes_item)
            
            # Переключаемся на меню финального подтверждения
            self.menu_manager.current_menu = final_confirm_menu
            
            # Отображаем сообщение подтверждения на экране
            message = "Финальное подтверждение удаления всех записей"
            display_manager.display_message(message, title="Окончательное подтверждение")
            
            # Озвучиваем сообщение
            if tts_enabled:
                try:
                    # Используем мужской голос для системных сообщений
                    system_voice = "ru-RU-Standard-D"
                    
                    tts_manager.play_speech_blocking("Финальное подтверждение удаления всех записей", voice_id=system_voice)
                except Exception as voice_error:
                    print(f"Ошибка при озвучивании финального подтверждения: {voice_error}")
                    sentry_sdk.capture_exception(voice_error)
            
            # Отображаем меню подтверждения
            self.menu_manager.display_current_menu()
        except Exception as e:
            error_msg = f"Ошибка при отображении финального подтверждения: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def return_to_dictaphone_menu(self):
        """Возвращение в меню диктофона после отмены удаления"""
        try:
            # Возвращаемся в режим диктофона
            dictaphone_menu = None
            
            # Ищем меню диктофона
            menu = self.menu_manager.current_menu
            while menu:
                if menu.name == "Режим диктофона":
                    dictaphone_menu = menu
                    break
                menu = menu.parent
            
            if dictaphone_menu:
                self.menu_manager.current_menu = dictaphone_menu
                self.menu_manager.display_current_menu()
            else:
                # Если не нашли меню диктофона, возвращаемся в корневое меню
                self.menu_manager.current_menu = self.menu_manager.root_menu
                self.menu_manager.display_current_menu()
        except Exception as e:
            error_msg = f"Ошибка при возврате в меню диктофона: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def execute_delete_folder(self, folder):
        """
        Выполняет удаление всех записей из указанной папки
        
        Args:
            folder (str): Буква папки (A, B, C)
        """
        try:
            # Получаем доступ к необходимым компонентам из менеджера меню
            settings_manager = self.menu_manager.settings_manager
            tts_manager = self.menu_manager.tts_manager
            display_manager = self.menu_manager.display_manager
            tts_enabled = self.menu_manager.tts_enabled
            
            # Формируем путь к папке
            folder_path = os.path.join(self.records_dir, folder)
            
            # Проверяем существование папки
            if not os.path.exists(folder_path):
                if self.debug:
                    print(f"Папка {folder_path} не существует, создаем...")
                os.makedirs(folder_path, exist_ok=True)
                
                # Сообщаем, что папка пуста
                display_manager.display_message(f"Папка {folder} пуста", title="Нет файлов")
                
                if tts_enabled:
                    voice = settings_manager.get_voice()
                    tts_manager.play_speech_blocking(f"Папка {folder} пуста", voice_id=voice)
                
                # Возвращаемся в меню диктофона через 2 секунды
                time.sleep(2)
                self.return_to_dictaphone_menu()
                return
            
            # Получаем список аудиофайлов
            audio_files = []
            for ext in ['.wav', '.mp3', '.ogg']:
                audio_files.extend(glob.glob(os.path.join(folder_path, f"*{ext}")))
            
            if not audio_files:
                # Если нет файлов, сообщаем об этом
                display_manager.display_message(f"В папке {folder} нет аудиозаписей", title="Нет файлов")
                
                if tts_enabled:
                    voice = settings_manager.get_voice()
                    tts_manager.play_speech_blocking(f"В папке {folder} нет аудиозаписей", voice_id=voice)
                
                # Возвращаемся в меню диктофона через 2 секунды
                time.sleep(2)
                self.return_to_dictaphone_menu()
                return
            
            # Удаляем все файлы
            deleted_count = 0
            for file_path in audio_files:
                try:
                    os.remove(file_path)
                    deleted_count += 1
                    
                    if self.debug:
                        print(f"Удален файл: {file_path}")
                except Exception as file_error:
                    print(f"Ошибка при удалении файла {file_path}: {file_error}")
                    sentry_sdk.capture_exception(file_error)
            
            # Выводим сообщение об успешном удалении
            message = f"Удалено {deleted_count} {self._get_files_word(deleted_count)} из папки {folder}"
            display_manager.display_message(message, title="Удаление завершено")
            
            if tts_enabled:
                try:
                    # Используем мужской голос для системных сообщений
                    system_voice = "ru-RU-Standard-D"
                    
                    tts_manager.play_speech_blocking(f"Удалено {deleted_count} {self._get_files_word(deleted_count)} из папки {folder}", voice_id=system_voice)
                except Exception as voice_error:
                    print(f"Ошибка при озвучивании результата удаления: {voice_error}")
                    sentry_sdk.capture_exception(voice_error)
            
            # Возвращаемся в меню диктофона через 2 секунды
            time.sleep(2)
            self.return_to_dictaphone_menu()
        except Exception as e:
            error_msg = f"Ошибка при удалении записей из папки {folder}: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
            # Выводим сообщение об ошибке
            display_manager = self.menu_manager.display_manager
            display_manager.display_message(f"Ошибка при удалении записей из папки {folder}", title="Ошибка")
            
            if self.menu_manager.tts_enabled:
                voice = self.menu_manager.settings_manager.get_voice()
                self.menu_manager.tts_manager.play_speech_blocking(f"Ошибка при удалении записей из папки {folder}", voice_id=voice)
            
            # Возвращаемся в меню диктофона через 2 секунды
            time.sleep(2)
            self.return_to_dictaphone_menu()
    
    def execute_delete_all_folders(self):
        """Выполняет удаление всех записей из всех папок"""
        try:
            # Получаем доступ к необходимым компонентам из менеджера меню
            settings_manager = self.menu_manager.settings_manager
            tts_manager = self.menu_manager.tts_manager
            display_manager = self.menu_manager.display_manager
            tts_enabled = self.menu_manager.tts_enabled
            
            folders = ['A', 'B', 'C']
            total_deleted = 0
            
            for folder in folders:
                # Формируем путь к папке
                folder_path = os.path.join(self.records_dir, folder)
                
                # Проверяем существование папки
                if not os.path.exists(folder_path):
                    if self.debug:
                        print(f"Папка {folder_path} не существует, создаем...")
                    os.makedirs(folder_path, exist_ok=True)
                    continue
                
                # Получаем список аудиофайлов
                audio_files = []
                for ext in ['.wav', '.mp3', '.ogg']:
                    audio_files.extend(glob.glob(os.path.join(folder_path, f"*{ext}")))
                
                # Удаляем все файлы
                for file_path in audio_files:
                    try:
                        os.remove(file_path)
                        total_deleted += 1
                        
                        if self.debug:
                            print(f"Удален файл: {file_path}")
                    except Exception as file_error:
                        print(f"Ошибка при удалении файла {file_path}: {file_error}")
                        sentry_sdk.capture_exception(file_error)
            
            # Выводим сообщение об успешном удалении
            message = f"Удалено {total_deleted} {self._get_files_word(total_deleted)} из всех папок"
            display_manager.display_message(message, title="Удаление завершено")
            
            if tts_enabled:
                try:
                    # Используем мужской голос для системных сообщений
                    system_voice = "ru-RU-Standard-D"
                    
                    tts_manager.play_speech_blocking(f"Удалено {total_deleted} {self._get_files_word(total_deleted)} из всех папок", voice_id=system_voice)
                except Exception as voice_error:
                    print(f"Ошибка при озвучивании результата удаления: {voice_error}")
                    sentry_sdk.capture_exception(voice_error)
            
            # Возвращаемся в меню диктофона через 2 секунды
            time.sleep(2)
            self.return_to_dictaphone_menu()
        except Exception as e:
            error_msg = f"Ошибка при удалении записей из всех папок: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
            # Выводим сообщение об ошибке
            display_manager = self.menu_manager.display_manager
            display_manager.display_message("Ошибка при удалении записей из всех папок", title="Ошибка")
            
            if self.menu_manager.tts_enabled:
                voice = self.menu_manager.settings_manager.get_voice()
                self.menu_manager.tts_manager.play_speech_blocking("Ошибка при удалении записей из всех папок", voice_id=voice)
            
            # Возвращаемся в меню диктофона через 2 секунды
            time.sleep(2)
            self.return_to_dictaphone_menu()
    
    def _get_files_word(self, count):
        """
        Возвращает правильное склонение слова "запись" в зависимости от числа
        
        Args:
            count (int): Количество
            
        Returns:
            str: Правильное склонение слова
        """
        if count % 10 == 1 and count % 100 != 11:
            return "запись"
        elif 2 <= count % 10 <= 4 and (count % 100 < 10 or count % 100 >= 20):
            return "записи"
        else:
            return "записей" 