#!/usr/bin/env python3
"""
Скрипт для запуска меню из корневой директории проекта.
"""
import sys
import os

# Добавляем текущую директорию в путь поиска модулей
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Импортируем основную функцию из пакета menu
from menu.main import main

if __name__ == "__main__":
    main() 