#!/usr/bin/env python3
"""
Главный файл для запуска иерархического меню.
"""
import os
import sys
import signal
import argparse
import sentry_sdk

from .menu_manager import MenuManager
from .input_handler import InputHandler
from .display_manager import DisplayManager
from .tts_manager import TTSManager
from .settings_manager import SettingsManager

def main():
    """Основная функция для запуска меню"""
    try:
        # Создаем парсер аргументов командной строки
        parser = argparse.ArgumentParser(description='Запуск иерархического меню с озвучкой')
        parser.add_argument('--no-tts', action='store_true', help='Отключить озвучку')
        parser.add_argument('--cache-dir', type=str, default='/home/aleks/cache_tts', help='Директория для кэширования звуков')
        parser.add_argument('--debug', action='store_true', help='Включить режим отладки с выводом диагностической информации')
        parser.add_argument('--use-mp3', action='store_true', help='Использовать MP3 вместо WAV для воспроизведения')
        parser.add_argument('--voice', type=str, help='Идентификатор голоса для озвучки')
        parser.add_argument('--tts-engine', type=str, choices=['gtts', 'google_cloud'], help='Движок для синтеза речи (gtts или google_cloud)')
        parser.add_argument('--google-cloud-credentials', type=str, help='Путь к файлу с учетными данными Google Cloud')
        parser.add_argument('--records-dir', type=str, default='/home/aleks/records', help='Директория для сохранения аудиозаписей')
        args = parser.parse_args()
        
        # Добавляем контекст для Sentry
        sentry_sdk.set_context("args", {
            "no_tts": args.no_tts,
            "cache_dir": args.cache_dir,
            "debug": args.debug,
            "use_mp3": args.use_mp3,
            "voice": args.voice,
            "tts_engine": args.tts_engine,
            "records_dir": args.records_dir
        })
        
        # Настраиваем обработчик Ctrl+C для корректного завершения
        signal.signal(signal.SIGINT, lambda signal, frame: sys.exit(0))
        
        # Создаем менеджер настроек
        settings_file = os.path.join(args.cache_dir, "settings.json")
        settings_manager = SettingsManager(settings_file=settings_file, debug=args.debug)
        
        # Устанавливаем настройки, если они указаны в аргументах
        if args.voice:
            if args.voice in settings_manager.get_available_voices():
                settings_manager.set_voice(args.voice)
                if args.debug:
                    print(f"Установлен голос: {args.voice}")
        
        # Устанавливаем движок TTS, если указан
        if args.tts_engine:
            settings_manager.set_tts_engine(args.tts_engine)
            if args.debug:
                print(f"Установлен движок TTS: {args.tts_engine}")
        
        # Устанавливаем путь к файлу с учетными данными Google Cloud, если указан
        if args.google_cloud_credentials:
            credentials_path = os.path.abspath(args.google_cloud_credentials)
            if os.path.exists(credentials_path):
                settings_manager.set_google_cloud_credentials(credentials_path)
                if args.debug:
                    print(f"Установлен файл учетных данных Google Cloud: {credentials_path}")
            else:
                print(f"Файл с учетными данными не найден: {credentials_path}")
        
        # Если включен режим отладки, выводим дополнительную информацию
        if args.debug:
            print(f"Запуск с параметрами: {args}")
            if not args.no_tts:
                current_voice = settings_manager.get_voice()
                current_engine = settings_manager.get_tts_engine()
                credentials_file = settings_manager.get_google_cloud_credentials()
                print(f"Текущий голос: {current_voice}")
                print(f"Текущий движок TTS: {current_engine}")
                print(f"Файл учетных данных Google Cloud: {credentials_file}")
        
        # Создаем менеджер меню
        menu_manager = MenuManager(
            tts_enabled=not args.no_tts, 
            cache_dir=args.cache_dir, 
            debug=args.debug,
            use_wav=not args.use_mp3,
            settings_manager=settings_manager,
            records_dir=args.records_dir
        )
        
        # Создаем структуру меню
        menu_manager.create_menu_structure()
        
        # Отображаем текущее меню
        menu_manager.display_current_menu()
        
        # Создаем обработчик ввода
        input_handler = InputHandler(menu_manager)
        
        # Запускаем цикл обработки ввода
        input_handler.start_input_loop()
    except Exception as e:
        error_msg = f"Критическая ошибка в main(): {e}"
        print(error_msg)
        sentry_sdk.capture_exception(e)
        sys.exit(1)

if __name__ == "__main__":
    try:
        # Преобразуем относительный импорт в абсолютный для запуска непосредственно этого файла
        if __package__ is None:
            # Добавляем родительскую директорию в sys.path
            sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
            from menu.menu_manager import MenuManager
            from menu.input_handler import InputHandler
            from menu.settings_manager import SettingsManager
        
        main()
    except Exception as e:
        error_msg = f"Критическая ошибка при запуске main.py: {e}"
        print(error_msg)
        sentry_sdk.capture_exception(e)
        sys.exit(1)