"""
Relational Persistence & Dual-Write Synchronization Service.
Persists application states to PostgreSQL (autoapply_db) while synchronizing Excel exports.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_

from app.core.database import SessionLocal, init_db, check_db_connection
from app.core.logger import logger
from app.models.db_models import (
    DBJobApplication,
    DBApplicationAttempt,
    DBRecruiterContact,
    DBOutreachMessage,
    DBInterventionTicket
)
from app.models.job import JobApplicationRecord, ApplicationStatus


class PersistenceService:
    """Enterprise persistence service managing PostgreSQL relational storage and dual-write to Excel."""

    def __init__(self):
        self._initialized = False

    def initialize(self):
        """Ensure database tables exist and sync initial records from Excel if table is empty."""
        if self._initialized:
            return
        try:
            if not check_db_connection():
                logger.warning("[Persistence] Database not accessible; running in degraded mode.")
                return

            init_db()
            self._sync_existing_excel_records()
            self._initialized = True
            logger.info("[Persistence] Relational database persistence initialized.")
        except Exception as e:
            logger.error(f"[Persistence] Error initializing database: {e}")

    def _sync_existing_excel_records(self):
        """Seed initial records from existing Excel spreadsheet if database table is empty."""
        from app.services.excel_tracker import excel_tracker

        with SessionLocal() as db:
            count = db.query(DBJobApplication).count()
            if count > 0:
                logger.info(f"[Persistence] Database already contains {count} application records. Skipping seed.")
                return

            records = excel_tracker.records.values()
            if not records:
                return

            logger.info(f"[Persistence] Seeding {len(records)} existing applications from Excel to PostgreSQL...")
            seeded = 0
            for rec in records:
                try:
                    dt = datetime.utcnow()
                    if rec.timestamp:
                        try:
                            dt = datetime.strptime(rec.timestamp, "%Y-%m-%d %H:%M:%S")
                        except Exception:
                            dt = datetime.utcnow()

                    app_entry = DBJobApplication(
                        timestamp=dt,
                        platform=rec.platform or "Unknown",
                        job_title=rec.job_title or "Software Engineer",
                        company=rec.company or "Company",
                        job_url=rec.job_url,
                        job_id=rec.job_id,
                        status=rec.status or "Discovered",
                        applied_date=rec.applied_date or date.today().isoformat(),
                        match_score=float(rec.match_score) if rec.match_score else 0.0,
                        job_quality_score=float(rec.job_quality_score) if rec.job_quality_score else 0.0,
                        priority_tier=rec.priority_tier or "STANDARD",
                        salary_raw=rec.salary_raw,
                        location_raw=rec.location_raw,
                        experience_raw=rec.experience_raw,
                        hr_email=rec.hr_email,
                        hr_name=rec.hr_name,
                        hr_phone=rec.hr_phone,
                        reason_code=rec.reason_code,
                        notes=rec.notes
                    )
                    db.add(app_entry)
                    seeded += 1
                except Exception as e:
                    logger.debug(f"[Persistence] Error seeding record {rec.job_url}: {e}")

            db.commit()
            logger.info(f"[Persistence] Successfully seeded {seeded} records to PostgreSQL.")

    def save_or_update_application(self, record: JobApplicationRecord) -> Optional[DBJobApplication]:
        """Upsert application record into PostgreSQL and sync Excel export."""
        from app.services.excel_tracker import excel_tracker

        # 1. Update Excel Tracker memory and workbook
        excel_tracker.log_application(record)

        # 2. Upsert in PostgreSQL
        try:
            with SessionLocal() as db:
                existing = db.query(DBJobApplication).filter(DBJobApplication.job_url == record.job_url).first()

                dt = datetime.utcnow()
                if record.timestamp:
                    try:
                        dt = datetime.strptime(record.timestamp, "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        dt = datetime.utcnow()

                status_str = record.status.value if hasattr(record.status, "value") else str(record.status)
                match_sc = float(record.match_score) if getattr(record, "match_score", None) is not None else 0.0
                quality_sc = float(record.job_quality_score) if getattr(record, "job_quality_score", None) is not None else 0.0

                if existing:
                    existing.status = status_str
                    existing.applied_date = getattr(record, "applied_date", None) or existing.applied_date
                    existing.job_title = getattr(record, "job_title", None) or existing.job_title
                    existing.company = getattr(record, "company", None) or existing.company
                    existing.job_id = getattr(record, "job_id", None) or existing.job_id
                    existing.match_score = match_sc or existing.match_score
                    existing.job_quality_score = quality_sc or existing.job_quality_score
                    existing.priority_tier = getattr(record, "priority_tier", None) or existing.priority_tier
                    existing.notes = getattr(record, "notes", None) or existing.notes
                    existing.reason_code = getattr(record, "reason_code", None) or existing.reason_code
                    if getattr(record, "hr_email", None):
                        existing.hr_email = record.hr_email
                    if getattr(record, "hr_name", None):
                        existing.hr_name = record.hr_name
                    elif getattr(record, "recruiter_name", None):
                        existing.hr_name = record.recruiter_name
                    if getattr(record, "hr_phone", None):
                        existing.hr_phone = record.hr_phone

                    db.commit()
                    db.refresh(existing)
                    return existing
                else:
                    new_app = DBJobApplication(
                        timestamp=dt,
                        platform=getattr(record, "platform", "Unknown"),
                        job_title=getattr(record, "job_title", "Software Engineer"),
                        company=getattr(record, "company", "Company"),
                        job_url=record.job_url,
                        job_id=getattr(record, "job_id", None),
                        status=status_str,
                        applied_date=getattr(record, "applied_date", None) or date.today().isoformat(),
                        match_score=match_sc,
                        job_quality_score=quality_sc,
                        priority_tier=getattr(record, "priority_tier", "STANDARD"),
                        salary_raw=getattr(record, "salary_raw", None),
                        location_raw=getattr(record, "location_raw", None),
                        experience_raw=getattr(record, "experience_raw", None),
                        hr_email=getattr(record, "hr_email", None),
                        hr_name=getattr(record, "hr_name", None) or getattr(record, "recruiter_name", None),
                        hr_phone=getattr(record, "hr_phone", None),
                        reason_code=getattr(record, "reason_code", None),
                        notes=getattr(record, "notes", "")
                    )
                    db.add(new_app)
                    db.commit()
                    db.refresh(new_app)
                    return new_app
        except Exception as e:
            logger.error(f"[Persistence] Failed to persist job {record.job_url} to database: {e}")
            return None

    def record_attempt(
        self,
        job_url: str,
        status: str,
        attempt_number: int = 1,
        screenshot_path: Optional[str] = None,
        error_message: Optional[str] = None,
        duration_seconds: Optional[float] = None
    ) -> Optional[DBApplicationAttempt]:
        """Record an automated submission attempt with diagnostics."""
        try:
            with SessionLocal() as db:
                app_entry = db.query(DBJobApplication).filter(DBJobApplication.job_url == job_url).first()
                if not app_entry:
                    return None

                attempt = DBApplicationAttempt(
                    application_id=app_entry.id,
                    attempt_number=attempt_number,
                    timestamp=datetime.utcnow(),
                    status=status,
                    screenshot_path=screenshot_path,
                    error_message=error_message,
                    duration_seconds=duration_seconds
                )
                db.add(attempt)
                db.commit()
                db.refresh(attempt)
                return attempt
        except Exception as e:
            logger.error(f"[Persistence] Failed to record attempt for {job_url}: {e}")
            return None

    def create_intervention_ticket(
        self,
        job_url: str,
        job_title: str,
        company: str,
        ticket_type: str,
        notes: Optional[str] = None
    ) -> Optional[DBInterventionTicket]:
        """Create a trackable intervention item in the database."""
        try:
            with SessionLocal() as db:
                ticket = DBInterventionTicket(
                    job_url=job_url,
                    job_title=job_title,
                    company=company,
                    ticket_type=ticket_type,
                    status="OPEN",
                    notes=notes,
                    created_at=datetime.utcnow()
                )
                db.add(ticket)
                db.commit()
                db.refresh(ticket)
                return ticket
        except Exception as e:
            logger.error(f"[Persistence] Failed to create intervention ticket: {e}")
            return None

    def get_applications(
        self,
        limit: int = 200,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve paginated and filtered applications from PostgreSQL."""
        try:
            with SessionLocal() as db:
                query = db.query(DBJobApplication)
                if platform and platform != "ALL":
                    query = query.filter(DBJobApplication.platform == platform)
                if status and status != "ALL":
                    if status == "SUCCESS":
                        query = query.filter(or_(
                            DBJobApplication.status.ilike("%success%"),
                            DBJobApplication.status.ilike("%applied%")
                        ))
                    elif status == "FAILED":
                        query = query.filter(DBJobApplication.status.ilike("%failed%"))
                    elif status == "MANUAL":
                        query = query.filter(or_(
                            DBJobApplication.status.ilike("%manual%"),
                            DBJobApplication.status.ilike("%review%")
                        ))
                    else:
                        query = query.filter(DBJobApplication.status == status)

                if search and search.strip():
                    term = f"%{search.strip()}%"
                    query = query.filter(or_(
                        DBJobApplication.job_title.ilike(term),
                        DBJobApplication.company.ilike(term),
                        DBJobApplication.notes.ilike(term)
                    ))

                results = query.order_by(desc(DBJobApplication.timestamp)).limit(limit).all()
                return [
                    {
                        "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M:%S") if r.timestamp else "",
                        "platform": r.platform,
                        "job_title": r.job_title,
                        "company": r.company,
                        "job_url": r.job_url,
                        "job_id": r.job_id,
                        "status": r.status,
                        "applied_date": r.applied_date,
                        "match_score": r.match_score,
                        "job_quality_score": r.job_quality_score,
                        "priority_tier": r.priority_tier,
                        "salary_raw": r.salary_raw,
                        "location_raw": r.location_raw,
                        "experience_raw": r.experience_raw,
                        "hr_email": r.hr_email,
                        "hr_name": r.hr_name,
                        "hr_phone": r.hr_phone,
                        "reason_code": r.reason_code,
                        "notes": r.notes
                    }
                    for r in results
                ]
        except Exception as e:
            logger.error(f"[Persistence] Query failed, falling back to Excel tracker: {e}")
            from app.services.excel_tracker import excel_tracker
            return excel_tracker.get_all_records(limit=limit)

    def get_statistics(self) -> Dict[str, Any]:
        """Aggregate application performance metrics from database."""
        try:
            with SessionLocal() as db:
                total = db.query(DBJobApplication).count()
                success = db.query(DBJobApplication).filter(or_(
                    DBJobApplication.status.ilike("%success%"),
                    DBJobApplication.status.ilike("%applied%")
                )).count()
                failed = db.query(DBJobApplication).filter(DBJobApplication.status.ilike("%failed%")).count()
                manual = db.query(DBJobApplication).filter(or_(
                    DBJobApplication.status.ilike("%manual%"),
                    DBJobApplication.status.ilike("%review%")
                )).count()

                # Platform breakdown
                platforms_raw = db.query(DBJobApplication.platform, func.count(DBJobApplication.id)).group_by(DBJobApplication.platform).all()
                by_platform = {p: count for p, count in platforms_raw}

                return {
                    "total_applications": total,
                    "success_count": success,
                    "failed_count": failed,
                    "manual_review_count": manual,
                    "success_rate": round((success / total * 100), 1) if total > 0 else 0.0,
                    "by_platform": by_platform
                }
        except Exception as e:
            logger.error(f"[Persistence] Failed to compute stats from database: {e}")
            from app.services.excel_tracker import excel_tracker
            return excel_tracker.get_statistics()


persistence_service = PersistenceService()
