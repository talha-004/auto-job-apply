# AutoApplyJobs — Implementation Roadmap & File Mapping

> **Document Type:** Phase 0 Implementation Deliverable  
> **Repository:** `d:\Coding\repo\AutoApplyJobs`  
> **Release Strategy:** 3 Major Releases (Phases 0–15)  

---

## 1. Release Milestones & Phase Schedule

The engineering execution is structured into three progressive releases:

```
Release 1: Reliable AutoApply (Phases 0–5)
├── Phase 0: Repository Audit & Planning [COMPLETED]
├── Phase 1: Candidate Intelligence & QA Vault
├── Phase 2: Hybrid Job Discovery Engine
├── Phase 3: Job Intelligence & Evaluation Engine
├── Phase 4: Application Orchestration Engine
└── Phase 5: Universal Application Adapter System

Release 2: Intelligent AutoApply (Phases 6–10)
├── Phase 6: AI Resume Tailoring Engine
├── Phase 7: AI Screening Question Engine
├── Phase 8: Recruiter Intelligence & Outreach
├── Phase 9: Persistent Browser & Session Management
└── Phase 10: Background Scheduler & Autonomous Execution

Release 3: Production AutoApply (Phases 11–15)
├── Phase 11: Dashboard Enhancement & Intervention Center
├── Phase 12: Application Tracking & Database Persistence
├── Phase 13: Notifications & Recruiter Response Monitoring
├── Phase 14: Security Hardening & Failure Recovery
└── Phase 15: Full Regression Testing & Quality Assurance
```

---

## 2. Detailed Task-to-File Mapping

### Release 1: Reliable AutoApply

#### Phase 1: Candidate Intelligence & QA Vault
* **Goal**: Single verified source of truth for candidate data and intelligent ATS question matching.
* **Target Files**:
  - `backend/app/models/job.py` [MODIFY]: Add `QAVault` model and extend `ResumeProfile` with strict fields (`notice_period_days`, `current_ctc_lpa`, `expected_ctc_lpa`, `work_authorization`, `require_sponsorship`, `willing_to_relocate`, etc.).
  - `backend/app/services/resume_parser.py` [MODIFY]: Improve PDF/DOCX section extraction and structure mapping.
  - `backend/app/services/qa_vault_service.py` [NEW]: Pre-mapped field matcher (`VAULT_FIELD_MAP`) inspired by `D:\Coding\auto\automation\form_autofiller.py` for deterministic form answering.
  - `backend/data/candidate_profile.json` [MODIFY]: Add full candidate `qa_vault` structure.
  - `backend/app/api/endpoints/resume.py` [MODIFY]: Add endpoints for QA Vault retrieval and updates (`GET /api/resume/vault`, `PUT /api/resume/vault`).
* **Dependencies**: None.
* **Testing Requirements**: Unit tests for QA Vault matching, schema validation, and missing field alerts.
* **Risks**: Ensuring backward compatibility with existing `candidate_profile.json` format.

#### Phase 2: Hybrid Job Discovery Engine
* **Goal**: Rapid multi-platform job discovery via HTTP guest endpoints without full browser overhead.
* **Target Files**:
  - `backend/requirements.txt` [MODIFY]: Add `python-jobspy>=1.1`.
  - `backend/app/models/job.py` [MODIFY]: Define standard `DiscoveredJob` normalized schema.
  - `backend/app/services/discovery/` [NEW]:
    - `base.py`: Provider interface (`JobDiscoveryProvider`).
    - `jobspy_provider.py`: Scrapes LinkedIn, Indeed, Glassdoor, and ZipRecruiter in parallel via HTTP.
    - `discovery_manager.py`: Coordinates providers, dedupes listings, and respects rate limits.
  - `backend/app/api/endpoints/bot.py` [MODIFY]: Add discovery trigger and status endpoints.
