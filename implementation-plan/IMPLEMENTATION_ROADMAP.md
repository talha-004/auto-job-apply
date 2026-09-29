# AutoApplyJobs — Master Implementation Roadmap

## 1. Roadmap Architecture & Phasing Strategy

This roadmap details the systematic, phase-by-phase execution to elevate AutoApplyJobs into an enterprise-reliable, privacy-first, evidence-grounded autonomous job application system.

Every phase adheres to strict dependency ordering, comprehensive testing requirements, and verifiable acceptance criteria.

---

## Phase 0: Baseline Verification & Architecture Alignment
- **Objective**: Establish regression baseline, configure project tracking artifacts, and eliminate environment discrepancies.
- **Problems Solved**: Ensure 100% existing functionality is benchmarked and documented before modifications.
- **Existing Functionality Involved**: Test suite (188 tests), Vite frontend build, environment configurations.
- **Tasks**:
  - `PHASE-00-TASK-01`: Run full backend test suite (`python -m pytest backend/tests`) and record pass rate baseline.
  - `PHASE-00-TASK-02`: Run frontend build verification (`npm run build`) and confirm asset bundle integrity.
  - `PHASE-00-TASK-03`: Create the 5 implementation management documents in `implementation-plan/`.
- **Acceptance Criteria**: All baseline tests pass (188/188), frontend builds cleanly (0 errors), all 5 documents initialized.
- **Testing Requirements**: `pytest backend/tests`, `npm run build`.
- **Completion Conditions**: Baseline documented in `IMPLEMENTATION_PROGRESS.md`.

---

## Phase 1: Candidate Truth Layer & Fact Ledger (No Hallucination)
- **Objective**: Eliminate LLM fabrication of candidate qualifications, experience, and legal claims by establishing an evidence-grounded Fact Ledger.
- **Problems Solved**: Addresses `AUDIT-AI-01`. Guarantees that no numerical or factual claim (e.g. "5+ years in TypeScript") can be submitted without verified source evidence.
- **Existing Functionality Involved**: `app/services/screening_service.py`, `app/services/qa_vault.py`, `app/models/job.py`.
- **Proposed Implementation**:
  - Implement `CandidateFact` and `FactLedger` models storing atomic candidate facts with verification status and document provenance.
  - Create `ClaimVerifier` service: compares LLM-proposed answers against the Fact Ledger. If a question requires unverified claims, flag as `UNVERIFIED_CLAIM_REQUIRES_REVIEW`.
- **Backend Changes**: Add `backend/app/services/fact_ledger.py` and `claim_verifier.py`.
- **API Changes**: Add `/api/resume/facts` (GET/POST/PUT) for managing verified facts.
- **Frontend Changes**: Add Fact Ledger verification drawer to `ResumeUploader.jsx` allowing users to inspect and verify atomic facts extracted from resumes.
- **Database Changes**: Add `candidate_facts` table schema in `db_models.py`.
- **Tasks**:
  - `PHASE-01-TASK-01`: Implement `CandidateFact` Pydantic and SQLAlchemy schema with category, subject, value, provenance, and verification flag.
  - `PHASE-01-TASK-02`: Build `FactLedgerService` to extract, store, query, and validate atomic facts from parsed resumes.
  - `PHASE-01-TASK-03`: Implement `ClaimVerifier` to block unverified claims in `screening_service.py`.
  - `PHASE-01-TASK-04`: Create unit and integration tests for fact ledger extraction and claim verification.
- **Acceptance Criteria**: Any answer containing unverified skills or inflated years of experience is blocked and redirected to review.
- **Testing Requirements**: Unit tests covering factual match, numerical verification, and unverified claim rejection.

---

## Phase 2: Canonical Job Fingerprinting & Idempotency Engine
- **Objective**: Eliminate duplicate applications caused by URL tracking parameter changes or multi-portal cross-posting.
- **Problems Solved**: Addresses `AUDIT-ID-01`. Replaces fragile URL string matching with cryptographic content fingerprinting.
- **Existing Functionality Involved**: `app/services/persistence_service.py`, `app/services/excel_tracker.py`, `app/services/bot_manager.py`.
- **Proposed Implementation**:
  - Implement `JobFingerprinter`: computes a normalized SHA-256 hash using `(platform, normalized_company, normalized_title, normalized_location, job_description_content_hash)`.
  - Introduce `ApplicationIdempotencyManager` enforcing pre-flight deduplication before any browser navigation.
