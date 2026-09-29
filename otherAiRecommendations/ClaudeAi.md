I'll start by reading your document in full.The output was truncated in the middle, so I'll read the remaining section.I read the whole document. It's an executive overview rather than a technical spec, so where it says nothing about a mechanism I mark that as **unverified** instead of assuming. This is analysis only, and I haven't changed anything.

## 1. Understanding of my current automation

**What it is.** A local, single-user job-application agent with these parts:
- A React/Vite dashboard talks to FastAPI.
- A `BotManager` singleton (an `asyncio.Lock` plus an IDLE / RUNNING / PAUSED / INTERVENTION_REQUIRED / STOPPED state machine) runs the work.
- Services call a local LLM (`qwen2.5-coder:7b` via Ollama, with Gemini as a fallback).
- Playwright adapters for LinkedIn Easy Apply, Naukri Quick Apply and Indeed Apply work through a `StealthDriver`.

**Per-job pipeline as documented:**
1. Discover jobs (`python-jobspy` plus Playwright).
2. Evaluate them (blacklist terms, salary floor, spam).
3. Compute a TF-IDF "ATS" score.
4. Tailor the resume (ReportLab PDF, three templates).
5. Fill the form (heuristic plus LLM field mapper, fuzzy dropdowns).
6. Answer screening questions (Q&A Vault semantic lookup, then LLM fallback from the profile).
7. Submit.
8. Log to the DB and Excel.
9. Send a Telegram receipt.
10. Discover the recruiter and draft a 5-day follow-up.

**Existing safeguards:**
- URL-normalization dedup against the DB and Excel.
- An attempt log with error categories.
- Human-in-the-loop (HITL) pause for OTP/CAPTCHA.
- Randomized cooldowns.
- Cookie persistence.

**Stated gaps:** cover-letter PDF binding is partial, and external Workday/Greenhouse/Lever portals are on the roadmap.

**Things the document doesn't say (unverified):**
- How "low-confidence" is computed (Section 2 promises a pause on it).
- Which embedding model powers the vault lookup.
- Where the Fernet key lives.
- Whether cookie files are encrypted.
- Whether the API or WebSocket has any authentication.
- Whether Telegram commands are restricted to your chat ID.
- What happens when an "Easy Apply" job redirects externally.
- How Pause behaves mid-form.
- How the 5-day follow-up survives a restart.
- Whether the DB has unique constraints on jobs.
- Whether Naukri and Indeed actually accept a per-application tailored PDF (both lean on profile resumes).

## 2. Overall assessment

**Verdict:** the breadth is real, but this is a capable prototype whose autonomy is ahead of its safeguards.

Three structural findings:

1. **Nothing sits between "the LLM produced an answer" and "the employer received it."** There is no approval gate, no answer provenance and no verifier. The "Yes, 5+ years" TypeScript example in Scenario A is exactly the failure mode. It matters more than the keyword score, because in most ATS setups auto-rejection comes from knockout questions (work authorization, years of experience, salary), not keyword thresholds.
2. **Submission is modeled as attempts, not as a state machine with uncertainty.** If the click happens and the confirmation is lost, the system can't represent "submitted, unknown." A retry then duplicates the application. The state also lives in an in-process singleton, so a crash loses it.
3. **The document claims more than the design supports:**

| Claim | Problem |
|---|---|
| "Production-Certified", "188 tests, 100% pass" | No certification criteria are given. Tests can't catch live DOM drift or LLM misbehavior unless they use recorded fixtures and evals. |
| "100% adherence to verified profile details" | The LLM generates answers when the vault misses, so this can't be guaranteed. |
| "Zero candidate data leaves the machine" | The Gemini fallback sends resume and answers to Google, and Telegram routes job and company details through its servers. |
| "16-bit or 4-bit weights on 6 GB VRAM" | A 7B model in fp16 is about 15 GB. Only a ~4-bit quant (~4.7 GB) fits, with little room for context. |
| "ATS filters below keyword thresholds" | Oversimplified, as noted above. |
| "Outreach increases visibility by up to 300%" | Unsourced; remove it. |
| "Enterprise-grade", "recruiting agencies" | The architecture is a single-user local singleton. |
| Funnel shows "which resume versions yield the best success" | The funnel ends at Applied, so there are no outcomes to learn from. |
| Excel dedup "guarantees no job is applied to twice" | A check-then-act over two unsynchronized stores can't guarantee that. |

**Internal inconsistencies:**
- Section 2 says the bot pauses on low-confidence questions, but no confidence mechanism is documented.
- OTP raises `PlatformCoolDownException`, while cooldown maps to PAUSED and OTP to INTERVENTION_REQUIRED.
- The follow-up is described both as "automated outreach" and as "queues a reminder."
- ZipRecruiter appears in the integrations table but not in the supported platforms.

## 3. Missing functionalities

