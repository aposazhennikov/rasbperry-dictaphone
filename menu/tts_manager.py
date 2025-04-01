#!/usr/bin/env python3
import os
import time
import hashlib
import threading
import subprocess
import json
from datetime import datetime
from gtts import gTTS
import importlib.util
import sys
import traceback
from .google_tts_manager import GoogleTTSManager
import sentry_sdk
import re

class TTSManager:
    """Управление озвучкой текста с помощью gTTS или Google Cloud TTS"""
    
    # Лимит бесплатных запросов в день (приблизительная оценка)
    FREE_DAILY_LIMIT = 200
    
    def __init__(self, cache_dir="/home/aleks/cache_tts", lang="ru", tld="com", debug=False, use_wav=True, 
                 voice="ru-RU-Standard-A", settings_manager=None):
        """
        Инициализация менеджера TTS
        
        Args:
            cache_dir (str): Директория для кэширования звуковых файлов
            lang (str): Язык озвучки (ru, en, и т.д.)
            tld (str): Домен Google для TTS (com, ru, и т.д.)
            debug (bool): Режим отладки
            use_wav (bool): Использовать WAV вместо MP3 для более быстрого воспроизведения
            voice (str): Идентификатор голоса для озвучки (используется только если нет settings_manager)
            settings_manager (SettingsManager): Менеджер настроек
        """
        self.cache_dir = cache_dir
        self.lang = lang
        self.tld = tld
        self.current_sound_process = None
        self.is_playing = False
        self.cache_lock = threading.Lock()
        self.debug = debug
        self.use_wav = use_wav
        self.settings_manager = settings_manager
        self.google_tts_manager = None
        
        # Определяем голос - берем из настроек, если доступны, иначе используем значение по умолчанию
        if self.settings_manager:
            try:
                self.voice = self.settings_manager.get_voice()
                print(f"[TTS INIT] Установлен голос из настроек: {self.voice}")
                sentry_sdk.add_breadcrumb(
                    category="voice",
                    message=f"TTS Manager: Голос установлен из настроек: {self.voice}",
                    level="info"
                )
            except Exception as voice_error:
                error_msg = f"Ошибка при получении голоса из настроек: {voice_error}"
                print(f"[TTS INIT ERROR] {error_msg}")
                sentry_sdk.capture_exception(voice_error)
                # Используем значение по умолчанию
                self.voice = voice
                print(f"[TTS INIT] Используем голос по умолчанию: {self.voice}")
        else:
            # Если нет settings_manager, используем значение параметра
            self.voice = voice
            print(f"[TTS INIT] Используем голос из параметра: {self.voice}")
        
        # Определяем движок TTS
        self.tts_engine = "gtts"  # По умолчанию используем gTTS
        
        if self.settings_manager:
            # Получаем настройку из менеджера настроек
            self.tts_engine = self.settings_manager.get_tts_engine()
            if self.debug:
                print(f"Используемый движок TTS: {self.tts_engine}")
            
            # Если выбран Google Cloud TTS, инициализируем его
            if self.tts_engine == "google_cloud":
                self._init_google_cloud_tts()
                
        # Статистика для режима отладки
        self.stats_file = os.path.join(cache_dir, "tts_stats.json")
        self.stats = {
            "total_requests": 0,
            "today_requests": 0,
            "today_date": datetime.now().strftime("%Y-%m-%d"),
            "cached_used": 0,
            "requests_history": []
        }
        
        # Создаем директорию для кэша, если она не существует
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
            
        # Загружаем статистику если она есть
        self._load_stats()
        
        # Обновляем счетчик дневных запросов
        self._update_day_counter()
        
    def _init_google_cloud_tts(self):
        """Инициализирует Google Cloud TTS менеджер"""
        try:
            import importlib.util  # Явно импортируем модуль внутри функции
            
            # Отладочная информация
            print("Начинаем инициализацию Google Cloud TTS")
            print(f"Текущая директория: {os.getcwd()}")
            print(f"Пути Python: {sys.path}")
            
            # Проверяем доступность модуля
            if importlib.util.find_spec("google.cloud.texttospeech") is not None:
                print("Модуль google.cloud.texttospeech найден")
                
                # Попытка импорта напрямую из текущего пакета
                try:
                    print("Пробуем импортировать GoogleTTSManager из текущего пакета")
                    # Обратите внимание на точку - это важно для относительного импорта
                    from .google_tts_manager import GoogleTTSManager
                    print("Импорт успешен!")
                except ImportError as e:
                    print(f"Ошибка импорта из текущего пакета: {e}")
                    sentry_sdk.capture_exception(e)
                    # Попробуем альтернативный метод импорта
                    try:
                        print("Пробуем альтернативный метод импорта")
                        import importlib.util
                        spec = importlib.util.spec_from_file_location(
                            "google_tts_manager", 
                            os.path.join(os.path.dirname(__file__), "google_tts_manager.py")
                        )
                        google_tts_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(google_tts_module)
                        GoogleTTSManager = google_tts_module.GoogleTTSManager
                        print("Альтернативный импорт успешен!")
                    except Exception as e:
                        print(f"Ошибка альтернативного импорта: {e}")
                        sentry_sdk.capture_exception(e)
                        raise
                
                # Получаем путь к файлу с учетными данными
                credentials_file = self.settings_manager.get_google_cloud_credentials()
                print(f"Путь к учетным данным: {credentials_file}")
                
                # Создаем экземпляр менеджера Google Cloud TTS
                self.google_tts_manager = GoogleTTSManager(
                    cache_dir=self.cache_dir,
                    credentials_file=credentials_file,
                    lang=self.lang,
                    debug=self.debug,
                    use_wav=self.use_wav,
                    voice=self.voice,
                    settings_manager=self.settings_manager
                )
                
                if self.debug:
                    print("Google Cloud TTS менеджер успешно инициализирован")
                    
                # Устанавливаем движок TTS в google_cloud
                self.tts_engine = "google_cloud"
                
            else:
                error_msg = "Модуль google.cloud.texttospeech не найден"
                print(f"[TTS ERROR] {error_msg}")
                sentry_sdk.capture_message(error_msg, level="error")
                
        except Exception as e:
            error_msg = f"Ошибка при инициализации Google Cloud TTS: {e}"
            print(f"[TTS ERROR] {error_msg}")
            sentry_sdk.capture_exception(e)
            traceback.print_exc()  # Печатаем полный стек ошибки
            
            # Возвращаемся к gTTS
            self.tts_engine = "gtts"
            print("[TTS INFO] Возврат к использованию gTTS")
    
    def set_tts_engine(self, engine):
        """
        Устанавливает движок TTS
        
        Args:
            engine (str): Название движка TTS (gtts или google_cloud)
            
        Returns:
            bool: True если успешно, иначе False
        """
        if engine not in ["gtts", "google_cloud"]:
            return False
            
        # Если движок уже установлен, ничего не делаем
        if self.tts_engine == engine:
            return True
            
        self.tts_engine = engine
        
        # Если выбран Google Cloud TTS, инициализируем его
        if engine == "google_cloud":
            if not self.google_tts_manager:
                self._init_google_cloud_tts()
                
            # Если инициализация не удалась, возвращаем False
            if self.tts_engine != "google_cloud":
                return False
        
        # Сохраняем настройку
        if self.settings_manager:
            self.settings_manager.set_tts_engine(engine)
            
        return True
        
    def set_voice(self, voice):
        """
        Устанавливает голос для озвучки
        
        Args:
            voice (str): Идентификатор голоса
            
        Returns:
            bool: True если успешно, иначе False
        """
        try:
            # Логируем начало процесса
            sentry_sdk.add_breadcrumb(
                category="voice",
                message=f"TTS Manager: Начало установки голоса {voice}",
                level="info"
            )
            print(f"[TTS] Запрос на установку голоса: {voice}")
            print(f"[TTS] Текущий голос перед установкой: {self.voice}")
            print(f"[TTS] Текущий движок TTS: {self.tts_engine}")
            
            # Проверяем наличие голоса, если есть settings_manager
            if self.settings_manager:
                available_voices = self.settings_manager.get_available_voices()
                sentry_sdk.add_breadcrumb(
                    category="voice",
                    message=f"TTS Manager: Доступные голоса: {available_voices}",
                    level="info"
                )
                print(f"[TTS] Доступные голоса: {available_voices}")
                
                if voice not in available_voices:
                    error_msg = f"TTS Manager: Голос {voice} не найден в списке доступных голосов"
                    print(f"[TTS ERROR] {error_msg}")
                    sentry_sdk.capture_message(error_msg, level="error")
                    return False

            # Сохраняем старый голос для логирования
            old_voice = self.voice
            
            # Устанавливаем новый голос
            self.voice = voice
            print(f"[TTS] Голос установлен: {voice}")
            
            # Если используем Google Cloud TTS, передаем настройку ему тоже
            if self.tts_engine == "google_cloud" and self.google_tts_manager:
                try:
                    print(f"[TTS] Вызов google_tts_manager.set_voice({voice})")
                    result = self.google_tts_manager.set_voice(voice)
                    sentry_sdk.add_breadcrumb(
                        category="voice",
                        message=f"TTS Manager: Результат установки голоса в Google Cloud TTS: {result}",
                        level="info"
                    )
                    print(f"[TTS] Результат установки голоса в Google Cloud TTS: {result}")
                    
                    if not result:
                        error_msg = f"Не удалось установить голос {voice} в Google Cloud TTS"
                        print(f"[TTS WARNING] {error_msg}")
                        sentry_sdk.capture_message(error_msg, level="warning")
                        # Важно: НЕ возвращаем False и не восстанавливаем старый голос!
                        # Голос будет установлен в TTSManager, но возможно не будет работать в Google Cloud
                        print(f"[TTS] Продолжаем установку голоса, несмотря на ошибку Google Cloud TTS")
                except Exception as cloud_error:
                    error_msg = f"Ошибка при установке голоса в Google Cloud TTS: {cloud_error}"
                    print(f"[TTS WARNING] {error_msg}")
                    sentry_sdk.capture_exception(cloud_error)
                    # Важно: НЕ возвращаем False и не восстанавливаем старый голос!
                    print(f"[TTS] Продолжаем установку голоса, несмотря на ошибку Google Cloud TTS")
                    
            # Проверяем, сохранился ли голос
            print(f"[TTS] Финальная проверка - текущий голос: {self.voice}")
            
            if self.voice != voice:
                error_msg = f"Голос не был установлен: ожидалось {voice}, получено {self.voice}"
                print(f"[TTS ERROR] {error_msg}")
                sentry_sdk.capture_message(error_msg, level="error")
                return False
                
            # Логируем успешную установку голоса
            sentry_sdk.add_breadcrumb(
                category="voice",
                message=f"TTS Manager: Голос успешно изменен с {old_voice} на {self.voice}",
                level="info"
            )
            print(f"[TTS] Голос успешно изменен с {old_voice} на {self.voice}")
                
            return True
                
        except Exception as e:
            error_msg = f"Критическая ошибка при установке голоса: {e}"
            print(f"[TTS CRITICAL ERROR] {error_msg}")
            sentry_sdk.capture_exception(e)
            return False
    
    def _load_stats(self):
        """Загружает статистику из файла"""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r') as f:
                    self.stats = json.load(f)
            except Exception as e:
                error_msg = f"Ошибка при загрузке статистики: {e}"
                if self.debug:
                    print(error_msg)
                sentry_sdk.capture_exception(e)
                
    def _save_stats(self):
        """Сохраняет статистику в файл"""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            error_msg = f"Ошибка при сохранении статистики: {e}"
            if self.debug:
                print(error_msg)
            sentry_sdk.capture_exception(e)
                
    def _update_day_counter(self):
        """Обновляет счетчик дневных запросов"""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.stats["today_date"] != today:
            self.stats["today_requests"] = 0
            self.stats["today_date"] = today
            self._save_stats()
            
    def get_debug_info(self):
        """
        Возвращает отладочную информацию для текущего состояния TTS менеджера
        
        Returns:
            dict: Словарь с отладочной информацией
        """
        debug_info = {
            "total_requests": self.stats["total_requests"],
            "today_requests": self.stats["today_requests"],
            "cached_used": self.stats["cached_used"],
            "last_error": getattr(self, "last_error", None),
            "current_voice": self.voice,
            "tts_engine": self.settings_manager.get_tts_engine() if self.settings_manager else "unknown"
        }
        
        # Обновляем счетчик дневных запросов
        self._update_day_counter()
        
        # Примерная оценка оставшихся запросов
        remaining = max(0, self.FREE_DAILY_LIMIT - self.stats["today_requests"])
        
        # Форматируем историю запросов для отображения
        formatted_history = []
        for entry in self.stats["requests_history"][-10:]:  # Последние 10 запросов
            formatted_history.append(
                f"{entry['text'][:20]}... - {entry['time']:.2f}с - {entry['date']}"
            )
        
        debug_info.update({
            "remaining_free_requests": remaining,
            "recent_requests": formatted_history
        })
        
        return debug_info
    
    def get_cached_filename(self, text, use_wav=None, voice=None):
        """
        Возвращает путь к кэшированному файлу для указанного текста и голоса
        
        Args:
            text (str): Текст для озвучки
            use_wav (bool, optional): Использовать WAV вместо MP3
            voice (str, optional): Идентификатор голоса
            
        Returns:
            str: Путь к файлу
        """
        try:
            if use_wav is None:
                use_wav = self.use_wav
                
            if voice is None:
                voice = self.voice
                
            # Хэшируем текст для создания имени файла
            text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
            
            # Добавляем идентификатор голоса к имени файла
            filename = f"{voice}_{text_hash}"
            
            # Определяем расширение файла
            ext = "wav" if use_wav else "mp3"
            
            # Формируем полный путь к файлу
            file_path = os.path.join(self.cache_dir, f"{filename}.{ext}")
            
            return file_path
        except Exception as e:
            error_msg = f"Ошибка при получении пути к кэшированному файлу: {e}"
            print(f"[TTS CACHE ERROR] {error_msg}")
            sentry_sdk.capture_exception(e)
            # Возвращаем стандартный путь в случае ошибки
            return os.path.join(self.cache_dir, f"error_{hashlib.md5(text.encode('utf-8')).hexdigest()}.mp3")
    
    def mp3_to_wav(self, mp3_file):
        """
        Конвертирует MP3 в WAV
        
        Args:
            mp3_file (str): Путь к MP3 файлу
            
        Returns:
            str: Путь к WAV файлу или None в случае ошибки
        """
        wav_file = mp3_file.replace(".mp3", ".wav")
        
        # Если WAV файл уже существует, просто возвращаем его
        if os.path.exists(wav_file):
            return wav_file
            
        try:
            # Проверяем, установлен ли ffmpeg
            if self.debug:
                print(f"Конвертация {mp3_file} в WAV...")
                
            # Используем mpg123 для конвертации, так как он скорее всего установлен
            subprocess.run(
                ["mpg123", "-w", wav_file, mp3_file],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=True
            )
            
            return wav_file
        except subprocess.CalledProcessError as e:
            print(f"Ошибка при конвертации MP3 в WAV: {e}")
            return None
        except FileNotFoundError:
            print("mpg123 не найден, конвертация невозможна")
            return None
            
    def _preprocess_text(self, text):
        """
        Предварительная обработка текста перед отправкой в TTS
        
        Args:
            text (str): Исходный текст
            
        Returns:
            str: Обработанный текст
        """
        if not text:
            return text
            
        import re
            
        # Удаляем расширения файлов (.mp3, .wav, .ogg, .txt и другие)
        # Ищем шаблоны типа "filename.ext" и заменяем на "filename"
        common_extensions = ['.mp3', '.wav', '.ogg', '.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.gif']
        processed_text = text
        
        # Заменяем конкретные расширения файлов на пробел
        for ext in common_extensions:
            processed_text = processed_text.replace(ext, ' ')
        
        # Используем регулярное выражение для более общего случая
        # Ищем паттерн "что-то.расширение" где расширение 2-4 символа
        # Исключаем даты в формате DD.MM.YYYY из обработки
        # Сначала находим и временно заменяем даты
        date_pattern = r'(\d{2})\.(\d{2})\.(\d{4})'
        # Сохраняем даты с временной меткой
        dates_found = re.findall(date_pattern, processed_text)
        for i, date_parts in enumerate(dates_found):
            date_str = f"{date_parts[0]}.{date_parts[1]}.{date_parts[2]}"
            processed_text = processed_text.replace(date_str, f"__DATE_{i}__")
        
        # Теперь обрабатываем расширения файлов
        processed_text = re.sub(r'(\w+)(\.\w{2,4})\b', r'\1', processed_text)
        
        # Восстанавливаем даты
        for i, date_parts in enumerate(dates_found):
            date_str = f"{date_parts[0]}.{date_parts[1]}.{date_parts[2]}"
            processed_text = processed_text.replace(f"__DATE_{i}__", date_str)
        
        # Заменяем тире и нижнее подчеркивание на пробелы
        processed_text = processed_text.replace('-', ' ').replace('_', ' ')
        
        # Удаляем лишние пробелы (несколько пробелов заменяем на один)
        processed_text = ' '.join(processed_text.split())
        
        if self.debug and processed_text != text:
            print(f"[TTS] Предобработка текста: '{text}' -> '{processed_text}'")
            
        return processed_text
        
    def generate_speech(self, text, force_regenerate=False, voice=None):
        """
        Генерирует озвучку для указанного текста и возвращает путь к аудиофайлу
        
        Args:
            text (str): Текст для озвучивания
            force_regenerate (bool): Принудительно сгенерировать озвучку, даже если файл уже существует
            voice (str): Идентификатор голоса (если None, используется текущий голос)
            
        Returns:
            str: Путь к аудиофайлу или None в случае ошибки
        """
        try:
            if not text:
                return None
                
            if voice is None:
                voice = self.voice
                
            # Предварительная обработка текста
            processed_text = self._preprocess_text(text)
            
            # Получаем путь к MP3 и WAV-файлам в кэше
            mp3_file = self.get_cached_filename(processed_text, use_wav=False, voice=voice)
            wav_file = self.get_cached_filename(processed_text, use_wav=True, voice=voice)
            
            # Проверяем наличие файлов
            mp3_exists = os.path.exists(mp3_file)
            wav_exists = os.path.exists(wav_file)
            
            # Если нужен WAV и он уже есть, возвращаем его
            if self.use_wav and wav_exists and not force_regenerate:
                # Увеличиваем счётчик использования кэша
                self.stats["cached_used"] += 1
                self._save_stats()
                
                if self.debug:
                    print(f"Использован кэш для: {processed_text} (голос: {voice})")
                    
                return wav_file
            
            # Если нужен MP3 и он уже есть, возвращаем его
            if not self.use_wav and mp3_exists and not force_regenerate:
                # Увеличиваем счётчик использования кэша
                self.stats["cached_used"] += 1
                self._save_stats()
                
                if self.debug:
                    print(f"Использован кэш для: {processed_text} (голос: {voice})")
                    
                return mp3_file
            
            # Если нужен WAV, но есть только MP3 и не нужно пересоздавать
            if self.use_wav and mp3_exists and not force_regenerate:
                # Конвертируем MP3 в WAV
                wav_result = self.mp3_to_wav(mp3_file)
                if wav_result:
                    # Увеличиваем счётчик использования кэша
                    self.stats["cached_used"] += 1
                    self._save_stats()
                    
                    if self.debug:
                        print(f"Использован кэш (конвертация в WAV) для: {processed_text} (голос: {voice})")
                        
                    return wav_result
            
            # Если нужно сгенерировать файл и мы используем Google Cloud TTS
            if self.tts_engine == "google_cloud" and self.google_tts_manager:
                return self.google_tts_manager.generate_speech(processed_text, force_regenerate, voice)
            
            if self.debug:
                print(f"[TTS] Генерация озвучки с помощью gTTS для: {processed_text} (голос: {voice})")
                
            # Увеличиваем счетчики запросов
            self.stats["total_requests"] += 1
            self.stats["today_requests"] += 1
            
            # Замеряем время запроса
            start_time = time.time()
            
            try:
                # Создаем объект gTTS и сохраняем в MP3-файл
                # Обратите внимание, что gTTS не поддерживает выбор конкретного голоса напрямую,
                # но мы все равно храним разные файлы для разных голосов
                tts = gTTS(text=processed_text, lang=self.lang, tld=self.tld, slow=False)
                tts.save(mp3_file)
                
                # Если нужен WAV, конвертируем MP3 в WAV
                result_file = mp3_file
                if self.use_wav:
                    wav_result = self.mp3_to_wav(mp3_file)
                    if wav_result:
                        result_file = wav_result
                
                # Вычисляем время выполнения
                elapsed_time = time.time() - start_time
                
                # Записываем в историю
                self.stats["requests_history"].append({
                    "text": processed_text,
                    "time": elapsed_time,
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "voice": voice
                })
                
                # Ограничиваем историю до 100 последних запросов
                if len(self.stats["requests_history"]) > 100:
                    self.stats["requests_history"] = self.stats["requests_history"][-100:]
                    
                # Сохраняем статистику
                self._save_stats()
                
                return result_file
            except Exception as e:
                error_msg = f"Ошибка при генерации озвучки: {e}"
                print(f"[TTS ERROR] {error_msg}")
                sentry_sdk.capture_exception(e)
                return None
        except Exception as e:
            error_msg = f"Ошибка при генерации речи: {e}"
            print(f"[TTS CRITICAL ERROR] {error_msg}")
            sentry_sdk.capture_exception(e)
            return None
    
    def _is_valid_audio_file(self, file_path):
        """
        Проверяет, является ли аудиофайл валидным и полным
        
        Args:
            file_path (str): Путь к аудиофайлу
            
        Returns:
            bool: True если файл валидный, иначе False
        """
        if not os.path.exists(file_path):
            return False
            
        # Проверка размера файла (должен быть не пустым)
        if os.path.getsize(file_path) < 100:
            if self.debug:
                print(f"[TTS] Аудиофайл слишком маленький: {file_path}")
            return False
            
        # Проверка формата MP3
        if file_path.endswith('.mp3'):
            try:
                result = subprocess.run(
                    ["mp3info", "-p", "%S", file_path], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                # Если вывод пустой или ошибка, файл может быть поврежден
                if not result.stdout.strip() or int(result.stdout.strip()) < 1:
                    if self.debug:
                        print(f"[TTS] MP3 файл может быть поврежден: {file_path}")
                    return False
            except:
                # Если mp3info не установлен, пропускаем эту проверку
                pass
                
        # Проверка формата WAV
        if file_path.endswith('.wav'):
            try:
                result = subprocess.run(
                    ["soxi", "-d", file_path], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                # Если вывод пустой или ошибка, файл может быть поврежден
                if "0:00" in result.stdout or not result.stdout.strip():
                    if self.debug:
                        print(f"[TTS] WAV файл может быть поврежден: {file_path}")
                    return False
            except:
                # Если soxi не установлен, пропускаем эту проверку
                pass
                
        return True
        
    def _ensure_audio_playable(self, file_path):
        """
        Проверяет и подготавливает аудиофайл к воспроизведению, 
        исправляя распространенные проблемы с буферизацией
        
        Args:
            file_path (str): Путь к аудиофайлу
            
        Returns:
            str: Путь к подготовленному файлу или None при ошибке
        """
        try:
            # Если файл не существует, выходим
            if not os.path.exists(file_path):
                return None
                
            # Для простоты проверяем только размер файла
            # Это надежнее чем вызов внешних программ
            if os.path.getsize(file_path) < 100:
                if self.debug:
                    print(f"[TTS] Аудиофайл слишком маленький: {file_path}")
                return None
                
            # Создаем буферизованную копию для WAV-файлов
            if file_path.endswith('.wav') and self.use_wav:
                try:
                    # Сначала определяем оригинальную частоту дискретизации
                    sample_rate = None
                    channels = None
                    bits = None
                    
                    try:
                        # Получаем частоту дискретизации
                        rate_result = subprocess.run(
                            ["soxi", "-r", file_path],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=False
                        )
                        if rate_result.stdout.strip().isdigit():
                            sample_rate = int(rate_result.stdout.strip())
                            if self.debug:
                                print(f"[TTS] Определена частота дискретизации: {sample_rate} Hz")
                                
                        # Получаем количество каналов
                        channels_result = subprocess.run(
                            ["soxi", "-c", file_path],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=False
                        )
                        if channels_result.stdout.strip().isdigit():
                            channels = int(channels_result.stdout.strip())
                            
                        # Получаем битность
                        bits_result = subprocess.run(
                            ["soxi", "-b", file_path],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=False
                        )
                        if bits_result.stdout.strip().isdigit():
                            bits = int(bits_result.stdout.strip())
                            
                    except Exception as e:
                        if self.debug:
                            print(f"[TTS] Ошибка определения параметров аудио: {e}")
                        
                    # Путь к буферизованному файлу
                    buffered_file = file_path.replace('.wav', '_buffered.wav')
                    
                    # Если буферизованный файл уже существует, возвращаем его
                    if os.path.exists(buffered_file) and os.path.getsize(buffered_file) > os.path.getsize(file_path):
                        return buffered_file
                        
                    # Создаем промежуточный файл для фиксации скорости
                    temp_file = file_path.replace('.wav', '_temp.wav')
                    
                    # Применяем фильтр для стабилизации скорости воспроизведения
                    speed_cmd = [
                        "sox",
                        file_path,
                        temp_file,
                        "rate", "-v" # Высокое качество конвертации
                    ]
                    
                    # Добавляем частоту дискретизации, если определили
                    if sample_rate:
                        speed_cmd.append(str(sample_rate))
                    else:
                        speed_cmd.append("24000") # Стандартная частота по умолчанию
                    
                    # Выполняем команду стабилизации скорости
                    try:
                        subprocess.run(
                            speed_cmd,
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE,
                            check=False
                        )
                    except Exception as e:
                        if self.debug:
                            print(f"[TTS] Ошибка при стабилизации скорости: {e}")
                        # Продолжаем с исходным файлом, если ошибка
                        temp_file = file_path
                    
                    # Создаем команду для sox с сохранением параметров аудио
                    cmd = [
                        "sox", 
                        temp_file
                    ]
                    
                    # Добавляем параметры аудио, если определили
                    if sample_rate:
                        cmd.extend(["-r", str(sample_rate)])
                    
                    # Добавляем выходной файл и параметры
                    cmd.extend([
                        buffered_file,
                        "pad", "0.3", "0.2",  # 0.3с в начале, 0.2с в конце
                        "norm"  # Нормализация уровня громкости
                    ])
                    
                    if self.debug:
                        print(f"[TTS] Буферизация аудио: {' '.join(cmd)}")
                        
                    subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE,
                        check=False
                    )
                    
                    # Удаляем временный файл, если он был создан
                    if temp_file != file_path and os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                    
                    if os.path.exists(buffered_file) and os.path.getsize(buffered_file) > 0:
                        return buffered_file
                except Exception as buffer_error:
                    if self.debug:
                        print(f"[TTS] Ошибка при буферизации файла: {buffer_error}")
                    # При ошибке продолжаем с исходным файлом
            
            return file_path
                
        except Exception as e:
            if self.debug:
                print(f"[TTS] Ошибка при подготовке аудиофайла: {e}")
            return file_path  # Возвращаем исходный файл при ошибке
            
    def play_speech(self, text, voice_id=None, blocking=False):
        """
        Озвучивает текст с помощью выбранного движка
        
        Args:
            text (str): Текст для озвучивания
            voice_id (str): Идентификатор голоса (можно переопределить)
            blocking (bool): Ожидать окончания воспроизведения
            
        Returns:
            bool: True, если озвучивание успешно запущено
        """
        try:
            if not text or not isinstance(text, str):
                return False
            
            # Предварительная обработка текста
            processed_text = self._preprocess_text(text)
                
            # Если используем Google Cloud TTS, делегируем ему воспроизведение
            if self.tts_engine == "google_cloud" and self.google_tts_manager:
                return self.google_tts_manager.play_speech(processed_text, voice_id, blocking)
            
            # Используем указанный голос или текущий по умолчанию
            if voice_id is None:
                voice_id = self.voice
            
            # Если уже что-то воспроизводится, останавливаем
            self.stop_current_sound()
            
            # Генерируем озвучку (генерация уже включает предобработку текста)
            audio_file = self.generate_speech(processed_text, force_regenerate=False, voice=voice_id)
            if not audio_file:
                if self.debug:
                    print(f"[TTS ERROR] Не удалось сгенерировать аудиофайл для текста: {processed_text}")
                return False
            
            # Проверяем и подготавливаем файл перед воспроизведением
            prepared_audio = self._ensure_audio_playable(audio_file)
            if not prepared_audio:
                # Если файл некорректный, пробуем пересоздать его
                if self.debug:
                    print(f"[TTS] Аудиофайл некорректный, пересоздаем: {audio_file}")
                audio_file = self.generate_speech(processed_text, force_regenerate=True, voice=voice_id)
                
                # Проверяем пересозданный файл
                prepared_audio = self._ensure_audio_playable(audio_file)
                if not prepared_audio:
                    if self.debug:
                        print(f"[TTS ERROR] Не удалось создать корректный аудиофайл после повторной попытки")
                    return False
            
            try:
                # Получаем текущий уровень громкости из настроек
                volume = 100
                if self.settings_manager:
                    try:
                        volume = self.settings_manager.get_system_volume()
                    except Exception as vol_error:
                        print(f"[TTS WARNING] Ошибка при получении громкости: {vol_error}")
                        sentry_sdk.capture_exception(vol_error)
                
                # Нормализуем громкость в диапазон 0-1 с экспоненциальной шкалой
                # Используем экспоненциальную шкалу для более естественного изменения громкости
                volume_exp = (volume / 100.0) ** 2
                
                # Использование более надежного метода воспроизведения
                if self.use_wav:
                    if os.path.exists("/usr/bin/paplay"):
                        # paplay использует линейную шкалу от 0 до 65536
                        volume_paplay = int(volume_exp * 65536)
                        cmd = ["paplay", "--volume", str(volume_paplay), prepared_audio]
                        if self.debug:
                            print(f"[TTS] Воспроизведение через paplay: {' '.join(cmd)}")
                        
                        # Добавляем небольшую паузу перед воспроизведением для стабильности
                        time.sleep(0.2)
                        
                        self.current_sound_process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                    elif os.path.exists("/usr/bin/aplay"):
                        cmd = ["aplay", prepared_audio]
                        if self.debug:
                            print(f"[TTS] Воспроизведение через aplay: {' '.join(cmd)}")
                            
                        # Добавляем небольшую паузу перед воспроизведением для стабильности
                        time.sleep(0.2)
                        
                        self.current_sound_process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                    else:
                        print("[TTS ERROR] Не найдены paplay или aplay для воспроизведения WAV")
                        return False
                else:
                    if os.path.exists("/usr/bin/mpg123"):
                        # mpg123 использует линейную шкалу от 0 до 32768
                        volume_mpg123 = int(volume_exp * 32768)
                        # Добавляем опции для предотвращения артефактов
                        cmd = ["mpg123", "-q", "--no-control", "-f", str(volume_mpg123), prepared_audio]
                        if self.debug:
                            print(f"[TTS] Воспроизведение через mpg123: {' '.join(cmd)}")
                            
                        # Добавляем небольшую паузу перед воспроизведением для стабильности
                        time.sleep(0.2)
                        
                        self.current_sound_process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                    else:
                        print("[TTS ERROR] Не найден mpg123 для воспроизведения MP3")
                        return False
                
                self.is_playing = True
                
                if blocking:
                    # Если нужно блокировать выполнение до окончания воспроизведения
                    if self.current_sound_process:
                        # Подождем завершения воспроизведения
                        ret_code = self.current_sound_process.wait()
                        
                        # Проверяем код возврата, чтобы понять успешно ли завершилось воспроизведение
                        if self.debug and ret_code != 0:
                            print(f"[TTS WARNING] Воспроизведение завершилось с кодом {ret_code}")
                        
                        # Добавляем небольшую паузу после воспроизведения для стабильности
                        time.sleep(0.3)
                        
                        self.is_playing = False
                        self.current_sound_process = None
                
                return True
            except Exception as play_error:
                error_msg = f"Ошибка при воспроизведении звука: {play_error}"
                print(f"[TTS ERROR] {error_msg}")
                sentry_sdk.capture_exception(play_error)
                return False
        except Exception as e:
            error_msg = f"Критическая ошибка при озвучивании текста: {e}"
            print(f"[TTS CRITICAL ERROR] {error_msg}")
            sentry_sdk.capture_exception(e)
            return False
    
    def wait_completion(self):
        """Ожидает завершения воспроизведения звука"""
        if self.current_sound_process:
            self.current_sound_process.wait()
            self.is_playing = False
            self.current_sound_process = None
    
    def stop_current_sound(self):
        """Останавливает текущий воспроизводимый звук"""
        # Если используем Google Cloud TTS, делегируем ему
        if self.tts_engine == "google_cloud" and self.google_tts_manager:
            return self.google_tts_manager.stop_current_sound()
            
        if self.current_sound_process and self.current_sound_process.poll() is None:
            try:
                self.current_sound_process.terminate()
                self.current_sound_process.wait()
            except:
                pass
                
        self.is_playing = False
        self.current_sound_process = None
    
    def pre_generate_menu_items(self, menu_items, voices=None):
        """
        Предварительно генерирует озвучки для пунктов меню
        
        Args:
            menu_items (list): Список текстов для озвучки
            voices (list, optional): Список голосов для предварительной генерации
        """
        # Если используем Google Cloud TTS, делегируем ему
        if self.tts_engine == "google_cloud" and self.google_tts_manager:
            return self.google_tts_manager.pre_generate_menu_items(menu_items, voices)
            
        if not voices:
            voices = [self.voice]  # По умолчанию только текущий голос
            
        # Удаляем дубликаты из списка текстов
        unique_items = set(menu_items)
        
        total_items = len(unique_items) * len(voices)
        processed = 0
        
        if self.debug:
            print(f"Предварительная генерация озвучки для {len(unique_items)} уникальных текстов в {len(voices)} голосах")
        
        for voice in voices:
            for text in unique_items:
                # Генерируем озвучку
                audio_file = self.generate_speech(text, force_regenerate=False, voice=voice)
                
                # Если файл был сгенерирован и мы используем WAV-формат, создаем буферизованную версию
                if audio_file and audio_file.endswith('.wav') and self.use_wav:
                    try:
                        # Создаем буферизованную версию
                        buffered_file = self._ensure_audio_playable(audio_file)
                        if self.debug and buffered_file and buffered_file != audio_file:
                            print(f"Создан буферизованный файл: {os.path.basename(buffered_file)}")
                    except Exception as buffer_error:
                        if self.debug:
                            print(f"[TTS] Ошибка при создании буферизованного файла: {buffer_error}")
                
                processed += 1
                if self.debug:
                    print(f"Предварительная генерация: {processed}/{total_items} - {text} (голос: {voice})")
    
    def pre_generate_missing_menu_items(self, menu_items, voices=None):
        """
        Предварительно генерирует только отсутствующие озвучки для пунктов меню
        
        Args:
            menu_items (list): Список текстов для озвучки
            voices (list, optional): Список голосов для предварительной генерации
        """
        # Если используем Google Cloud TTS, делегируем ему
        if self.tts_engine == "google_cloud" and self.google_tts_manager:
            return self.google_tts_manager.pre_generate_missing_menu_items(menu_items, voices)
            
        if not voices:
            voices = [self.voice]  # По умолчанию только текущий голос
            
        # Удаляем дубликаты из списка текстов
        unique_items = set(menu_items)
        
        missing_items = []
        
        # Проверяем наличие файлов и составляем список отсутствующих
        for voice in voices:
            for text in unique_items:
                # Получаем имя файла без проверки существования
                filename = self._get_voice_specific_filename(text, voice, check_exists=False)
                if not os.path.exists(filename):
                    missing_items.append((text, voice))
        
        total_missing = len(missing_items)
        processed = 0
        
        if self.debug:
            print(f"Предварительная генерация отсутствующей озвучки: найдено {total_missing} из {len(unique_items) * len(voices)} возможных файлов")
        
        if total_missing == 0:
            print("Все аудиофайлы уже сгенерированы. Нет необходимости в дополнительной генерации.")
            return
        
        for text, voice in missing_items:
            # Генерируем озвучку
            audio_file = self.generate_speech(text, force_regenerate=False, voice=voice)
            
            # Если файл был сгенерирован и мы используем WAV-формат, создаем буферизованную версию
            if audio_file and audio_file.endswith('.wav') and self.use_wav:
                try:
                    # Создаем буферизованную версию
                    buffered_file = self._ensure_audio_playable(audio_file)
                    if self.debug and buffered_file and buffered_file != audio_file:
                        print(f"Создан буферизованный файл: {os.path.basename(buffered_file)}")
                except Exception as buffer_error:
                    if self.debug:
                        print(f"[TTS] Ошибка при создании буферизованного файла: {buffer_error}")
            
            processed += 1
            if self.debug:
                print(f"Генерация: {processed}/{total_missing} - {text} (голос: {voice})")

    def speak_text(self, text, voice_id=None):
        """
        Озвучивает текст (псевдоним для play_speech)
        
        Args:
            text (str): Текст для озвучивания
            voice_id (str): Идентификатор голоса (можно переопределить)
            
        Returns:
            bool: True, если озвучивание успешно запущено
        """
        try:
            # Предварительная обработка текста выполняется внутри play_speech
            if self.debug:
                print(f"Озвучивание текста: {text}")
            return self.play_speech(text, voice_id=voice_id, blocking=False)
        except Exception as e:
            error_msg = f"Ошибка при озвучивании текста: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False
    
    def play_speech_blocking(self, text, voice_id=None):
        """
        Озвучивает текст с помощью выбранного движка в блокирующем режиме
        
        Args:
            text (str): Текст для озвучивания
            voice_id (str): Идентификатор голоса (можно переопределить)
            
        Returns:
            bool: True, если озвучивание успешно выполнено
        """
        try:
            # Предварительная обработка текста выполняется внутри play_speech
            if self.debug:
                print(f"Блокирующее озвучивание текста: {text}")
            return self.play_speech(text, voice_id=voice_id, blocking=True)
        except Exception as e:
            error_msg = f"Ошибка при блокирующем воспроизведении речи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False

    def _get_voice_specific_filename(self, text, voice, check_exists=True):
        """
        Возвращает путь к файлу для конкретного голоса, без зависимости от API
        
        Args:
            text (str): Текст для озвучки
            voice (str): Идентификатор голоса
            check_exists (bool): Проверять ли существование файла
            
        Returns:
            str: Путь к файлу или None, если файл не найден и check_exists=True
        """
        try:
            # Получаем базовый путь к файлу
            file_path = self.get_cached_filename(text, use_wav=self.use_wav, voice=voice)
            
            # Проверяем существование файла, если нужно
            if check_exists and not os.path.exists(file_path):
                return None
                
            return file_path
        except Exception as e:
            error_msg = f"Ошибка при получении пути к файлу для голоса {voice}: {e}"
            print(f"[TTS CACHE ERROR] {error_msg}")
            sentry_sdk.capture_exception(e)
            return None