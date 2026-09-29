"""
Unit Tests for CalendarSyncService and Live Conflict Resolution.
Validates iCalendar (.ics) parsing, overlap detection, conflict-free slot calculation,
and dynamic integration with EmailAutoResponderService.
"""

from datetime import datetime, date, time, timedelta
import pytest

from app.services.calendar_sync import CalendarSyncService, CalendarEvent, calendar_sync
from app.services.email_auto_responder import email_auto_responder


SAMPLE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Google Inc//Google Calendar 70.9054//EN
BEGIN:VEVENT
UID:event_001@google.com
DTSTART:20261001T140000Z
DTEND:20261001T160000Z
SUMMARY:Sprint Planning Meeting
END:VEVENT
BEGIN:VEVENT
UID:event_002@google.com
DTSTART:20261002
DTEND:20261003
SUMMARY:All Hands Offsite
END:VEVENT
END:VCALENDAR
"""


def test_parse_ics_content():
    service = CalendarSyncService()
    events = service.parse_ics_content(SAMPLE_ICS)

    assert len(events) == 2
    assert events[0].summary == "Sprint Planning Meeting"
    assert events[0].start_time == datetime(2026, 10, 1, 14, 0, 0)
    assert events[0].end_time == datetime(2026, 10, 1, 16, 0, 0)
    assert events[0].is_all_day is False

    assert events[1].summary == "All Hands Offsite"
    assert events[1].is_all_day is True


def test_slot_conflict_detection():
    service = CalendarSyncService()
    service.parse_ics_content(SAMPLE_ICS)

    # 1. Direct overlap with Sprint Planning (Oct 1, 14:00 - 16:00)
    slot1_start = datetime(2026, 10, 1, 14, 30)
    slot1_end = datetime(2026, 10, 1, 15, 30)
    assert service.is_slot_free(slot1_start, slot1_end) is False

    # 2. Free time before Sprint Planning (Oct 1, 10:00 - 12:00)
    slot2_start = datetime(2026, 10, 1, 10, 0)
    slot2_end = datetime(2026, 10, 1, 12, 0)
    assert service.is_slot_free(slot2_start, slot2_end) is True

    # 3. All-day event conflict (Oct 2)
    slot3_start = datetime(2026, 10, 2, 11, 0)
    slot3_end = datetime(2026, 10, 2, 12, 0)
    assert service.is_slot_free(slot3_start, slot3_end) is False


def test_get_conflict_free_slots():
    service = CalendarSyncService()
    service.parse_ics_content(SAMPLE_ICS)

    # Starting Oct 1, 2026 (Thursday)
    base = date(2026, 10, 1)
    slots = service.get_conflict_free_slots(base_date=base, days_ahead=4)

    assert len(slots) >= 1
    # Oct 1 between 14:00 and 16:00 is busy, so only 10:00 - 12:00 or 16:00 - 17:00 should be offered for Oct 1
    oct1_slots = [s for s in slots if "Oct 01" in s]
    for s in oct1_slots:
        assert "2:00 PM – 4:00 PM" not in s


@pytest.mark.asyncio
async def test_email_auto_responder_integrates_calendar_slots():
    # Configure calendar sync with an event
    calendar_sync.clear()
    calendar_sync.parse_ics_content(SAMPLE_ICS)

    draft = await email_auto_responder.generate_rsvp_draft(
        email_id="cal_test_email",
        sender="recruiter@datadog.com",
        company="Datadog",
        role="Senior SRE"
    )

    assert len(draft.suggested_slots) >= 1
    # Verify body text includes dynamically computed slots
    assert "between" in draft.body
    assert "EST" in draft.body

    calendar_sync.clear()
