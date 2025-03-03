import os

# Настройки устройства
TARGET_DEVICE_NAME = "HAOBO Technology USB Composite Device Keyboard"
RECORDS_BASE_DIR = "/home/aleks/records"
SOUNDS_DIR = "/home/aleks/main-sounds"
DEBOUNCE_TIME = 0.1

# Коды клавиш
KEY_UP = 103
KEY_DOWN = 108
KEY_SELECT = 353
KEY_BACK = 158
KEY_LEFT = 105
KEY_RIGHT = 106
KEY_VOLUMEUP = 115
KEY_VOLUMEDOWN = 114
KEY_POWER = 116

# Названия меню
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

# Соответствие месяцев звуковым файлам
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

# Соответствие дней недели звуковым файлам
WEEKDAY_TO_SOUND = {
    0: "monday",
    1: "tuesday",
    2: "wednesday",
    3: "thursday",
    4: "friday",
    5: "saturday",
    6: "sunday"
}

# Настройки VLC
os.environ["VLC_PLUGIN_PATH"] = "/usr/lib/x86_64-linux-gnu/vlc/plugins"
os.environ["LD_LIBRARY_PATH"] = "/usr/lib/x86_64-linux-gnu" 