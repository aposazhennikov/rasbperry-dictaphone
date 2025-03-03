#!/usr/bin/env python3
import sys
from evdev import ecodes
from config.constants import (
    KEY_UP, KEY_DOWN, KEY_SELECT, KEY_BACK, KEY_LEFT, KEY_RIGHT,
    KEY_VOLUMEUP, KEY_VOLUMEDOWN, KEY_POWER
)
from src.audio.player import AudioPlayer
from src.audio.recorder import Recorder
from src.device.remote import RemoteDevice
from src.menu.manager import MenuManager

def main():
    try:
        # Инициализация устройства
        dev = RemoteDevice.get_device()
        print("Найдено устройство:", dev.path)

        # Инициализация компонентов
        audio = AudioPlayer()
        recorder = Recorder()
        menu = MenuManager(audio, recorder)

        # Отображение начального экрана
        menu.display_current_screen()
        audio.play_sound_sequence_async(["start", "dictaphone-mode"])

        # Состояния клавиш для отслеживания длительного нажатия
        key_states = {
            KEY_LEFT: False,
            KEY_RIGHT: False
        }

        # Основной цикл обработки событий
        for event in dev.read_loop():
            if event.type == ecodes.EV_KEY:
                key_code = event.code
                key_value = event.value

                if key_value == 1:  # Нажатие клавиши
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
                            menu.enter_selection()
                        elif menu.in_play_mode:
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

                elif key_value == 0:  # Отпускание клавиши
                    if key_code == KEY_RIGHT:
                        if key_states[KEY_RIGHT]:
                            key_states[KEY_RIGHT] = False
                            audio.stop_right_fast_forward()
                    elif key_code == KEY_LEFT:
                        if key_states[KEY_LEFT]:
                            key_states[KEY_LEFT] = False
                            audio.stop_left_rewind()

    except KeyboardInterrupt:
        print("Завершение работы...")
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 