#!/usr/bin/env python3
"""
Главный файл для запуска иерархического меню.
"""
import os
import sys
import signal

from .menu_manager import MenuManager
from .input_handler import InputHandler

def main():
    """Основная функция для запуска меню"""
    # Настраиваем обработчик Ctrl+C для корректного завершения
    signal.signal(signal.SIGINT, lambda signal, frame: sys.exit(0))
    
    # Создаем менеджер меню
    menu_manager = MenuManager()
    
    # Создаем структуру меню
    menu_manager.create_menu_structure()
    
    # Отображаем текущее меню
    menu_manager.display_current_menu()
    
    # Создаем обработчик ввода
    input_handler = InputHandler(menu_manager)
    
    # Запускаем цикл обработки ввода
    input_handler.start_input_loop()
    

if __name__ == "__main__":
    # Преобразуем относительный импорт в абсолютный для запуска непосредственно этого файла
    if __package__ is None:
        # Добавляем родительскую директорию в sys.path
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        from menu.menu_manager import MenuManager
        from menu.input_handler import InputHandler
    
    main() 