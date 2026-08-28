import os
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from app.core.config import settings
from app.core.logger import logger
from app.models.job import JobApplicationRecord, ApplicationStatus

class ExcelTracker:
    COLUMNS = [
        "Timestamp",
        "Platform",
        "Job Title",
        "Company",
        "Job URL",
        "Status",
        "Applied Date",
        "Notes"
    ]

    def __init__(self, file_path: Path = settings.EXCEL_FILE_PATH):
        self.file_path = file_path
        self._lock = threading.Lock()
        self._applied_urls: Set[str] = set()
        self._ensure_workbook_exists()
        self._load_existing_urls()

    def _ensure_workbook_exists(self) -> None:
        """Create workbook with styled header if it does not exist."""
        if not self.file_path.exists():
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Applications"
            
            # Header styling
            header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
            header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)

            ws.append(self.COLUMNS)
            ws.row_dimensions[1].height = 28

            for col_idx in range(1, len(self.COLUMNS) + 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = align_center

            # Set column widths
            column_widths = {
                1: 20, # Timestamp
                2: 14, # Platform
                3: 30, # Job Title
                4: 25, # Company
                5: 45, # Job URL
                6: 18, # Status
                7: 15, # Applied Date
                8: 35  # Notes
            }
            for col_idx, width in column_widths.items():
                col_letter = get_column_letter(col_idx)
                ws.column_dimensions[col_letter].width = width

            wb.save(str(self.file_path))
            logger.info(f"Initialized job application tracking workbook at {self.file_path}")

    def _load_existing_urls(self) -> None:
        """Cache all previously applied job URLs to quickly prevent duplicates."""
        if not self.file_path.exists():
            return
        try:
            wb = openpyxl.load_workbook(str(self.file_path), read_only=True)
            ws = wb.active
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row and len(row) >= 5 and row[4]:
                    url = str(row[4]).strip()
                    if url:
                        self._applied_urls.add(url)
            wb.close()
            logger.info(f"Loaded {len(self._applied_urls)} previously tracked job URLs from Excel.")
        except Exception as e:
            logger.error(f"Error loading existing URLs from Excel: {e}")

    def is_already_applied(self, job_url: str) -> bool:
        """Check if job URL has already been recorded."""
        if not job_url:
            return False
        clean_url = job_url.strip().split("?")[0] # normalize query params
        for applied in self._applied_urls:
            if applied.strip().split("?")[0] == clean_url:
                return True
        return False

    def log_application(self, record: JobApplicationRecord) -> None:
        """Thread-safely append a new job application record to the Excel sheet."""
        with self._lock:
            try:
                wb = openpyxl.load_workbook(str(self.file_path))
                ws = wb.active

                row_values = [
                    record.timestamp,
                    record.platform,
                    record.job_title,
                    record.company,
                    record.job_url,
                    record.status.value if isinstance(record.status, ApplicationStatus) else str(record.status),
                    record.applied_date,
                    record.notes
                ]

                ws.append(row_values)
                new_row_idx = ws.max_row
                ws.row_dimensions[new_row_idx].height = 20

                # Style row based on status
                status_color = "000000"
                fill_color = None
                status_str = str(record.status)
                if ApplicationStatus.SUCCESS.value in status_str or "Success" in status_str:
                    fill_color = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid") # light green
                elif ApplicationStatus.FAILED.value in status_str or "Failed" in status_str:
                    fill_color = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid") # light red
                elif ApplicationStatus.MANUAL_REVIEW_NEEDED.value in status_str:
                    fill_color = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid") # light yellow

                border_thin = Border(
                    left=Side(style='thin', color='E2E8F0'),
                    right=Side(style='thin', color='E2E8F0'),
                    top=Side(style='thin', color='E2E8F0'),
                    bottom=Side(style='thin', color='E2E8F0')
                )

                for col_idx in range(1, len(self.COLUMNS) + 1):
                    cell = ws.cell(row=new_row_idx, column=col_idx)
                    cell.font = Font(name="Calibri", size=10)
                    cell.border = border_thin
                    cell.alignment = Alignment(vertical="center")
                    if fill_color:
                        cell.fill = fill_color

                wb.save(str(self.file_path))
                if record.job_url:
                    self._applied_urls.add(record.job_url.strip())
                logger.info(f"Recorded application to Excel: {record.job_title} at {record.company} [{record.status}]")
            except Exception as e:
                logger.error(f"Failed to log application to Excel: {e}")

    def get_all_records(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Retrieve application records as a list of dictionaries for API/UI."""
        records = []
        if not self.file_path.exists():
            return records

        with self._lock:
            try:
                wb = openpyxl.load_workbook(str(self.file_path), read_only=True)
                ws = wb.active
                rows = list(ws.iter_rows(min_row=2, values_only=True))
                wb.close()

                # Return recent first
                for row in reversed(rows):
                    if not row or not any(row):
                        continue
                    records.append({
                        "timestamp": row[0] or "",
                        "platform": row[1] or "",
                        "job_title": row[2] or "",
                        "company": row[3] or "",
                        "job_url": row[4] or "",
                        "status": row[5] or "",
                        "applied_date": row[6] or "",
                        "notes": row[7] if len(row) > 7 and row[7] else ""
                    })
                    if len(records) >= limit:
                        break
            except Exception as e:
                logger.error(f"Error reading applications from Excel: {e}")

        return records

    def get_statistics(self) -> Dict[str, Any]:
        """Compute summary statistics for dashboard analytics."""
        records = self.get_all_records(limit=2000)
        total = len(records)
        success = 0
        failed = 0
        manual = 0
        platforms: Dict[str, int] = {}

        for r in records:
            st = str(r.get("status", ""))
            plat = str(r.get("platform", "Unknown"))
            platforms[plat] = platforms.get(plat, 0) + 1

            if "Success" in st or "Applied" in st or "Dry Run" in st:
                success += 1
            elif "Failed" in st:
                failed += 1
            elif "Manual" in st:
                manual += 1

        return {
            "total_applications": total,
            "success_count": success,
            "failed_count": failed,
            "manual_review_count": manual,
            "platform_breakdown": platforms
        }

excel_tracker = ExcelTracker()
