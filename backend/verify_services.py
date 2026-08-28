import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.models.job import JobApplicationRecord, ApplicationStatus
from app.services.excel_tracker import excel_tracker
from app.services.resume_parser import resume_parser_service

def test_excel():
    print("Testing Excel Tracker...")
    test_record = JobApplicationRecord(
        platform="LinkedIn",
        job_title="Full Stack Developer",
        company="Antigravity Technologies",
        job_url="https://www.linkedin.com/jobs/view/999999",
        status=ApplicationStatus.SUCCESS,
        notes="Applied via Easy Apply"
    )
    excel_tracker.log_application(test_record)
    
    # Check duplicate
    assert excel_tracker.is_already_applied("https://www.linkedin.com/jobs/view/999999") == True
    print("[OK] Duplicate URL check verified.")

    # Check stats
    stats = excel_tracker.get_statistics()
    print("[OK] Excel Stats:", stats)
    assert stats["total_applications"] >= 1
    print("[OK] Excel Tracker test passed!")

def test_pdf_extraction():
    print("\nTesting PDF Resume Extraction...")
    workspace_root = Path(__file__).resolve().parent.parent
    pdf_files = list(workspace_root.glob("*.pdf"))
    if pdf_files:
        pdf_path = pdf_files[0]
        print(f"Reading {pdf_path.name}...")
        text = resume_parser_service.extract_text_from_pdf(pdf_path)
        print(f"[OK] Successfully extracted {len(text)} characters of text from PDF.")
        print("Preview (first 150 chars):", repr(text[:150]))
    else:
        print("No sample PDF found in workspace.")

if __name__ == "__main__":
    test_excel()
    test_pdf_extraction()
    print("\n[SUCCESS] All services verification tests passed successfully!")