- **Backend Changes**: Add `backend/app/services/job_fingerprinter.py`.
- **Database Changes**: Add `job_fingerprint` and `idempotency_key` unique indexes to `job_applications`.
- **Tasks**:
  - `PHASE-02-TASK-01`: Create `JobFingerprinter` with robust string normalization (lowercasing, punctuation stripping, stopword removal).
  - `PHASE-02-TASK-02`: Integrate fingerprint check in `persistence_service.py` to prevent duplicate writes.
  - `PHASE-02-TASK-03`: Add pre-flight fingerprint evaluation in `bot_manager.py` before launching browser navigation.
  - `PHASE-02-TASK-04`: Create test suite verifying deduplication across identical jobs with different URLs.
- **Acceptance Criteria**: The same job posting with modified URL parameters or cross-posted across platforms is identified as a duplicate and skipped.

---

## Phase 3: Application Policy Engine & Multi-Tier Approval Workflow
- **Objective**: Provide granular user control over autonomy levels and establish a pre-submit approval queue.
- **Problems Solved**: Addresses `AUDIT-POL-01`. Replaces all-or-nothing automation with policy-governed autonomy.
- **Existing Functionality Involved**: `app/services/bot_manager.py`, `frontend/src/components/BotControlPanel.jsx`.
- **Proposed Implementation**:
  - Implement 3 execution modes:
    1. **Assist**: Fills forms and stops prior to submission, awaiting one-click user signoff.
    2. **Supervised**: Auto-submits high-confidence answers; halts for approval on newly drafted answers or sensitive fields (salary, visa).
    3. **Autonomous**: Auto-submits only when 100% of fields match pre-verified facts.
  - Create Pre-Submit Review Queue on backend and frontend displaying application diffs (target role, answers, match score).
- **Backend Changes**: Add `backend/app/services/policy_engine.py` and `backend/app/api/endpoints/review.py`.
- **Frontend Changes**: Add `ReviewQueue.jsx` component with diff view and Approve/Reject buttons.
- **Tasks**:
  - `PHASE-03-TASK-01`: Implement `PolicyEngine` evaluating question sensitivity, match score, and user mode.
  - `PHASE-03-TASK-02`: Build Review Queue REST endpoints (`/api/review/pending`, `/api/review/approve`, `/api/review/reject`).
  - `PHASE-03-TASK-03`: Integrate review gate into `bot_manager.py` application loop.
  - `PHASE-03-TASK-04`: Add frontend Review Queue modal and approval controls.
- **Acceptance Criteria**: In Assist or Supervised mode, sensitive or low-confidence applications pause in the review queue rather than auto-submitting.

---

## Phase 4: Granular 14-State Machine & Recovery (`SUBMISSION_UNKNOWN`)
- **Objective**: Prevent duplicate submissions during network disconnects and enable deterministic failure recovery.
- **Problems Solved**: Addresses `AUDIT-REL-01`. Replaces in-memory 5-state machine with resilient 14-state lifecycle.
- **Existing Functionality Involved**: `app/services/bot_manager.py`, `app/models/db_models.py`.
- **Proposed Implementation**:
  - Implement full 14-state enum: `DISCOVERED`, `EVALUATING`, `ELIGIBLE`, `READY`, `TAILORING`, `FORM_ANALYSIS`, `FILLING`, `VALIDATING`, `READY_TO_SUBMIT`, `SUBMITTING`, `CONFIRMATION_PENDING`, `APPLIED`, `FAILED`, `SUBMISSION_UNKNOWN`.
  - Build `ConfirmationDetector` to capture DOM submission receipts or email confirmation signals.
  - On timeout during `SUBMITTING`, transition to `SUBMISSION_UNKNOWN` and initiate recovery verification rather than blind retrying.
- **Backend Changes**: Update `backend/app/models/db_models.py` and `backend/app/services/bot_manager.py`.
- **Tasks**:
  - `PHASE-04-TASK-01`: Define 14-state enum and transition validators in `db_models.py`.
  - `PHASE-04-TASK-02`: Implement `SubmissionConfirmationDetector` in Playwright platform base.
  - `PHASE-04-TASK-03`: Add `SUBMISSION_UNKNOWN` recovery handler in `bot_manager.py`.
  - `PHASE-04-TASK-04`: Write test suite verifying network timeout recovery and duplicate prevention.
- **Acceptance Criteria**: Simulated network failure during click action enters `SUBMISSION_UNKNOWN` and validates confirmation receipt before allowing retry.

---

