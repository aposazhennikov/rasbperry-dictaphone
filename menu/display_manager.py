#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import sentry_sdk

class DisplayManager:
    """
    Класс для управления отображением информации на экране.
    Поддерживает различные экраны: меню, запись, воспроизведение.
    """
    
    def __init__(self, menu_manager):
        """
        Инициализация менеджера отображения
        
        Args:
            menu_manager: Менеджер меню для доступа к данным
        """
        try:
            self.menu_manager = menu_manager
            self.debug = menu_manager.debug
            
            # Текущий экран (menu, recording, playback, delete_confirmation)
            self.current_screen = "menu"
            
            # Размеры экрана
            self.screen_width = 80
            self.screen_height = 24
            
            if self.debug:
                print("DisplayManager инициализирован")
        except Exception as e:
            error_msg = f"Ошибка при инициализации DisplayManager: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def clear_screen(self):
        """Очищает экран"""
        try:
            os.system('cls' if os.name == 'nt' else 'clear')
        except Exception as e:
            error_msg = f"Ошибка при очистке экрана: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def display_menu(self, menu):
        """
        Отображает меню
        
        Args:
            menu: Объект меню для отображения
        """
        try:
            self.current_screen = "menu"
            self.clear_screen()
            
            # Заголовок
            print("=" * self.screen_width)
            print(menu.name.center(self.screen_width))
            print("=" * self.screen_width + "\n")
            
            # Проверяем, есть ли элементы в меню
            if not menu.items:
                print("Меню пусто".center(self.screen_width))
                return
            
            # Отображаем элементы меню
            for i, item in enumerate(menu.items):
                prefix = "→ " if i == menu.current_selection else "  "
                print(f"{prefix}{item.name}")
            
            # Добавляем пустое пространство до нижней части экрана
            visible_items = len(menu.items)
            for _ in range(max(0, self.screen_height - visible_items - 7)):
                print()
            
            # Нижняя часть экрана
            print("\n" + "=" * self.screen_width)
            print("Навигация: UP/DOWN - перемещение, SELECT - выбор, BACK - возврат")
            print("=" * self.screen_width)
        except Exception as e:
            error_msg = f"Ошибка при отображении меню: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def display_recording_screen(self, status, time, folder):
        """
        Отображает экран записи
        
        Args:
            status (str): Статус записи ("Recording" или "Paused")
            time (str): Текущее время записи
            folder (str): Папка для сохранения
        """
        try:
            self.current_screen = "recording"
            self.clear_screen()
            
            # Заголовок
            print("=" * self.screen_width)
            print("РЕЖИМ ЗАПИСИ".center(self.screen_width))
            print("=" * self.screen_width)
            
            # Статус записи
            status_text = "ЗАПИСЬ" if status == "Recording" else "ПАУЗА"
            print(f"\nСтатус: {status_text}")
            print(f"Время записи: {time}")
            print(f"Папка: {folder}")
            
            # Инструкции
            print("\n" + "=" * self.screen_width)
            print("SELECT - пауза/возобновление, BACK - остановка и сохранение")
            print("=" * self.screen_width)
        except Exception as e:
            error_msg = f"Ошибка при отображении экрана записи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def display_playback_screen(self, status, time, progress, file_name, folder):
        """
        Отображает экран воспроизведения
        
        Args:
            status (str): Статус воспроизведения ("Playing" или "Paused")
            time (str): Текущее время/общая длительность
            progress (int): Прогресс воспроизведения (0-100)
            file_name (str): Имя файла
            folder (str): Папка с файлами
        """
        try:
            self.current_screen = "playback"
            self.clear_screen()
            
            # Заголовок
            print("=" * self.screen_width)
            print("ВОСПРОИЗВЕДЕНИЕ ЗАПИСИ".center(self.screen_width))
            print("=" * self.screen_width)
            
            # Информация о файле
            print(f"\nФайл: {file_name}")
            print(f"Папка: {folder}")
            
            # Статус и время
            status_text = "ВОСПРОИЗВЕДЕНИЕ" if status == "Playing" else "ПАУЗА"
            print(f"\nСтатус: {status_text}")
            print(f"Время: {time}")
            
            # Прогресс-бар
            bar_width = 50
            filled_width = int(bar_width * progress / 100)
            bar = "▓" * filled_width + "░" * (bar_width - filled_width)
            print(f"\n[{bar}] {progress}%")
            
            # Инструкции
            print("\n" + "=" * self.screen_width)
            print("SELECT - пауза/возобновление, BACK - остановка")
            print("UP/DOWN - громкость, LEFT(удерж) - перемотка, RIGHT(удерж) - ускорение")
            print("PAGE UP/DOWN - пред./след. запись, POWER - удалить запись")
            print("=" * self.screen_width)
        except Exception as e:
            error_msg = f"Ошибка при отображении экрана воспроизведения: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def display_delete_confirmation(self, file_name, selected_option="Нет"):
        """
        Отображает экран подтверждения удаления
        
        Args:
            file_name (str): Имя файла для удаления
            selected_option (str): Выбранный вариант ("Да" или "Нет")
        """
        try:
            self.current_screen = "delete_confirmation"
            self.clear_screen()
            
            # Заголовок
            print("=" * self.screen_width)
            print("ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ".center(self.screen_width))
            print("=" * self.screen_width)
            
            # Информация о файле
            print(f"\nВы уверены, что хотите удалить файл:")
            print(f"\n{file_name}")
            
            # Варианты выбора
            print("\nВыберите действие:")
            yes_prefix = "→ " if selected_option == "Да" else "  "
            no_prefix = "→ " if selected_option == "Нет" else "  "
            
            print(f"{yes_prefix}Да - удалить файл")
            print(f"{no_prefix}Нет - отменить удаление")
            
            # Инструкции
            print("\n" + "=" * self.screen_width)
            print("UP/DOWN - выбор, SELECT - подтвердить, BACK - отменить")
            print("=" * self.screen_width)
        except Exception as e:
            error_msg = f"Ошибка при отображении экрана подтверждения удаления: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def display_message(self, message, title="Сообщение"):
        """
        Отображает информационное сообщение
        
        Args:
            message (str): Текст сообщения
            title (str): Заголовок сообщения
        """
        try:
            self.clear_screen()
            
            # Заголовок
            print("=" * self.screen_width)
            print(title.center(self.screen_width))
            print("=" * self.screen_width)
            
            # Содержимое сообщения
            print(f"\n{message}\n")
            
            # Инструкции
            print("\n" + "=" * self.screen_width)
            print("Нажмите любую клавишу для продолжения...")
            print("=" * self.screen_width)
        except Exception as e:
            error_msg = f"Ошибка при отображении сообщения: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def display_debug_info(self):
        """Отображает отладочную информацию"""
        try:
            # Сохраняем текущий экран
            previous_screen = self.current_screen
            
            self.clear_screen()
            
            # Заголовок
            print("=" * self.screen_width)
            print("ОТЛАДОЧНАЯ ИНФОРМАЦИЯ".center(self.screen_width))
            print("=" * self.screen_width + "\n")
            
            # Получаем отладочную информацию из меню
            debug_info = self.menu_manager.get_debug_info()
            
            # Выводим информацию
            for key, value in debug_info.items():
                print(f"{key}: {value}")
            
            print("\n" + "=" * self.screen_width)
            print("Нажмите любую клавишу для возврата...")
            
            # Восстанавливаем предыдущий экран
            self.current_screen = previous_screen
        except Exception as e:
            error_msg = f"Ошибка при отображении отладочной информации: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e) 