import logging
from typing import Callable, Any, Dict, List

logger = logging.getLogger(__name__)

class EventBus:
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, listener: Callable):
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(listener)
        logger.debug(f"[EventBus] Subscribed to {event_type}")

    def emit(self, event_type: str, payload: Any):
        logger.info(f"[EventBus] Emitting {event_type}")
        if event_type in self._listeners:
            for listener in self._listeners[event_type]:
                try:
                    listener(payload)
                except Exception as e:
                    logger.exception(f"[EventBus] Error in listener for {event_type}: {e}")

bus = EventBus()
