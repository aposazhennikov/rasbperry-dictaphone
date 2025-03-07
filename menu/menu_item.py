#!/usr/bin/env python3

class MenuItem:
    """Базовый класс для пунктов меню"""
    
    def __init__(self, name, action=None):
        """
        Инициализация пункта меню
        
        Args:
            name (str): Название пункта меню
            action (callable, optional): Функция, которая будет вызвана при выборе пункта меню
        """
        self.name = name
        self.action = action
    
    def select(self):
        """Вызывается при выборе пункта меню"""
        if self.action:
            return self.action()
        return None


class SubMenu(MenuItem):
    """Класс для подменю, содержащего другие пункты меню"""
    
    def __init__(self, name, parent=None):
        """
        Инициализация подменю
        
        Args:
            name (str): Название подменю
            parent (SubMenu, optional): Родительское меню
        """
        super().__init__(name)
        self.parent = parent
        self.items = []
        self.current_selection = 0
    
    def add_item(self, item):
        """Добавляет пункт меню в подменю"""
        self.items.append(item)
        if isinstance(item, SubMenu):
            item.parent = self
    
    def select(self):
        """Вызывается при выборе подменю"""
        # При выборе подменю мы просто возвращаем его самого,
        # чтобы менеджер меню мог переключиться на него
        return self
    
    def get_current_item(self):
        """Возвращает текущий выбранный пункт меню"""
        if not self.items:
            return None
        return self.items[self.current_selection]
    
    def move_up(self):
        """Перемещение вверх по списку пунктов меню (циклически)"""
        if not self.items:
            return
        self.current_selection = (self.current_selection - 1) % len(self.items)
    
    def move_down(self):
        """Перемещение вниз по списку пунктов меню (циклически)"""
        if not self.items:
            return
        self.current_selection = (self.current_selection + 1) % len(self.items) 