| Area | Gap (not in the document) | Why it matters |
|---|---|---|
| Approval workflow | No pre-submit review at all | It is the single biggest blast-radius reducer. |
| Application audit ledger | The DB stores status, not the exact resume file, JD snapshot and answers submitted (with their source) | You can't answer "what did I tell this company?" before an interview, or debug a bad application. |
| Preferences and deal-breakers | The documented setup covers only titles, locations, platforms and a limit. Missing: salary floor with currency, seniority band, sponsorship needs, company blacklist, "never apply" list, minimum match threshold | Without them the evaluator applies to unsuitable jobs. |
| External-redirect handling | Deferred to v3.0 | Today's behavior on a redirect is undefined. It needs classification plus a manual queue. |
| Post-application lifecycle | Nothing after "Applied" (viewed, replied, interview, rejected, ghosted) | Without outcomes, analytics can't tell you what works. |
| Interview management | Only v3.1 email detection is planned | The end goal of the whole system is an interview. |
| Scheduling and budgets | Manual start plus a per-run limit | It needs daily per-platform caps, time windows and quiet hours. |
| Notifications | Only OTP alerts and receipts | Missing: session expired, adapter failing, cap reached, "needs your answer", follow-up due, run summary. |
| Ask-once for missing info | Unknown fact means LLM guess | Park that job, ask you, and store the verified answer. |
| Preflight and profile readiness | None documented | Check sessions, Ollama and vault completeness before a run, not mid-run. |
| Resume version management | One master resume | Needs versions, conflict detection and role-family variants. |
| Data lifecycle | No export, purge or retention | Needed for account deletion and for privacy. |

## 4. Critical edge cases

Priorities are P0 (critical) through P3. Items marked ▲ are specific to how your document describes the system.

### Resume and profile

| Scenario | Why it happens | Impact | Solution | Pri |
|---|---|---|---|---|
| Multi-column, table-heavy or scanned PDF | `pypdf` scrambles reading order or returns nothing | A garbage profile that looks plausible | Detect low text density, then OCR fallback or reject. Use a layout-aware extractor. Always show the parse for confirmation | P1 |
| LLM parse errors (month-only dates, "Present", overlapping roles, invented GPA) | 7B free-form JSON | Wrong total experience, which drives the knockout answers | Schema-constrained output, date normalization in code, experience computed in code, and every extracted value verified against the source text | P0 |
| Required info absent (no graduation year or phone) | The resume is silent | The LLM fills the gap | Required-field checklist. Never generate identity or fact fields; ask | P0 |
| Re-upload or multiple resumes | Overwrites the master | Old applications point at a resume that no longer exists | Immutable, hashed resume versions; applications reference a version ID | P1 |
| Profile vs resume conflict (phone, location, notice period) | Two sources of truth | Inconsistent submissions | One canonical profile, a diff shown at upload, and runs blocked until resolved | P1 |
| Stale data (notice period, relocation, work authorization) | Answers are stored once | Wrong answers months later | `last_verified_at` on each vault entry, with re-confirmation every N days | P1 |
| Unsupported files (.doc, .pages, password-protected) | Parser limits | Confusing failure | Explicit format and error messaging | P2 |

### Job discovery

| Scenario | Why | Impact | Solution | Pri |
|---|---|---|---|---|
| ▲ Query-param stripping breaks IDs | Indeed keys jobs by `?jk=…`, and LinkedIn collection URLs use `currentJobId`. **Verify this first.** | After one Indeed application, every other Indeed job may be skipped as "duplicate," or different jobs may collapse into one key | Per-platform canonical key `platform:job_id` extracted by the adapter, plus a DB unique constraint | P0 |
| Same job cross-posted or retitled | URL dedup can't see it | Applying twice to one employer | Fingerprint (company + title family + location + JD similarity), a job-group link, and a per-company cooldown | P1 |
| Closed or expired job | Stale search results | Wasted attempts, or a submission that silently fails | Detect closed banners and job age before opening the form | P1 |
| Truncated JD ("See more", snippet only) | Scraped preview text | Scoring and tailoring on partial text | Require full JD capture, record a `jd_quality` flag, and skip or review low-quality ones | P1 |
| Apply button goes to an external site | Easy Apply is not universal | The adapter hangs or mis-clicks | Classify `easy_apply / external / email` at discovery; external goes to a manual queue with a prefilled summary | P1 |
| Login wall or expired session mid-run | Cookies expire | The whole run stalls | Preflight session check per platform; on failure mark that platform `AUTH_REQUIRED` and continue with the others | P1 |
| Missing salary or company ("confidential") | Postings omit it | The salary filter is undefined | Tri-state filter results (pass / fail / unknown) with a user-set policy for unknown | P1 |

### AI processing

