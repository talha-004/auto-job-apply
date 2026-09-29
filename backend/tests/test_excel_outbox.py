import pytest
from unittest.mock import patch
from app.models.job import JobApplicationRecord, ApplicationStatus
from app.services.excel_outbox import ExcelOutboxWorker


def test_excel_outbox_queue_and_flush():
    """Verify that records are enqueued and flushed successfully under normal operation."""
    worker = ExcelOutboxWorker()
    rec = JobApplicationRecord(
        platform="LinkedIn",
        job_url="https://linkedin.com/jobs/view/outbox-1",
        job_title="Software Engineer",
        company="Outbox Systems",
        status=ApplicationStatus.APPLIED
    )

    worker.enqueue(rec)
    assert worker.pending_count == 1

    with patch("app.services.excel_tracker.excel_tracker.log_application") as mock_log:
        flushed = worker.flush_sync()
        assert flushed == 1
        assert worker.pending_count == 0
        mock_log.assert_called_once_with(rec)


def test_excel_outbox_handles_file_lock_without_crashing():
    """Verify that PermissionError (Excel open) retains records in queue without crashing."""
    worker = ExcelOutboxWorker()
    rec1 = JobApplicationRecord(
        platform="LinkedIn",
        job_url="https://linkedin.com/jobs/view/outbox-lock-1",
        job_title="Backend Dev",
        company="Locked Files Corp",
        status=ApplicationStatus.APPLIED
    )

    worker.enqueue(rec1)
    assert worker.pending_count == 1

    # Simulate Excel file locked by user
    with patch("app.services.excel_tracker.excel_tracker.log_application", side_effect=PermissionError("File locked by Excel.exe")):
        flushed = worker.flush_sync()
        assert flushed == 0
        # The record MUST be retained in queue!
        assert worker.pending_count == 1
        assert "locked by an external process" in worker.last_error

    # Now simulate Excel lock released
    with patch("app.services.excel_tracker.excel_tracker.log_application") as mock_log:
        flushed = worker.flush_sync()
        assert flushed == 1
        assert worker.pending_count == 0
        mock_log.assert_called_once_with(rec1)