* **Dependencies**: Phase 1 schemas.
* **Testing Requirements**: Mock HTTP responses for discovery providers; verify schema normalization and deduplication.
* **Risks**: Rate limiting on guest endpoints; fallback to browser search when guest APIs are blocked.

#### Phase 3: Job Intelligence & Evaluation Engine
* **Goal**: Screen discovered jobs before initiating any browser session.
* **Target Files**:
  - `backend/app/services/match_scorer.py` [PRESERVE & EXTEND]: Keep 60/20/10/10 mathematical scoring. Add batch evaluation method.
  - `backend/app/services/job_quality_scorer.py` [PRESERVE & EXTEND]: Keep risk evaluation.
  - `backend/app/services/job_evaluator.py` [NEW]: Central evaluation coordinator combining match score, quality score, hard exclusion rules, and candidate preferences.
* **Dependencies**: Phase 1 (candidate profile) & Phase 2 (discovered jobs).
* **Testing Requirements**: Unit tests verifying hard disqualification rules (e.g. excluded tech stack, location mismatch) and score breakdown explainability.
* **Risks**: Overly aggressive filtering skipping viable jobs. Must support configurable thresholds in `SearchConfig`.

#### Phase 4: Application Orchestration Engine
* **Goal**: Central stateful workflow coordinator driving the complete job lifecycle.
* **Target Files**:
  - `backend/app/services/orchestrator.py` [NEW]: Central coordinator managing:
    `DISCOVERED -> EVALUATING -> ELIGIBLE -> PREPARING -> APPLYING -> SUBMITTED / FAILED / MANUAL_REVIEW`.
  - `backend/app/services/bot_manager.py` [REFACTOR]: Transition from procedural platform iteration to orchestrator-driven task dispatch.
  - `backend/app/models/job.py` [MODIFY]: Complete lifecycle state machine definitions.
* **Dependencies**: Phases 1, 2, 3.
* **Testing Requirements**: Mock job pipeline execution testing state transitions, checkpoint recovery, and pause/resume triggers.
* **Risks**: Thread/event-loop synchronization on Windows. Must retain `WindowsProactorEventLoopPolicy`.

#### Phase 5: Universal Application Adapter System
* **Goal**: Expand application automation beyond on-platform Easy Apply to standard external ATS systems.
* **Target Files**:
  - `backend/app/platforms/adapter_interface.py` [NEW]: Common `ApplicationAdapter` ABC (`detect`, `authenticate`, `extract_form`, `fill_form`, `submit`, `verify_submission`).
  - `backend/app/platforms/base.py` [MODIFY]: Adapt to `ApplicationAdapter` interface.
  - `backend/app/platforms/naukri.py` [MODIFY]: Conform to new adapter interface.
  - `backend/app/platforms/linkedin.py` [MODIFY]: Conform to new adapter interface.
  - `backend/app/platforms/indeed.py` [MODIFY]: Conform to new adapter interface.
  - `backend/app/platforms/external/` [NEW]:
    - `greenhouse.py`: Greenhouse board filler.
    - `lever.py`: Lever application filler.
    - `smartrecruiters.py`: SmartRecruiters filler.
* **Dependencies**: Phase 1 (QA Vault) & Phase 4 (Orchestrator).
* **Testing Requirements**: Mock HTML fixtures for Greenhouse, Lever, and LinkedIn Easy Apply modals; verify field mapping and submission detection.
* **Risks**: Complex custom ATS fields; safe fallback to `MANUAL_REVIEW_NEEDED` when unfamiliar validation blocks submission.

---

### Release 2: Intelligent AutoApply

#### Phase 6: AI Resume Tailoring Engine
* **Goal**: Generate ATS-compliant job-specific resumes matching job descriptions.
* **Target Files**:
  - `backend/requirements.txt` [MODIFY]: Add `reportlab>=4.0`.
  - `backend/app/services/resume_tailorer.py` [NEW]: Port and enhance ReportLab generator from `D:\Coding\auto\core\resume_exporter.py`. Tailors summary, top skills, and achievement bullets.
  - `backend/data/resumes/` [NEW DIR]: Versioned storage (`resumes/original/` and `resumes/tailored/{job_id}/`).
