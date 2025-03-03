import os
import subprocess
from datetime import datetime
from config.constants import RECORDS_BASE_DIR

def get_records_list(folder):
    """Получить список записей в папке с их длительностью"""
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

def get_calendar_structure(folder):
    """Получить структуру календаря для выбранной папки"""
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