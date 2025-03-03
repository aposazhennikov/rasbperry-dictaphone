import os
import time
import threading
import sounddevice as sd
import soundfile as sf
from config.constants import RECORDS_BASE_DIR

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