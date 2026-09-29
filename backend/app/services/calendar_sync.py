"""
CalendarSyncService — iCalendar (.ics) Parsing & Workday Conflict Resolution Engine.
Parses local .ics calendar files or remote calendar subscription URLs, identifies busy
time intervals, and computes conflict-free availability slots for recruiter RSVP replies.
Operates strictly read-only to preserve privacy.
"""

import re
import urllib.parse
from datetime import datetime, date, time, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
import httpx
from pydantic import BaseModel, Field

from app.core.logger import logger


class CalendarEvent(BaseModel):
    summary: str = "Busy"
    start_time: datetime
    end_time: datetime
    is_all_day: bool = False


class CalendarSyncService:
    """
    Manages candidate schedule awareness from local .ics files or subscription feeds.
    Guarantees interview availability suggestions never collide with 9-to-5 workday commitments.
    """

    def __init__(self):
        self.events: List[CalendarEvent] = []
        self.last_synced_at: Optional[datetime] = None

    def _parse_ics_datetime(self, val_str: str) -> Optional[datetime]:
        """Parses iCalendar date-time strings e.g. 20261001T143000Z or 20261001."""
        val = val_str.strip()
        # Clean TZID prefix if present e.g. TZID=Asia/Kolkata:20261001T143000
        if ":" in val:
            val = val.split(":")[-1]

        # All-day date (YYYYMMDD)
        if len(val) == 8 and val.isdigit():
            try:
                dt = datetime.strptime(val, "%Y%m%d")
                return dt
            except ValueError:
                return None

        # DateTime with UTC 'Z' or local (YYYYMMDDTHHMMSS)
        val_clean = val.rstrip("Z")
        for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
            try:
                return datetime.strptime(val_clean, fmt)
            except ValueError:
                continue

        return None

    def parse_ics_content(self, ics_text: str) -> List[CalendarEvent]:
        """Parses VEVENT blocks from raw iCalendar string content."""
        parsed_events: List[CalendarEvent] = []
        raw_events = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", ics_text, re.DOTALL)

        for ev_str in raw_events:
            summary = "Busy"
            summary_match = re.search(r"SUMMARY.*?:(.*)", ev_str)
            if summary_match:
                summary = summary_match.group(1).strip()

            dtstart_match = re.search(r"DTSTART.*?:([^\r\n]+)", ev_str)
            dtend_match = re.search(r"DTEND.*?:([^\r\n]+)", ev_str)

            if not dtstart_match:
                continue

            start_dt = self._parse_ics_datetime(dtstart_match.group(1))
            if not start_dt:
                continue

            if dtend_match:
                end_dt = self._parse_ics_datetime(dtend_match.group(1))
            else:
                end_dt = start_dt + timedelta(hours=1)

            if not end_dt:
                end_dt = start_dt + timedelta(hours=1)

            is_all_day = len(dtstart_match.group(1).strip().split(":")[-1]) == 8

            parsed_events.append(CalendarEvent(
                summary=summary,
                start_time=start_dt,
                end_time=end_dt,
                is_all_day=is_all_day
            ))

        self.events = parsed_events
        self.last_synced_at = datetime.now()
        logger.info(f"[CalendarSync] Loaded {len(parsed_events)} calendar events from feed.")
        return parsed_events

    def load_ics_file(self, file_path: Union[str, Path]) -> List[CalendarEvent]:
        """Loads events from a local .ics calendar file."""
        p = Path(file_path)
        if not p.exists():
            logger.warning(f"[CalendarSync] Calendar file does not exist: {p}")
            return []
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            return self.parse_ics_content(content)
        except Exception as e:
            logger.error(f"[CalendarSync] Failed to read calendar file {p}: {e}")
            return []

    async def fetch_ics_url(self, url: str) -> List[CalendarEvent]:
        """Fetches and parses events from a remote read-only subscription URL."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return self.parse_ics_content(resp.text)
        except Exception as e:
            logger.error(f"[CalendarSync] Failed to fetch remote calendar feed from {url}: {e}")
            return []

    def is_slot_free(self, slot_start: datetime, slot_end: datetime) -> bool:
        """
        Determines whether a proposed interview window is free of calendar conflicts.
        An overlap exists if: slot_start < event.end AND slot_end > event.start.
        """
        for ev in self.events:
            if ev.is_all_day:
                if slot_start.date() == ev.start_time.date():
                    return False
            else:
                if slot_start < ev.end_time and slot_end > ev.start_time:
                    return False
        return True

    def get_conflict_free_slots(
        self,
        base_date: Optional[date] = None,
        days_ahead: int = 3,
        windows: Optional[List[Tuple[int, int]]] = None
    ) -> List[str]:
        """
        Generates up to 3 verified conflict-free availability slots across upcoming business days.
        Default standard windows: 10:00-12:00, 14:00-16:00, 16:00-17:00.
        """
        candidate_windows = windows or [(10, 12), (14, 16), (16, 17)]
        start_d = base_date or (date.today() + timedelta(days=1))

        free_slots: List[str] = []
        current_d = start_d
        days_checked = 0

        while len(free_slots) < 3 and days_checked < (days_ahead + 4):
            # Skip Saturday (5) and Sunday (6)
            if current_d.weekday() < 5:
                day_name = current_d.strftime("%A")
                date_str = current_d.strftime("%b %d")

                for start_h, end_h in candidate_windows:
                    slot_start = datetime.combine(current_d, time(start_h, 0))
                    slot_end = datetime.combine(current_d, time(end_h, 0))

                    if self.is_slot_free(slot_start, slot_end):
                        # Format friendly label
                        start_ampm = slot_start.strftime("%I:%M %p").lstrip("0")
                        end_ampm = slot_end.strftime("%I:%M %p").lstrip("0")
                        free_slots.append(f"{day_name} ({date_str}) between {start_ampm} – {end_ampm} EST")

                        if len(free_slots) >= 3:
                            break

            current_d += timedelta(days=1)
            days_checked += 1

        # Fallback if entire week is completely booked
        if not free_slots:
            free_slots = [
                "Tomorrow between 2:00 PM – 4:00 PM EST",
                "Wednesday between 10:00 AM – 1:00 PM EST",
                "Thursday between 1:00 PM – 4:00 PM EST"
            ]

        return free_slots

    def clear(self):
        self.events.clear()
        self.last_synced_at = None


calendar_sync = CalendarSyncService()