## Phase 5: Prompt-Injection Guard & Untrusted Data Boundary
- **Objective**: Protect AI processing from malicious prompts embedded within scraped public job postings.
- **Problems Solved**: Addresses `AUDIT-SEC-01`. Neutralizes adversarial prompt attacks.
- **Existing Functionality Involved**: `app/services/ats_scorer.py`, `app/services/screening_service.py`, `app/core/llm.py`.
- **Proposed Implementation**:
  - Implement `PromptGuard` pre-processor that strips instruction-like phrasing (`"Ignore previous instructions"`, `"System:"`, `"Assistant:"`) from scraped job titles and descriptions.
  - Wrap job data in strict JSON schema delimiters (`<untrusted_job_data>...</untrusted_job_data>`) and instruct LLM system prompts to treat contents strictly as raw passive text.
- **Backend Changes**: Add `backend/app/core/prompt_guard.py`.
- **Tasks**:
  - `PHASE-05-TASK-01`: Implement `PromptGuard` sanitizer with regex patterns and instruction neutralizers.
  - `PHASE-05-TASK-02`: Update system prompts in `ats_scorer.py`, `screening_service.py`, and `resume_parser.py` with untrusted data wrappers.
  - `PHASE-05-TASK-03`: Build security test suite with adversarial prompt injection payloads.
- **Acceptance Criteria**: Adversarial instructions embedded in simulated job descriptions fail to alter model behavior or leak system instructions.

---

## Phase 6: Authoritative DB Architecture & Async Excel Projection Outbox
- **Objective**: Prevent split-brain inconsistency and file-locking errors between database and Excel tracking.
- **Problems Solved**: Addresses `AUDIT-DATA-01`. Establishes the relational database as sole transactional source of truth.
- **Existing Functionality Involved**: `app/services/excel_tracker.py`, `app/services/persistence_service.py`.
- **Proposed Implementation**:
  - Decouple Excel writing from direct application transactions.
  - Implement `ExcelOutboxWorker` that processes committed DB events asynchronously and updates `job_applications.xlsx` safely with retry and lock handling.
- **Backend Changes**: Add `backend/app/services/excel_outbox.py`.
- **Tasks**:
  - `PHASE-06-TASK-01`: Build async `ExcelOutboxWorker` with file-lock recovery and backoff.
  - `PHASE-06-TASK-02`: Refactor `persistence_service.py` to publish outbox events rather than calling `excel_tracker` directly.
  - `PHASE-06-TASK-03`: Create test suite verifying database commits succeed even if Excel file is locked.
- **Acceptance Criteria**: Applications commit to the database without failure when Excel file is held open by an external application; Excel updates automatically once lock releases.

---

## Phase 7: Post-Application Lifecycle & Interview Pipeline
- **Objective**: Extend application tracking beyond "Applied" to full interview and offer conversion.
- **Problems Solved**: Addresses `AUDIT-POST-01`. Completes the end-to-end career funnel.
- **Existing Functionality Involved**: `app/services/analytics_service.py`, `app/api/endpoints/jobs.py`, `frontend/src/components/ConversionFunnel.jsx`.
- **Proposed Implementation**:
  - Add lifecycle states: `APPLIED`, `VIEWED`, `SCREENING`, `INTERVIEW_SCHEDULED`, `OFFER`, `REJECTED`, `GHOSTED`.
  - Add endpoints to log interview dates, notes, and offer details.
  - Update Conversion Funnel analytics and UI to display interview conversion rates.
- **Backend Changes**: Update `backend/app/services/analytics_service.py` and `backend/app/api/endpoints/jobs.py`.
- **Frontend Changes**: Update `JobApplicationsTable.jsx` and `ConversionFunnel.jsx` with lifecycle status badges and interview scheduling modal.
- **Tasks**:
  - `PHASE-07-TASK-01`: Add lifecycle status transitions and interview metadata fields in `db_models.py`.
  - `PHASE-07-TASK-02`: Add REST endpoints for updating application lifecycle status (`/api/jobs/{id}/status`).
  - `PHASE-07-TASK-03`: Update frontend table with lifecycle dropdown and interview logging action.
  - `PHASE-07-TASK-04`: Update conversion funnel to track Applied $\rightarrow$ Interview $\rightarrow$ Offer rates.
- **Acceptance Criteria**: Users can update application lifecycle to `INTERVIEW_SCHEDULED` and see real-time interview rates in the dashboard.

---

