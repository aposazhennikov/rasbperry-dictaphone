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
    return MENU_NAMES.get(menu, "main-menu")

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

MENUS = {
    "MAIN_MENU": [
        ("Режим диктофона", "DICTAPHONE_MENU"),
        ("Режим звонка", "CALL_MENU"),
        ("Режим управления радио", "RADIO_MENU")
    ],
    "DICTAPHONE_MENU": [
        ("Создать новую запись", "FOLDER_SELECT_RECORD"),
        ("Календарь", "FOLDER_SELECT_CALENDAR"),
        ("Воспроизвести уже имеющуюся запись", "FOLDER_SELECT_PLAY"),
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

class MenuManager:
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
        self.calendar_years = []
        self.calendar_months = []
        self.calendar_days = []
        self.current_year = None
        self.current_month = None
        self.is_calendar_playback = False

    def display_current_screen(self):
        """Отображение текущего экрана"""
        if self.current_menu == "RECORDS_MENU":
            self.display_records_menu()
        elif self.current_menu == "DELETE_RECORDS_MENU":
            self.display_delete_records_menu()
        elif self.current_menu == "CONFIRM_DELETE_MENU":
            self.display_confirm_delete_menu()
        elif self.current_menu == "CALENDAR_YEAR_MENU":
            self.display_calendar_year_menu()
        elif self.current_menu == "CALENDAR_MONTH_MENU":
            self.display_calendar_month_menu()
        elif self.current_menu == "CALENDAR_DAY_MENU":
            self.display_calendar_day_menu()
        else:
            self.display_menu()

    def display_menu(self):
        os.system("clear")
        menu_items = MENUS.get(self.current_menu, [])
        print("Меню: ", self.current_menu)
        for i, (title, _) in enumerate(menu_items):
            prefix = " > " if i == self.current_selection else "   "
            print(prefix + title)

    def display_confirm_delete_menu(self):
        """Отображение меню подтверждения удаления"""
        os.system("clear")
        filename = self.selected_record_to_delete.split('(')[0].strip()
        file_path = os.path.join(RECORDS_BASE_DIR, self.choosen_folder, filename)
        print("Удаление композиции:", file_path)
        print("Точно хотите удалить?\n")
        menu_items = MENUS["CONFIRM_DELETE_MENU"]
        for i, (title, _) in enumerate(menu_items):
            prefix = " > " if i == self.current_selection else "   "
            print(prefix + title)

    def display_records_menu(self):
        os.system("clear")
        print("Список записей (Воспроизведение):")
        if not self.records_list:
            print("Нет записей.")
        else:
            for i, rec in enumerate(self.records_list):
                prefix = " > " if i == self.current_selection else "   "
                print(f"{prefix}{i+1}. {rec}")

    def display_delete_records_menu(self):
        os.system("clear")
        print("Список записей (Удаление):")
        if not self.records_list:
            print("Нет записей.")
        else:
            for i, rec in enumerate(self.records_list):
                prefix = " > " if i == self.current_selection else "   "
                print(f"{prefix}{i+1}. {rec}")
            if self.records_list:
                print(f"\nСейчас я на композиции: {self.records_list[self.current_selection]}")

    def go_back(self):
        self.audio.stop_current_sound()
        if self.current_menu == "DELETE_RECORDS_MENU":
            # При возврате из режима удаления - возвращаемся в режим диктофона
            self.audio.play_sound_sequence_async(["return-to", "dictaphone-mode"])
            # Ищем в стеке меню диктофона
            for i in range(len(self.parent_menu_stack)):
                if self.parent_menu_stack[i][0] == "DICTAPHONE_MENU":
                    # Очищаем стек до режима диктофона
                    while len(self.parent_menu_stack) > i:
                        self.parent_menu_stack.pop()
                    break
            self.current_menu = "DICTAPHONE_MENU"
            self.current_selection = 0
            self.display_current_screen()
            return
        elif self.current_menu == "RECORDS_MENU" and self.parent_menu_stack and self.parent_menu_stack[-1][0] == "CALENDAR_DAY_MENU":
            # Обновляем структуру календаря перед возвратом
            self.calendar_structure = self.get_calendar_structure(self.choosen_folder)
            # Проверяем, остались ли записи в выбранный день
            current_day = self.calendar_days[self.parent_menu_stack[-1][1]]
            if current_day in self.calendar_structure[self.current_year][self.current_month]:
                # Возвращаемся к выбору дня
                prev = self.parent_menu_stack.pop()
                self.current_menu = prev[0]
                self.current_selection = prev[1]
                self.audio.play_sound_sequence_async(["return-to", f"{self.calendar_days[self.current_selection]}e"])
            else:
                # Если записей не осталось, возвращаемся к выбору месяца
                self.parent_menu_stack.pop()
                self.current_menu = "CALENDAR_MONTH_MENU"
                self.current_selection = 0
                self.audio.play_sound_sequence_async(["return-to", MONTH_TO_SOUND[self.calendar_months[0]]])
            self.display_current_screen()
        elif self.current_menu in ["FOLDER_SELECT_CALENDAR", "FOLDER_SELECT_PLAY", "FOLDER_SELECT_DELETE", "FOLDER_SELECT_RECORD"]:
            # При возврате из режима выбора папки
            self.audio.play_sound_sequence_async(["return-to", "dictaphone-mode"])
            if self.parent_menu_stack:
                prev = self.parent_menu_stack.pop()
                self.current_menu, self.current_selection = prev
            self.display_current_screen()
        else:
            if self.parent_menu_stack:
                prev = self.parent_menu_stack.pop()
                self.current_menu, self.current_selection = prev
                self.audio.play_sound_sequence_async(["return-to", menu_name_for_audio(self.current_menu)])
            else:
                self.current_menu = "MAIN_MENU"
                self.current_selection = 0
                self.audio.play_sound_sequence_async(["return-to", "main-menu"])
            self.display_current_screen()

    def play_menu_sound(self):
        if self.current_menu == "MAIN_MENU":
            if self.current_selection == 0:
                self.audio.play_sound("dictaphone-mode")
            elif self.current_selection == 1:
                self.audio.play_sound("call-mode")
            elif self.current_selection == 2:
                self.audio.play_sound("radio-mode")

        if self.current_menu == "DICTAPHONE_MENU":
            if self.current_selection == 0:
                self.audio.play_sound("create-new-record")
            elif self.current_selection == 1:
                self.audio.play_sound("calendar")
            elif self.current_selection == 2:
                self.audio.play_sound("play-existing-records")
            elif self.current_selection == 3:
                self.audio.play_sound("delete-record")

        if self.current_menu in ["FOLDER_SELECT_RECORD", "FOLDER_SELECT_PLAY", "FOLDER_SELECT_DELETE", "FOLDER_SELECT_CALENDAR"]:
            if self.current_selection == 0:
                self.audio.play_sound("folder-a")
            elif self.current_selection == 1:
                self.audio.play_sound("folder-b")
            elif self.current_selection == 2:
                self.audio.play_sound("folder-c")

        if self.current_menu == "CONFIRM_DELETE_MENU":
            if self.current_selection == 0:
                self.audio.play_sound("no")
            elif self.current_selection == 1:
                self.audio.play_sound("yes")

    def move_up(self):
        if self.current_menu in ["RECORDS_MENU", "DELETE_RECORDS_MENU"]:
            if self.records_list:
                self.current_selection = (self.current_selection - 1) % len(self.records_list)
            self.display_current_screen()
            self.audio.stop_current_sound()
            if self.records_list:
                self.audio.play_sound(str(self.current_selection+1))
        elif self.current_menu == "CONFIRM_DELETE_MENU":
            menu_items = MENUS["CONFIRM_DELETE_MENU"]
            self.current_selection = (self.current_selection - 1) % len(menu_items)
            self.display_current_screen()
            self.audio.stop_current_sound()
            self.play_menu_sound()
        elif self.current_menu == "CALENDAR_YEAR_MENU":
            if self.calendar_years:
                self.current_selection = (self.current_selection - 1) % len(self.calendar_years)
                self.display_current_screen()
                self.audio.play_sound(f"{self.calendar_years[self.current_selection]}-year")
        elif self.current_menu == "CALENDAR_MONTH_MENU":
            if self.calendar_months:
                self.current_selection = (self.current_selection - 1) % len(self.calendar_months)
                self.display_current_screen()
                self.audio.play_sound(MONTH_TO_SOUND[self.calendar_months[self.current_selection]])
        elif self.current_menu == "CALENDAR_DAY_MENU":
            if self.calendar_days:
                self.current_selection = (self.current_selection - 1) % len(self.calendar_days)
                self.display_current_screen()
                # Проигрываем число и месяц последовательно
                day = self.calendar_days[self.current_selection]
                self.audio.play_sound_sequence_async([f"{day}e", f"{MONTH_TO_SOUND[self.current_month]}a"])
        else:
            menu_items = MENUS.get(self.current_menu, [])
            if menu_items:
                self.current_selection = (self.current_selection - 1) % len(menu_items)
            self.display_current_screen()
            self.audio.stop_current_sound()
            self.play_menu_sound()

    def move_down(self):
        if self.current_menu in ["RECORDS_MENU", "DELETE_RECORDS_MENU"]:
            if self.records_list:
                self.current_selection = (self.current_selection + 1) % len(self.records_list)
            self.display_current_screen()
            self.audio.stop_current_sound()
            if self.records_list:
                self.audio.play_sound(str(self.current_selection+1))
        elif self.current_menu == "CONFIRM_DELETE_MENU":
            menu_items = MENUS["CONFIRM_DELETE_MENU"]
            self.current_selection = (self.current_selection + 1) % len(menu_items)
            self.display_current_screen()
            self.audio.stop_current_sound()
            self.play_menu_sound()
        elif self.current_menu == "CALENDAR_YEAR_MENU":
            if self.calendar_years:
                self.current_selection = (self.current_selection + 1) % len(self.calendar_years)
                self.display_current_screen()
                self.audio.play_sound(f"{self.calendar_years[self.current_selection]}-year")
        elif self.current_menu == "CALENDAR_MONTH_MENU":
            if self.calendar_months:
                self.current_selection = (self.current_selection + 1) % len(self.calendar_months)
                self.display_current_screen()
                self.audio.play_sound(MONTH_TO_SOUND[self.calendar_months[self.current_selection]])
        elif self.current_menu == "CALENDAR_DAY_MENU":
            if self.calendar_days:
                self.current_selection = (self.current_selection + 1) % len(self.calendar_days)
                self.display_current_screen()
                # Проигрываем число и месяц последовательно
                day = self.calendar_days[self.current_selection]
                self.audio.play_sound_sequence_async([f"{day}e", f"{MONTH_TO_SOUND[self.current_month]}a"])
        else:
            menu_items = MENUS.get(self.current_menu, [])
            if menu_items:
                self.current_selection = (self.current_selection + 1) % len(menu_items)
            self.display_current_screen()
            self.audio.stop_current_sound()
            self.play_menu_sound()

    def enter_selection(self):
        self.audio.stop_current_sound()

        # При входе в режим выбора папки
        if self.current_menu == "DICTAPHONE_MENU":
            if self.current_selection in [0, 1, 2, 3]:  # Для всех режимов, где нужно выбрать папку
                self.parent_menu_stack.append((self.current_menu, self.current_selection))
                
                # Выбираем правильное сообщение в зависимости от режима
                if self.current_selection == 0:  # Режим записи
                    self.audio.play_sound_sequence_async(["please-select-folder-for-record", "folder-a"])
                    self.current_menu = "FOLDER_SELECT_RECORD"
                elif self.current_selection == 1:  # Режим календаря
                    self.audio.play_sound_sequence_async(["please-select-folder-for-calendar", "folder-a"])
                    self.current_menu = "FOLDER_SELECT_CALENDAR"
                elif self.current_selection == 2:  # Режим воспроизведения
                    self.audio.play_sound_sequence_async(["please-select-folder-for-play", "folder-a"])
                    self.current_menu = "FOLDER_SELECT_PLAY"
                elif self.current_selection == 3:  # Режим удаления
                    self.audio.play_sound_sequence_async(["please-select-folder-for-delete", "folder-a"])
                    self.current_menu = "FOLDER_SELECT_DELETE"
                    
                self.current_selection = 0
                self.display_current_screen()
                return

        # При выборе папки в режиме календаря
        if self.current_menu == "FOLDER_SELECT_CALENDAR":
            folder = ["A", "B", "C"][self.current_selection]
            self.choosen_folder = folder
            
            # Сначала проигрываем сообщения о выборе папки
            sounds = ["going-to", f"folder-{str(folder).lower()}"]
            for sound in sounds:
                process = subprocess.Popen(
                    ["paplay", f"{SOUNDS_DIR}/{sound}.wav"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                process.wait()  # Ждем окончания каждого звука
            
            # Получаем структуру календаря
            self.calendar_structure = self.get_calendar_structure(self.choosen_folder)
            if not self.calendar_structure:
                self.audio.play_sound("folder-empty")
                self.exit_to_parent_menu()
                return
            
            # Переходим к выбору года
            self.calendar_years = sorted(self.calendar_structure.keys(), reverse=True)
            self.current_menu = "CALENDAR_YEAR_MENU"
            self.current_selection = 0
            
            # После этого озвучиваем первый год
            if self.calendar_years:
                self.audio.play_sound(f"{self.calendar_years[0]}-year")
            
            self.display_current_screen()
            return

        # При выборе папки в других режимах
        if self.current_menu in ["FOLDER_SELECT_PLAY", "FOLDER_SELECT_DELETE", "FOLDER_SELECT_RECORD"]:
            chosen = ["A", "B", "C"][self.current_selection]
            self.choosen_folder = chosen
            if self.current_menu == "FOLDER_SELECT_RECORD":
                self._record_sequence(chosen)
                return
            else:
                self.audio.play_sound_sequence_async(["chosen", f"folder-{str(chosen).lower()}"])
                records = self.get_records_list(self.choosen_folder)
                if not records:
                    self.audio.play_sound("folder-empty")
                    self.exit_to_parent_menu()
                else:
                    if self.current_menu == "FOLDER_SELECT_PLAY":
                        self.current_menu = "RECORDS_MENU"
                    else:
                        self.current_menu = "DELETE_RECORDS_MENU"
                    self.records_list = records
                    self.current_selection = 0
                    self.display_current_screen()
                return

        # При выборе года
        if self.current_menu == "CALENDAR_YEAR_MENU":
            self.current_year = self.calendar_years[self.current_selection]
            self.calendar_months = sorted(self.calendar_structure[self.current_year].keys())
            
            # Сначала проигрываем год
            sounds = ["going-to", f"{self.current_year}-year"]
            for sound in sounds:
                process = subprocess.Popen(
                    ["paplay", f"{SOUNDS_DIR}/{sound}.wav"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                process.wait()  # Ждем окончания каждого звука
            
            self.current_menu = "CALENDAR_MONTH_MENU"
            self.current_selection = 0
            
            # После этого проигрываем первый месяц
            if self.calendar_months:
                self.audio.play_sound(MONTH_TO_SOUND[self.calendar_months[0]])
            
            self.display_current_screen()
            return

        # При выборе месяца
        if self.current_menu == "CALENDAR_MONTH_MENU":
            self.current_month = self.calendar_months[self.current_selection]
            self.calendar_days = sorted(self.calendar_structure[self.current_year][self.current_month].keys())
            
            # Сначала проигрываем вход в месяц
            sounds = ["going-to", MONTH_TO_SOUND[self.current_month]]
            for sound in sounds:
                process = subprocess.Popen(
                    ["paplay", f"{SOUNDS_DIR}/{sound}.wav"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                process.wait()  # Ждем окончания каждого звука
            
            self.current_menu = "CALENDAR_DAY_MENU"
            self.current_selection = 0
            
            # После этого озвучиваем первый день и месяц с "a" на конце
            if self.calendar_days:
                day = self.calendar_days[0]
                self.audio.play_sound_sequence_async([f"{day}e", f"{MONTH_TO_SOUND[self.current_month]}a"])
            
            self.display_current_screen()
            return

        # При выборе дня в календаре
        if self.current_menu == "CALENDAR_DAY_MENU":
            current_day = self.calendar_days[self.current_selection]
            self.records_list = self.calendar_structure[self.current_year][self.current_month][current_day]
            
            # Определяем день недели
            date = datetime(self.current_year, self.current_month, current_day)
            weekday = date.weekday()
            
            # Воспроизводим системные сообщения последовательно
            sounds = [
                "going-to",
                f"{current_day}e",
                f"{MONTH_TO_SOUND[self.current_month]}a",
                WEEKDAY_TO_SOUND[weekday]
            ]
            
            for sound in sounds:
                process = subprocess.Popen(
                    ["paplay", f"{SOUNDS_DIR}/{sound}.wav"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                process.wait()
            
            # Устанавливаем флаг календарного воспроизведения
            self.is_calendar_playback = True
            self.parent_menu_stack.append(("CALENDAR_DAY_MENU", self.current_selection))
            self.current_menu = "RECORDS_MENU"
            self.current_selection = 0
            if self.records_list:
                self.audio.play_sound("1")
            self.display_current_screen()
            return

        # При входе в обычный режим воспроизведения
        if self.current_menu == "FOLDER_SELECT_PLAY":
            self.is_calendar_playback = False  # Сбрасываем флаг
            # При выборе папки
            if self.current_menu in ["FOLDER_SELECT_CALENDAR", "FOLDER_SELECT_PLAY", "FOLDER_SELECT_DELETE", "FOLDER_SELECT_RECORD"]:
                folder = ["A", "B", "C"][self.current_selection]
                self.choosen_folder = folder
                self.audio.play_sound_sequence_async(["going-to", f"folder-{str(folder).lower()}"])

                if self.current_menu == "FOLDER_SELECT_CALENDAR":
                    # Получаем структуру календаря
                    self.calendar_structure = self.get_calendar_structure(self.choosen_folder)
                    if not self.calendar_structure:
                        self.audio.play_sound_sequence_async(["folder-empty", "return-to", "dictaphone-mode"])
                        self.current_menu = "DICTAPHONE_MENU"
                        self.current_selection = 0
                        self.display_current_screen()
                        return

                    # Переходим к выбору года
                    self.calendar_years = sorted(self.calendar_structure.keys(), reverse=True)
                    self.current_menu = "CALENDAR_YEAR_MENU"
                    self.current_selection = 0
                    self.audio.play_sound(f"{self.calendar_years[0]}-year")
                    self.display_current_screen()
                    return

            if self.current_menu == "CONFIRM_DELETE_MENU":
                if self.current_selection == 1:  # Да
                    filename = self.selected_record_to_delete.split('(')[0].strip()
                    filepath = os.path.join(RECORDS_BASE_DIR, self.choosen_folder, filename)
                    
                    if os.path.exists(filepath):
                        self.audio.stop_playback()
                        self.in_play_mode = False
                        os.remove(filepath)
                        
                        if self.is_calendar_playback:
                            # Если удаление из режима календаря
                            self.audio.play_sound_sequence_async(["delete-success", "return-to", "select-audio-mode"])
                            
                            # Обновляем структуру календаря
                            self.calendar_structure = self.get_calendar_structure(self.choosen_folder)
                            calendar_menu_index = len(self.parent_menu_stack) - 2
                            current_day = self.calendar_days[self.parent_menu_stack[calendar_menu_index][1]]
                            
                            if current_day in self.calendar_structure[self.current_year][self.current_month]:
                                # Возвращаемся к списку записей этого дня
                                self.records_list = self.calendar_structure[self.current_year][self.current_month][current_day]
                                self.current_menu = "RECORDS_MENU"
                                self.parent_menu_stack.pop()  # Удаляем только контекст подтверждения
                            else:
                                # Если записей не осталось, возвращаемся к выбору месяца
                                while len(self.parent_menu_stack) > 0 and self.parent_menu_stack[-1][0] != "CALENDAR_MONTH_MENU":
                                    self.parent_menu_stack.pop()
                                self.current_menu = "CALENDAR_MONTH_MENU"
                        else:
                            # Если из обычного режима воспроизведения
                            self.audio.play_sound_sequence_async(["delete-success", "return-to", "select-audio-mode"])
                            self.current_menu = "RECORDS_MENU"
                            self.records_list = self.get_records_list(self.choosen_folder)
                            while len(self.parent_menu_stack) > 1:
                                self.parent_menu_stack.pop()
                        
                        self.current_selection = 0
                        self.display_current_screen()
                    self.selected_record_to_delete = None
                
                else:  # Нет
                    # Возвращаемся к воспроизведению
                    self.audio.play_sound_sequence_async(["return-to", "select-audio-mode"])
                    self.current_menu = "RECORDS_MENU"
                    self.parent_menu_stack.pop()  # Удаляем контекст подтверждения удаления
                    self.current_selection = self.parent_menu_stack[-1][1]  # Восстанавливаем позицию в списке
                    self.display_current_screen()
                    # Снимаем с паузы и продолжаем воспроизведение
                    self.audio.play_sound("play-will-continue-in-321")
                    while self.audio.current_sound_process and self.audio.current_sound_process.poll() is None:
                        time.sleep(0.05)
                    self.audio.toggle_pause()
                    self.display_playback_screen(self.records_list[self.current_selection])
                return

        if self.current_menu in ["FOLDER_SELECT_PLAY", "FOLDER_SELECT_DELETE"]:
            if self.current_selection == 0:
                self.choosen_folder = "A"
            elif self.current_selection == 1:
                self.choosen_folder = "B"
            elif self.current_selection == 2:
                self.choosen_folder = "C"

            records = self.get_records_list(self.choosen_folder)
            if not records:
                self.audio.play_sound_sequence_async(["folder-empty", "return-to", "dictaphone-mode"])
                self.current_menu = "DICTAPHONE_MENU"
                self.current_selection = 0
                self.display_current_screen()
                return
            else:
                self.audio.play_sound_sequence_async(["chosen", f"folder-{self.choosen_folder.lower()}"])
                self.records_list = records
                self.current_menu = "RECORDS_MENU" if self.current_menu == "FOLDER_SELECT_PLAY" else "DELETE_RECORDS_MENU"
                self.current_selection = 0
                self.display_current_screen()
                return

        if self.current_menu == "RECORDS_MENU":
            if self.records_list:
                rec = self.records_list[self.current_selection]
                filename = rec.split('(')[0].strip()
                filepath = os.path.join(RECORDS_BASE_DIR, self.choosen_folder, filename)
                if os.path.exists(filepath):
                    self.in_play_mode = True
                    def finish_playback():
                        self.in_play_mode = False
                        self.audio.play_sound_sequence_async(["return-to", "select-audio-mode"])
                        self.current_menu = "RECORDS_MENU"
                        self.current_selection = 0
                        self.display_current_screen()
                    self.audio.start_playback(filepath, on_finish_callback=finish_playback)
                    self.display_playback_screen(rec)
            return

        if self.current_menu == "DELETE_RECORDS_MENU":
            if self.records_list:
                print(f"\nУдаляю запись: {self.records_list[self.current_selection]}")
                self.selected_record_to_delete = self.records_list[self.current_selection]
                self.parent_menu_stack.append((self.current_menu, self.current_selection))
                self.current_menu = "CONFIRM_DELETE_MENU"
                self.current_selection = 0
                self.audio.play_sound_sequence_async(["want-to-delete"])
                self.display_current_screen()
            return

        menu_items = MENUS.get(self.current_menu, [])
        if not menu_items:
            return

        title, submenu = menu_items[self.current_selection]

        if self.current_menu == "MAIN_MENU":
            if self.current_selection == 0:
                self.audio.play_sound_sequence_async(["going-to", "dictaphone-mode", "create-new-record"])
            elif self.current_selection == 1:
                self.audio.play_sound_sequence_async(["going-to", "call-mode"])
            elif self.current_selection == 2:
                self.audio.play_sound_sequence_async(["going-to", "radio-mode"])

        self.parent_menu_stack.append((self.current_menu, self.current_selection))

        if self.current_menu == "DICTAPHONE_MENU":
            if self.current_selection == 0:
                self.audio.play_sound_sequence_async(["please-select-folder-for-record", "folder-a"])
                self.current_menu = "FOLDER_SELECT_RECORD"
                self.current_selection = 0
                self.display_current_screen()
                return
            elif self.current_selection == 1:
                self.audio.play_sound_sequence_async(["please-select-folder-for-play", "folder-a"])
                self.current_menu = "FOLDER_SELECT_PLAY"
                self.current_selection = 0
                self.display_current_screen()
                return
            elif self.current_selection == 2:
                self.audio.play_sound_sequence_async(["please-select-folder-for-delete", "folder-a"])
                self.current_menu = "FOLDER_SELECT_DELETE"
                self.current_selection = 0
                self.display_current_screen()
                return

        if self.current_menu in ["FOLDER_SELECT_RECORD", "FOLDER_SELECT_PLAY", "FOLDER_SELECT_DELETE"]:
            chosen = ["A","B","C"][self.current_selection]
            self.choosen_folder = chosen
            if self.current_menu == "FOLDER_SELECT_RECORD":
                self._record_sequence(chosen)
                return
            else:
                self.audio.play_sound_sequence_async(["chosen", f"folder-{str(chosen).lower()}"])
                records = self.get_records_list(self.choosen_folder)
                if not records:
                    self.audio.play_sound("folder-empty")
                    self.exit_to_parent_menu()
                else:
                    if self.current_menu == "FOLDER_SELECT_PLAY":
                        self.current_menu = "RECORDS_MENU"
                    else:
                        self.current_menu = "DELETE_RECORDS_MENU"
                    self.records_list = records
                    self.current_selection = 0
                    self.display_current_screen()
                return

        if submenu:
            self.current_menu = submenu
            self.current_selection = 0
        else:
            self.audio.play_sound("yes")
            self.exit_to_parent_menu()

        self.display_current_screen()

    def _record_sequence(self, chosen):
        def start_recording():
            self.recorder.start_recording_delayed(self.choosen_folder)
            self.display_recording_screen(self.recorder.file_path)

        self.audio.stop_current_sound()
        
        # Проигрываем только необходимые системные сообщения
        sounds = ["record-will-start-in-321", "beep"]
        for sound in sounds:
            subprocess.run(
                ["paplay", f"{SOUNDS_DIR}/{sound}.wav"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        
        # Запускаем запись только после завершения всех звуков
        threading.Thread(target=start_recording, daemon=True).start()

    def exit_to_parent_menu(self):
        if self.parent_menu_stack:
            prev = self.parent_menu_stack.pop()
            self.current_menu, self.current_selection = prev
            self.audio.play_sound_sequence_async(["return-to", menu_name_for_audio(self.current_menu)])
        else:
            self.current_menu = "MAIN_MENU"
            self.current_selection = 0
            self.audio.play_sound_sequence_async(["return-to", "main-menu"])
        self.display_current_screen()

    def get_records_list(self, folder):
        path = os.path.join(RECORDS_BASE_DIR, folder)
        if not os.path.isdir(path):
            return []

        files = []
        for f in os.listdir(path):
            if f.endswith(".wav"):
                filepath = os.path.join(path, f)
                try:
                    # Получаем длительность файла
                    duration_output = subprocess.check_output(['soxi', '-D', filepath], stderr=subprocess.DEVNULL)
                    duration = float(duration_output.decode().strip())

                    # Форматируем длительность
                    hours = int(duration // 3600)
                    minutes = int((duration % 3600) // 60)
                    seconds = int(duration % 60)

                    if hours > 0:
                        duration_str = f"({hours}:{minutes:02d}:{seconds:02d})"
                    else:
                        duration_str = f"({minutes}:{seconds:02d})"

                    # Добавляем файл с длительностью
                    files.append(f"{f}{duration_str}")
                except:
                    files.append(f)

        # Сортируем по времени изменения
        files.sort(key=lambda x: os.path.getmtime(os.path.join(path, x.split('(')[0])), reverse=True)
        return files

    def display_recording_screen(self, filename):
        os.system("clear")
        print("Идет запись в папку", os.path.basename(os.path.dirname(filename)))
        print("Файл:", os.path.basename(filename))
        print("KEY_SELECT - пауза/продолжить запись")
        print("KEY_BACK - остановить и сохранить")

    def display_playback_screen(self, record_name):
        """Отображение экрана воспроизведения"""
        def update_screen():
            last_state = None
            while self.audio.playback_in_progress:
                # Если мы в режиме подтверждения удаления, не обновляем экран воспроизведения
                if self.current_menu == "CONFIRM_DELETE_MENU":
                    time.sleep(0.1)
                    continue
                    
                current_state = (self.audio.current_position, self.audio.paused)
                if current_state == last_state:
                    time.sleep(0.1)
                    continue
                    
                os.system("clear")
                filename = record_name.split('(')[0].strip()
                print("Воспроизводится запись:", filename)
                print("KEY_SELECT - пауза/продолжить восроизведение")
                print("KEY_BACK - остановить и вернуться в список записей")
                print("Зажмите KEY_RIGHT - 2x скорость")
                print("Нажмите KEY_LEFT - премотка азад")
                print()

                current = int(self.audio.current_position)
                total = int(self.audio.total_duration)
                current_str = f"{current//60}:{current%60:02d}"
                total_str = f"{total//60}:{total%60:02d}"

                bar_width = 40
                if total > 0:
                    position = int(bar_width * current / total)
                else:
                    position = 0
                progress_bar = "▓" * position + "░" * (bar_width - position)

                print(f"{current_str} {progress_bar} {total_str}")

                if self.audio.paused:
                    print("\nНа паузе")
                    
                last_state = current_state
                time.sleep(0.1)

        # апускаем обновление в отдельном потоке
        threading.Thread(target=update_screen, daemon=True).start()

    def pause_resume_recording(self):
        if self.recorder.recording_in_progress:
            self.audio.stop_current_sound()
            if self.recorder.record_paused:
                # Сначала проигрываем все системные сообщения последовательно
                for sound in ["record-will-continue-in-321", "beep"]:
                    process = subprocess.Popen(
                        ["paplay", f"{SOUNDS_DIR}/{sound}.wav"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    process.wait()  # Ждем окончания каждого звука
                
                # Только после завершения всех звуков возобновляем запись
                if not self.recorder.stop_flag:
                    self.recorder.resume_recording()
            else:
                self.audio.play_sound("record-is-on-pause")
                self.recorder.pause_recording()

    def pause_resume_playback(self):
        """Управление паузой воспроизведения"""
        if self.in_play_mode:
            self.audio.stop_current_sound()
            if not self.audio.paused:
                # Сначал ставим на паузу
                self.audio.toggle_pause()
                # Затем проигрываем системное сообщение
                self.audio.play_sound("record-is-on-pause")
                self.display_playback_screen(self.records_list[self.current_selection])
            else:
                # Сначала проигрываем системные сообщения последовательно
                for sound in ["play-will-continue-in-321", "beep"]:
                    subprocess.run(
                        ["paplay", f"{SOUNDS_DIR}/{sound}.wav"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                # Только после того как все сообщения проиграны, снимаем с паузы
                self.audio.toggle_pause()
                self.display_playback_screen(self.records_list[self.current_selection])

    def request_delete_during_playback(self):
        """Запрос на удаление во время воспроизведения"""
        if self.in_play_mode:
            # Если не на паузе
            if not self.audio.paused:
                # Сначала ствим на паузу
                self.audio.toggle_pause()
                # Затем проигрываем системное сообщение
                self.audio.play_sound("record-is-on-pause")
                while self.audio.current_sound_process and self.audio.current_sound_process.poll() is None:
                    time.sleep(0.05)
            
            # Сохраняем текущий фйл для даления
            current_file = self.records_list[self.current_selection]
            self.selected_record_to_delete = current_file
            
            # Переходим в меню подтверждения удаления
            self.parent_menu_stack.append(("RECORDS_MENU", self.current_selection))
            self.current_menu = "CONFIRM_DELETE_MENU"
            self.current_selection = 0
            # Проигрываем последовательность сообщений
            self.audio.play_sound_sequence_async(["want-to-delete", "no"])  # Добавляем озвучивание первого выбора
            self.display_current_screen()

    def stop_playback_return(self):
        """Остановка воспроизведения и возврат в меню"""
        if self.in_play_mode:
            self.audio.stop_playback()
            self.in_play_mode = False
            self.audio.play_sound_sequence_async(["return-to", "select-audio-mode"])
            
            if self.is_calendar_playback:
                # Возвращаемся в календарный день
                if self.parent_menu_stack and self.parent_menu_stack[-1][0] == "CALENDAR_DAY_MENU":
                    prev = self.parent_menu_stack.pop()
                    self.current_menu = prev[0]
                    self.current_selection = prev[1]
            else:
                # Возвращаемся в обычный режим воспроизведения
                self.current_menu = "RECORDS_MENU"
                self.current_selection = 0
                
            self.display_current_screen()

    def stop_recording_return(self):
        """Остановка записи и возврат в меню"""
        self.recorder.stop_recording()
        self.audio.stop_current_sound()
        self.audio.play_sound_sequence_async(["record-created-and-saved", "return-to", "dictaphone-mode"])
        self.current_menu = "DICTAPHONE_MENU"
        self.current_selection = 0
        self.display_current_screen()

    def toggle_pause_playback(self):
        """Переключение паузы воспроизведения"""
        try:
            self.audio.toggle_pause()
            self.display_playback_screen(self.records_list[self.current_selection])
        except:
            self.stop_playback_return()

    def get_calendar_structure(self, folder):
        """Получение структуры календаря для выбранной папки"""
        path = os.path.join(RECORDS_BASE_DIR, folder)
        if not os.path.isdir(path):
            return {}

        structure = {}
        for f in os.listdir(path):
            if f.endswith(".wav"):
                try:
                    # Парсим имя файла
                    parts = f.split("-")
                    year = int(parts[0])
                    month = int(parts[1])
                    day = int(parts[2])
                    
                    # Получаем длительность файла
                    filepath = os.path.join(path, f)
                    duration_output = subprocess.check_output(['soxi', '-D', filepath], stderr=subprocess.DEVNULL)
                    duration = float(duration_output.decode().strip())
                    
                    # Форматируем длительность
                    hours = int(duration // 3600)
                    minutes = int((duration % 3600) // 60)
                    seconds = int(duration % 60)
                    if hours > 0:
                        duration_str = f"({hours}:{minutes:02d}:{seconds:02d})"
                    else:
                        duration_str = f"({minutes}:{seconds:02d})"
                    
                    # Добавляем в структуру
                    if year not in structure:
                        structure[year] = {}
                    if month not in structure[year]:
                        structure[year][month] = {}
                    if day not in structure[year][month]:
                        structure[year][month][day] = []
                    
                    structure[year][month][day].append(f"{f}{duration_str}")
                except:
                    continue

        return structure

    def display_calendar_year_menu(self):
        os.system("clear")
        print("Выберите год:")
        for i, year in enumerate(self.calendar_years):
            prefix = " > " if i == self.current_selection else "   "
            print(f"{prefix}{year}")

    def display_calendar_month_menu(self):
        os.system("clear")
        print(f"Год: {self.current_year}")
        print("Выберите месяц:")
        for i, month in enumerate(self.calendar_months):
            prefix = " > " if i == self.current_selection else "   "
            month_name = MONTH_TO_SOUND[month].capitalize()
            print(f"{prefix}{month_name}")

    def display_calendar_day_menu(self):
        os.system("clear")
        print(f"Год: {self.current_year}, Месяц: {MONTH_TO_SOUND[self.current_month].capitalize()}")
        print("Выберите день:")
        for i, day in enumerate(self.calendar_days):
            prefix = " > " if i == self.current_selection else "   "
            records = self.calendar_structure[self.current_year][self.current_month][day]
            print(f"{prefix}{day} ({len(records)} записей)")

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
