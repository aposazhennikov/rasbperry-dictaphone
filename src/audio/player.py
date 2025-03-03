import os
import time
import threading
import subprocess
import vlc
from config.constants import SOUNDS_DIR

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
            media = self.instance.media_new(file_path)
            self.player.set_media(media)

            media.parse()
            self.total_duration = media.get_duration() / 1000.0

            self.player.play()
            self.playback_in_progress = True
            self.paused = False
            self.current_speed = 1.0
            self.player.set_rate(self.current_speed)

            self.progress_stop_flag = False
            self.progress_thread = threading.Thread(target=self._update_progress, daemon=True)
            self.progress_thread.start()

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
                    self.current_position = self.player.get_time() / 1000.0
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
        self.volume = max(0, min(100, volume))
        self.player.audio_set_volume(self.volume)

    def volume_up(self):
        self.set_volume(self.volume + 10)

    def volume_down(self):
        self.set_volume(self.volume - 10)

    def start_right_fast_forward(self):
        if self.playback_in_progress:
            self.set_speed(2.0)

    def stop_right_fast_forward(self):
        if self.playback_in_progress:
            self.set_speed(1.0)

    def start_left_rewind(self):
        if self.playback_in_progress:
            self.seek(-5)

    def stop_left_rewind(self):
        pass

    def play_sound(self, sound_name):
        self.stop_current_sound()
        try:
            self.current_sound_process = subprocess.Popen(
                ["paplay", f"{SOUNDS_DIR}/{sound_name}.wav"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print(f"Sound playback error: {e}")

    def play_sound_sequence_async(self, sounds):
        self.stop_current_sound()
        
        with self.queue_lock:
            self.sound_queue = sounds.copy()
            
            if not self.queue_running:
                self.queue_running = True
                self.queue_thread = threading.Thread(target=self._process_sound_queue, daemon=True)
                self.queue_thread.start()

    def _process_sound_queue(self):
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
        with self.queue_lock:
            self.sound_queue.clear()
            
        if self.current_sound_process and self.current_sound_process.poll() is None:
            try:
                self.current_sound_process.terminate()
                self.current_sound_process.wait()
            except:
                pass
            self.current_sound_process = None 