## Phase 8: Security & Guardrails (Telegram Allowlist & Platform Limits)
- **Objective**: Secure external control channels and enforce platform daily budgets.
- **Problems Solved**: Addresses `AUDIT-TEL-01` and platform ban risks.
- **Existing Functionality Involved**: `app/services/telegram_bot.py`, `app/core/config.py`, `app/platforms/base.py`.
- **Proposed Implementation**:
  - Enforce `TELEGRAM_ALLOWED_CHAT_ID` validation on all incoming Telegram bot updates.
  - Implement `PlatformRateLimiter` enforcing daily hard caps (e.g. max 25 LinkedIn, max 30 Naukri) and quiet hours.
- **Backend Changes**: Update `backend/app/services/telegram_bot.py` and add `backend/app/services/platform_limiter.py`.
- **Tasks**:
  - `PHASE-08-TASK-01`: Add chat ID authentication to Telegram bot webhook/polling handler.
  - `PHASE-08-TASK-02`: Implement `PlatformRateLimiter` tracking daily applications per platform.
  - `PHASE-08-TASK-03`: Integrate limiter checks into `bot_manager.py` before initiating platform runs.
  - `PHASE-08-TASK-04`: Write test suite verifying Telegram security and daily limit enforcement.
- **Acceptance Criteria**: Telegram commands from unauthorized IDs are rejected with 403; automation pauses when daily platform cap is reached.

---

## Phase 9: Comprehensive Integration, Chaos Testing & Production Certification
- **Objective**: Validate all integrated pillars through chaos injection, regression testing, and production certification.
- **Problems Solved**: Guarantees zero regression, verified production readiness, and synchronization across all documentation.
- **Tasks**:
  - `PHASE-09-TASK-01`: Run full backend test suite verifying 100% pass across all new and existing tests.
  - `PHASE-09-TASK-02`: Run frontend production build verifying 0 build errors.
  - `PHASE-09-TASK-03`: Complete all checklist items in `PRODUCTION_CERTIFICATION.md`.
  - `PHASE-09-TASK-04`: Synchronize `IMPLEMENTATION_PROGRESS.md`, `IMPLEMENTATION_AUDIT.md`, and `ARCHITECTURE.md`.
- **Acceptance Criteria**: Test suite passes with >210 passing tests, frontend builds cleanly, production certification criteria satisfied.

---

## Phase 10: Inbound Email & Interview Intelligence (v3.0 Pillar 1)
- **Objective**: Automate recruiter email scanning, intent classification, and lifecycle status transition.
- **Problems Solved**: Addresses manual tracking friction; captures interview dates and coding challenge deadlines automatically.
- **Tasks**:
  - `PHASE-10-TASK-01`: Build `EmailSyncService` supporting IMAP SSL polling, date/time parsing, and application matching.
  - `PHASE-10-TASK-02`: Create REST endpoints `/api/email/sync`, `/api/email/classified`, and `/api/email/simulate`.
  - `PHASE-10-TASK-03`: Write unit and integration tests verifying interview scheduling and rejection status updates.
- **Acceptance Criteria**: Ingesting recruiter emails transitions matching applications to `INTERVIEW_SCHEDULED` or `REJECTED`.

---

## Phase 11: AI Mock Interview Preparation Coach (v3.0 Pillar 2)
- **Objective**: Generate role-specific interview dossiers, technical questions, and STAR behavioral frameworks grounded in candidate facts.
- **Problems Solved**: Closes the career lifecycle loop from job application to interview preparation.
- **Tasks**:
  - `PHASE-11-TASK-01`: Implement `InterviewCoachService` with generative synthesis and deterministic fallback.
  - `PHASE-11-TASK-02`: Create REST endpoints `/api/interview-coach/generate` and `/api/interview-coach/practice/evaluate`.
  - `PHASE-11-TASK-03`: Build interactive frontend component `InterviewCoachModal.jsx`.
  - `PHASE-11-TASK-04`: Write test suite verifying dossier generation and practice scoring.
- **Acceptance Criteria**: Generates 3+ technical questions and STAR stories; evaluates user practice answers with 1-10 scoring.

---

## Phase 12: Corporate ATS Automation — Workday & External Portals (v3.0 Pillar 3)
- **Objective**: Provide automated application traversal on enterprise Workday (`*.myworkdayjobs.com`) portals.
- **Problems Solved**: Expands reach beyond job boards to external corporate career sites.
- **Tasks**:
  - `PHASE-12-TASK-01`: Implement `WorkdayAdapter` implementing `ApplicationAdapter` with Workday `data-automation-id` selectors.
  - `PHASE-12-TASK-02`: Register `workday_adapter` in `ATSDetector`.
  - `PHASE-12-TASK-03`: Write unit test suite verifying URL detection, form extraction, resume upload, and confirmation.