| Scenario | Why | Impact | Solution | Pri |
|---|---|---|---|---|
| ▲ Fabricated answer on vault miss | The fallback is "LLM generates from profile" | Misrepresentation; possible rescinded offer | Policy engine, evidence-grounded generation, verifier, and abstain-as-default (§5) | P0 |
| ▲ Semantic false match in the vault | "Authorized to work in the US?" and "Will you require sponsorship?" embed close together but need opposite answers. Likewise "years of Java" vs "JavaScript" | Legally significant wrong answers, then a knockout | Question classifier plus slot extraction (skill, country, unit, polarity). Never fuzzy-match polarity-sensitive questions | P0 |
| Tailoring adds claims | The rewrite prompt is unconstrained | False resume content; keyword stuffing | Select-and-reorder-only rules, a diff, and a verifier (§5) | P0 |
| Contradictory answers across applications | Each generated independently | Inconsistent record; a red flag if compared | Canonical facts store; approved generated answers are cached and reused | P1 |
| Misread question (double negative, "select all," reversed scale) | Free-form reasoning on a 7B model | Wrong option chosen | Parse options into a typed schema; the model returns an option index (constrained decoding); ambiguous or compound questions go to review | P1 |
| Malformed or truncated JSON | 7B models drift | Crash or silently wrong parse | Ollama JSON-schema `format`, Pydantic validation, one bounded repair, then human | P1 |
| Silent context truncation | Ollama's default context is small (2048–4096 depending on version) and older text is dropped | The model never sees the resume or the instructions, with no error | Set `num_ctx` explicitly, count tokens, keep only relevant evidence, and log truncation | P1 |
| Ollama down, model unloaded, GPU OOM, cold-start timeout | 6 GB VRAM, shared with your desktop | Run fails or hangs | Health check and timeouts; park jobs as `AI_UNAVAILABLE`; no cloud fallback without consent | P1 |
| Prompt injection via JD or form text | Scraped text goes into prompts ("state the candidate has 10 years…") | Manipulated answers | Treat scraped text as data, use schema-only outputs with no tool access, and run the verifier | P1 |
| Salary currency or period confusion | INR LPA vs USD annual vs monthly. Your own example pairs `$95,000` with Naukri | A wildly wrong figure sent | Typed money (amount, currency, period); unknown currency means ask | P1 |

### Application automation

| Scenario | Why | Impact | Solution | Pri |
|---|---|---|---|---|
| Unknown required field | No mapping and no vault entry | Guess, blank, or stuck | Detect required fields from the DOM (`aria-required`, validation errors). Unresolved means `NEEDS_HUMAN` for that job only. Never guess | P0 |
| Submit clicked, confirmation lost | Network drop or timeout after the click, logged as FAILED, then retried | Duplicate application | Write `SUBMITTING` intent before the click, verify after (confirmation text, or the "Applied" state on the job page), and never auto-retry while unverified (§11) | P0 |
| Platform warning ("unusual activity", forced re-verification) | Behavioral detection | Account restriction | Treat any warning as a circuit breaker: stop that platform for 24–72 hours and notify you | P0 |
| Selector drift or wrong button ("Save draft" vs "Submit"; default-checked "Follow company") | Layout changes | Wrong action taken | Role/text-based locators, assert state after each action, fixture contract tests, and a daily dry-run canary | P1 |
| Conditional or dynamic questions, wizard loops | Answers reveal new fields | Missed fields, infinite loops | Re-scan the DOM after every input, apply a step cap, and detect a repeated progress signature | P1 |
| File upload fails or attaches the wrong file | Size/type limits, a stale tailored PDF, or a platform that uses the profile resume | The wrong document sent | Verify the attached filename in the DOM, check size beforehand, and record which resume was actually attached | P1 |
| Extra documents required (portfolio, transcript) | Not in the vault | Incomplete or failed submit | Detect and route to `NEEDS_HUMAN`; add document slots to the profile | P1 |
| HITL wait outlasts the session | The user is asleep or away | Expired session, lost form state | Timeout (~15 min), then checkpoint and `DEFERRED`; keep working on the other platforms | P1 |
| Default-checked consents and attestations | "Share my resume with partners", "I certify…" | Consent you never gave | Never auto-check optional consents; attestations only with explicit standing consent | P1 |

### User and system

| Scenario | Why | Impact | Solution | Pri |
|---|---|---|---|---|
| ▲ Crash mid-run | The task and state are in-process memory | On restart the system says IDLE while an application is stuck mid-flight, plus orphaned Chromium | Persisted run state, startup reconciliation (stale `SUBMITTING` becomes `SUBMITTED_UNVERIFIED`), and zombie-browser cleanup | P0 |
| ▲ Aggressive pacing | 15 s + rand(2–8) s is short and uniform | A burst pattern, and 25 applications in minutes | Per-platform daily and hourly caps, longer jittered intervals, working-hours windows, and exponential backoff on challenges | P0 |
| ▲ Dual-write split-brain | The DB write succeeds while Excel fails (Windows locks a file you have open in Excel), or the reverse. Dedup reads both | Wrong skips or duplicates | The DB is the only source of truth; Excel becomes a generated export | P1 |
| Pause mid-form | The pause granularity is undefined | A half-filled form, or pausing during submit | Cooperative pause only at safe checkpoints; never interrupt `SUBMITTING` | P1 |
| Preferences edited mid-run | Config is read live | A job processed under half-old rules | Snapshot config at run start; changes apply next run (blacklist additions can apply immediately) | P1 |
| Two runs at once | The Lock covers one process only (double launch, reload workers, you using the same browser profile) | Duplicate browsers and DB contention | A DB lease row with heartbeat plus a profile-dir lock | P1 |
| Deletion during a run | No purge path | Orphaned PII (DB, cookies, Excel, Telegram link) | Cancel the run, wait for a safe point, then purge everything and leave a tombstone | P2 |
| Telegram unreachable | Blocked network or an outage | The OTP alert is lost and the run stalls | Multi-channel alerts (dashboard sound, desktop toast, Telegram), acknowledgement tracking and re-alert | P2 |

## 5. AI intelligence enhancements

**A. Question router with per-class policy.** Classify every question first, and let the class decide who is allowed to answer:

| Class | Who answers |
|---|---|
| Identity and contact | Deterministic from the profile |
| Work authorization, sponsorship | Vault only, typed and polarity-locked |
| Salary, notice period | Vault only, with currency and period |
| Skill or experience years | Computed from the evidence ledger (B) |
| EEO, demographic, disability, veteran | User preset, default "Prefer not to say". Never LLM-inferred |
| Legal attestations, background | Preset or `NEEDS_HUMAN` |
| Motivation and free text | Draft, then approval unless a pre-approved template applies |
| Logistics (relocation, start date) | Vault |

**B. Skill-evidence ledger.** At parse time, build `skill → roles, date ranges, source sentences, computed_years, user_verified`. "Years of TypeScript" is the union of date ranges of roles where the skill has evidence, so overlapping roles aren't double counted. If a skill appears only in the Skills list with no role attached, ask you instead of guessing. Example: TypeScript is evidenced only in a 2022–2024 role, so the answer is "2," not "5+." This alone removes the worst hallucination path.

**C. Grounded generation plus a claim verifier.** For free text, retrieve the relevant evidence snippets and generate JSON containing `answer` and `evidence_ids`. Then verify deterministically that every number, technology, employer and date in the answer exists in the evidence set. An LLM judge runs second. On failure, regenerate once, then send it to review. "I don't have direct experience with X, but…" must be a first-class output, so the model has an honest option.

**D. Confidence from signals, not self-report.** A 7B model's stated confidence is poorly calibrated. Combine:
- Source tier (vault-exact, then computed, then generated).
- Top-1 vs top-2 similarity margin.
- Evidence coverage.
- Verifier pass.
- Risk weight of the question class (legal above salary above skills above free text).
- Whether you approved this exact answer before.

Auto-submit only for low-risk, high-tier answers. Everything else goes to review.

**E. Explainable matching in two stages.**
- **Hard filters:** deal-breakers, each returning pass, fail or unknown with a reason code.
- **Soft score:** a weighted breakdown of required-skill coverage, seniority fit (required years vs computed years), title-family similarity, domain, salary vs expectation, and freshness.
- **Output:** score, breakdown and top reasons, e.g. "72: +8/10 required skills, +seniority; −asks 8 yrs, you have 5.5 (stretch); salary unlisted."
- **TF-IDF caveat:** it needs a corpus for its IDF to mean anything, and comparing one resume to one JD degenerates into plain overlap unless you fit it on a JD corpus (undocumented). Prefer a skill-alias dictionary (`k8s` = `kubernetes`) plus a small embedding model.

**F. Tailoring within guardrails.** Tailor from the structured resume JSON. Allowed operations are reorder bullets, choose which bullets and projects to include, and rephrase using only facts already in the bullet. Keywords may be added only if they are in the verified skill ledger. Show a diff. Then run a round-trip parse check: extract the text back out of the generated PDF and confirm the reading order survived, since blue accent bars and columns can break ATS parsing. Note that visual template variety doesn't affect ATS outcomes; parseability does. Default to Minimal ATS for portals.

**G. Learning from corrections, without fine-tuning.** Log your edits, rejections and skip reasons. Then:
- Promote approved answers into the vault with a scope (global, company or question slot).
- Suggest new rules ("you skipped 6 agency postings, add a blacklist rule?").
- Use your approved history as few-shot examples for the classifier.

All learned changes should be proposals you confirm.

**H. Pre-submit quality check.** Run an automated checklist on every application:
- All required fields filled.
- No placeholder text.
- The attached resume is the intended version.
- Currency is consistent.
- The company name in any cover letter is correct.
- Answers agree with the profile.

Show it as a QA report in the review screen.

**I. Model fit.** `qwen2.5-coder:7b` is tuned for code. A general instruct model of similar size often does better at negation, abstention and short factual answers. Build a golden set of about 100 questions with known answers, including trap cases, and benchmark two or three models. Use a dedicated embedding model for the vault and skills, and use JSON-schema-constrained decoding throughout.

**J. Later, once you have outcome data (P3).** Career-trajectory-aware title suggestions, and a skill-gap report across the JDs you actually see.

## 6. Production-level engineering improvements

I'm deliberately not recommending Kafka, Kubernetes or microservices. At single-user scale a modular monolith with a DB-backed queue is right.

