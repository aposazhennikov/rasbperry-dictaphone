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
            voice (str): Идентификатор голоса для озвучки
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
        self.voice = voice
        self.settings_manager = settings_manager
        self.google_tts_manager = None
        
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
                    voice=self.voice
                )
                
                if self.debug:
                    print(f"Google Cloud TTS менеджер инициализирован успешно")
            else:
                print("Библиотека Google Cloud Text-to-Speech не установлена")
                print("Для установки выполните: pip install google-cloud-texttospeech")
                # Переключаемся на gTTS
                self.tts_engine = "gtts"
                if self.settings_manager:
                    self.settings_manager.set_tts_engine("gtts")
        except Exception as e:
            print(f"Ошибка при инициализации Google Cloud TTS: {e}")
            import traceback
            print("Стек вызовов:")
            traceback.print_exc()
            # Переключаемся на gTTS
            self.tts_engine = "gtts"
            if self.settings_manager:
                self.settings_manager.set_tts_engine("gtts")
    
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
        """
        self.voice = voice
        
        # Если используем Google Cloud TTS, передаем настройку ему тоже
        if self.tts_engine == "google_cloud" and self.google_tts_manager:
            self.google_tts_manager.set_voice(voice)
            
        if self.debug:
            print(f"Установлен голос: {voice}")
        
    def _load_stats(self):
        """Загружает статистику из файла"""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r') as f:
                    self.stats = json.load(f)
            except Exception as e:
                if self.debug:
                    print(f"Ошибка при загрузке статистики: {e}")
                
    def _save_stats(self):
        """Сохраняет статистику в файл"""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            if self.debug:
                print(f"Ошибка при сохранении статистики: {e}")
                
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
        Создает имя файла на основе текста и голоса в читаемом формате
        
        Args:
            text (str): Текст для озвучки
            use_wav (bool, optional): Использовать WAV вместо MP3
            voice (str, optional): Идентификатор голоса
            
        Returns:
            str: Путь к файлу
        """
        # Если используем Google Cloud TTS, делегируем ему получение имени файла
        if self.tts_engine == "google_cloud" and self.google_tts_manager:
            return self.google_tts_manager.get_cached_filename(text, use_wav, voice)
        
        # Если use_wav не указан, используем значение по умолчанию
        if use_wav is None:
            use_wav = self.use_wav
            
        # Если voice не указан, используем текущий голос
        if voice is None:
            voice = self.voice
            
        # Создаем понятное имя файла на основе текста
        # 1. Заменяем пробелы и специальные символы на подчеркивания
        # 2. Ограничиваем длину имени файла
        # 3. Добавляем идентификатор голоса
        safe_text = text[:30]  # Берем только первые 30 символов
        safe_text = ''.join(c if c.isalnum() or c.isspace() else '_' for c in safe_text)
        safe_text = safe_text.replace(' ', '_').lower()
        
        # Добавляем короткое обозначение голоса
        voice_short = voice.split('-')[-1]  # Берем только последнюю часть, например "A" из "ru-RU-Standard-A"
        
        # Создаем имя файла, но также добавляем хеш для уникальности
        text_hash = hashlib.md5(f"{text}_{voice}".encode('utf-8')).hexdigest()[:8]
        
        # Формируем имя файла
        filename = f"{safe_text}_{voice_short}_{text_hash}"
        
        # Возвращаем имя файла с соответствующим расширением
        if use_wav:
            return os.path.join(self.cache_dir, f"{filename}.wav")
        else:
            return os.path.join(self.cache_dir, f"{filename}.mp3")
    
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
            
    def generate_speech(self, text, force_regenerate=False, voice=None):
        """
        Генерирует озвучку текста и сохраняет в кэш
        
        Args:
            text (str): Текст для озвучки
            force_regenerate (bool): Пересоздать файл, даже если он уже существует
            voice (str, optional): Идентификатор голоса
            
        Returns:
            str: Путь к сгенерированному файлу
        """
        try:
            if not text or not isinstance(text, str):
                return None
                
            # Если используем Google Cloud TTS, делегируем ему генерацию
            if self.tts_engine == "google_cloud" and self.google_tts_manager:
                return self.google_tts_manager.generate_speech(text, force_regenerate, voice)
            
            # Используем указанный голос или текущий по умолчанию
            if voice is None:
                voice = self.voice
            
            # Сначала получаем имя MP3 файла с учетом голоса
            mp3_file = self.get_cached_filename(text, use_wav=False, voice=voice)
            
            # Если нужен WAV, определяем его имя
            wav_file = None
            if self.use_wav:
                wav_file = self.get_cached_filename(text, use_wav=True, voice=voice)
            
            with self.cache_lock:
                # Проверяем наличие файлов в кэше
                mp3_exists = os.path.exists(mp3_file)
                wav_exists = wav_file and os.path.exists(wav_file)
                
                # Если нужен MP3 и он есть, или нужен WAV и он есть
                if (not self.use_wav and mp3_exists and not force_regenerate) or \
                   (self.use_wav and wav_exists and not force_regenerate):
                    # Увеличиваем счётчик использования кэша
                    self.stats["cached_used"] += 1
                    self._save_stats()
                    
                    if self.debug:
                        print(f"Использован кэш для: {text} (голос: {voice})")
                        
                    return wav_file if self.use_wav else mp3_file
                
                # Если нужен WAV, но есть только MP3 и не нужно пересоздавать
                if self.use_wav and mp3_exists and not force_regenerate:
                    # Конвертируем MP3 в WAV
                    wav_result = self.mp3_to_wav(mp3_file)
                    if wav_result:
                        # Увеличиваем счётчик использования кэша
                        self.stats["cached_used"] += 1
                        self._save_stats()
                        
                        if self.debug:
                            print(f"Использован кэш (конвертация в WAV) для: {text} (голос: {voice})")
                            
                        return wav_result
                
                if self.debug:
                    print(f"Генерация озвучки для: {text} (голос: {voice})")
                    
                # Увеличиваем счетчики запросов
                self.stats["total_requests"] += 1
                self.stats["today_requests"] += 1
                
                # Замеряем время запроса
                start_time = time.time()
                
                try:
                    # Создаем объект gTTS и сохраняем в MP3-файл
                    # Обратите внимание, что gTTS не поддерживает выбор конкретного голоса напрямую,
                    # но мы все равно храним разные файлы для разных голосов
                    tts = gTTS(text=text, lang=self.lang, tld=self.tld, slow=False)
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
                        "text": text,
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
                    print(f"Ошибка при генерации озвучки: {e}")
                    return None
        except Exception as e:
            error_msg = f"Ошибка при генерации речи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return None
    
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
                
            # Если используем Google Cloud TTS, делегируем ему воспроизведение
            if self.tts_engine == "google_cloud" and self.google_tts_manager:
                return self.google_tts_manager.play_speech(text, voice_id)
            
            # Используем указанный голос или текущий по умолчанию
            if voice_id is None:
                voice_id = self.voice
            
            # Если уже что-то воспроизводится, останавливаем
            self.stop_current_sound()
            
            # Генерируем озвучку
            audio_file = self.generate_speech(text, force_regenerate=False, voice=voice_id)
            if not audio_file:
                return False
            
            try:
                # Запускаем процесс воспроизведения звука
                if self.use_wav:
                    # Для WAV используем paplay или aplay
                    try:
                        self.current_sound_process = subprocess.Popen(
                            ["paplay", audio_file],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                    except:
                        # Если paplay не доступен, пробуем aplay
                        self.current_sound_process = subprocess.Popen(
                            ["aplay", audio_file],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                else:
                    # Для MP3 используем mpg123
                    self.current_sound_process = subprocess.Popen(
                        ["mpg123", audio_file],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                    
                # Запускаем поток ожидания завершения воспроизведения
                self.is_playing = True
                wait_thread = threading.Thread(target=self.wait_completion, daemon=True)
                wait_thread.start()
                
                return True
            except Exception as e:
                print(f"Ошибка при воспроизведении звука: {e}")
                return False
        except Exception as e:
            error_msg = f"Ошибка при воспроизведении речи: {e}"
            print(error_msg)
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
                self.generate_speech(text, force_regenerate=False, voice=voice)
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
            self.generate_speech(text, force_regenerate=False, voice=voice)
            processed += 1
            if self.debug:
                print(f"Генерация: {processed}/{total_missing} - {text} (голос: {voice})")

    def speak_text(self, text, voice_id=None):
        """
        Синтезирует и воспроизводит речь для указанного текста
        
        Args:
            text (str): Текст для озвучивания
            voice_id (str): Идентификатор голоса (можно переопределить)
            
        Returns:
            bool: True, если озвучивание успешно запущено
        """
        try:
            return self.play_speech(text, voice_id)
        except Exception as e:
            error_msg = f"Ошибка при озвучивании текста: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False

    def play_speech_blocking(self, text, voice_id=None):
        """
        Озвучивает текст и ожидает завершения озвучивания
        
        Args:
            text (str): Текст для озвучивания
            voice_id (str): Идентификатор голоса (можно переопределить)
            
        Returns:
            bool: True, если озвучивание успешно выполнено
        """
        try:
            return self.play_speech(text, voice_id, blocking=True)
        except Exception as e:
            error_msg = f"Ошибка при блокирующем воспроизведении речи: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return False