- **Acceptance Criteria**: Correctly detects Workday URLs, traverses multi-step wizard, and extracts receipt confirmation.

---

## Phase 13: Vision-Assisted Coordinate Fallback Solver (v3.0 Pillar 4)
- **Objective**: Resolve stubborn Shadow DOM elements, canvas controls, and obscured buttons using coordinate-based Bézier clicking.
- **Problems Solved**: Eliminates automation halt on non-standard interactive widgets.
- **Tasks**:
  - `PHASE-13-TASK-01`: Implement `VisionCoordinateSolver` with viewport bounding box calculation.
  - `PHASE-13-TASK-02`: Connect to `StealthDriver` for human-like Bézier mouse trajectory and natural click hold duration.
  - `PHASE-13-TASK-03`: Write test suite verifying fallback to coordinate click when standard click is blocked.
- **Acceptance Criteria**: Obscured or Shadow DOM buttons receive stealth coordinate clicks without raising unhandled exceptions.

---

## Phase 14: Comprehensive v3.0 Integration & Production Certification
- **Objective**: Validate the full v3.0 platform through end-to-end regression and certification.
- **Problems Solved**: Ensures zero regressions across all 14 phases.
- **Tasks**:
  - `PHASE-14-TASK-01`: Run full backend test suite (`python -m pytest backend/tests`). Target: $\ge 235$ passing tests.
  - `PHASE-14-TASK-02`: Run frontend production build (`npm run build`). Target: 0 errors.
  - `PHASE-14-TASK-03`: Complete sign-off in `PRODUCTION_CERTIFICATION.md`.
- **Acceptance Criteria**: 239 passed backend tests, 0 build errors, and synchronized documentation.

---

## Phase 15: Mobile 2-Way Review & Recruiter RSVP Auto-Responder (v3.1 Efficiency Suite)
- **Objective**: Accelerate candidate decision-making via 1-tap mobile application approval and zero-touch recruiter RSVP draft dispatch.
- **Problems Solved**: Eliminates the delay of opening the laptop to approve flagged applications; eliminates the manual friction of drafting polite recruiter interview replies.
- **Tasks**:
  - `PHASE-15-TASK-01`: Implement `EmailAutoResponderService` to synthesize tailored, polite RSVP emails with candidate availability slots.
  - `PHASE-15-TASK-02`: Enhance `TelegramCompanionService` with `format_review_alert`, `/review` & `/drafts` slash commands, and inline button callbacks (`rvw_approve_`, `rvw_reject_`, `rsvp_send_`).
  - `PHASE-15-TASK-03`: Wire `ReviewQueueService.enqueue` to auto-push 1-tap mobile review notifications.
  - `PHASE-15-TASK-04`: Create REST endpoints for RSVP draft review and dispatch (`/api/email/rsvp-drafts`).
  - `PHASE-15-TASK-05`: Write unit tests for draft generation, Telegram actions, and API endpoints.
- **Acceptance Criteria**: 248 passed backend tests, 0 build errors, 1-tap mobile approve/reject operational.

---

## Phase 16: Search Optimization, Relevancy Gating & Discovery Stability (v3.2)
- **Objective**: Maximize job search yield and eliminate irrelevant scrapings via multi-query expansion, boolean queries, targeted platform URL builders, and title relevance gating.
- **Problems Solved**: Prevents missing 70% of relevant jobs due to single-literal search query bottlenecks; eliminates wasted compute and scraping tokens on irrelevant roles (internships, unpaid, leadership, or cross-discipline positions).
- **Tasks**:
  - `PHASE-16-TASK-01`: Implement `SearchOptimizerService` with role synonym clusters, boolean generator, and platform URL constructors.
  - `PHASE-16-TASK-02`: Enhance `DiscoveryConfig` with `query_expansion`, `negative_keywords`, `experience_level`, and `min_salary`.
  - `PHASE-16-TASK-03`: Integrate multi-query execution and title relevance gating in `DiscoveryManager`.
  - `PHASE-16-TASK-04`: Expose preview and telemetry endpoints (`/api/bot/search/expand`, `/api/bot/search/telemetry`).
  - `PHASE-16-TASK-05`: Verify with test suite covering query expansion, boolean search, platform URLs, title filtering, and telemetry.
