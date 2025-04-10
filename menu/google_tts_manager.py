#!/usr/bin/env python3
import os
import time
import hashlib
import threading
import subprocess
import json
from datetime import datetime, timedelta
from google.cloud import texttospeech
from google.cloud import monitoring_v3
import io
import sentry_sdk

class GoogleTTSManager:
    """Управление озвучкой текста с помощью Google Cloud Text-to-Speech API"""
    
    # Цены на использование Google Cloud TTS (в долларах за 1 миллион символов)
    # Источник: https://cloud.google.com/text-to-speech/pricing
    PRICING = {
        "standard": 4.00,   # Стандартные голоса (Standard)
        "wavenet": 16.00,   # WaveNet голоса
        "neural2": 16.00,   # Neural2 голоса
        "studio": 100.00    # Studio голоса
    }
    
    # Бесплатный лимит в месяц (в символах)
    FREE_MONTHLY_CHARS = 1000000  # 1 миллион символов
    
    def __init__(self, cache_dir="/home/aleks/cache_tts", credentials_file="credentials-google-api.json", 
                 lang="ru-RU", debug=False, use_wav=True, voice="ru-RU-Standard-A", settings_manager=None):
        """
        Инициализация менеджера Google TTS
        
        Args:
            cache_dir (str): Директория для кэширования звуковых файлов
            credentials_file (str): Путь к файлу с учетными данными Google Cloud
            lang (str): Язык озвучки (ru-RU, en-US, и т.д.)
            debug (bool): Режим отладки
            use_wav (bool): Использовать WAV вместо MP3 для более быстрого воспроизведения
            voice (str): Идентификатор голоса для озвучки
            settings_manager (SettingsManager): Менеджер настроек
        """
        try:
            self.cache_dir = cache_dir
            self.credentials_file = os.path.abspath(credentials_file)
            self.lang = lang
            self.current_sound_process = None
            self.is_playing = False
            self.cache_lock = threading.Lock()
            self.debug = debug
            self.use_wav = use_wav
            self.settings_manager = settings_manager
            self.monitoring_client = None
            self.project_id = None
            self.monthly_chars_used = 0
            self.last_metrics_update = None
            
            # Проверяем наличие файла с учетными данными
            if not os.path.exists(self.credentials_file):
                raise FileNotFoundError(f"Файл с учетными данными не найден: {self.credentials_file}")
            
            # Устанавливаем переменную окружения для аутентификации Google Cloud
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials_file
            
            # Загружаем информацию о проекте из файла учетных данных
            try:
                with open(self.credentials_file, 'r') as f:
                    credentials_data = json.load(f)
                    self.project_id = credentials_data.get("project_id")
                    if self.debug:
                        print(f"ID проекта Google Cloud: {self.project_id}")
            except Exception as e:
                print(f"Ошибка при загрузке информации о проекте: {e}")
            
            # Инициализируем клиент Google Cloud TTS
            try:
                self.client = texttospeech.TextToSpeechClient()
                if self.debug:
                    print(f"Клиент Google Cloud TTS инициализирован успешно")
                
                # Если есть ID проекта, инициализируем клиент мониторинга
                if self.project_id:
                    self.monitoring_client = monitoring_v3.MetricServiceClient()
                    # Получаем начальные метрики использования
                    self._update_usage_metrics()
            except Exception as e:
                print(f"Ошибка при инициализации клиента Google Cloud TTS: {e}")
                raise
            
            # Статистика для режима отладки
            self.stats_file = os.path.join(cache_dir, "google_tts_stats.json")
            self.stats = {
                "total_requests": 0,
                "today_requests": 0,
                "today_date": datetime.now().strftime("%Y-%m-%d"),
                "cached_used": 0,
                "requests_history": [],
                "total_chars": 0,
                "month_chars": 0,
                "estimated_cost": 0.0
            }
            
            # Создаем директорию для кэша, если она не существует
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
            
            # Загружаем статистику если она есть
            self._load_stats()
            
            # Обновляем счетчик дневных запросов
            self._update_day_counter()
            
            if self.debug:
                print(f"GoogleTTSManager инициализирован. Голос по умолчанию: {voice}")
            
            # Определяем голос - берем из настроек, если доступны, иначе используем значение по умолчанию
            if self.settings_manager:
                try:
                    self.voice = self.settings_manager.get_voice()
                    print(f"[GOOGLE TTS INIT] Установлен голос из настроек: {self.voice}")
                    sentry_sdk.add_breadcrumb(
                        category="voice",
                        message=f"Google TTS Manager: Голос установлен из настроек: {self.voice}",
                        level="info"
                    )
                except Exception as voice_error:
                    error_msg = f"Ошибка при получении голоса из настроек: {voice_error}"
                    print(f"[GOOGLE TTS INIT ERROR] {error_msg}")
                    sentry_sdk.capture_exception(voice_error)
                    # Используем значение по умолчанию
                    self.voice = voice
                    print(f"[GOOGLE TTS INIT] Используем голос по умолчанию: {self.voice}")
            else:
                # Если нет settings_manager, используем значение параметра
                self.voice = voice
                print(f"[GOOGLE TTS INIT] Используем голос из параметра: {self.voice}")
        except Exception as e:
            error_msg = f"Ошибка при инициализации GoogleTTSManager: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def _update_usage_metrics(self):
        """Обновляет метрики использования API из Google Cloud Monitoring"""
        if not self.monitoring_client or not self.project_id:
            return
            
        try:
            # Обновляем не чаще чем раз в 10 минут
            now = datetime.now()
            if self.last_metrics_update and (now - self.last_metrics_update) < timedelta(minutes=10):
                return
                
            self.last_metrics_update = now
            
            # Формируем запрос к API мониторинга
            project = f"projects/{self.project_id}"
            interval = monitoring_v3.TimeInterval()
            
            # Устанавливаем период для запроса - с начала текущего месяца
            now = time.time()
            start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            seconds = int(start_of_month.timestamp())
            nanos = int((start_of_month.timestamp() - seconds) * 10**9)
            interval.start_time.seconds = seconds
            interval.start_time.nanos = nanos
            
            seconds = int(now)
            nanos = int((now - seconds) * 10**9)
            interval.end_time.seconds = seconds
            interval.end_time.nanos = nanos
            
            # Запрос для API Text-to-Speech
            tts_filter = 'metric.type = "texttospeech.googleapis.com/character_count" AND resource.type = "global"'
            
            # Выполняем запрос
            results = self.monitoring_client.list_time_series(
                request={
                    "name": project,
                    "filter": tts_filter,
                    "interval": interval,
                    "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                }
            )
            
            # Обрабатываем результаты
            total_chars = 0
            for time_series in results:
                for point in time_series.points:
                    total_chars += point.value.int64_value
            
            self.monthly_chars_used = total_chars
            self.stats["month_chars"] = total_chars
            
            # Рассчитываем примерную стоимость
            voice_type = "standard"  # По умолчанию стандартные голоса
            if "WaveNet" in self.voice:
                voice_type = "wavenet"
            elif "Neural2" in self.voice:
                voice_type = "neural2"
            elif "Studio" in self.voice:
                voice_type = "studio"
                
            # Вычисляем стоимость использования сверх бесплатного лимита
            excess_chars = max(0, total_chars - self.FREE_MONTHLY_CHARS)
            cost = 0
            if excess_chars > 0:
                cost = (excess_chars / 1000000) * self.PRICING[voice_type]
                
            self.stats["estimated_cost"] = cost
            self._save_stats()
            
            if self.debug:
                print(f"Использовано символов в этом месяце: {total_chars}")
                print(f"Осталось бесплатных символов: {max(0, self.FREE_MONTHLY_CHARS - total_chars)}")
                if cost > 0:
                    print(f"Примерная стоимость: ${cost:.2f}")
                    
        except Exception as e:
            print(f"Ошибка при получении метрик использования: {e}")
            
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
                message=f"Google TTS Manager: Начало установки голоса {voice}",
                level="info"
            )
            print(f"[GOOGLE TTS] Запрос на установку голоса: {voice}")
            print(f"[GOOGLE TTS] Текущий голос перед установкой: {self.voice}")
            
            # Получаем список доступных голосов
            try:
                available_voices = self.get_available_voices()
                sentry_sdk.add_breadcrumb(
                    category="voice",
                    message=f"Google TTS Manager: Доступные голоса: {list(available_voices.keys())}",
                    level="info"
                )
                print(f"[GOOGLE TTS] Доступные голоса: {list(available_voices.keys())}")
                
                if voice not in available_voices:
                    # Проверяем, есть ли голос в стандартном списке
                    standard_voices = self._get_default_voices()
                    if voice in standard_voices:
                        print(f"[GOOGLE TTS] Голос {voice} не найден в API, но есть в стандартном списке")
                        # Допускаем стандартные голоса, даже если API их не вернул
                    else:
                        error_msg = f"Google TTS Manager: Голос {voice} не найден в Google Cloud TTS"
                        print(f"[GOOGLE TTS ERROR] {error_msg}")
                        sentry_sdk.capture_message(error_msg, level="error")
                        return False
            except Exception as avail_error:
                error_msg = f"Ошибка при получении списка доступных голосов: {avail_error}"
                print(f"[GOOGLE TTS WARNING] {error_msg}")
                sentry_sdk.capture_message(error_msg, level="warning")
                # Проверяем, есть ли голос в стандартном списке
                standard_voices = self._get_default_voices()
                if voice not in standard_voices:
                    print(f"[GOOGLE TTS ERROR] Голос {voice} не найден в стандартном списке")
                    return False
                else:
                    print(f"[GOOGLE TTS] Голос {voice} найден в стандартном списке")
            
            # Сохраняем старый голос для логирования
            old_voice = self.voice
                
            # Устанавливаем новый голос
            self.voice = voice
            
            # Проверяем, сохранился ли голос
            print(f"[GOOGLE TTS] Голос установлен: {self.voice}")
            
            if self.voice != voice:
                error_msg = f"Google TTS Manager: Голос не был установлен: ожидалось {voice}, получено {self.voice}"
                print(f"[GOOGLE TTS ERROR] {error_msg}")
                sentry_sdk.capture_message(error_msg, level="error")
                return False
            
            # Логируем успешную установку голоса
            sentry_sdk.add_breadcrumb(
                category="voice",
                message=f"Google TTS Manager: Голос успешно изменен с {old_voice} на {self.voice}",
                level="info"
            )
            print(f"[GOOGLE TTS] Голос успешно изменен с {old_voice} на {self.voice}")
                
            return True
        except Exception as e:
            error_msg = f"Критическая ошибка при установке голоса в Google TTS: {e}"
            print(f"[GOOGLE TTS CRITICAL ERROR] {error_msg}")
            sentry_sdk.capture_exception(e)
            return False
    
    def get_available_voices(self):
        """
        Получает список доступных голосов из Google Cloud TTS API
        
        Returns:
            dict: Словарь с доступными голосами {voice_id: name}
        """
        try:
            # Логируем начало процесса
            print(f"[GOOGLE TTS] Запрос на получение списка доступных голосов")
            
            # Проверяем инициализацию клиента
            if not hasattr(self, 'client') or self.client is None:
                error_msg = "Google Cloud TTS клиент не инициализирован"
                print(f"[GOOGLE TTS WARNING] {error_msg}")
                sentry_sdk.capture_message(error_msg, level="warning")
                # Возвращаем стандартный список голосов
                return self._get_default_voices()
                
            # Пробуем получить список голосов для указанного языка
            try:
                response = self.client.list_voices(language_code=self.lang)
                voices = {}
                
                for voice in response.voices:
                    # Добавляем только голоса для нашего языка
                    if self.lang in voice.language_codes:
                        # Создаем удобное имя для голоса
                        if "Standard" in voice.name:
                            name_type = "Стандартный"
                        elif "WaveNet" in voice.name:
                            name_type = "WaveNet"
                        elif "Neural2" in voice.name:
                            name_type = "Neural2"
                        elif "Studio" in voice.name:
                            name_type = "Студийный"
                        else:
                            name_type = "Обычный"
                            
                        # Определяем пол голоса
                        if voice.ssml_gender == texttospeech.SsmlVoiceGender.FEMALE:
                            gender = "женский"
                        elif voice.ssml_gender == texttospeech.SsmlVoiceGender.MALE:
                            gender = "мужской"
                        else:
                            gender = "нейтральный"
                            
                        # Формируем описание голоса
                        voice_desc = f"{name_type} {gender} ({voice.name})"
                        voices[voice.name] = voice_desc
                
                if not voices:
                    print(f"[GOOGLE TTS WARNING] Не найдены голоса для языка {self.lang}, возвращаем стандартный список")
                    return self._get_default_voices()
                    
                print(f"[GOOGLE TTS] Успешно получены {len(voices)} голосов из API")
                return voices
                
            except Exception as api_error:
                error_msg = f"Ошибка при запросе голосов из API: {str(api_error)}"
                print(f"[GOOGLE TTS WARNING] {error_msg}")
                sentry_sdk.capture_exception(api_error)
                # Возвращаем стандартный список голосов
                return self._get_default_voices()
                
        except Exception as e:
            error_msg = f"Критическая ошибка при получении списка голосов: {str(e)}"
            print(f"[GOOGLE TTS ERROR] {error_msg}")
            sentry_sdk.capture_exception(e)
            # Возвращаем стандартный список голосов
            return self._get_default_voices()
    
    def _get_default_voices(self):
        """
        Возвращает стандартный список голосов, когда API недоступен
        
        Returns:
            dict: Словарь с доступными голосами {voice_id: name}
        """
        print(f"[GOOGLE TTS] Возвращаем стандартный список голосов")
        return {
            "ru-RU-Standard-A": "Стандартный женский (ru-RU-Standard-A)",
            "ru-RU-Standard-B": "Стандартный мужской (ru-RU-Standard-B)",
            "ru-RU-Standard-C": "Стандартный женский (ru-RU-Standard-C)",
            "ru-RU-Standard-D": "Стандартный мужской (ru-RU-Standard-D)",
            "ru-RU-Standard-E": "Стандартный женский (ru-RU-Standard-E)"
        }
    
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
        filename = f"gc_{safe_text}_{voice_short}_{text_hash}"
        
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
        Генерирует озвучку текста с помощью Google Cloud TTS и сохраняет в кэш
        
        Args:
            text (str): Текст для озвучки
            force_regenerate (bool): Пересоздать файл, даже если он уже существует
            voice (str, optional): Идентификатор голоса
            
        Returns:
            str: Путь к сгенерированному файлу
        """
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
            
            # Увеличиваем счетчик символов
            char_count = len(text)
            self.stats["total_chars"] += char_count
            
            # Замеряем время запроса
            start_time = time.time()
            
            try:
                # Создаем запрос к Google Cloud TTS API
                synthesis_input = texttospeech.SynthesisInput(text=text)
                
                # Настраиваем голос
                voice_params = texttospeech.VoiceSelectionParams(
                    language_code=self.lang,
                    name=voice
                )
                
                # Настраиваем аудио выход
                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3
                )
                
                # Отправляем запрос на синтез речи
                response = self.client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice_params,
                    audio_config=audio_config
                )
                
                # Сохраняем аудио в файл
                with open(mp3_file, "wb") as out:
                    out.write(response.audio_content)
                
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
                    "voice": voice,
                    "chars": char_count
                })
                
                # Ограничиваем историю до 100 последних запросов
                if len(self.stats["requests_history"]) > 100:
                    self.stats["requests_history"] = self.stats["requests_history"][-100:]
                    
                # Обновляем метрики использования
                self._update_usage_metrics()
                
                # Сохраняем статистику
                self._save_stats()
                
                return result_file
            except Exception as e:
                print(f"Ошибка при генерации озвучки: {e}")
                return None
    
    def get_usage_info(self):
        """
        Возвращает информацию об использовании API
        
        Returns:
            dict: Информация об использовании API
        """
        # Обновляем метрики использования
        self._update_usage_metrics()
        
        # Рассчитываем оставшуюся квоту
        remaining_free = max(0, self.FREE_MONTHLY_CHARS - self.monthly_chars_used)
        
        # Определяем тип голоса для расчета цены
        voice_type = "standard"
        if "WaveNet" in self.voice:
            voice_type = "wavenet"
        elif "Neural2" in self.voice:
            voice_type = "neural2"
        elif "Studio" in self.voice:
            voice_type = "studio"
            
        # Рассчитываем стоимость символов
        price_per_million = self.PRICING.get(voice_type, self.PRICING["standard"])
        
        return {
            "total_requests": self.stats["total_requests"],
            "today_requests": self.stats["today_requests"],
            "total_chars": self.stats["total_chars"],
            "monthly_chars_used": self.monthly_chars_used,
            "remaining_free_chars": remaining_free,
            "price_per_million": price_per_million,
            "estimated_cost": self.stats["estimated_cost"],
            "voice_type": voice_type,
            "last_update": self.last_metrics_update.strftime("%Y-%m-%d %H:%M:%S") if self.last_metrics_update else "Никогда"
        }
    
    def play_speech(self, text, voice=None, blocking=False):
        """
        Воспроизводит озвученный текст
        
        Args:
            text (str): Текст для озвучки
            voice (str, optional): Идентификатор голоса
            blocking (bool): Ожидать окончания воспроизведения
            
        Returns:
            bool: True если воспроизведение запущено, иначе False
        """
        try:
            # Используем указанный голос или текущий по умолчанию
            if voice is None:
                voice = self.voice
                
            # Если уже что-то воспроизводится, останавливаем
            self.stop_current_sound()
            
            # Генерируем озвучку
            audio_file = self.generate_speech(text, force_regenerate=False, voice=voice)
            if not audio_file:
                return False
                
            try:
                # Получаем текущий уровень громкости из настроек
                volume = 100
                if self.settings_manager:
                    try:
                        volume = self.settings_manager.get_system_volume()
                    except Exception as vol_error:
                        print(f"[GOOGLE TTS WARNING] Ошибка при получении громкости: {vol_error}")
                        sentry_sdk.capture_exception(vol_error)
                
                # Нормализуем громкость в диапазон 0-1 с экспоненциальной шкалой
                # Используем экспоненциальную шкалу для более естественного изменения громкости
                volume_exp = (volume / 100.0) ** 2
                
                # Запускаем процесс воспроизведения звука с указанной громкостью
                if self.use_wav:
                    # Для WAV используем paplay или aplay с контролем громкости
                    try:
                        # paplay использует линейную шкалу от 0 до 65536
                        volume_paplay = int(volume_exp * 65536)
                        self.current_sound_process = subprocess.Popen(
                            ["paplay", "--volume", str(volume_paplay), audio_file],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                    except:
                        # Если paplay не доступен, пробуем aplay с softvol
                        # aplay использует линейную шкалу от 0 до 100
                        volume_aplay = int(volume_exp * 100)
                        self.current_sound_process = subprocess.Popen(
                            ["aplay", "-D", f"softvol,softvol=volume={volume_aplay}", audio_file],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                else:
                    # Для MP3 используем mpg123 с контролем громкости
                    # mpg123 использует линейную шкалу от 0 до 32768
                    volume_mpg123 = int(volume_exp * 32768)
                    self.current_sound_process = subprocess.Popen(
                        ["mpg123", "-f", str(volume_mpg123), audio_file],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                    
                # Запускаем поток ожидания завершения воспроизведения
                self.is_playing = True
                wait_thread = threading.Thread(target=self.wait_completion, daemon=True)
                wait_thread.start()
                
                # Если нужен блокирующий режим, ждем завершения
                if blocking:
                    wait_thread.join()
                
                return True
            except Exception as e:
                error_msg = f"Ошибка при воспроизведении звука: {e}"
                print(f"[GOOGLE TTS ERROR] {error_msg}")
                sentry_sdk.capture_exception(e)
                return False
        except Exception as e:
            error_msg = f"Ошибка при воспроизведении речи: {e}"
            print(f"[GOOGLE TTS ERROR] {error_msg}")
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
        if not voices:
            voices = [self.voice]  # По умолчанию только текущий голос
            
        # Удаляем дубликаты из списка текстов
        unique_items = set(menu_items)
        
        total_items = len(unique_items) * len(voices)
        processed = 0
        total_chars = 0
        
        if self.debug:
            print(f"Предварительная генерация озвучки для {len(unique_items)} уникальных текстов в {len(voices)} голосах")
        
        for voice in voices:
            for text in unique_items:
                self.generate_speech(text, force_regenerate=False, voice=voice)
                processed += 1
                total_chars += len(text)
                if self.debug:
                    print(f"Предварительная генерация: {processed}/{total_items} - {text} (голос: {voice})")
        
        # Обновляем метрики использования
        self._update_usage_metrics()
        
        if self.debug:
            print(f"Предварительная генерация завершена. Всего символов: {total_chars}")
            print(f"Примерная стоимость: ${(total_chars / 1000000) * self.PRICING['standard']:.4f}")
            usage_info = self.get_usage_info()
            print(f"Использовано символов в этом месяце: {usage_info['monthly_chars_used']}")
            print(f"Осталось бесплатных символов: {usage_info['remaining_free_chars']}")
            print(f"Общая стоимость: ${usage_info['estimated_cost']:.2f}")
    
    def pre_generate_missing_menu_items(self, menu_items, voices=None):
        """
        Предварительно генерирует только отсутствующие озвучки для пунктов меню
        
        Args:
            menu_items (list): Список текстов для озвучки
            voices (list, optional): Список голосов для предварительной генерации
        """
        if not voices:
            voices = [self.voice]  # По умолчанию только текущий голос
            
        # Удаляем дубликаты из списка текстов
        unique_items = set(menu_items)
        
        missing_items = []
        
        # Проверяем наличие файлов и составляем список отсутствующих
        for voice in voices:
            for text in unique_items:
                # Получаем имя файла без проверки существования
                filename = self.get_cached_filename(text, use_wav=False, voice=voice)
                if not os.path.exists(filename):
                    missing_items.append((text, voice))
        
        total_missing = len(missing_items)
        processed = 0
        total_chars = 0
        
        if self.debug:
            print(f"Предварительная генерация отсутствующей озвучки: найдено {total_missing} из {len(unique_items) * len(voices)} возможных файлов")
        
        if total_missing == 0:
            print("Все аудиофайлы Google Cloud TTS уже сгенерированы. Нет необходимости в дополнительной генерации.")
            return
        
        for text, voice in missing_items:
            self.generate_speech(text, force_regenerate=False, voice=voice)
            processed += 1
            total_chars += len(text)
            if self.debug:
                print(f"Генерация Google Cloud TTS: {processed}/{total_missing} - {text} (голос: {voice})")
        
        # Обновляем метрики использования
        self._update_usage_metrics()
        
        if self.debug:
            print(f"Генерация отсутствующих звуков завершена. Всего символов: {total_chars}")
            print(f"Примерная стоимость: ${(total_chars / 1000000) * self.PRICING['standard']:.4f}")
            usage_info = self.get_usage_info()
            print(f"Использовано символов в этом месяце: {usage_info['monthly_chars_used']}")
            print(f"Осталось бесплатных символов: {usage_info['remaining_free_chars']}")
            print(f"Общая стоимость: ${usage_info['estimated_cost']:.2f}") 