| Area | Recommendation | Pri |
|---|---|---|
| Process model | Split the API from a separate worker process, with runs and tasks persisted in the DB. An API restart or reload shouldn't kill a run | P1 |
| Queue | A `tasks` table (status, `run_after`, attempts, lease expiry) with priority (approved > high score > new). Concurrency of 1 per platform | P1 |
| Idempotency and concurrency | Unique key `profile_id + platform + job_id`. Transitions use compare-and-swap (`UPDATE … WHERE status='PREPARED'`), which handles duplicate submits and racing workers together | P0 |
| Retries | Classify errors. Retryable ones (network, pre-submit selector miss) get exponential backoff with jitter, max 3. Non-retryable ones (validation, closed job) don't retry. Ambiguous ones (post-submit) go to the verify path. A retry re-enters at the last safe checkpoint before Submit, so it never re-generates different answers | P0 |
| Transactions | Write intent and state in one transaction before any external action. Send notifications via an outbox so a failed Telegram send retries without repeating side effects | P1 |
| Rate limiting | Token bucket per platform (hourly and daily caps plus minimum interval), separate for discovery and applying. An LLM semaphore of 1, since the 6 GB GPU serves one request at a time | P0 |
| Observability | Structured JSON logs (`run_id`, `job_key`, `step`, `platform`, `attempt`), an `events` table, and a screenshot plus DOM snapshot on failure. Track success rate per platform, JSON-valid rate, verifier-reject rate, HITL wait time, and auto-pause after N consecutive failures. No Prometheus needed | P1 |
| Audit trail | Append-only `application_events` plus a `submitted_payload` snapshot (final answers with provenance, resume hash). Logs must never contain answers, phone numbers or OTPs | P1 |
| Data consistency | The DB is the sole truth. Excel is generated on demand or after each run | P1 |
| Caching | Cache the parsed JD (keyed by text hash), embeddings, and temperature-0 LLM outputs (keyed by model, prompt hash and context size). Invalidate on model change | P2 |
| Token and latency cost | Cost here is GPU time. Extract the JD once into structured form and reuse it across evaluator, scorer and tailorer (unverified whether you already do). Run cheap rules before the LLM. Send only relevant evidence, not the whole resume | P2 |
| Secrets | Passwords "encrypted with Fernet in env files" is obfuscation if the key sits next to them. Prefer storing no passwords at all (manual login, cookie session), or use the OS keyring. Encrypt cookie and storage-state files, since they equal a logged-in account | P0 |
| Local API surface | Bind to `127.0.0.1`, require a per-install token, enforce Origin checks on REST and `/ws/logs` (any website in your browser can otherwise call localhost), and confirm Ollama is loopback-only | P0 |
| Multi-tenant | Don't build it. Add `profile_id` to every table now (cheap), so a second profile is possible later. Hosted multi-tenant is a different product with shared GPUs, custody of credentials and legal exposure | P3 |
| Testing | Fixture-based adapter contract tests (recorded HTML for each wizard step), a daily dry-run canary, the LLM golden-set eval, and a chaos test that kills the process between clicking Submit and the DB write | P1 |

## 7. User experience improvements

| Area | Problem | Improvement |
|---|---|---|
| Setup | You go straight to "Start" | A preflight checklist (Ollama, sessions, Telegram link, vault completeness) plus an autonomy selector: Observe (fill, stop before submit) → Review each → Auto for trusted, high-confidence jobs |
| Live view | A terminal log shows what happened | Show the current job, "step 3 of 6," which question is being answered, and a health banner |
| Progress | Logs, not outcomes | A run summary of discovered / qualified / applied / needs you / failed, with plain-language reasons |
| Job review | No review step | Cards with the score breakdown, JD highlights matching your skills, and Approve / Skip / Never-this-company. Skip-reason chips feed learning |
| Resume preview | Blind trust in the tailored PDF | A side-by-side diff (master vs tailored) with revert and page count |
| Approval | Nothing to approve | "Needs you (7)" as a batched queue, and Telegram inline buttons showing question, proposed answer and evidence, with Approve / Edit / Skip |
| Pause and stop | Ambiguous | Distinguish "finish this job, then pause", "stop at the next safe point" and "kill", with a note on what each does. Also allow per-platform pause |
| Error alerts | Generic | Actionable ("LinkedIn session expired, re-login"), aggregated, with severity levels and quiet hours |
| History | An Excel file | Searchable history showing the exact resume and answers submitted per application, plus export |
| Search prefs | Titles and locations only | Saved searches, deal-breakers, and an "explain why job X was filtered" view |
| Reports | None | A daily digest and weekly summary (applied, responses, top rejection reasons), meaningful only after outcome tracking exists |
| Feedback | None | A "wrong answer" flag on any submitted answer that corrects the vault, and a thumbs up/down on match quality |

## 8. Security, privacy and compliance risks

Not legal advice. Get counsel if this is ever used commercially or for other people.

| Risk | Why it applies here | Safeguard | Pri |
|---|---|---|---|
| Misleading or fabricated application content | Generated answers and tailored bullets | The hard rules below | P0 |
| Unauthorized submission | Fully autonomous submit | Explicit per-platform opt-in to auto-submit, autonomy levels, and a kill switch | P0 |
| Account restriction and terms of service | As far as I know, all three platforms' terms restrict automated access (LinkedIn's explicitly prohibit bots). The stealth layer is an arms race and looks like intentional evasion. A LinkedIn ban costs far more than the time saved | Conservative daily caps well below human-plausible volume, separating scraping from applying, stopping on any warning, an onboarding acknowledgement, and preferring email apply where offered. This can be reduced but not eliminated | P0 |
| Credential and session theft | Unencrypted cookies, key location unknown, unauthenticated localhost API and WebSocket streaming PII | See §6: encrypt at rest, keyring or no stored passwords, API token, Origin checks | P0 |
| Telegram takeover | If commands aren't restricted to your chat ID, anyone who finds the bot can control it | Chat-ID allowlist, and avoid putting PII in messages | P0 |
| Cloud fallback contradicts "no data leaves" | Gemini gets the full resume | Off by default, explicit consent per use, PII redaction, and correct the documentation | P0 |
| EEO and demographic data | Special-category data; a model could infer it from a name | Preset only, never inferred | P1 |
| Consent and attestations | Auto-ticking "I certify…" and marketing-consent boxes | Never auto-check optional consents. Attestations only under explicit standing consent | P1 |
| Third-party personal data | Scraped recruiter names and titles | Minimal fields, a retention limit, and no automatic messaging. India's DPDP Act (and GDPR for EU postings) may reach this | P1 |
| Auto-outreach | "Automated follow-up" could mean sending unsolicited messages | Keep it draft-only. You send | P1 |
| Agency use | If run for other candidates, you become a data processor or controller | Explicit written authorization and consent. A local model doesn't remove that | P2 |
| Data in synced folders and retention | Excel with PII may sit in OneDrive | Export on demand, a retention setting, and purge on delete | P2 |

