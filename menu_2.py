#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import signal
import tempfile
import json
import threading
import sounddevice as sd
import soundfile as sf
from evdev import InputDevice, ecodes, list_devices
from datetime import datetime
import calendar

# Добавляем эти строки перед импортом vlc
os.environ["VLC_PLUGIN_PATH"] = "/usr/lib/x86_64-linux-gnu/vlc/plugins"
os.environ["LD_LIBRARY_PATH"] = "/usr/lib/x86_64-linux-gnu"

import vlc

TARGET_DEVICE_NAME = "HAOBO Technology USB Composite Device Keyboard"
RECORDS_BASE_DIR = "/home/aleks/records"
SOUNDS_DIR = "/home/aleks/main-sounds"
DEBOUNCE_TIME = 0.1

KEY_UP = 103
KEY_DOWN = 108
KEY_SELECT = 353
KEY_BACK = 158
KEY_LEFT = 105
KEY_RIGHT = 106
KEY_VOLUMEUP = 115
KEY_VOLUMEDOWN = 114
KEY_POWER = 116

MENU_NAMES = {
    "MAIN_MENU": "main-menu",
    "DICTAPHONE_MENU": "dictaphone-mode",
    "FOLDER_SELECT_RECORD": "choose-folder-record",
    "FOLDER_SELECT_PLAY": "choose-folder-play",
    "FOLDER_SELECT_DELETE": "choose-folder-delete",
    "RECORDS_MENU": "records-menu",
    "DELETE_RECORDS_MENU": "delete-records-menu",
    "CALL_MENU": "call-mode",
    "MAKE_CALL_MENU": "make-call-menu",
    "FAVORITES_MENU": "favorites-menu",
    "RECENT_MENU": "recent-menu",
    "INCOMING_CALL": "incoming-call",
    "INCOMING_CALL_PROMPT": "incoming-call-prompt",
    "RADIO_MENU": "radio-mode",
    "RADIO_STATION_MENU": "radio-station-menu",
    "CONFIRM_DELETE_MENU": "confirm-delete-menu",
    "FOLDER_SELECT_CALENDAR": "choose-folder-calendar",
    "CALENDAR_YEAR_MENU": "year-menu",
    "CALENDAR_MONTH_MENU": "month-menu",
    "CALENDAR_DAY_MENU": "day-menu",
    "PLAYBACK_SCREEN": "playback-screen"
}

MONTH_TO_SOUND = {
    1: "january",
    2: "february",
    3: "march",
    4: "april",
    5: "may",
    6: "june",
    7: "july",
    8: "august",
    9: "september",
    10: "october",
    11: "november",
    12: "december"
}

WEEKDAY_TO_SOUND = {
    0: "monday",
    1: "tuesday",
    2: "wednesday",
    3: "thursday",
    4: "friday",
    5: "saturday",
    6: "sunday"
}

def menu_name_for_audio(menu):
    """Возвращает звуковой файл для названия меню"""
    return MENU_NAMES.get(menu, "main-menu")

# Структура меню
MENUS = {
    "MAIN_MENU": [
        ("Режим диктофона", "DICTAPHONE_MODE"),
        ("Режим звонка", "CALL_MENU"),
        ("Режим управления радио", "RADIO_MENU")
    ],
    "DICTAPHONE_MENU": [
        ("Создать новую запись", "RECORD_NEW"),
        ("Календарь", "CALENDAR"),
        ("Воспроизвести уже имеющуюся запись", "FOLDER_SELECT"),
        ("Удалить запись", "FOLDER_SELECT_DELETE")
    ],
    "FOLDER_SELECT_RECORD": [
        ("Папка A", None),
        ("Папка B", None),
        ("Папка C", None),
    ],
    "FOLDER_SELECT_PLAY": [
        ("Папка A", None),
        ("Папка B", None),
        ("Папка C", None),
    ],
    "FOLDER_SELECT_DELETE": [
        ("Папка A", None),
        ("Папка B", None),
        ("Папка C", None),
    ],
    "CALL_MENU": [
        ("Принять звонок", "INCOMING_CALL"),
        ("Совершить звонок", "MAKE_CALL_MENU"),
    ],
    "INCOMING_CALL": [
        ("ЗВОНИТ NAME", "INCOMING_CALL_PROMPT")
    ],
    "INCOMING_CALL_PROMPT": [
        ("Да", None),
        ("Нет", None)
    ],
    "MAKE_CALL_MENU": [
        ("Избранные контакты", "FAVORITES_MENU"),
        ("Последние набраные", "RECENT_MENU"),
    ],
    "FAVORITES_MENU": [
        ("NAME1", None),
        ("NAME2", None),
        ("Удалить избранный контакт", None),
        ("Добавить избранный контакт", None),
    ],
    "RECENT_MENU": [
        ("NAME", None)
    ],
    "RADIO_MENU": [
        ("Радиостанция Юмор", "RADIO_STATION_MENU"),
        ("Радиостанция Наука", "RADIO_STATION_MENU"),
        ("Радиостанция политика", "RADIO_STATION_MENU"),
        ("Радиостанция Трошин", "RADIO_STATION_MENU"),
        ("Радиостанция Шаов", "RADIO_STATION_MENU"),
        ("Радиостация Природа", "RADIO_STATION_MENU"),
    ],
    "RADIO_STATION_MENU": [
        ("Что сейчас звучит?", None),
        ("Начать текущую композицию с начала", None),
        ("Переключить на предыдущую композицию", None),
        ("Переключить на следующую композицию", None),
    ],
    "CONFIRM_DELETE_MENU": [
        ("Нет", None),
        ("Да", None)
    ],
    "FOLDER_SELECT_CALENDAR": [
        ("Папка A", None),
        ("Папка B", None),
        ("Папка C", None),
    ]
}

# Словарь папок
FOLDERS = {
    "Папка A": "A",
    "Папка B": "B",
    "Папка C": "C"
}

