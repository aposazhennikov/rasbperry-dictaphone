#!/usr/bin/env python3
"""
Скрипт для запуска меню из корневой директории проекта.
"""
import sys
import os
import argparse

# Добавляем текущую директорию в путь поиска модулей
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Создаем парсер аргументов командной строки
parser = argparse.ArgumentParser(description='Запуск иерархического меню с озвучкой')
parser.add_argument('--no-tts', action='store_true', help='Отключить озвучку')
parser.add_argument('--cache-dir', type=str, default='/home/aleks/cache_tts', help='Директория для кэширования звуков')
parser.add_argument('--pre-generate', action='store_true', help='Предварительно сгенерировать все звуки и выйти')
parser.add_argument('--debug', action='store_true', help='Включить режим отладки с выводом диагностической информации')
parser.add_argument('--use-mp3', action='store_true', help='Использовать MP3 вместо WAV для воспроизведения')

args = parser.parse_args()

if args.pre_generate:
    print("Предварительная генерация звуков...")
    # Импортируем классы для генерации звуков
    from menu import MenuManager, TTSManager
    
    # Создаем менеджер меню
    menu_manager = MenuManager(
        tts_enabled=True, 
        cache_dir=args.cache_dir, 
        debug=args.debug,
        use_wav=not args.use_mp3
    )
    
    # Создаем структуру меню
    menu_manager.create_menu_structure()
    
    print("Генерация звуков завершена.")
    
    # Если в режиме отладки, выводим статистику
    if args.debug and menu_manager.tts_enabled:
        debug_info = menu_manager.tts_manager.get_debug_info()
        print("\n=== Статистика TTS ===")
        print(f"Всего запросов: {debug_info['total_requests']}")
        print(f"Запросов сегодня: {debug_info['today_requests']}")
        print(f"Примерно осталось бесплатных запросов: {debug_info['remaining_free_requests']}")
        print(f"Использований кэша: {debug_info['cached_used']}")
    
    sys.exit(0)

# Импортируем основную функцию из пакета menu
from menu.main import main

if __name__ == "__main__":
    # Передаем аргументы в sys.argv для использования в main.py
    main()