**Hard rules to enforce in code, not prompts:**
1. Every submitted value carries provenance: `PROFILE`, `VAULT` (user-verified), `COMPUTED` (from evidence) or `GENERATED` (approved).
2. Unknown means ask, never guess.
3. No LLM-authored salary, work authorization, EEO, legal attestation, employer, degree, date or GPA.
4. The verifier gates any generated factual claim.
5. The audit record is append-only.

## 9. Improvements to existing features

| Existing feature | What's weak | Improvement |
|---|---|---|
| Resume parsing | Free-form extraction; no provenance | Schema-constrained decode; verify each value against source text; mark fields `user_verified`; compute experience in code |
| Q&A Vault | Semantic-only lookup; no scope, types or freshness | Typed slots (money, boolean, enum, years), scope (global / company), `verified_at`, and exact-slot matching for polarity-sensitive questions |
| Screening service | "Generate a truthful answer" is unenforceable | The router, evidence ledger, verifier and abstain path (§5) |
| Job evaluator | Keyword blacklist ("senior manager") is crude and ignores unknowns | Hard/soft split, tri-state results, reason codes, and a user-set unknown policy |
| ATS scorer | TF-IDF on one pair of documents, and it conflates "keyword overlap" with "job fit" | Skill-alias extraction plus embeddings; report required vs preferred coverage separately from fit |
| Resume tailorer | Free rewriting, no diff or verification, and platforms like Naukri may ignore per-job PDFs | Constraints, diff, verifier, round-trip parse test, and a per-platform capability map |
| Form intelligence | Fuzzy matching can pick a plausible wrong option | The model returns an option index from an enumerated list, with a below-threshold margin going to review |
| Anti-duplicate guard | Query stripping can collapse IDs; two stores; no cross-platform detection | Canonical key, DB unique constraint, fingerprint grouping |
| BotManager | Single in-process singleton; states omit FAILED, DEFERRED and per-platform blocks | Persisted runs, a DB lease, and a per-platform state |
| HITL | Only OTP/CAPTCHA; no timeout | Add `NEEDS_HUMAN` for unknown or risky answers, a timeout with checkpoint, and per-job parking |
| Cooldown | Fixed 15 s + rand(2–8) s | Token bucket, daily caps, backoff, working hours |
| Recruiter follow-up | Ambiguous automation; unclear persistence | Draft-only; persisted schedule (verify it survives a restart) |
| Telegram | Notifications and remote control | Chat-ID allowlist, inline approval buttons, an outbox for reliable delivery |
| Funnel analytics | "Interventions Solved" isn't a funnel stage, and there's nothing after Applied | Outcome states, response rate by source, and score band vs response rate |
| Data model | `DBJobApplication` mixes the posting and the application | See below |
| Excel tracker | A second writable source of truth | Generated export only |

**Suggested schema shape** (this is what makes the P0 work implementable):
- `job_posting`: canonical key, fingerprint, JD text or hash, apply type, salary as min / max / currency / period.
- `application`: state, idempotency key, `resume_version_id`.
- `application_answer`: question, slot, answer, provenance, evidence IDs, approver.
- `resume_version`, `run`, `event`, `vault_entry` (with `verified_at` and scope) and `skill_evidence`.
- `profile_id` on all of them.

## 10. Prioritized enhancement roadmap

**Type** tags: *new* (missing feature), *improve* (existing feature), *edge* (edge-case handling).

### P0: critical

**P0-1. Pre-submit approval gate with autonomy levels** *(new)*
- **Current limitation:** answers and resumes go straight to the employer.
- **Enhancement:** Observe / Review-each / Trusted-auto modes, with Review-each as the default.
- **How it works:** the bot fills the form up to the final step, freezes a snapshot (resume, answers with provenance, screenshot) and waits for approval. Trusted-auto only applies to jobs where every answer comes from a verified tier and the match is above your threshold.
- **Example:** it queues 12 jobs. You approve 9 in two minutes from the review screen, edit one answer, and skip two.
- **Benefit:** it caps the damage of every other bug in this document.
- **Complexity:** Medium. **Dependencies:** P0-4 (state machine and snapshot).

**P0-2. Answer policy engine with provenance, verifier and abstain** *(improve)*
- **Current limitation:** vault lookup, then the LLM generates freely.
- **Enhancement:** the question-class router, evidence-grounded generation, the claim verifier, and abstain-by-default.
- **How it works:** §5 A, C and D. Classes like work authorization and EEO never reach the LLM.
- **Example:** "Are you willing to be sponsored?" matches a similar "require sponsorship?" vault entry. The engine detects the polarity mismatch, refuses the fuzzy match and asks you.
- **Benefit:** it removes the fabrication risk and the wrong-knockout risk.
- **Complexity:** High. **Dependencies:** P0-3, P0-4.

