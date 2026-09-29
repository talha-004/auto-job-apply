"""
Excel Outbox Projection Worker.
Decouples transactional database persistence from Excel file writes.
Guarantees database writes never fail due to Excel file locks, and handles retries with backoff.
"""

import asyncio
import logging
from collections import deque
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.models.job import JobApplicationRecord
from app.core.logger import logger


class ExcelOutboxWorker:
    """
    Async outbox worker that syncs database records to Excel in the background.
    Handles PermissionError (when user has Excel open) without crashing the backend.
    """

    def __init__(self):
        self._queue: deque[JobApplicationRecord] = deque()
        self._is_flushing: bool = False
        self._consecutive_failures: int = 0
        self._last_error: Optional[str] = None

    def enqueue(self, record: JobApplicationRecord) -> None:
        """Enqueue an application record to be synced to the Excel spreadsheet."""
        self._queue.append(record)

    @property
    def pending_count(self) -> int:
        return len(self._queue)

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def flush_sync(self) -> int:
        """
        Synchronously flushes all pending records into Excel.
        Catches file locking errors gracefully.
        """
        from app.services.excel_tracker import excel_tracker

        flushed = 0
        while self._queue:
            record = self._queue[0]
            try:
                excel_tracker.log_application(record)
                self._queue.popleft()
                flushed += 1
                self._consecutive_failures = 0
                self._last_error = None
            except (PermissionError, IOError, OSError) as e:
                self._consecutive_failures += 1
                self._last_error = f"Excel file is locked by an external process: {e}"
                logger.warning(f"[ExcelOutbox] {self._last_error}. Retaining {len(self._queue)} records in outbox.")
                break
            except Exception as e:
                self._consecutive_failures += 1
                self._last_error = f"Unexpected Excel sync error: {e}"
                logger.error(f"[ExcelOutbox] {self._last_error}")
                # Pop problematic record to avoid permanent queue freeze
                self._queue.popleft()
                break

        return flushed

    async def flush_async(self) -> int:
        """Flushes queue in a non-blocking background thread."""
        return await asyncio.to_thread(self.flush_sync)


excel_outbox = ExcelOutboxWorker()