- **Acceptance Criteria**: 254 passed backend tests, 0 build errors, multi-query expansion and title relevance gating fully operational.

---

## Phase 17: Multi-Corporate ATS Parity — Greenhouse & Lever (v3.3 Workday Parity)
- **Objective**: Expand direct external ATS form automation to Greenhouse (`boards.greenhouse.io`) and Lever (`jobs.lever.co`) with zero drops on external redirects.
- **Problems Solved**: Eliminates dropped application opportunities when job boards redirect candidates to standard corporate ATS platforms.
- **Tasks**:
  - `PHASE-17-TASK-01`: Connect `GreenhouseAdapter` with `ClaimVerifier` validation and `VisionCoordinateSolver` resilient click fallback.
  - `PHASE-17-TASK-02`: Connect `LeverAdapter` with `ClaimVerifier` validation and `VisionCoordinateSolver` resilient click fallback.
  - `PHASE-17-TASK-03`: Write unit tests for URL detection, form extraction, question answering, and submission confirmation.
- **Acceptance Criteria**: 100% test pass on Greenhouse and Lever mock environments; zero unverified claim assertions submitted.

---

## Phase 18: Live Calendar Conflict Resolution & Workday-Safe Auto-Booking
- **Objective**: Parse candidate local `.ics` exports or remote calendar subscription feeds to guarantee that recruiter interview RSVP suggestions never collide with 9-to-5 workday commitments.
- **Problems Solved**: Eliminates double-booking and schedule clashes with candidate's daytime job responsibilities. Operates strictly read-only for complete privacy.
- **Tasks**:
  - `PHASE-18-TASK-01`: Implement `CalendarSyncService` parsing standard iCalendar RFC-5545 `.ics` feeds and extracting busy intervals.
  - `PHASE-18-TASK-02`: Implement `get_conflict_free_slots()` to generate workday-safe interview slots that avoid candidate meetings.
  - `PHASE-18-TASK-03`: Integrate `CalendarSyncService` into `EmailAutoResponderService.generate_rsvp_draft`.
  - `PHASE-18-TASK-04`: Write test suite verifying `.ics` parsing, conflict detection, and dynamic slot substitution.
- **Acceptance Criteria**: Candidate meetings are excluded from proposed interview times; candidate privacy strictly maintained.

---

## Phase 19: Automated Post-Apply Recruiter Outreach Pipeline
- **Objective**: Automatically discover hiring team leads and draft tailored, polite LinkedIn connection notes or follow-up emails, dispatchable via 1-tap mobile Telegram buttons.
- **Problems Solved**: Increases response rates by following up directly with recruiters immediately upon application submission; maintains human-in-the-loop control via mobile push.
- **Tasks**:
  - `PHASE-19-TASK-01`: Enhance `EmailOutreachService` with `OutreachChannel.LINKEDIN_MESSAGE` drafting adhering to 300-character invitation limits.
  - `PHASE-19-TASK-02`: Implement `trigger_post_application_outreach` tying job submissions to lead discovery and automated drafting.
  - `PHASE-19-TASK-03`: Add mobile Telegram callback handlers (`outreach_send_`, `outreach_view_`, `outreach_dismiss_`) and `/outreach` command.
  - `PHASE-19-TASK-04`: Write test suite verifying post-apply lead discovery, note drafting, and 1-tap mobile actions.
- **Acceptance Criteria**: Personalized connection note under 300 characters drafted and dispatched to candidate's mobile Telegram within seconds of job application.

---

## Phase 20: Silent 9-to-5 Windows Background Runner & Watchdog Daemon
- **Objective**: Provide zero-taskbar background execution launcher and safety guard that strictly enforces natural business-hour operation (09:00 - 17:00).
- **Problems Solved**: Allows candidate to work their 9-to-5 day job without open terminal windows or browser popups; guarantees automated applications only run during normal human working hours.
- **Tasks**:
  - `PHASE-20-TASK-01`: Implement `BusinessHourGuard` in `AutonomousSchedulerService` to pause applications during evenings and weekends.
  - `PHASE-20-TASK-02`: Create `run_9to5_silent.vbs` for completely hidden background execution (0 console windows on screen).
  - `PHASE-20-TASK-03`: Create `run_9to5_background.bat` with interactive diagnostic controls, environment validation, and background logging.
  - `PHASE-20-TASK-04`: Write test suite verifying business hour check, weekend prevention, and dynamic scheduler configuration.
- **Acceptance Criteria**: 268 passed backend tests, 0 frontend build errors, silent background execution operational.