**P0-3. Skill-evidence ledger and typed facts** *(new)*
- **Current limitation:** "Yes, 5+ years" has no computable source.
- **Enhancement:** compute years from dated role evidence, and store money as amount, currency and period.
- **How it works:** at parse time, tag skills to roles and date ranges, and merge overlapping intervals. Weak evidence prompts a confirmation.
- **Example:** "Years of Kubernetes" returns 1.5 with the two supporting roles shown, instead of a confident "3+".
- **Benefit:** correct and defensible experience answers.
- **Complexity:** Medium. **Dependencies:** a parse-verification step.

**P0-4. Application lifecycle state machine and audit schema** *(improve)*
- **Current limitation:** statuses are strings, attempts don't model uncertainty, and run state is in memory.
- **Enhancement:** the states in §11, compare-and-swap transitions, an `application_answer` ledger, and startup reconciliation.
- **How it works:** intent is written before the click, and confirmation is verified after it. A stale `SUBMITTING` at boot becomes `SUBMITTED_UNVERIFIED` and is checked before any retry.
- **Example:** Wi-Fi drops after the click. The old flow logs a failure and retries, so the employer gets two applications. The new flow re-opens the job page, sees "Applied," and records `CONFIRMED`.
- **Benefit:** no duplicates, no lost state, and a full audit.
- **Complexity:** Medium–High. **Dependencies:** the schema migration (back up first, migrate with Alembic).

