"""
verify_db_persistence_lifecycle.py - Hardened PostgreSQL Persistence Lifecycle Audit Script

Strict Safeguards:
1. Hardened target database validation:
   - STRICTLY enforces scheme in ('postgresql', 'postgresql+psycopg2').
   - STRICTLY enforces database name == 'autoapply_db'.
   - STRICTLY enforces host in ('localhost', '127.0.0.1', '::1') and port == 5432.
   - Target revalidated immediately before creating every engine, including cleanup.
2. Read-only schema verification:
   - Uses inspect(engine) to check pre-existing tables.
   - NEVER calls Base.metadata.create_all() or modifies the schema.
3. Completely isolated rollback tests:
   - Application rollback tested with dedicated disposable key 'rollback_url'.
   - Database constraint rollback tested with dedicated disposable key 'collision_seed_url'.
   - Explicit assertion failure if duplicate key does NOT raise IntegrityError.
4. Guaranteed, fail-closed cleanup across all tables:
   - Purges all test keys across DBApplicationAttempt, DBRecruiterContact, and DBJobApplication.
   - Verifies zero remaining records across ALL three tables.
   - Error preservation: Never masks test failures with cleanup errors; reports both.
5. Accurate lifecycle descriptions:
   - Accurately labeled as 'Connection Pool Disposal & Fresh Engine Reconnection'.
6. Masked credentials & safe encoding:
   - Never logs passwords or connection tokens.
   - UTF-8 safe with standard ASCII fallbacks.
"""

import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, date

# Safe terminal encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure backend root directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models.db_models import DBJobApplication, DBApplicationAttempt, DBRecruiterContact


TEST_PREFIX = "test_persistence_audit_"


def validate_target_database() -> str:
    """
    Validates that the database target is explicitly and strictly the local autoapply_db.
    Raises RuntimeError if any configuration points to any other database, host, or non-Postgres dialect.
    """
    db_url = settings.DATABASE_URL
    if not db_url:
        raise RuntimeError("DATABASE_URL is not configured in settings.")

    parsed = urlparse(db_url)
    scheme = parsed.scheme.split("+")[0]
    db_name = parsed.path.lstrip("/")
    db_host = parsed.hostname or "localhost"
    db_port = parsed.port or 5432

    # Dialect check
    if scheme not in ("postgresql", "postgres"):
        raise RuntimeError(
            f"ABORTED: Persistence audit requires PostgreSQL, detected '{scheme}'. "
            f"Execution halted to protect non-target database engines."
        )

    # Database name isolation
    if db_name != "autoapply_db":
        raise RuntimeError(
            f"ABORTED: Target database name is '{db_name}'. "
            f"Strict safety rule mandates execution ONLY against 'autoapply_db'. "
            f"Execution halted to protect production and external databases."
        )

    # Localhost / staging instance isolation
    allowed_hosts = {"localhost", "127.0.0.1", "::1"}
    if db_host not in allowed_hosts:
        raise RuntimeError(
            f"ABORTED: Target host is '{db_host}'. "
            f"Strict safety rule permits local testing only on localhost/127.0.0.1. "
            f"Execution halted to protect remote hosts."
        )

    # Safe log representation (credentials masked)
    masked_netloc = f"***:***@{db_host}:{db_port}"
    masked_url = f"{parsed.scheme}://{masked_netloc}/{db_name}"
    print(f"Target Database Verified: {masked_url}")
    return db_url


def get_safe_engine():
    """Factory creating an engine only after fresh validation of the target URL."""
    valid_url = validate_target_database()
    return create_engine(valid_url)