class AudioPlayer:
    def __init__(self):
        self.current_sound_process = None
        self.playback_in_progress = False
        self.paused = False
        self.current_position = 0
        self.total_duration = 0
        self.sound_queue = []
        self.queue_thread = None
        self.queue_running = False
        self.queue_lock = threading.Lock()
        self.progress_thread = None
        self.progress_stop_flag = False

        # Инициализация VLC
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        self.current_speed = 1.0
        self.volume = 100

    def start_playback(self, file_path, on_finish_callback=None):
        self.stop_playback()
        try:
            # Создаем медиа и загружаем файл
            media = self.instance.media_new(file_path)
            self.player.set_media(media)

            # Получаем длительность файла
            media.parse()
            self.total_duration = media.get_duration() / 1000.0  # конвертируем из мс в секунды

            # Начинаем воспроизведение
            self.player.play()
            self.playback_in_progress = True
            self.paused = False
            self.current_speed = 1.0
            self.player.set_rate(self.current_speed)

            # Запускаем поток обновления прогресса
            self.progress_stop_flag = False
            self.progress_thread = threading.Thread(target=self._update_progress, daemon=True)
            self.progress_thread.start()

            # Запускаем поток ожидания завершения
            def wait_playback():
                while self.playback_in_progress:
                    state = self.player.get_state()
                    if state == vlc.State.Ended:
                        self.stop_playback()
                        if on_finish_callback:
                            on_finish_callback()
                        break
                    time.sleep(0.1)

            threading.Thread(target=wait_playback, daemon=True).start()

        except Exception as e:
            print(f"Playback error: {e}")
            self.stop_playback()

    def _update_progress(self):
        while not self.progress_stop_flag and self.playback_in_progress:
            if not self.paused:
                try:
                    self.current_position = self.player.get_time() / 1000.0  # конвертируем из мс в секунды
                except:
                    pass
            time.sleep(0.1)

    def stop_playback(self):
        self.progress_stop_flag = True
        if self.progress_thread:
            self.progress_thread.join()
        self.player.stop()
        self.playback_in_progress = False
        self.paused = False
        self.current_position = 0
        self.current_speed = 1.0

    def toggle_pause(self):
        if self.playback_in_progress:
            self.player.pause()
            self.paused = not self.paused

    def set_speed(self, speed):
        if self.playback_in_progress:
            self.current_speed = speed
            self.player.set_rate(speed)

    def seek(self, seconds):
        if self.playback_in_progress:
            current_ms = self.player.get_time()
            new_ms = max(0, current_ms + int(seconds * 1000))
            self.player.set_time(new_ms)

    def set_volume(self, volume):
        """Установить громкость (0-100)"""
        self.volume = max(0, min(100, volume))
        self.player.audio_set_volume(self.volume)

    def volume_up(self):
        """Увеличить громкость на 10%"""
        self.set_volume(self.volume + 10)

    def volume_down(self):
        """Уменьшить громкость на 10%"""
        self.set_volume(self.volume - 10)

    def start_right_fast_forward(self):
        """Ускоренное воспроизведение"""
        if self.playback_in_progress:
            self.set_speed(2.0)

    def stop_right_fast_forward(self):
        """Возврат к нормальной скорости"""
        if self.playback_in_progress:
            self.set_speed(1.0)

    def start_left_rewind(self):
        """Начать перемотку назад"""
        if self.playback_in_progress:
            self.seek(-5)  # перемотка на 5 секунд назад

    def stop_left_rewind(self):
        """Остановить перемотку назад"""
        pass  # Ничего не делаем, так как перемотка происходит по одному событию

    def play_sound(self, sound_name):
        """Воспроизвести системный звук"""
        self.stop_current_sound()
        try:
            self.current_sound_process = subprocess.Popen(
                ["paplay", f"{SOUNDS_DIR}/{sound_name}.wav"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print(f"Sound playback error: {e}")

    def play_sound_sequence_async(self, sounds):
        """Воспроизвести последовательность системных звуков асинхронно"""
        self.stop_current_sound()
        
        with self.queue_lock:
            self.sound_queue = sounds.copy()
            
            if not self.queue_running:
                self.queue_running = True
                self.queue_thread = threading.Thread(target=self._process_sound_queue, daemon=True)
                self.queue_thread.start()

    def _process_sound_queue(self):
        """Обработчик очереди звуков"""
        while self.queue_running:
            current_sound = None
            
            with self.queue_lock:
                if self.sound_queue:
                    current_sound = self.sound_queue.pop(0)
                else:
                    self.queue_running = False
                    break

            if current_sound:
                try:
                    self.current_sound_process = subprocess.Popen(
                        ["paplay", f"{SOUNDS_DIR}/{current_sound}.wav"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                    self.current_sound_process.wait()
                except Exception as e:
                    print(f"Sound sequence error: {e}")

        self.current_sound_process = None
        self.queue_running = False

    def stop_current_sound(self):
        """Остановить текущий системный звук"""
        with self.queue_lock:
            self.sound_queue.clear()
            
        if self.current_sound_process and self.current_sound_process.poll() is None:
            try:
                self.current_sound_process.terminate()
                self.current_sound_process.wait()
            except:
                pass
            self.current_sound_process = None

class Recorder:
    def __init__(self):
        self.recording_in_progress = False
        self.record_paused = False
        self.stop_flag = False
        self.file = None
        self.file_path = None
        self.stream = None
        self.start_time = 0
        self.pause_total = 0
        self.pause_start = None
        self.timer_thread = None
        self.timer_running = False

    def start_recording_delayed(self, folder):
        os.makedirs(os.path.join(RECORDS_BASE_DIR, folder), exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d-%H-%M-%S")
        self.file_path = os.path.join(RECORDS_BASE_DIR, folder, f"{timestamp}.wav")

        self.recording_in_progress = True
        self.record_paused = False
        self.stop_flag = False
        self.start_time = time.time()
        self.pause_total = 0
        self.pause_start = None

        samplerate = 44100
        channels = 1
        self.file = sf.SoundFile(self.file_path, mode='x', samplerate=samplerate, channels=channels, subtype='PCM_16')

        def callback(indata, frames, time_, status):
            if self.stop_flag:
                raise sd.CallbackStop()
            if not self.record_paused:
                self.file.write(indata)

        self.stream = sd.InputStream(samplerate=samplerate, channels=channels, dtype='int16', callback=callback)
        self.stream.start()

        self.timer_running = True
        self.timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self.timer_thread.start()

    def _timer_loop(self):
        while self.timer_running and self.recording_in_progress and not self.stop_flag:
            elapsed = self._get_elapsed_time()
            self.update_recording_screen(elapsed)
            time.sleep(1)

    def _get_elapsed_time(self):
        elapsed = time.time() - self.start_time - self.pause_total
        if elapsed < 0:
            elapsed = 0
        return elapsed

    def update_recording_screen(self, elapsed):
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        status = "ЗАПИСЬ НА ПАУЗЕ" if self.record_paused else f"●REC {minutes:02d}:{seconds:02d}"
        os.system("clear")
        print("Идет запись в папку", os.path.basename(os.path.dirname(self.file_path)))
        print("Файл:", os.path.basename(self.file_path))
        print("KEY_SELECT - пауза/продолжить запись")
        print("KEY_BACK - остановить и сохранить")
        print(status)

    def pause_recording(self):
        if self.recording_in_progress and not self.record_paused:
            self.record_paused = True
            self.pause_start = time.time()

    def resume_recording(self):
        if self.recording_in_progress and self.record_paused:
            self.record_paused = False
            if self.pause_start:
                self.pause_total += (time.time() - self.pause_start)
                self.pause_start = None

    def stop_recording(self):
        if self.recording_in_progress:
            self.stop_flag = True
            self.timer_running = False
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            if self.file:
                self.file.close()
                self.file = None
            self.recording_in_progress = False
            self.record_paused = False

class BaseMenuManager:
    def __init__(self, audio: AudioPlayer, recorder: Recorder):
        self.current_menu = "MAIN_MENU"
        self.current_selection = 0
        self.parent_menu_stack = []
        self.audio = audio
        self.recorder = recorder
        self.choosen_folder = None
        self.records_list = []
        self.in_play_mode = False
        self.selected_record_to_delete = None
        self.is_calendar_playback = False
        
        # Создаем менеджеры для разных функциональностей
        self.display_manager = DisplayManager(self)
        self.navigation_manager = NavigationManager(self)
        self.playback_manager = PlaybackManager(self)
        self.recording_manager = RecordingManager(self)
        self.calendar_manager = CalendarManager(self)
        
    def play_menu_sound(self):
        """Воспроизводит звук перемещения по меню в зависимости от текущего меню и выбранного пункта"""
        # Останавливаем текущий звук
        self.audio.stop_current_sound()
        
        # Воспроизводим соответствующий звук в зависимости от текущего меню и выбранного пункта
        if self.current_menu == "MAIN_MENU":
            if self.current_selection == 0:  # Dictaphone Mode
                self.audio.play_sound("dictaphone-mode")
            elif self.current_selection == 1:  # Call Mode
                self.audio.play_sound("call-mode")
            elif self.current_selection == 2:  # Radio Mode
                self.audio.play_sound("radio-mode")
        elif self.current_menu == "DICTAPHONE_MENU":
            if self.current_selection == 0:  # Create New Record
                self.audio.play_sound("create-new-record")
            elif self.current_selection == 1:  # Calendar
                self.audio.play_sound("calendar")
            elif self.current_selection == 2:  # Play Records
                self.audio.play_sound("play-existing")
            elif self.current_selection == 3:  # Delete Records
                self.audio.play_sound("delete-record")
        elif self.current_menu == "CALL_MENU":
            if self.current_selection == 0:  # Dial Number
                self.audio.play_sound("dial-number")
            elif self.current_selection == 1:  # Phone Book
                self.audio.play_sound("phone-book")
            elif self.current_selection == 2:  # Call Log
                self.audio.play_sound("call-log")
        elif self.current_menu == "RADIO_MENU":
            if self.current_selection == 0:  # Play Radio
                self.audio.play_sound("play-radio")
            elif self.current_selection == 1:  # Radio Stations
                self.audio.play_sound("radio-stations")
        elif self.current_menu == "RECORDS_MENU":
            if self.records_list:
                # Уже обрабатывается в move_up и move_down - озвучивание номера записи
                pass
        elif self.current_menu == "DELETE_RECORDS_MENU":
            if self.records_list:
                # Уже обрабатывается в move_up и move_down - озвучивание номера записи
                pass
        elif self.current_menu == "CONFIRM_DELETE_MENU":
            if self.current_selection == 0:  # Нет
                self.audio.play_sound("no")
            elif self.current_selection == 1:  # Да
                self.audio.play_sound("yes")
        else:
            # Для всех остальных случаев воспроизводим стандартный звук меню
            self.audio.play_sound("menu-move")
        
    def get_records_list(self, folder):
        """Получение списка записей из указанной папки"""
        if not os.path.exists(folder):
            return []
        
        files = []
        for file in sorted(os.listdir(folder), reverse=True):
            if file.endswith(".wav"):
                files.append(file)
        return files
        
    # Метод-прокси для отображения текущего экрана
    def display_current_screen(self):
        self.display_manager.display_current_screen()
        
    # Методы-прокси для навигации
    def move_up(self):
        self.navigation_manager.move_up()
        
    def move_down(self):
        self.navigation_manager.move_down()
        
    def enter_selection(self):
        self.navigation_manager.enter_selection()
        
    def go_back(self):
        self.navigation_manager.go_back()
        
    def exit_to_parent_menu(self):
        self.navigation_manager.exit_to_parent_menu()
    
    # Методы-прокси для воспроизведения
    def pause_resume_playback(self):
        self.playback_manager.pause_resume_playback()
    
    def stop_playback_return(self):
        self.playback_manager.stop_playback_return()
    
    def request_delete_during_playback(self):
        self.playback_manager.request_delete_during_playback()
    
    def toggle_pause_playback(self):
        self.playback_manager.toggle_pause_playback()
    
    # Методы-прокси для записи
    def pause_resume_recording(self):
        self.recording_manager.pause_resume_recording()
    
    def stop_recording_return(self):
        self.recording_manager.stop_recording_return()
    
    def _record_sequence(self, chosen):
        self.recording_manager._record_sequence(chosen)


class DisplayManager:
    def __init__(self, base_manager):
        self.base = base_manager
    
    def display_current_screen(self):
        """Отображает текущий экран в зависимости от текущего состояния меню"""
        if self.base.current_menu == "MAIN_MENU":
            self.display_main_menu()
        elif self.base.current_menu == "DICTAPHONE_MENU":
            self.display_dictaphone_menu()
        elif self.base.current_menu == "CALL_MENU":
            self.display_call_menu()
        elif self.base.current_menu == "RADIO_MENU":
            self.display_radio_menu()
        elif self.base.current_menu == "RECORDS_MENU":
            self.display_records_menu()
        elif self.base.current_menu == "DELETE_RECORDS_MENU":
            self.display_delete_records_menu()
        elif self.base.current_menu == "CONFIRM_DELETE_MENU":
            self.display_confirm_delete_menu()
        elif self.base.current_menu == "RECORDING_SCREEN":
            self.display_recording_screen()
        elif self.base.current_menu == "PLAYBACK_SCREEN":
            self.display_playback_screen()
        elif self.base.current_menu == "CALENDAR_YEAR_MENU":
            self.display_calendar_year_menu()
        elif self.base.current_menu == "CALENDAR_MONTH_MENU":
            self.display_calendar_month_menu()
        elif self.base.current_menu == "CALENDAR_DAY_MENU":
            self.display_calendar_day_menu()
        else:
            # Для остальных меню используем стандартное отображение
            self.display_generic_menu()
    
    def display_main_menu(self):
        """Отображение главного меню"""
        os.system("clear")
        print(f"=== {menu_name_for_audio(self.base.current_menu)} ===")
        
        for i, (name, _) in enumerate(MENUS[self.base.current_menu]):
            prefix = "> " if i == self.base.current_selection else "  "
            print(f"{prefix}{name}")
            
    def display_dictaphone_menu(self):
        """Отображение меню диктофона"""
        os.system("clear")
        print(f"=== {menu_name_for_audio(self.base.current_menu)} ===")
        
        for i, (name, _) in enumerate(MENUS[self.base.current_menu]):
            prefix = "> " if i == self.base.current_selection else "  "
            print(f"{prefix}{name}")
            
    def display_call_menu(self):
        """Отображение меню звонков"""
        os.system("clear")
        print(f"=== {menu_name_for_audio(self.base.current_menu)} ===")
        
        for i, (name, _) in enumerate(MENUS[self.base.current_menu]):
            prefix = "> " if i == self.base.current_selection else "  "
            print(f"{prefix}{name}")
            
    def display_radio_menu(self):
        """Отображение меню радио"""
        os.system("clear")
        print(f"=== {menu_name_for_audio(self.base.current_menu)} ===")
        
        for i, (name, _) in enumerate(MENUS[self.base.current_menu]):
            prefix = "> " if i == self.base.current_selection else "  "
            print(f"{prefix}{name}")
            
    def display_records_menu(self):
        """Отображение меню записей"""
        os.system("clear")
        print("=== Записи ===")
        
        if not self.base.records_list:
            print("Нет записей")
            return
            
        for i, record in enumerate(self.base.records_list):
            prefix = "> " if i == self.base.current_selection else "  "
            print(f"{prefix}{record}")
            
    def display_delete_records_menu(self):
        """Отображение меню удаления записей"""
        os.system("clear")
        print("=== Удаление записей ===")
        
        if not self.base.records_list:
            print("Нет записей")
            return
            
        for i, record in enumerate(self.base.records_list):
            prefix = "> " if i == self.base.current_selection else "  "
            print(f"{prefix}{record}")
    
    def display_confirm_delete_menu(self):
        """Отображение меню подтверждения удаления"""
        os.system("clear")
        print("=== Подтвердите удаление ===")
        print(f"Файл: {self.base.selected_record_to_delete}")
        print("")
        
        for i, (name, _) in enumerate(MENUS["CONFIRM_DELETE_MENU"]):
            prefix = "> " if i == self.base.current_selection else "  "
            print(f"{prefix}{name}")
            
    def display_recording_screen(self):
        """Отображает экран записи"""
        os.system("clear")
        print("=== ЗАПИСЬ ===")
        
        if self.base.recording_manager.current_record_filename:
            print(f"Текущий файл: {self.base.recording_manager.current_record_filename}")
        
        # Показываем время записи (placeholder, нужна реальная реализация)
        print("Время записи: 00:00")
        
        # Показываем статус записи
        status = "ПАУЗА" if self.base.recording_manager.is_paused else "ЗАПИСЬ"
        print(f"Статус: {status}")
        
        print("\nУправление:")
        print("OK - Пауза/Продолжить")
        print("BACK - Остановить и выйти")

    def display_playback_screen(self):
        """Отображение экрана воспроизведения"""
        def update_screen():
            os.system("clear")
            print("=== Воспроизведение ===")
            print(f"Файл: {self.base.playback_manager.current_record_name}")
            
            duration = self.base.audio.total_duration
            position = self.base.audio.current_position
            
            if duration > 0:
                progress = int(position / duration * 20)
                progress_bar = "█" * progress + "░" * (20 - progress)
                print(f"Прогресс: [{progress_bar}] {position:.1f}s / {duration:.1f}s")
            
            volume = self.base.audio.volume
            print(f"Громкость: {volume}%")
            
            speed = self.base.audio.speed
            print(f"Скорость: {speed:.1f}x")
            print("")
            
            if self.base.playback_manager.is_paused:
                state = "Пауза"
            else:
                state = "Воспроизведение"
                
            print(f"Статус: {state}")
            print("")
            print("F1 - Пауза/Продолжить")
            print("F2 - Остановить")
            print("POWER - Удалить")
            print("LEFT - Перемотка назад")
            print("RIGHT - Перемотка вперед")
            print("UP - Увеличить громкость")
            print("DOWN - Уменьшить громкость")
            
        update_screen()
        
        # Запускаем обновление экрана в отдельном потоке
        if hasattr(self, "_update_thread") and self._update_thread.is_alive():
            self._update_thread_stop = True
            self._update_thread.join()
            
        self._update_thread_stop = False
        self._update_thread = threading.Thread(target=self._update_loop, args=(update_screen,))
        self._update_thread.daemon = True
        self._update_thread.start()
    
    def _update_loop(self, update_func):
        """Цикл обновления экрана воспроизведения"""
        while not getattr(self, "_update_thread_stop", False):
            update_func()
            time.sleep(0.5)

    def display_calendar_year_menu(self):
        """Отображение меню выбора года в календаре"""
        os.system("clear")
        print("=== Выбор года ===")
        
        if not self.base.calendar_manager.calendar_years:
            print("Нет доступных записей в календаре")
            return
            
        for i, year in enumerate(self.base.calendar_manager.calendar_years):
            prefix = "> " if i == self.base.current_selection else "  "
            print(f"{prefix}{year}")
    
    def display_calendar_month_menu(self):
        """Отображение меню выбора месяца в календаре"""
        os.system("clear")
        print(f"=== Выбор месяца {self.base.calendar_manager.current_year} ===")
        
        if not self.base.calendar_manager.calendar_months:
            print("Нет доступных месяцев")
            return
            
        for i, month in enumerate(self.base.calendar_manager.calendar_months):
            prefix = "> " if i == self.base.current_selection else "  "
            month_name = MONTH_TO_SOUND[month].capitalize()
            print(f"{prefix}{month_name}")
    
    def display_calendar_day_menu(self):
        """Отображение меню выбора дня в календаре"""
        os.system("clear")
        print(f"=== Выбор дня {self.base.calendar_manager.current_year}-{self.base.calendar_manager.current_month} ===")
        
        if not self.base.calendar_manager.calendar_days:
            print("Нет доступных дней")
            return
            
        for i, day in enumerate(self.base.calendar_manager.calendar_days):
            prefix = "> " if i == self.base.current_selection else "  "
            print(f"{prefix}{day}")
            
    def get_record_files(self):
        """Получает список файлов записей в формате WAV"""
        records = []
        
        try:
            for file in os.listdir(RECORDS_BASE_DIR):
                if file.endswith(".wav"):
                    # Добавляем полный путь к файлу
                    records.append(os.path.join(RECORDS_BASE_DIR, file))
        except Exception as e:
            print(f"Ошибка при получении списка записей: {e}")
            
        return records


class NavigationManager:
    def __init__(self, base_manager):
        self.base = base_manager
    
    def move_up(self):
        """Перемещение вверх по меню"""
        if self.base.current_menu == "PLAYBACK_SCREEN":
            self.base.audio.volume_up()
            self.base.display_current_screen()
            return
            
        if self.base.in_play_mode:
            return
            
        # Сначала останавливаем текущий звук
        self.base.audio.stop_current_sound()
            
        if self.base.current_menu in ["RECORDS_MENU", "DELETE_RECORDS_MENU"]:
            if self.base.records_list:
                self.base.current_selection = (self.base.current_selection - 1) % len(self.base.records_list)
                self.base.display_current_screen()
                # Озвучиваем номер записи
                self.base.audio.play_sound(str(self.base.current_selection+1))
            return
        elif self.base.current_menu == "CONFIRM_DELETE_MENU":
            menu_items = MENUS["CONFIRM_DELETE_MENU"]
            self.base.current_selection = (self.base.current_selection - 1) % len(menu_items)
            self.base.display_current_screen()
            self.base.play_menu_sound()
            return
        elif self.base.current_menu == "CALENDAR_YEAR_MENU":
            if self.base.calendar_manager.calendar_years:
                self.base.current_selection = (self.base.current_selection - 1) % len(self.base.calendar_manager.calendar_years)
                self.base.display_current_screen()
                year = self.base.calendar_manager.calendar_years[self.base.current_selection]
                self.base.audio.play_sound(f"{year}-year")
            return
        elif self.base.current_menu == "CALENDAR_MONTH_MENU":
            if self.base.calendar_manager.calendar_months:
                self.base.current_selection = (self.base.current_selection - 1) % len(self.base.calendar_manager.calendar_months)
                self.base.display_current_screen()
                month = self.base.calendar_manager.calendar_months[self.base.current_selection]
                self.base.audio.play_sound(MONTH_TO_SOUND[month])
            return
        elif self.base.current_menu == "CALENDAR_DAY_MENU":
            if self.base.calendar_manager.calendar_days:
                self.base.current_selection = (self.base.current_selection - 1) % len(self.base.calendar_manager.calendar_days)
                self.base.display_current_screen()
                day = self.base.calendar_manager.calendar_days[self.base.current_selection]
                self.base.audio.play_sound_sequence_async([f"{day}e", f"{MONTH_TO_SOUND[self.base.calendar_manager.current_month]}a"])
            return
        else:
            # Для стандартных меню
            current_menu = MENUS.get(self.base.current_menu, [])
            if current_menu:
                self.base.current_selection = (self.base.current_selection - 1) % len(current_menu)
                self.base.display_current_screen()
                self.base.play_menu_sound()
    
    def move_down(self):
        """Перемещение вниз по меню"""
        if self.base.current_menu == "PLAYBACK_SCREEN":
            self.base.audio.volume_down()
            self.base.display_current_screen()
            return
            
        if self.base.in_play_mode:
            return
            
        # Сначала останавливаем текущий звук
        self.base.audio.stop_current_sound()
        
        if self.base.current_menu in ["RECORDS_MENU", "DELETE_RECORDS_MENU"]:
            if self.base.records_list:
                self.base.current_selection = (self.base.current_selection + 1) % len(self.base.records_list)
                self.base.display_current_screen()
                # Озвучиваем номер записи
                self.base.audio.play_sound(str(self.base.current_selection+1))
            return
        elif self.base.current_menu == "CONFIRM_DELETE_MENU":
            menu_items = MENUS["CONFIRM_DELETE_MENU"]
            self.base.current_selection = (self.base.current_selection + 1) % len(menu_items)
            self.base.display_current_screen()
            self.base.play_menu_sound()
            return
        elif self.base.current_menu == "CALENDAR_YEAR_MENU":
            if self.base.calendar_manager.calendar_years:
                self.base.current_selection = (self.base.current_selection + 1) % len(self.base.calendar_manager.calendar_years)
                self.base.display_current_screen()
                year = self.base.calendar_manager.calendar_years[self.base.current_selection]
                self.base.audio.play_sound(f"{year}-year")
            return
        elif self.base.current_menu == "CALENDAR_MONTH_MENU":
            if self.base.calendar_manager.calendar_months:
                self.base.current_selection = (self.base.current_selection + 1) % len(self.base.calendar_manager.calendar_months)
                self.base.display_current_screen()
                month = self.base.calendar_manager.calendar_months[self.base.current_selection]
                self.base.audio.play_sound(MONTH_TO_SOUND[month])
            return
        elif self.base.current_menu == "CALENDAR_DAY_MENU":
            if self.base.calendar_manager.calendar_days:
                self.base.current_selection = (self.base.current_selection + 1) % len(self.base.calendar_manager.calendar_days)
                self.base.display_current_screen()
                day = self.base.calendar_manager.calendar_days[self.base.current_selection]
                self.base.audio.play_sound_sequence_async([f"{day}e", f"{MONTH_TO_SOUND[self.base.calendar_manager.current_month]}a"])
            return
        else:
            # Для стандартных меню
            current_menu = MENUS.get(self.base.current_menu, [])
            if current_menu:
                self.base.current_selection = (self.base.current_selection + 1) % len(current_menu)
                self.base.display_current_screen()
                self.base.play_menu_sound()
    
    def enter_selection(self):
        """Обработка выбора текущего пункта меню"""
        if self.base.in_play_mode:
            return

        if self.base.current_menu == "MAIN_MENU":
            if self.base.current_selection == 0:  # Dictaphone Mode
                # Сохраняем предыдущее меню в стек
                self.base.parent_menu_stack.append(self.base.current_menu)
                self.base.current_menu = "DICTAPHONE_MENU"
                self.base.current_selection = 0
                # Сначала проигрываем звук входа, затем звук режима
                self.base.audio.play_sound_sequence_async(["entering-2", "dictaphone-mode"])
                self.base.display_current_screen()
            elif self.base.current_selection == 1:  # Call Mode
                # Сохраняем предыдущее меню в стек
                self.base.parent_menu_stack.append(self.base.current_menu)
                self.base.current_menu = "CALL_MENU"
                self.base.current_selection = 0
                # Сначала проигрываем звук входа, затем звук режима
                self.base.audio.play_sound_sequence_async(["entering-2", "call-mode"])
                self.base.display_current_screen()
            elif self.base.current_selection == 2:  # Radio Mode
                # Сохраняем предыдущее меню в стек
                self.base.parent_menu_stack.append(self.base.current_menu)
                self.base.current_menu = "RADIO_MENU"
                self.base.current_selection = 0
                # Сначала проигрываем звук входа, затем звук режима
                self.base.audio.play_sound_sequence_async(["entering-2", "radio-mode"])
                self.base.display_current_screen()
        elif self.base.current_menu == "DICTAPHONE_MENU":
            if self.base.current_selection == 0:  # Создать запись
                # Запуск записи
                self.base.parent_menu_stack.append(self.base.current_menu)  # Сохраняем меню диктофона в стек
                self.base.current_menu = "RECORDING_SCREEN"
                self.base.audio.play_sound_sequence_async(["entering-2", "creating-new-record"])
                # Обновляем экран перед началом записи
                self.base.display_current_screen()
                # Запускаем запись после небольшой задержки
                threading.Timer(3.0, self.base.recording_manager.start_recording).start()
            elif self.base.current_selection == 1:  # Calendar
                # Инициализируем и переходим к меню календаря
                self.base.calendar_manager.initialize_calendar_years()
                if self.base.calendar_manager.calendar_years:
                    # Сохраняем предыдущее меню в стек
                    self.base.parent_menu_stack.append(self.base.current_menu)
                    self.base.current_menu = "CALENDAR_YEAR_MENU"
                    self.base.current_selection = 0
                    # Сначала проигрываем звук входа, затем звук режима
                    self.base.audio.play_sound_sequence_async(["entering-2", "calendar"])
                    self.base.display_current_screen()
                else:
                    self.base.audio.play_sound("no-records")
            elif self.base.current_selection == 2:  # Play Records
                # Загружаем записи и переходим к их списку
                self.base.records_list = self.base.display_manager.get_record_files()
                if self.base.records_list:
                    # Сохраняем предыдущее меню в стек
                    self.base.parent_menu_stack.append(self.base.current_menu)
                    self.base.current_menu = "RECORDS_MENU"
                    self.base.current_selection = 0
                    # Сначала проигрываем звук входа, затем звук режима
                    self.base.audio.play_sound_sequence_async(["entering-2", "play-existing"])
                    self.base.display_current_screen()
                    # Озвучиваем первую запись
                    self.base.audio.play_sound("1")
                else:
                    self.base.audio.play_sound("no-records")
            elif self.base.current_selection == 3:  # Delete Records
                # Загружаем записи и переходим к меню удаления
                self.base.records_list = self.base.display_manager.get_record_files()
                if self.base.records_list:
                    # Сохраняем предыдущее меню в стек
                    self.base.parent_menu_stack.append(self.base.current_menu)
                    self.base.current_menu = "DELETE_RECORDS_MENU"
                    self.base.current_selection = 0
                    # Сначала проигрываем звук входа, затем звук режима
                    self.base.audio.play_sound_sequence_async(["entering-2", "want-to-delete"])
                    self.base.display_current_screen()
                    # Озвучиваем первую запись
                    self.base.audio.play_sound("1")
                else:
                    self.base.audio.play_sound("no-records")
        elif self.base.current_menu == "CALL_MENU":
            # Обработка пунктов меню звонков
            # Сначала проигрываем звук входа, затем звук режима
            self.base.audio.play_sound_sequence_async(["entering-2", "menu-select"])
            # TODO: Реализовать функциональность для режима звонков
        elif self.base.current_menu == "RADIO_MENU":
            # Обработка пунктов меню радио
            # Сначала проигрываем звук входа, затем звук режима
            self.base.audio.play_sound_sequence_async(["entering-2", "menu-select"])
            # TODO: Реализовать функциональность для режима радио
        elif self.base.current_menu == "RECORDS_MENU":
            if self.base.records_list:
                # Воспроизводим выбранную запись
                self.base.playback_manager.play_selected_record()
        elif self.base.current_menu == "DELETE_RECORDS_MENU":
            if self.base.records_list:
                # Переходим к подтверждению удаления
                # Сохраняем предыдущее меню в стек
                self.base.parent_menu_stack.append(self.base.current_menu)
                self.base.current_menu = "CONFIRM_DELETE_MENU"
                self.base.current_selection = 0
                # Сначала проигрываем звук входа, затем звук режима
                self.base.audio.play_sound_sequence_async(["entering-2", "want-to-delete"])
                self.base.display_current_screen()
        elif self.base.current_menu == "CONFIRM_DELETE_MENU":
            if self.base.current_selection == 0:  # Нет
                # Возвращаемся к списку записей
                if self.base.parent_menu_stack:
                    self.base.current_menu = self.base.parent_menu_stack.pop()
                    self.base.current_selection = 0
                    self.base.audio.play_sound("menu-select")
                    self.base.display_current_screen()
            elif self.base.current_selection == 1:  # Да
                # Удаляем выбранную запись
                if self.base.records_list:
                    record_to_delete = self.base.records_list[self.base.current_selection]
                    try:
                        os.remove(record_to_delete)
                        self.base.audio.play_sound("record-deleted")
                    except Exception as e:
                        print(f"Ошибка при удалении записи: {e}")
                        self.base.audio.play_sound("error")
                    # Обновляем список записей
                    self.base.records_list = self.base.display_manager.get_record_files()
                    if self.base.records_list:
                        # Возвращаемся к списку записей
                        if self.base.parent_menu_stack:
                            self.base.current_menu = self.base.parent_menu_stack.pop()
                            self.base.current_selection = 0
                    else:
                        # Если записей не осталось, возвращаемся в меню диктофона
                        self.base.current_menu = "DICTAPHONE_MENU"
                        self.base.current_selection = 3
                        self.base.audio.play_sound("no-records")
                    self.base.display_current_screen()
        elif self.base.current_menu == "CALENDAR_YEAR_MENU":
            if self.base.calendar_manager.calendar_years:
                # Выбираем год и переходим к месяцам
                self.base.calendar_manager.select_year(self.base.current_selection)
                if self.base.calendar_manager.calendar_months:
                    # Сохраняем предыдущее меню в стек
                    self.base.parent_menu_stack.append(self.base.current_menu)
                    self.base.current_menu = "CALENDAR_MONTH_MENU"
                    self.base.current_selection = 0
                    # Сначала проигрываем звук входа, затем звук режима
                    month = self.base.calendar_manager.calendar_months[0]
                    self.base.audio.play_sound_sequence_async(["entering-2", MONTH_TO_SOUND[month]])
                    self.base.display_current_screen()
                else:
                    self.base.audio.play_sound("no-records")
        elif self.base.current_menu == "CALENDAR_MONTH_MENU":
            if self.base.calendar_manager.calendar_months:
                # Выбираем месяц и переходим к дням
                self.base.calendar_manager.select_month(self.base.current_selection)
                if self.base.calendar_manager.calendar_days:
                    # Сохраняем предыдущее меню в стек
                    self.base.parent_menu_stack.append(self.base.current_menu)
                    self.base.current_menu = "CALENDAR_DAY_MENU"
                    self.base.current_selection = 0
                    # Сначала проигрываем звук входа, затем звук режима
                    day = self.base.calendar_manager.calendar_days[0]
                    self.base.audio.play_sound_sequence_async(["entering-2", f"{day}e", f"{MONTH_TO_SOUND[self.base.calendar_manager.current_month]}a"])
                    self.base.display_current_screen()
                else:
                    self.base.audio.play_sound("no-records")
            else:
                self.base.audio.play_sound("no-records")
        elif self.base.current_menu == "CALENDAR_DAY_MENU":
            if self.base.calendar_manager.calendar_days:
                # Выбираем день и загружаем записи за этот день
                day = self.base.calendar_manager.select_day(self.base.current_selection)
                self.base.records_list = self.base.calendar_manager.get_records_for_date()
                if self.base.records_list:
                    # Сохраняем предыдущее меню в стек
                    self.base.parent_menu_stack.append(self.base.current_menu)
                    self.base.current_menu = "RECORDS_MENU"
                    self.base.current_selection = 0
                    # Отмечаем, что мы находимся в календарном просмотре
                    self.base.is_calendar_playback = True
                    # Сначала проигрываем звук входа, затем звук режима
                    self.base.audio.play_sound_sequence_async(["entering-2", "play-existing"])
                    self.base.display_current_screen()
                    # Озвучиваем первую запись
                    self.base.audio.play_sound("1")
                else:
                    self.base.audio.play_sound("no-records")
        else:
            # Обработка стандартных меню
            if self.base.current_menu in MENUS:
                menu_items = MENUS[self.base.current_menu]
                if self.base.current_selection < len(menu_items):
                    item_id = menu_items[self.base.current_selection][1]
                    
                    if item_id == "DICTAPHONE_MODE":
                        # Сохраняем текущее меню в стек
                        self.base.parent_menu_stack.append(self.base.current_menu)
                        self.base.current_menu = "DICTAPHONE_MENU"
                        self.base.current_selection = 0
                        # Сначала проигрываем звук входа, затем звук режима
                        self.base.audio.play_sound_sequence_async(["entering-2", "dictaphone-mode"])
                    elif item_id == "CALL_MENU":
                        # Сохраняем текущее меню в стек
                        self.base.parent_menu_stack.append(self.base.current_menu)
                        self.base.current_menu = "CALL_MENU"
                        self.base.current_selection = 0
                        # Сначала проигрываем звук входа, затем звук режима
                        self.base.audio.play_sound_sequence_async(["entering-2", "call-mode"])
                    elif item_id == "RADIO_MENU":
                        # Сохраняем текущее меню в стек
                        self.base.parent_menu_stack.append(self.base.current_menu)
                        self.base.current_menu = "RADIO_MENU"
                        self.base.current_selection = 0
                        # Сначала проигрываем звук входа, затем звук режима
                        self.base.audio.play_sound_sequence_async(["entering-2", "radio-mode"])
                    
                    self.base.display_current_screen()
    
    def go_back(self):
        """Возврат в предыдущее меню"""
        if self.base.in_play_mode or len(self.base.parent_menu_stack) == 0:
            return
            
        # Сбрасываем признак календаря, если мы возвращаемся из просмотра записей календаря
        if self.base.is_calendar_playback and self.base.current_menu == "RECORDS_MENU":
            self.base.is_calendar_playback = False
            
        self.base.current_menu = self.base.parent_menu_stack.pop()
        self.base.current_selection = 0
        self.base.audio.play_sound("menu-back")
        self.base.display_current_screen()
    
    def exit_to_parent_menu(self):
        """Выход в родительское меню"""
        if not self.base.parent_menu_stack:
            return
            
        self.base.current_menu = self.base.parent_menu_stack.pop()
        self.base.current_selection = 0
        self.base.audio.play_sound("menu-back")
        self.base.display_current_screen()


class PlaybackManager:
    """Класс для управления воспроизведением звука"""
    def __init__(self, base_manager):
        self.base = base_manager
        self.is_playing = False
        self.is_paused = False
        self.current_record_name = None
        self.current_position = 0
        self.total_duration = 0

    def play_selected_record(self):
        """Воспроизводит выбранную запись"""
        if not self.base.records_list:
            return
            
        # Получаем путь к выбранной записи
        selected_record = self.base.records_list[self.base.current_selection]
        self.current_record_name = os.path.basename(selected_record)
        
        # Переходим в режим воспроизведения
        self.base.in_play_mode = True
        self.base.current_menu = "PLAYBACK_SCREEN"
        self.is_playing = True
        self.is_paused = False
        
        # Отображаем экран воспроизведения
        self.base.display_current_screen()
        
        # Проигрываем звуковое сообщение и начинаем воспроизведение
        self.base.audio.play_sound_sequence_async(["play-mode"])
        
        # Функция, которая будет вызвана после завершения воспроизведения
        def playback_complete():
            self.is_playing = False
            self.base.in_play_mode = False
            self.base.current_menu = "RECORDS_MENU"
            self.base.display_current_screen()
        
        # Запускаем воспроизведение с задержкой
        def delayed_start():
            time.sleep(1)  # Даем время для проигрывания звукового сообщения
            # Начинаем воспроизведение
            self.base.audio.start_playback(selected_record, playback_complete)
        
        # Запускаем воспроизведение в отдельном потоке
        threading.Thread(target=delayed_start).start()

    def pause_resume_playback(self):
        """Приостанавливает или возобновляет воспроизведение"""
        if not self.is_playing:
            return
            
        if self.is_paused:
            # Возобновляем воспроизведение
            self.is_paused = False
            self.base.audio.toggle_pause()
            self.base.audio.play_sound_sequence_async(["play-will-continue-in-321"])
        else:
            # Приостанавливаем воспроизведение
            self.is_paused = True
            self.base.audio.toggle_pause()
            self.base.audio.play_sound("playback-paused")
        
        # Обновляем отображение
        self.base.display_current_screen()

    def stop_playback_return(self):
        """Останавливает воспроизведение и возвращается в предыдущее меню"""
        if not self.is_playing:
            return
            
        # Останавливаем воспроизведение
        self.is_playing = False
        self.is_paused = False
        self.base.audio.stop_playback()
        
        # Возвращаемся в меню записей
        self.base.in_play_mode = False
        self.base.current_menu = "RECORDS_MENU"
        self.base.display_current_screen()

    def request_delete_during_playback(self):
        """Запрос на удаление во время воспроизведения"""
        if not self.is_playing:
            return
            
        # Приостанавливаем воспроизведение
        self.is_paused = True
        self.base.audio.toggle_pause()
        
        # Сохраняем текущую запись для удаления
        selected_record = self.base.records_list[self.base.current_selection]
        self.base.selected_record_to_delete = selected_record
        
        # Переходим к меню подтверждения удаления
        self.base.current_menu = "CONFIRM_DELETE_MENU"
        self.base.current_selection = 0
        self.base.audio.play_sound_sequence_async(["entering-2", "want-to-delete"])
        self.base.display_current_screen()

    def toggle_pause_playback(self):
        """Переключение паузы воспроизведения"""
        if not self.is_playing:
            return
            
        self.is_paused = not self.is_paused
        self.base.audio.toggle_pause()
        self.base.display_current_screen()


class RecordingManager:
    """Класс для управления записью звука"""
    def __init__(self, base_manager):
        self.base = base_manager
        self.is_recording = False
        self.is_paused = False
        self.current_record_filename = None

    def start_recording(self):
        """Запускает процесс записи звука"""
        # Останавливаем текущий звук
        self.base.audio.stop_current_sound()
        
        # Формируем имя для новой записи (timestamp)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_record_filename = f"{timestamp}.wav"
        
        # Полный путь к файлу записи
        record_path = os.path.join(RECORDS_BASE_DIR, self.current_record_filename)
        
        # Проигрываем звуковое сообщение о начале записи
        self.base.audio.play_sound_sequence_async(["record-will-start-in-321"])
        
        # Запускаем запись с небольшой задержкой
        def delayed_start():
            time.sleep(3)  # Задержка для проигрывания звукового сообщения
            self.is_recording = True
            self.is_paused = False
            
            # Здесь должен быть код для запуска записи через sounddevice или другую библиотеку
            # Пример (заглушка):
            print(f"Начало записи в файл: {record_path}")
            
            # Отображаем экран записи
            self.base.display_current_screen()
            
            # Проигрываем звук начала записи
            self.base.audio.play_sound("recording-started")
            
        # Запускаем отложенный старт записи в отдельном потоке
        threading.Thread(target=delayed_start).start()

    def pause_resume_recording(self):
        """Приостанавливает или возобновляет запись"""
        if not self.is_recording:
            return
            
        if self.is_paused:
            # Возобновляем запись
            self.is_paused = False
            self.base.audio.play_sound_sequence_async(["record-will-continue-in-321"])
            # Здесь должен быть код для возобновления записи
            print("Возобновление записи")
        else:
            # Приостанавливаем запись
            self.is_paused = True
            self.base.audio.play_sound("record-is-on-pause")
            # Здесь должен быть код для приостановки записи
            print("Приостановка записи")
                
        # Обновляем отображение
        self.base.display_current_screen()

    def stop_recording_return(self):
        """Останавливает запись и возвращается в предыдущее меню"""
        if self.is_recording:
            # Останавливаем запись
            self.is_recording = False
            self.is_paused = False
            
            # Здесь должен быть код для остановки записи и сохранения файла
            print(f"Запись остановлена, файл сохранен: {self.current_record_filename}")
            
            # Проигрываем звуковое сообщение
            self.base.audio.play_sound("record-created-and-saved")
            
            # Возвращаемся в меню диктофона
            if self.base.parent_menu_stack:
                self.base.current_menu = self.base.parent_menu_stack.pop()
            else:
                self.base.current_menu = "DICTAPHONE_MENU"
                
            self.base.current_selection = 0
            self.base.display_current_screen()


class CalendarManager:
    """Класс для управления функциональностью календаря"""
    def __init__(self, base_manager):
        self.base = base_manager
        self.calendar_years = []
        self.calendar_months = []
        self.calendar_days = []
        self.current_year = None
        self.current_month = None
        self.current_day = None
        
    def initialize_calendar_years(self):
        """Инициализирует список доступных лет в календаре"""
        # Получаем текущий год
        current_date = datetime.now()
        self.calendar_years = [current_date.year]  # Пока только текущий год
        
    def select_year(self, selection_index):
        """Выбираем год и инициализируем список месяцев"""
        if self.calendar_years:
            self.current_year = self.calendar_years[selection_index]
            # Получаем список доступных месяцев для выбранного года
            self._initialize_calendar_months()
            return self.current_year
        return None
        
    def select_month(self, selection_index):
        """Выбираем месяц и инициализируем список дней"""
        if self.calendar_months:
            self.current_month = self.calendar_months[selection_index]
            # Получаем список доступных дней для выбранного месяца
            self._initialize_calendar_days()
            return self.current_month
        return None
        
    def select_day(self, selection_index):
        """Выбираем день"""
        if self.calendar_days:
            self.current_day = self.calendar_days[selection_index]
            return self.current_day
        return None
        
    def _initialize_calendar_months(self):
        """Инициализирует список доступных месяцев"""
        # Для демонстрации используем все месяцы
        self.calendar_months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
        
    def _initialize_calendar_days(self):
        """Инициализирует список доступных дней для выбранного месяца и года"""
        if self.current_year and self.current_month:
            # Получаем последний день месяца
            last_day = calendar.monthrange(self.current_year, self.current_month)[1]
            self.calendar_days = list(range(1, last_day + 1))
        else:
            self.calendar_days = []
            
    def get_records_for_date(self):
        """Возвращает список записей для выбранной даты"""
        if not (self.current_year and self.current_month and self.current_day):
            return []
            
        # Формируем путь к папке с записями для этой даты
        date_folder = f"{self.current_year}_{self.current_month}_{self.current_day}"
        
        # Путь к папке с записями
        folder_path = os.path.join(RECORDS_BASE_DIR, date_folder)
        
        # Проверяем, существует ли такая папка
        if not os.path.exists(folder_path):
            # Если нет, создаем её
            try:
                os.makedirs(folder_path)
            except Exception as e:
                print(f"Ошибка при создании папки: {e}")
                return []
                
        # Получаем список записей
        records = []
        try:
            for file in os.listdir(folder_path):
                if file.endswith(".wav"):
                    # Добавляем полный путь к файлу
                    records.append(os.path.join(folder_path, file))
        except Exception as e:
            print(f"Ошибка при получении списка записей: {e}")
            
        return records


class MenuManager(BaseMenuManager):
    """Класс-обертка для обратной совместимости"""
    pass
    
def find_remote_device():
    devices = [InputDevice(path) for path in list_devices()]
    for dev in devices:
        if dev.name == TARGET_DEVICE_NAME:
            return dev.path
    return None

def main():
    device_path = find_remote_device()
    if device_path is None:
        print("Ошибка: USB пульт не найден")
        sys.exit(1)
    else:
        print("Найдено устройство:", device_path)

    dev = InputDevice(device_path)
    audio = AudioPlayer()
    recorder = Recorder()
    menu = MenuManager(audio, recorder)

    menu.display_current_screen()
    audio.play_sound_sequence_async(["start", "dictaphone-mode"])

    key_states = {
        KEY_LEFT: False,
        KEY_RIGHT: False
    }

    for event in dev.read_loop():
        if event.type == ecodes.EV_KEY:
            key_code = event.code
            key_value = event.value
            if key_value == 1:
                audio.stop_current_sound()
                if key_code == KEY_POWER and menu.in_play_mode:
                    menu.request_delete_during_playback()
                elif key_code == KEY_UP:
                    menu.move_up()
                elif key_code == KEY_DOWN:
                    menu.move_down()
                elif key_code == KEY_VOLUMEUP and menu.in_play_mode:
                    audio.volume_up()
                elif key_code == KEY_VOLUMEDOWN and menu.in_play_mode:
                    audio.volume_down()
                elif key_code == KEY_SELECT:
                    if menu.current_menu == "CONFIRM_DELETE_MENU":
                        # Если мы в меню подтверждения, обрабатываем выбор
                        menu.enter_selection()
                    elif menu.in_play_mode:
                        # Иначе обрабатываем как паузу/воспроизведение
                        menu.pause_resume_playback()
                    elif recorder.recording_in_progress:
                        menu.pause_resume_recording()
                    else:
                        menu.enter_selection()
                elif key_code == KEY_BACK:
                    if menu.in_play_mode:
                        menu.stop_playback_return()
                    elif recorder.recording_in_progress:
                        menu.stop_recording_return()
                    else:
                        menu.go_back()
                elif key_code == KEY_RIGHT:
                    if not key_states[KEY_RIGHT]:
                        key_states[KEY_RIGHT] = True
                        audio.start_right_fast_forward()
                elif key_code == KEY_LEFT:
                    if not key_states[KEY_LEFT]:
                        key_states[KEY_LEFT] = True
                        audio.start_left_rewind()

            elif key_value == 0:
                if key_code == KEY_RIGHT:
                    if key_states[KEY_RIGHT]:
                        key_states[KEY_RIGHT] = False
                        audio.stop_right_fast_forward()
                elif key_code == KEY_LEFT:
                    if key_states[KEY_LEFT]:
                        key_states[KEY_LEFT] = False
                        audio.stop_left_rewind()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Завершение работы...")