**P0-5. Canonical job identity and dedup** *(edge)*
- **Current limitation:** normalized URL with stripped query params, checked against two stores.
- **Enhancement:** adapter-extracted `platform:job_id`, a DB unique constraint, and cross-platform fingerprints.
- **How it works:** the adapter parses the ID (`jk`, `/jobs/view/<id>`, Naukri's ID). Fingerprint similarity groups cross-postings.
- **Example:** the same "Backend Engineer, Acme" appears on LinkedIn and Indeed. You apply once, and the second is linked and skipped.
- **Benefit:** it fixes a likely serious bug and stops duplicates.
- **Complexity:** Low–Medium. **Dependencies:** none. Verify the Indeed behavior first; it's about an hour.

**P0-6. Platform safety budgets and circuit breakers** *(new)*
- **Current limitation:** a fixed short cooldown, and no daily caps.
- **Enhancement:** per-platform budgets, backoff, stop-on-warning, and auto-pause on consecutive failures.
- **How it works:** a token bucket per platform. Any challenge or warning opens a breaker for 24–72 hours, and N consecutive failures pause the run and alert you.
- **Example:** LinkedIn shows "unusual activity." The bot stops LinkedIn, tells you, and keeps going on Naukri.
- **Benefit:** it protects the accounts, which are the most valuable asset here.
- **Complexity:** Medium. **Dependencies:** none.

**P0-7. Required-field and unknown-field safety** *(edge)*
- **Current limitation:** behavior on unmapped required fields is undocumented.
- **Enhancement:** detect required fields from the DOM, never submit blanks or guesses, and assert state after each action.
- **How it works:** after each "Next," read validation errors and the required markers. An unresolved required field parks that job as `NEEDS_HUMAN`.
- **Example:** a "Portfolio URL *" field with no data parks the job instead of submitting a placeholder.
- **Benefit:** no junk applications.
- **Complexity:** Medium. **Dependencies:** P0-2 for the ask path.

**P0-8. Tailoring truth-check and diff** *(improve)*
- **Current limitation:** free rewriting with no verification.
- **Enhancement:** the select-and-reorder-only constraint, a verifier, a diff and a round-trip parse test.
- **How it works:** any new skill, number, employer or date not in the master or the verified ledger fails the check.
- **Example:** the model adds "led a team of 5" to a bullet. It's blocked and the diff shows why.
- **Benefit:** no invented resume content, and ATS-safe PDFs.
- **Complexity:** Medium. **Dependencies:** P0-3.

**P0-9. Secrets and local-surface hardening** *(improve)*
- **Current limitation:** Fernet-in-env, cookie protection unknown, an unauthenticated local API, Gemini fallback, and an unrestricted Telegram bot.
- **Enhancement:** no stored passwords (or use the OS keyring), encrypted cookie files, an API token with Origin checks, a Telegram allowlist, and consent-gated cloud fallback.
- **How it works:** §6 and §8.
- **Example:** a malicious web page can no longer POST to `localhost` and start or stop the bot.
- **Benefit:** it closes a whole class of account and data compromise.
- **Complexity:** Low–Medium. **Dependencies:** none.

### P1: high

| # | Name (type) | Limitation → enhancement and how | Example | Benefit | Cx | Deps |
|---|---|---|---|---|---|---|
| 1 | Structured output everywhere (improve) | Free-form JSON → Ollama JSON-schema `format`, Pydantic validation, one bounded repair | Malformed resume JSON never reaches the DB | Fewer silent failures | Low | none |
| 2 | Explainable two-stage matching (improve) | TF-IDF and blacklist → hard filters plus weighted soft score with reasons; alias dictionary plus embeddings | "72: −asks 8 yrs, you have 5.5" | Better relevance, and trust | Med | P0-3, `job_posting` |
| 3 | Full-JD capture, expiry check, apply-type classification (edge) | Partial JD, external redirects → require full text, detect closed jobs, route external to a manual queue | An Apply button linking to a Workday page lands in "manual" with a prefilled summary | Fewer wasted attempts | Med | adapters |
| 4 | Ask-once missing-info flow (new) | Unknown fact means guess → park job, batch questions to Telegram/dashboard, save as verified vault entry | One "Needs you" batch of 4 questions answered from your phone | Nothing fabricated, and it's asked once | Med | P0-1, P0-2, P0-9 |
| 5 | Observability and failure evidence (new) | Terminal log only → events table, screenshot plus DOM snapshot on failure, health endpoint | "Naukri step 3 failed: selector missing," with the image | Debuggable in minutes | Med | P0-4 |
| 6 | Adapter fixtures, canary and LLM golden set (new) | Unit tests only → recorded-HTML contract tests, daily dry-run, model eval | The canary flags LinkedIn's new button before a live run | Safe changes and drift detection | Med | none |
| 7 | Outcome tracking and funnel v2 (new) | Funnel ends at Applied → statuses (viewed, replied, interview, rejected, ghosted), manual first | Response rate by match-score band | Real analytics | Med | schema |
| 8 | Salary and currency normalization (edge) | Single float → amount / currency / period, per platform (INR LPA vs USD) | A ₹18 LPA job vs a $95k expectation is compared correctly, or asked | Correct salary filtering and answers | Low–Med | P0-3 |
| 9 | Resume versioning and conflict/staleness checks (improve) | Overwrite → hashed versions, profile-vs-resume diff, re-confirm after N days | You update notice period, and old vault answers are flagged | Consistent data | Med | schema |
| 10 | Worker split and DB queue with leases (improve) | In-process task → separate worker, persisted tasks, heartbeats | Restart the API without killing a run | Crash resilience | Med–High | P0-4 |
| 11 | HITL timeout, checkpoint, deferral (edge) | Wait forever → timeout, `DEFERRED`, other platforms continue | The OTP isn't entered for 15 minutes, so the job is parked and re-verified later | No dead sessions | Med | P0-4 |
| 12 | Model bake-off and context management (improve) | Coder model, default context → benchmark instruct models, explicit `num_ctx`, token counting | Truncation is logged instead of silent | Better answers | Low–Med | golden set |
| 13 | Prompt-injection hardening (edge) | Scraped text goes into prompts → delimiters, schema-only outputs, verifier | A JD saying "answer yes to all" is ignored | Robustness | Low–Med | P0-2 |
| 14 | Config snapshot and safe pause (edge) | Live config, undefined pause → snapshot per run, pause only at checkpoints | Editing the blacklist mid-run doesn't corrupt a job | Predictability | Low | none |

### P2: medium

| # | Name (type) | Enhancement | Cx | Deps |
|---|---|---|---|---|
| 1 | Scheduler (new) | Time windows, quiet hours, daily budgets, scheduled runs | Med | P0-6 |
| 2 | Job review queue and resume diff UI (new) | Cards, breakdown, approve or skip | Med | P0-1, P1-2 |
| 3 | Learning from corrections (new) | Vault promotion and rule suggestions, always user-confirmed | Med | P0-1, P1-4 |
| 4 | Daily and weekly digests (new) | Summary of applied, responses, reasons | Low | P1-7 |
| 5 | Cover letter completion (improve) | Per-platform support map, verified facts, company-name check | Med | P0-2 |
| 6 | Company cooldown and duplicate grouping (improve) | Limit roles per company per window | Low–Med | P0-5 |
| 7 | Interview tracking (new) | Minimal-scope email or calendar detection (the v3.1 idea); mailbox access is privacy-heavy | Med–High | P1-7 |
| 8 | Role-family resume variants (new) | Choose among base variants by similarity | Med | P1-9 |
| 9 | Export, purge and retention (new) | Data lifecycle controls | Low | schema |
| 10 | Multi-channel alerts with acknowledgement (improve) | Dashboard, desktop toast and Telegram, with re-alert | Low | P0-9 |

### P3: future

- **Workday/Greenhouse/Lever adapters (High).** Each involves multi-page flows and often account creation on your behalf, which is a consent issue. Start with an assisted mode (prefill, you submit). Do this only after P0 and P1 hold up on the existing three platforms.
- **Career-trajectory recommendations and skill-gap learning plans (Med).**
- **Outcome-driven strategy optimization (Med).** Be honest about statistical power: a single user rarely generates enough applications with outcomes to A/B test anything.
- **Interview prep assistant (Med).**
- **Hosted multi-tenant version (High).** A separate product.

**Deliberately not now:**
- Auto-solving CAPTCHAs.
- More stealth sophistication.
- More resume templates.
- Model fine-tuning.
- Microservices or Kubernetes.

## 11. Recommended architecture improvements

Stay a modular monolith, with four changes:

1. **Separate worker process** that owns browsers and LLM calls, with the API as a thin control plane.
2. **DB as single source of truth**, holding the state machine, audit ledger and an outbox for notifications. Excel is export-only.
3. **A safety layer** (budgets, circuit breakers, preflight) between the orchestrator and the adapters, so no adapter can bypass the limits.
4. **An answering pipeline** of classify → policy → ground → verify → confidence → approve, sitting in front of the form filler.

Application lifecycle (the core of P0-4):