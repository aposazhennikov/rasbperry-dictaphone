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