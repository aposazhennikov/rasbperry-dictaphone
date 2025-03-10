#!/usr/bin/env python3
"""
Скрипт для запуска меню из корневой директории проекта.
"""
import sys
import os
import argparse
import glob
import json

# Интеграция с Sentry для отслеживания ошибок
import sentry_sdk
sentry_sdk.init(
    dsn="https://990b663058427f36a87004fc14319c09@o4508953992101888.ingest.de.sentry.io/4508953994330192",
    # Добавляем данные о пользователе и запросах
    send_default_pii=True,
    # Включаем отслеживание исключений в фоновых потоках
    enable_tracing=True,
)

# Добавляем текущую директорию в путь поиска модулей
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Создаем парсер аргументов командной строки
parser = argparse.ArgumentParser(description='Запуск иерархического меню с озвучкой')
parser.add_argument('--no-tts', action='store_true', help='Отключить озвучку')
parser.add_argument('--cache-dir', type=str, default='/home/aleks/cache_tts', help='Директория для кэширования звуков')
parser.add_argument('--pre-generate', action='store_true', help='Предварительно сгенерировать все звуки и выйти')
parser.add_argument('--pre-generate-missing', action='store_true', help='Предварительно сгенерировать только отсутствующие звуки и выйти')
parser.add_argument('--debug', action='store_true', help='Включить режим отладки с выводом диагностической информации')
parser.add_argument('--use-mp3', action='store_true', help='Использовать MP3 вместо WAV для воспроизведения')
parser.add_argument('--voice', type=str, help='Идентификатор голоса для озвучки')
parser.add_argument('--tts-engine', type=str, choices=['gtts', 'google_cloud'], help='Движок для синтеза речи (gtts или google_cloud)')
parser.add_argument('--google-cloud-credentials', type=str, help='Путь к файлу с учетными данными Google Cloud')
parser.add_argument('--show-metrics', action='store_true', help='Показать подробную информацию об использовании Google Cloud API')
parser.add_argument('--records-dir', type=str, default='/home/aleks/records', help='Директория для хранения записей диктофона')

args = parser.parse_args()

