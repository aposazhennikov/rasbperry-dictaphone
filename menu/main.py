#!/usr/bin/env python3
"""
Главный файл для запуска иерархического меню.
"""
import os
import sys
import signal
import argparse

from .menu_manager import MenuManager
from .input_handler import InputHandler

def main():
    """Основная функция для запуска меню"""
    # Создаем парсер аргументов командной строки
    parser = argparse.ArgumentParser(description='Запуск иерархического меню с озвучкой')
    parser.add_argument('--no-tts', action='store_true', help='Отключить озвучку')
    parser.add_argument('--cache-dir', type=str, default='/home/aleks/cache_tts', help='Директория для кэширования звуков')
    parser.add_argument('--debug', action='store_true', help='Включить режим отладки с выводом диагностической информации')
    parser.add_argument('--use-mp3', action='store_true', help='Использовать MP3 вместо WAV для воспроизведения')
    args = parser.parse_args()
    
    # Настраиваем обработчик Ctrl+C для корректного завершения
    signal.signal(signal.SIGINT, lambda signal, frame: sys.exit(0))
    
    # Создаем менеджер меню
    menu_manager = MenuManager(
        tts_enabled=not args.no_tts, 
        cache_dir=args.cache_dir, 
        debug=args.debug,
        use_wav=not args.use_mp3
    )
    
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