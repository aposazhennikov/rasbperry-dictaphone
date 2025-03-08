#!/usr/bin/env python3
import os
import time
import hashlib
import threading
import subprocess
import json
from datetime import datetime
from gtts import gTTS

class TTSManager:
    """Управление озвучкой текста с помощью gTTS"""
    
    # Лимит бесплатных запросов в день (приблизительная оценка)
    FREE_DAILY_LIMIT = 200
    
    def __init__(self, cache_dir="/home/aleks/cache_tts", lang="ru", tld="com", debug=False, use_wav=True):
        """
        Инициализация менеджера TTS
        
        Args:
            cache_dir (str): Директория для кэширования звуковых файлов
            lang (str): Язык озвучки (ru, en, и т.д.)
            tld (str): Домен Google для TTS (com, ru, и т.д.)
            debug (bool): Режим отладки
            use_wav (bool): Использовать WAV вместо MP3 для более быстрого воспроизведения
        """
        self.cache_dir = cache_dir
        self.lang = lang
        self.tld = tld
        self.current_sound_process = None
        self.is_playing = False
        self.cache_lock = threading.Lock()
        self.debug = debug
        self.use_wav = use_wav
        
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
        Возвращает отладочную информацию
        
        Returns:
            dict: Статистика использования TTS
        """
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
        
        return {
            "total_requests": self.stats["total_requests"],
            "today_requests": self.stats["today_requests"],
            "remaining_free_requests": remaining,
            "cached_used": self.stats["cached_used"],
            "recent_requests": formatted_history
        }
    
    def get_cached_filename(self, text, use_wav=None):
        """
        Создает имя файла на основе хэша текста
        
        Args:
            text (str): Текст для озвучки
            use_wav (bool, optional): Использовать WAV вместо MP3
            
        Returns:
            str: Путь к файлу
        """
        # Если use_wav не указан, используем значение по умолчанию
        if use_wav is None:
            use_wav = self.use_wav
            
        # Создаем хэш текста для уникального имени файла
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        
        # Возвращаем имя файла с соответствующим расширением
        if use_wav:
            return os.path.join(self.cache_dir, f"{text_hash}_{self.lang}.wav")
        else:
            return os.path.join(self.cache_dir, f"{text_hash}_{self.lang}.mp3")
    
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
            
    def generate_speech(self, text, force_regenerate=False):
        """
        Генерирует озвучку текста и сохраняет в кэш
        
        Args:
            text (str): Текст для озвучки
            force_regenerate (bool): Пересоздать файл, даже если он уже существует
            
        Returns:
            str: Путь к сгенерированному файлу
        """
        # Сначала получаем имя MP3 файла
        mp3_file = self.get_cached_filename(text, use_wav=False)
        
        # Если нужен WAV, определяем его имя
        wav_file = None
        if self.use_wav:
            wav_file = self.get_cached_filename(text, use_wav=True)
        
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
                    print(f"Использован кэш для: {text}")
                    
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
                        print(f"Использован кэш (конвертация в WAV) для: {text}")
                        
                    return wav_result
                
            if self.debug:
                print(f"Генерация озвучки для: {text}")
                
            # Увеличиваем счетчики запросов
            self.stats["total_requests"] += 1
            self.stats["today_requests"] += 1
            
            # Замеряем время запроса
            start_time = time.time()
            
            try:
                # Создаем объект gTTS и сохраняем в MP3-файл
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
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                
                # Ограничиваем историю последними 100 запросами
                if len(self.stats["requests_history"]) > 100:
                    self.stats["requests_history"] = self.stats["requests_history"][-100:]
                
                # Сохраняем статистику
                self._save_stats()
                
                if self.debug:
                    print(f"Озвучка сгенерирована за {elapsed_time:.2f} секунд")
                    print(f"Сегодня выполнено {self.stats['today_requests']} запросов из примерно {self.FREE_DAILY_LIMIT}")
                
                return result_file
                
            except Exception as e:
                print(f"Ошибка при генерации озвучки: {e}")
                return None
    
    def play_speech(self, text):
        """
        Воспроизводит озвучку текста
        
        Args:
            text (str): Текст для озвучки
        """
        self.stop_current_sound()
        
        # Получаем файл озвучки
        speech_file = self.get_cached_filename(text, use_wav=self.use_wav)
        
        # Если файла нет в кэше, генерируем его
        if not os.path.exists(speech_file):
            speech_file = self.generate_speech(text)
            if not speech_file:
                return
        else:
            # Увеличиваем счётчик использования кэша
            self.stats["cached_used"] += 1
            self._save_stats()
        
        try:
            # В Windows используем другой подход, чем в Linux
            if os.name == 'nt':
                # Бесшумный запуск на Windows
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                self.current_sound_process = subprocess.Popen(
                    ["powershell", "-c", f"(New-Object Media.SoundPlayer '{speech_file}').PlaySync()"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    startupinfo=startupinfo
                )
            else:
                # Определяем тип воспроизведения в зависимости от формата
                if speech_file.endswith('.wav'):
                    # Для WAV используем aplay
                    self.current_sound_process = subprocess.Popen(
                        ["aplay", "-q", speech_file],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                else:
                    # Для MP3 используем mpg123 с оптимизациями
                    self.current_sound_process = subprocess.Popen(
                        ["mpg123", "-q", "--no-control", "-Z", "--no-gapless", "-A", "hw:0", speech_file],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                
            self.is_playing = True
            
            # Ждем завершения воспроизведения в отдельном потоке
            def wait_completion():
                if self.current_sound_process:
                    self.current_sound_process.wait()
                    self.is_playing = False
                    self.current_sound_process = None
            
            threading.Thread(target=wait_completion, daemon=True).start()
            
        except Exception as e:
            print(f"Ошибка при воспроизведении: {e}")
    
    def stop_current_sound(self):
        """Останавливает текущее воспроизведение"""
        if self.current_sound_process and self.is_playing:
            try:
                self.current_sound_process.terminate()
                self.is_playing = False
                self.current_sound_process = None
            except Exception as e:
                print(f"Ошибка при остановке звука: {e}")
    
    def pre_generate_menu_items(self, menu_items):
        """
        Предварительно генерирует озвучку для всех пунктов меню
        
        Args:
            menu_items (list): Список текстов пунктов меню
            
        Returns:
            dict: Словарь с путями к файлам для каждого пункта меню
        """
        results = {}
        total_items = len(menu_items)
        
        print(f"Предварительная генерация озвучки для {total_items} пунктов меню...")
        
        for i, item in enumerate(menu_items):
            if item:
                if self.debug:
                    print(f"[{i+1}/{total_items}] Генерация: {item}")
                results[item] = self.generate_speech(item)
                
        # Статистика сгенерированных файлов
        new_files = len([f for f in results.values() if f])
        print(f"Сгенерировано {new_files} файлов озвучки")
        
        # Если в режиме отладки, выводим дополнительную статистику
        if self.debug:
            debug_info = self.get_debug_info()
            print("\n=== Статистика TTS ===")
            print(f"Всего запросов к gTTS: {debug_info['total_requests']}")
            print(f"Запросов сегодня: {debug_info['today_requests']}")
            print(f"Примерно осталось бесплатных запросов: {debug_info['remaining_free_requests']}")
            print(f"Использований кэша: {debug_info['cached_used']}")
            
            if debug_info['recent_requests']:
                print("\nПоследние запросы:")
                for req in debug_info['recent_requests']:
                    print(f"  {req}")
        
        return results