if args.pre_generate or args.pre_generate_missing:
    print("Предварительная генерация звуков...")
    # Импортируем классы для генерации звуков
    from menu import MenuManager, SettingsManager
    
    # Создаем менеджеры
    settings_file = os.path.join(args.cache_dir, "settings.json")
    settings_manager = SettingsManager(settings_file=settings_file, debug=args.debug)
    
    # Если указан движок TTS, устанавливаем его
    if args.tts_engine:
        settings_manager.set_tts_engine(args.tts_engine)
        print(f"Установлен движок TTS: {args.tts_engine}")
    
    # Если указан файл с учетными данными Google Cloud, устанавливаем его
    if args.google_cloud_credentials:
        credentials_path = os.path.abspath(args.google_cloud_credentials)
        if os.path.exists(credentials_path):
            settings_manager.set_google_cloud_credentials(credentials_path)
            print(f"Установлен файл учетных данных Google Cloud: {credentials_path}")
        else:
            print(f"Файл с учетными данными не найден: {credentials_path}")
    
    # Если указан голос, устанавливаем его
    if args.voice:
        if args.voice in settings_manager.get_available_voices():
            settings_manager.set_voice(args.voice)
            print(f"Установлен голос: {args.voice}")
        else:
            print(f"Голос {args.voice} не найден, используется голос по умолчанию.")
            print(f"Доступные голоса: {', '.join(settings_manager.get_available_voices().keys())}")
    
    # Создаем менеджер меню
    menu_manager = MenuManager(
        tts_enabled=True, 
        cache_dir=args.cache_dir, 
        debug=args.debug,
        use_wav=not args.use_mp3,
        settings_manager=settings_manager,
        records_dir=args.records_dir
    )
    
    # Создаем структуру меню
    menu_manager.create_menu_structure()
    
    # Генерируем озвучку для всех голосов или только для указанного
    voices = None  # Все голоса по умолчанию
    if args.voice:
        voices = [args.voice]
    
    # Предварительная генерация озвучки
    print("Генерация озвучки для всех пунктов меню...")
    if args.debug:
        print(f"Используемый голос: {args.voice if args.voice else 'все доступные голоса'}")
        print(f"Используемый движок TTS: {settings_manager.get_tts_engine()}")
    
    # Выбираем нужный метод генерации в зависимости от флага
    if args.pre_generate_missing:
        print("Режим: генерация только отсутствующих файлов")
        menu_manager.pre_generate_missing_speech(voices=voices)
    else:
        print("Режим: генерация всех файлов")
        menu_manager.pre_generate_all_speech(voices=voices)
    
    print("\nГенерация звуков завершена.")
    
    # Проверяем, что файлы имеют правильный формат имени
    wav_files = glob.glob(os.path.join(args.cache_dir, "*.wav"))
    mp3_files = glob.glob(os.path.join(args.cache_dir, "*.mp3"))
    cache_files = wav_files + mp3_files
    
    if cache_files:
        print(f"\nПримеры сгенерированных файлов (всего: {len(cache_files)}):")
        for example in cache_files[:5]:  # Показываем первые 5 файлов
            print(f"  {os.path.basename(example)}")
    
    # Если в режиме отладки, выводим статистику
    if args.debug and menu_manager.tts_enabled:
        debug_info = menu_manager.get_debug_info()
        
        print("\n=== Статистика TTS ===")
        
        if 'tts' in debug_info:
            tts_info = debug_info['tts']
            print(f"Всего запросов: {tts_info['total_requests']}")
            print(f"Запросов сегодня: {tts_info['today_requests']}")
            print(f"Использований кэша: {tts_info['cached_used']}")
            print(f"Текущий голос: {tts_info['current_voice']}")
            print(f"Текущий движок TTS: {tts_info['tts_engine']}")
        
        # Если используется Google Cloud TTS, выводим дополнительную информацию
        if 'google_cloud_tts' in debug_info:
            gc_info = debug_info['google_cloud_tts']
            print("\n=== Статистика Google Cloud TTS ===")
            print(f"Всего символов: {gc_info['total_chars']}")
            print(f"Символов в этом месяце: {gc_info['monthly_chars_used']}")
            print(f"Осталось бесплатных символов: {gc_info['remaining_free_chars']}")
            print(f"Тип голоса: {gc_info['voice_type']}")
            print(f"Цена за миллион символов: {gc_info['price_per_million']}")
            print(f"Примерная стоимость: {gc_info['estimated_cost']}")
            print(f"Последнее обновление метрик: {gc_info['last_update']}")
            
            # Если запрошен подробный вывод метрик
            if args.show_metrics:
                print("\nПодробная информация о запросах:")
                for idx, req in enumerate(menu_manager.tts_manager.google_tts_manager.stats["requests_history"][-10:]):
                    print(f"{idx+1}. Текст: '{req['text'][:30]}...' | Символов: {req.get('chars', 'н/д')} | Голос: {req['voice']} | Время: {req['time']:.2f}с | Дата: {req['date']}")
    
    sys.exit(0)
else:
    # Для обычного запуска (не pre-generate) нужно передать параметры в main.py
    # Эти аргументы будут обработаны в main.py
    sys.argv = [sys.argv[0]]
    
    if args.no_tts:
        sys.argv.append('--no-tts')
    
    if args.cache_dir:
        sys.argv.extend(['--cache-dir', args.cache_dir])
    
    if args.debug:
        sys.argv.append('--debug')
    
    if args.use_mp3:
        sys.argv.append('--use-mp3')
    
    if args.voice:
        sys.argv.extend(['--voice', args.voice])
    
    if args.tts_engine:
        sys.argv.extend(['--tts-engine', args.tts_engine])
    
    if args.google_cloud_credentials:
        sys.argv.extend(['--google-cloud-credentials', args.google_cloud_credentials])

# Импортируем основную функцию из пакета menu
from menu.main import main

if __name__ == "__main__":
    # Вызываем основную функцию
    main()