* **Dependencies**: Phase 1 (candidate profile) & Phase 3 (job evaluation).
* **Testing Requirements**: Verify PDF generation, text extractability, Unicode font handling, and zero fabrication of employment dates or degrees.
* **Risks**: ReportLab font availability on Linux/Docker environments. Use Unicode fallback fonts.

#### Phase 7: AI Screening Question Engine
* **Goal**: Answer screening questions accurately using QA Vault and verified candidate information.
* **Target Files**:
  - `backend/app/core/llm.py` [MODIFY]: Add multi-provider client interface (`Ollama`, `Gemini`, `DeepSeek`, `Groq`).
  - `backend/app/services/screening_service.py` [NEW]: Answering pipeline with provenance classification (`EXACT_VAULT`, `DERIVED`, `UNKNOWN`).
* **Dependencies**: Phase 1 (QA Vault).
* **Testing Requirements**: Unit tests with question classification fixtures verifying unknown sensitive questions trigger human intervention.
* **Risks**: LLM hallucination on numeric fields (e.g. salary). Hard-enforce QA Vault lookups before calling LLM.

#### Phase 8: Recruiter Intelligence & Outreach
* **Goal**: Extract recruiter contact information and automate direct cold email and WhatsApp preparation.
* **Target Files**:
  - `backend/app/platforms/naukri_helpers.py` [PRESERVE & EXTEND]: Reuse `extract_job_contacts`.
  - `backend/app/services/contact_extractor.py` [NEW]: Universal recruiter contact extractor across all platforms.
  - `backend/app/services/email_outreach_service.py` [NEW]: SMTP email sender with attachment support and draft generation, adapted from `D:\Coding\auto\core\email_smtp.py`.
  - `backend/app/models/job.py` [MODIFY]: Add `RecruiterContact` and `OutreachMessage` schemas.
* **Dependencies**: Phase 5 (adapters) & Phase 6 (tailored resumes).
* **Testing Requirements**: Mock SMTP server tests for email drafting, sending, and attachment delivery; test WhatsApp URL construction.
* **Risks**: Unsolicited email sending limits; require draft approval mode by default.

#### Phase 9: Persistent Browser & Session Management
* **Goal**: Maintain authenticated sessions across runs to prevent frequent logins and 2FA prompts.
* **Target Files**:
  - `backend/app/core/config.py` [MODIFY]: Add `BROWSER_USER_DATA_DIR` and `USE_PERSISTENT_CONTEXT`.
  - `backend/app/platforms/base.py` [MODIFY]: Support `browser_type.launch_persistent_context` with user data profile.
* **Dependencies**: Existing Playwright setup.
* **Testing Requirements**: Test session cookie validation and persistent context directory isolation.
* **Risks**: File locks on browser profile if user's main browser is open simultaneously. Provide clear documentation and graceful fallback.

#### Phase 10: Background Scheduler & Autonomous Execution
* **Goal**: Autonomous recurring execution without manual clicks.
* **Target Files**:
  - `backend/requirements.txt` [MODIFY]: Add `APScheduler>=3.10.4`.
  - `backend/app/services/scheduler.py` [NEW]: Daily cron scheduler for morning job hunt and Naukri headline refresh heartbeat.
  - `backend/app/api/endpoints/bot.py` [MODIFY]: Endpoints to configure and toggle scheduler.
* **Dependencies**: Phase 4 (Orchestrator).
* **Testing Requirements**: Fast-forward scheduler tests; verify daily cap enforcement and clean shutdown.
* **Risks**: Job overlap across scheduled runs; enforce mutex locking per candidate profile.

---

### Release 3: Production AutoApply

