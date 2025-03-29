#!/usr/bin/env python3
import threading
import sentry_sdk
from typing import Dict, List, Callable

class EventBus:
    """
    Простая система событий для связи между компонентами.
    Позволяет компонентам подписываться на события и публиковать их.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls):
        """
        Реализация паттерна Singleton для EventBus
        
        Returns:
            EventBus: Единственный экземпляр EventBus
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
                # Логируем создание EventBus
                sentry_sdk.add_breadcrumb(
                    category="event_bus",
                    message="EventBus создан",
                    level="info"
                )
            return cls._instance
    
    def __init__(self):
        """Инициализация EventBus"""
        self.subscribers: Dict[str, List[Callable]] = {}
        self.lock = threading.Lock()
        self.debug = False
        
        # Логируем инициализацию
        sentry_sdk.add_breadcrumb(
            category="event_bus",
            message="EventBus инициализирован",
            level="info"
        )
    
    def set_debug(self, debug: bool):
        """
        Устанавливает режим отладки
        
        Args:
            debug (bool): Включить/выключить режим отладки
        """
        self.debug = debug
        
        # Логируем изменение режима отладки
        sentry_sdk.add_breadcrumb(
            category="event_bus",
            message=f"Режим отладки установлен: {debug}",
            level="info"
        )
    
    def subscribe(self, event_name: str, callback: Callable):
        """
        Подписка на событие
        
        Args:
            event_name (str): Имя события
            callback (Callable): Функция обратного вызова
        """
        try:
            with self.lock:
                if event_name not in self.subscribers:
                    self.subscribers[event_name] = []
                
                # Проверка, не подписан ли уже данный обработчик
                if callback in self.subscribers[event_name]:
                    # Логируем повторную подписку
                    sentry_sdk.add_breadcrumb(
                        category="event_bus",
                        message=f"Попытка повторной подписки на событие '{event_name}'",
                        level="warning"
                    )
                    
                    if self.debug:
                        print(f"EventBus: Предупреждение - {callback} уже подписан на событие '{event_name}'")
                    return
                
                self.subscribers[event_name].append(callback)
                
                # Логируем успешную подписку
                sentry_sdk.add_breadcrumb(
                    category="event_bus",
                    message=f"Подписка на событие '{event_name}', callback: {callback.__qualname__ if hasattr(callback, '__qualname__') else str(callback)}",
                    level="info"
                )
                
                if self.debug:
                    print(f"EventBus: Подписка на событие '{event_name}', всего подписчиков: {len(self.subscribers[event_name])}")
        except Exception as e:
            error_msg = f"Ошибка при подписке на событие '{event_name}': {e}"
            print(error_msg)
            
            # Добавляем контекст ошибки
            sentry_sdk.set_context("event_details", {
                "event_name": event_name,
                "callback": str(callback),
                "action": "subscribe"
            })
            sentry_sdk.capture_exception(e)
    
    def unsubscribe(self, event_name: str, callback: Callable):
        """
        Отписка от события
        
        Args:
            event_name (str): Имя события
            callback (Callable): Функция обратного вызова
        """
        try:
            with self.lock:
                if event_name in self.subscribers:
                    if callback in self.subscribers[event_name]:
                        self.subscribers[event_name].remove(callback)
                        
                        # Логируем успешную отписку
                        sentry_sdk.add_breadcrumb(
                            category="event_bus",
                            message=f"Отписка от события '{event_name}', осталось подписчиков: {len(self.subscribers[event_name])}",
                            level="info"
                        )
                        
                        if self.debug:
                            print(f"EventBus: Отписка от события '{event_name}', осталось подписчиков: {len(self.subscribers[event_name])}")
                    else:
                        # Логируем попытку отписки несуществующего обработчика
                        sentry_sdk.add_breadcrumb(
                            category="event_bus",
                            message=f"Попытка отписки необработчика от события '{event_name}'",
                            level="warning"
                        )
                        
                        if self.debug:
                            print(f"EventBus: Предупреждение - обработчик не найден для отписки от события '{event_name}'")
                else:
                    # Логируем попытку отписки от несуществующего события
                    sentry_sdk.add_breadcrumb(
                        category="event_bus",
                        message=f"Попытка отписки от несуществующего события '{event_name}'",
                        level="warning"
                    )
                    
                    if self.debug:
                        print(f"EventBus: Предупреждение - событие '{event_name}' не найдено для отписки")
        except Exception as e:
            error_msg = f"Ошибка при отписке от события '{event_name}': {e}"
            print(error_msg)
            
            # Добавляем контекст ошибки
            sentry_sdk.set_context("event_details", {
                "event_name": event_name,
                "callback": str(callback),
                "action": "unsubscribe"
            })
            sentry_sdk.capture_exception(e)
    
    def publish(self, event_name: str, **kwargs):
        """
        Публикация события
        
        Args:
            event_name (str): Имя события
            **kwargs: Параметры события
        """
        try:
            callbacks = []
            subscribers_count = 0
            
            with self.lock:
                if event_name in self.subscribers:
                    subscribers_count = len(self.subscribers[event_name])
                    callbacks = self.subscribers[event_name].copy()
            
            # Логируем публикацию события
            safe_kwargs = {k: v for k, v in kwargs.items() if isinstance(v, (str, int, float, bool, type(None)))}
            sentry_sdk.add_breadcrumb(
                category="event_bus",
                message=f"Публикация события '{event_name}' для {subscribers_count} подписчиков",
                level="info",
                data=safe_kwargs
            )
            
            if self.debug:
                print(f"EventBus: Публикация события '{event_name}' с параметрами {kwargs}, подписчиков: {len(callbacks)}")
            
            if subscribers_count == 0:
                # Логируем отсутствие подписчиков
                sentry_sdk.add_breadcrumb(
                    category="event_bus",
                    message=f"Нет подписчиков для события '{event_name}'",
                    level="warning"
                )
            
            # Вызываем коллбэки вне блокировки
            for callback in callbacks:
                try:
                    # Логируем вызов обработчика
                    callback_name = callback.__qualname__ if hasattr(callback, '__qualname__') else str(callback)
                    sentry_sdk.add_breadcrumb(
                        category="event_bus",
                        message=f"Вызов обработчика {callback_name} для события '{event_name}'",
                        level="info"
                    )
                    
                    # Вызываем обработчик
                    callback(**kwargs)
                    
                    # Логируем успешное выполнение
                    sentry_sdk.add_breadcrumb(
                        category="event_bus",
                        message=f"Обработчик {callback_name} успешно выполнен",
                        level="info"
                    )
                except Exception as callback_error:
                    error_msg = f"Ошибка при вызове обработчика события '{event_name}': {callback_error}"
                    print(error_msg)
                    
                    # Добавляем контекст ошибки
                    sentry_sdk.set_context("event_details", {
                        "event_name": event_name,
                        "callback": str(callback),
                        "action": "callback_execution",
                        "parameters": str(safe_kwargs)
                    })
                    sentry_sdk.capture_exception(callback_error)
        except Exception as e:
            error_msg = f"Ошибка при публикации события '{event_name}': {e}"
            print(error_msg)
            
            # Добавляем контекст ошибки
            sentry_sdk.set_context("event_details", {
                "event_name": event_name,
                "action": "publish",
                "parameters": str({k: v for k, v in kwargs.items() if isinstance(v, (str, int, float, bool, type(None)))})
            })
            sentry_sdk.capture_exception(e)

# Константы для названий событий
EVENT_USB_MIC_DISCONNECTED = "usb_microphone_disconnected"
EVENT_RECORDING_SAVED = "recording_saved"
EVENT_RECORDING_FAILED = "recording_failed" 

# Логируем определение констант событий для Sentry
sentry_sdk.add_breadcrumb(
    category="event_bus",
    message="Определены константы событий системы",
    level="info",
    data={
        "EVENT_USB_MIC_DISCONNECTED": EVENT_USB_MIC_DISCONNECTED,
        "EVENT_RECORDING_SAVED": EVENT_RECORDING_SAVED,
        "EVENT_RECORDING_FAILED": EVENT_RECORDING_FAILED
    }
) 