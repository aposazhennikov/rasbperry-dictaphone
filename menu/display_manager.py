#!/usr/bin/env python3
import os
import sys

class DisplayManager:
    """Класс для отображения меню на экране"""
    
    def __init__(self, menu_manager):
        """
        Инициализация менеджера отображения
        
        Args:
            menu_manager: Менеджер меню
        """
        self.menu_manager = menu_manager
    
    def clear_screen(self):
        """Очищает экран"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def display_menu(self):
        """Отображает текущее меню"""
        self.clear_screen()
        
        current_menu = self.menu_manager.current_menu
        if not current_menu:
            return
            
        # Отображаем заголовок меню
        print(f"=== {current_menu.name} ===\n")
        
        # Отображаем пункты меню
        for i, item in enumerate(current_menu.items):
            # Добавляем маркер для текущего выбранного пункта
            prefix = "> " if i == current_menu.current_selection else "  "
            print(f"{prefix}{item.name}")
            
        # Добавляем подсказку для навигации
        print("\n--- Навигация ---")
        print("↑/↓: Перемещение по меню")
        print("Enter: Выбор")
        print("Back: Возврат в предыдущее меню")
    
    def display_message(self, message, title=None):
        """
        Отображает сообщение
        
        Args:
            message (str): Текст сообщения
            title (str, optional): Заголовок сообщения
        """
        self.clear_screen()
        
        if title:
            print(f"=== {title} ===\n")
            
        print(message)
        print("\nНажмите любую клавишу для продолжения...") 