#### Phase 11: Dashboard Enhancement & Intervention Center
* **Goal**: Full visibility, live intervention handling, and configuration management.
* **Target Files**:
  - `frontend/src/components/InterventionCenter.jsx` [NEW]: Dedicated panel for CAPTCHA, 2FA, unknown questions, and email approvals.
  - `frontend/src/components/QAVaultEditor.jsx` [NEW]: Candidate QA Vault management interface.
  - `frontend/src/components/SchedulerSettings.jsx` [NEW]: Schedule configuration UI.
  - `frontend/src/components/JobApplicationsTable.jsx` [MODIFY]: Add outreach status, tailored resume download, and quick resolution buttons.
  - `frontend/src/App.jsx` [MODIFY]: Integrate new components into modern layout.
* **Dependencies**: Releases 1 and 2 backend endpoints.
* **Testing Requirements**: Frontend component tests, state sync verification via WebSocket, and error handling.
* **Risks**: UI clutter. Maintain existing glassmorphism aesthetic and clear visual hierarchy.

#### Phase 12: Application Tracking & Database Persistence
* **Goal**: SQLite relational persistence with Excel export synchronization.
* **Target Files**:
  - `backend/app/core/database.py` [NEW]: SQLAlchemy session factory and engine setup.
  - `backend/app/models/db_models.py` [MODIFY]: Extend models to cover jobs, applications, attempts, recruiter contacts, and interventions.
  - `backend/app/services/persistence_service.py` [NEW]: Dual-write service writing to SQLite as primary store and updating `job_applications.xlsx` asynchronously.
  - `backend/app/services/excel_tracker.py` [MODIFY]: Delegate state retrieval to database, functioning as export and reporting engine.
* **Dependencies**: All prior phases.
* **Testing Requirements**: Transactional integrity tests, migration script tests, and Excel export verification.
* **Risks**: Database access rule compliance. (All operations strictly user-approved).

#### Phase 13: Notifications & Recruiter Response Monitoring
* **Goal**: Proactive alerts on interview invites, assessment requests, and verified submissions.
* **Target Files**:
  - `backend/app/services/notification_service.py` [NEW]: Desktop / webhook / email notifications.
  - `backend/app/services/inbox_monitor.py` [NEW]: Optional IMAP/OAuth email response classifier.
* **Dependencies**: Phase 8 (outreach) & Phase 12 (persistence).
* **Testing Requirements**: Mock IMAP parsing tests for interview invitations and rejections.
* **Risks**: IMAP security; make inbox monitoring strictly opt-in.

#### Phase 14: Security Hardening & Failure Recovery
* **Goal**: Credential encryption, input sanitization, and graceful failure recovery.
* **Target Files**:
  - `backend/app/core/security.py` [NEW]: Credential encryption (`cryptography.fernet` or `keyring`).
  - `backend/app/core/logger.py` [MODIFY]: Redact credentials, tokens, and cookies from log streams.
  - `backend/app/services/orchestrator.py` [MODIFY]: Add circuit breaker and crash checkpointing.
* **Dependencies**: All prior phases.
* **Testing Requirements**: Security audit tests; verify log sanitization and crash resumption.
* **Risks**: Secret key management on local installations.

#### Phase 15: Full Regression Testing & Quality Assurance
* **Goal**: End-to-end verification and production readiness.
* **Target Files**:
  - `backend/requirements.txt` [MODIFY]: Add `pytest-asyncio>=0.23.0`.
  - `backend/pytest.ini` [MODIFY]: Configure `asyncio_mode = auto`.
  - `backend/tests/` [EXPAND]:
    - `test_orchestrator.py`: Full lifecycle tests.
    - `test_qa_vault.py`: Vault matching and answer generation.
    - `test_discovery.py`: Hybrid provider tests.
    - `test_adapters.py`: Platform and external ATS adapter tests.
    - `test_tailorer.py`: Resume generation tests.
* **Dependencies**: All phases complete.
* **Testing Requirements**: 100% passing tests across unit, integration, and dry-run end-to-end suites.
* **Risks**: Flaky network-dependent tests. Mock all external HTTP and browser calls in CI/test runs.