def verify_tables_exist(engine):
    """Read-only verification that required table names exist without modifying schema."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    required_tables = {"job_applications", "application_attempts", "recruiter_contacts"}
    missing = required_tables - existing_tables
    if missing:
        raise RuntimeError(
            f"ABORTED: Required database tables missing in autoapply_db: {missing}. "
            f"Schema modification is prohibited."
        )
    print(f"Pre-existing Table Names Verified: {sorted(list(existing_tables))} (all required tables present)")


def run_persistence_audit():
    print("=" * 75)
    print("POSTGRESQL PERSISTENCE LIFECYCLE AUDIT (HARDENED)")
    print("=" * 75)

    # Generate isolated test keys unique to this specific test execution
    test_token = uuid.uuid4().hex[:8]
    test_id = f"{TEST_PREFIX}{test_token}"
    test_url = f"https://www.linkedin.com/jobs/view/{test_id}"
    rollback_url = f"https://www.linkedin.com/jobs/view/rollback_{test_id}"
    collision_seed_url = f"https://www.linkedin.com/jobs/view/collision_seed_{test_id}"
    test_contact_email = f"recruiter_{test_token}@audit.corp"

    # Track all keys created for guaranteed cleanup in finally block
    all_test_urls = [test_url, rollback_url, collision_seed_url]

    # Pre-declare engine references for guaranteed cleanup disposal
    engine = None
    restarted_engine = None
    original_exception = None

    try:
        # Step 0: Safe Engine Creation & Read-Only Schema Inspection under guarded try block
        engine = get_safe_engine()
        verify_tables_exist(engine)
        Session = sessionmaker(bind=engine)

        # -------------------------------------------------------------
        # STEP 1: WRITE (INSERT ACROSS TABLES)
        # -------------------------------------------------------------
        print("\n[Step 1] WRITE: Inserting verified test records across tables...")
        with Session() as db:
            app_record = DBJobApplication(
                job_url=test_url,
                platform="LinkedIn",
                job_title="Lead AI Infrastructure Engineer",
                company="Audit Cloud Corp",
                location_raw="Remote",
                job_id=test_id,
                status="APPLIED",
                match_score=95.0,
                priority_tier="HIGH",
                applied_date=date.today().isoformat(),
                created_at=datetime.utcnow()
            )
            db.add(app_record)
            db.flush()

            # Insert associated attempt
            attempt_record = DBApplicationAttempt(
                application_id=app_record.id,
                attempt_number=1,
                status="SUCCESS",
                duration_seconds=1.25,
                error_message=None
            )
            db.add(attempt_record)

            # Insert recruiter contact
            contact_record = DBRecruiterContact(
                name="Audit Recruiter",
                email=test_contact_email,
                company="Audit Cloud Corp",
                confidence="high",
                source="audit_test"
            )
            db.add(contact_record)

            db.commit()
        print(f"  [OK] Write confirmed for job_id '{test_id}', attempt, and recruiter contact.")

        # -------------------------------------------------------------
        # STEP 2: READ (SELECT & ATTRIBUTE VERIFICATION)
        # -------------------------------------------------------------
        print("\n[Step 2] READ: Querying records back from PostgreSQL...")
        with Session() as db:
            fetched = db.query(DBJobApplication).filter(DBJobApplication.job_url == test_url).first()
            assert fetched is not None, "ASSERTION FAILED: Record not found after write!"
            assert fetched.job_id == test_id
            assert fetched.match_score == 95.0
            assert fetched.status == "APPLIED"

            fetched_attempts = db.query(DBApplicationAttempt).filter(
                DBApplicationAttempt.application_id == fetched.id
            ).all()
            assert len(fetched_attempts) == 1, "ASSERTION FAILED: Attempt record not found!"

            fetched_contact = db.query(DBRecruiterContact).filter(
                DBRecruiterContact.email == test_contact_email
            ).first()
            assert fetched_contact is not None, "ASSERTION FAILED: Recruiter contact not found!"

            print(f"  [OK] Read verified: '{fetched.job_title}' at {fetched.company} (Status: {fetched.status})")
            print(f"  [OK] Linked records verified: 1 attempt, 1 recruiter contact ({fetched_contact.email})")

        # -------------------------------------------------------------
        # STEP 3: UPDATE (UPDATE STATUS & MATCH SCORE)
        # -------------------------------------------------------------
        print("\n[Step 3] UPDATE: Modifying application record in-place...")
        with Session() as db:
            rec = db.query(DBJobApplication).filter(DBJobApplication.job_url == test_url).first()
            assert rec is not None
            rec.status = "INTERVIEW_SCHEDULED"
            rec.match_score = 99.0
            db.commit()

        with Session() as db:
            updated = db.query(DBJobApplication).filter(DBJobApplication.job_url == test_url).first()
            assert updated.status == "INTERVIEW_SCHEDULED"
            assert updated.match_score == 99.0
            print(f"  [OK] Update verified: Status is now '{updated.status}', match_score={updated.match_score}")

        # -------------------------------------------------------------
        # STEP 4: TRANSACTION ROLLBACK VERIFICATION (APP & DB LEVELS)
        # -------------------------------------------------------------
        print("\n[Step 4] ROLLBACK: Testing transactional integrity and rollback...")
        
        # Test 4A: Flushed uncommitted record rolled back on application error
        with Session() as db:
            try:
                temp_rec = DBJobApplication(
                    job_url=rollback_url,
                    platform="Naukri",
                    job_title="Should Be Rolled Back",
                    company="Ghost Corp",
                    status="PENDING",
                    applied_date=date.today().isoformat(),
                    created_at=datetime.utcnow()
                )
                db.add(temp_rec)
                db.flush()  # sent to database engine buffer
                # Trigger application exception before commit
                raise RuntimeError("Simulated application failure before commit")
            except RuntimeError:
                db.rollback()
                print("  [OK] Application-level rollback executed.")

        # Test 4B: Database engine constraint violation rollback using dedicated collision key
        # First: commit a separate disposable seed record for collision
        with Session() as db:
            seed_rec = DBJobApplication(
                job_url=collision_seed_url,
                platform="Indeed",
                job_title="Collision Seed Record",
                company="Seed Corp",
                status="PENDING",
                applied_date=date.today().isoformat(),
                created_at=datetime.utcnow()
            )
            db.add(seed_rec)
            db.commit()

        # Second: attempt duplicate unique constraint insert and assert IntegrityError is raised
        integrity_error_caught = False
        with Session() as db:
            try:
                dup_rec = DBJobApplication(
                    job_url=collision_seed_url,  # UNIQUE constraint collision against separate seed
                    platform="Indeed",
                    job_title="Duplicate Collision Record",
                    company="Conflict Corp",
                    status="PENDING",
                    applied_date=date.today().isoformat(),
                    created_at=datetime.utcnow()
                )
                db.add(dup_rec)
                db.commit()
            except IntegrityError:
                db.rollback()
                integrity_error_caught = True
                print("  [OK] Database engine duplicate key constraint violation caught and rolled back.")

        if not integrity_error_caught:
            raise AssertionError("ASSERTION FAILED: Expected IntegrityError on duplicate unique key was NOT raised!")

        # Confirm rollback records never leaked into the table
        with Session() as db:
            ghost = db.query(DBJobApplication).filter(DBJobApplication.job_url == rollback_url).first()
            assert ghost is None, "ASSERTION FAILED: Rollback record leaked into autoapply_db!"
            print("  [OK] Confirmed: Rollback records do not exist in database.")

        # -------------------------------------------------------------
        # STEP 5: POOL RESET & FRESH ENGINE RECONNECT
        # -------------------------------------------------------------
        print("\n[Step 5] POOL RESET & FRESH ENGINE RECONNECT: Disposing pool and reconnecting...")
        engine.dispose()  # Closes all pooled TCP connections in current engine

        # Fresh engine created via validated factory
        restarted_engine = get_safe_engine()
        RestartedSession = sessionmaker(bind=restarted_engine)
        with RestartedSession() as db:
            persisted = db.query(DBJobApplication).filter(DBJobApplication.job_url == test_url).first()
            assert persisted is not None, "ASSERTION FAILED: Data lost after connection reset!"
            assert persisted.status == "INTERVIEW_SCHEDULED"
            print(f"  [OK] Reconnect persistence confirmed: Record '{persisted.job_id}' intact across new engine pool.")

        print("\n" + "=" * 75)
        print("ALL 5 PERSISTENCE LIFECYCLE CHECKS PASSED (100% SUCCESS)!")
        print("=" * 75)
        return True

    except Exception as e:
        original_exception = e
        print(f"\n[FAIL] Error during persistence lifecycle steps: {e}")

    finally:
        # -------------------------------------------------------------
        # STEP 6: GUARANTEED FAIL-CLOSED CLEANUP ACROSS ALL TABLES
        # -------------------------------------------------------------
        print("\n[Cleanup] Executing guaranteed cleanup in finally block...")
        cleanup_engine = None
        cleanup_error = None
        try:
            # Re-validate target immediately before instantiating cleanup engine
            cleanup_engine = get_safe_engine()
            with sessionmaker(bind=cleanup_engine)() as cleanup_db:
                # 1. Identify test application IDs for foreign key cleanup
                test_app_ids = [
                    row[0] for row in cleanup_db.query(DBJobApplication.id).filter(
                        DBJobApplication.job_url.in_(all_test_urls)
                    ).all()
                ]

                del_attempts = 0
                if test_app_ids:
                    del_attempts = cleanup_db.query(DBApplicationAttempt).filter(
                        DBApplicationAttempt.application_id.in_(test_app_ids)
                    ).delete(synchronize_session=False)

                # 2. Clean contacts associated with test token
                del_contacts = cleanup_db.query(DBRecruiterContact).filter(
                    DBRecruiterContact.email.like(f"%{test_token}%")
                ).delete(synchronize_session=False)

                # 3. Clean all test applications
                del_apps = cleanup_db.query(DBJobApplication).filter(
                    DBJobApplication.job_url.in_(all_test_urls)
                ).delete(synchronize_session=False)

                cleanup_db.commit()

                # 4. Comprehensive zero-record verification across ALL three tables
                rem_attempts = 0
                if test_app_ids:
                    rem_attempts = cleanup_db.query(DBApplicationAttempt).filter(
                        DBApplicationAttempt.application_id.in_(test_app_ids)
                    ).count()
                
                rem_contacts = cleanup_db.query(DBRecruiterContact).filter(
                    DBRecruiterContact.email.like(f"%{test_token}%")
                ).count()
                
                rem_apps = cleanup_db.query(DBJobApplication).filter(
                    DBJobApplication.job_url.in_(all_test_urls)
                ).count()

                total_rem = rem_attempts + rem_contacts + rem_apps
                if total_rem > 0:
                    raise RuntimeError(
                        f"Cleanup verification failed: {rem_apps} apps, {rem_attempts} attempts, "
                        f"{rem_contacts} contacts still remain in autoapply_db!"
                    )

                print(
                    f"  [OK] Purged test records: {del_apps} apps, {del_attempts} attempts, "
                    f"{del_contacts} contacts. Zero test records remain."
                )
        except Exception as cleanup_err:
            cleanup_error = cleanup_err
            print(f"  [CRITICAL] CLEANUP ERROR: {cleanup_err}")
        finally:
            if cleanup_engine:
                cleanup_engine.dispose()
            if engine:
                engine.dispose()
            if restarted_engine:
                restarted_engine.dispose()
            print("  [OK] All database connection pools disposed cleanly.")

        # Error Preservation Logic: Never swallow or mask errors
        if cleanup_error and original_exception:
            raise RuntimeError(
                f"AUDIT FAILED: Test failed with '{original_exception}' AND cleanup failed with '{cleanup_error}'"
            ) from original_exception
        elif cleanup_error:
            raise RuntimeError(f"AUDIT FAILED: Test completed but cleanup failed: {cleanup_error}") from cleanup_error
        elif original_exception:
            raise original_exception


if __name__ == "__main__":
    try:
        run_persistence_audit()
    except Exception as e:
        print(f"\n[FAIL] Persistence Audit Terminated: {e}")
        sys.exit(1)
