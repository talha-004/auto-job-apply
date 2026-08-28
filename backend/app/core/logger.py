import asyncio
import json
import logging
from collections import deque
from datetime import datetime
from typing import List, Set, Optional, Dict, Any
from fastapi import WebSocket
from app.models.job import LogMessage, LogLevel

from logging.handlers import RotatingFileHandler
from app.core.config import settings

# Setup standard python logger with console and rotating file handler
logger = logging.getLogger("AutoApplyJobs")
logger.setLevel(logging.INFO)

# Console Handler
c_handler = logging.StreamHandler()
c_format = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")
c_handler.setFormatter(c_format)
logger.addHandler(c_handler)

# File Handler (5 MB max size, 5 backup files)
try:
    f_handler = RotatingFileHandler(
        str(settings.LOG_FILE_PATH),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    f_format = logging.Formatter("%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s")
    f_handler.setFormatter(f_format)
    logger.addHandler(f_handler)
except Exception as e:
    print(f"Warning: Could not initialize file logger: {e}")

class EventBroadcaster:
    def __init__(self, max_history: int = 500):
        self.active_connections: Set[WebSocket] = set()
        self.log_history: deque = deque(maxlen=max_history)
        self.main_loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock: Optional[asyncio.Lock] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self.main_loop = loop
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            self.active_connections.add(websocket)
        
        # Send recent history to new connection
        history_list = list(self.log_history)
        for log in history_list:
            try:
                await websocket.send_text(json.dumps(log.model_dump()))
            except Exception:
                break

    async def disconnect(self, websocket: WebSocket):
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            self.active_connections.discard(websocket)

    async def _broadcast(self, payload: str):
        if not self.active_connections:
            return
        dead_connections = set()
        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
            except Exception:
                dead_connections.add(connection)
        for dead in dead_connections:
            self.active_connections.discard(dead)

    async def emit_log(
        self,
        message: str,
        level: LogLevel = LogLevel.INFO,
        platform: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        log_entry = LogMessage(
            timestamp=datetime.now().strftime("%H:%M:%S"),
            level=level,
            platform=platform,
            message=message,
            details=details
        )
        self.log_history.append(log_entry)

        # Also write to standard logger
        log_prefix = f"[{platform}] " if platform else ""
        formatted_msg = f"{log_prefix}{message}"
        if level == LogLevel.ERROR:
            logger.error(formatted_msg)
        elif level == LogLevel.WARNING:
            logger.warning(formatted_msg)
        elif level == LogLevel.SUCCESS:
            logger.info(f"SUCCESS: {formatted_msg}")
        else:
            logger.info(formatted_msg)

        # Broadcast to active WebSockets
        payload = json.dumps(log_entry.model_dump())
        if self.main_loop and self.main_loop.is_running():
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = None

            if current_loop == self.main_loop:
                await self._broadcast(payload)
            else:
                asyncio.run_coroutine_threadsafe(self._broadcast(payload), self.main_loop)
        else:
            await self._broadcast(payload)

    def get_recent_logs(self, limit: int = 100) -> List[LogMessage]:
        return list(self.log_history)[-limit:]

broadcaster = EventBroadcaster()
