"""
AI Mock Interview Preparation Coach Service.
Generates company & role intelligence dossiers, targeted technical questions,
and STAR behavioral frameworks grounded in the candidate's verified CandidateFact ledger.
Provides real-time interactive answer evaluation and scoring.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.core.logger import logger
from app.core.llm import llm_client
from app.core.prompt_guard import prompt_guard
from app.models.fact_ledger import CandidateFact
from app.services.fact_ledger import fact_ledger_service


class TechnicalQuestion(BaseModel):
    id: str
    question: str
    target_skill: str
    difficulty: str  # Fundamental, Intermediate, Advanced
    expected_concepts: List[str]
    sample_answer_outline: str


class StarBehavioralStory(BaseModel):
    id: str
    prompt: str
    situation: str
    task: str
    action: str
    result: str
    relevant_fact_id: Optional[str] = None


class CompanyDossier(BaseModel):
    company: str
    industry: str
    suggested_questions_to_ask: List[str]
    key_focus_areas: List[str]


class InterviewPrepPackage(BaseModel):
    job_id: str
    job_title: str
    company: str
    dossier: CompanyDossier
    technical_questions: List[TechnicalQuestion]
    behavioral_stories: List[StarBehavioralStory]


class PracticeFeedback(BaseModel):
    score: int = Field(ge=1, le=10)
    strengths: List[str]
    improvement_areas: List[str]
    sample_polished_answer: str


class InterviewCoachService:
    """
    Synthesizes job requirements and verified candidate facts to generate
    interview preparation dossiers and evaluate candidate answers.
    """

    def __init__(self):
        self._cached_packages: Dict[str, InterviewPrepPackage] = {}

    def _generate_fallback_package(
        self,
        job_id: str,
        job_title: str,
        company: str,
        verified_facts: List[CandidateFact]
    ) -> InterviewPrepPackage:
        """Generates deterministic high-quality interview preparation when LLM is unavailable."""
        dossier = CompanyDossier(
            company=company,
            industry="Software & Technology",
            suggested_questions_to_ask=[
                f"What does the core technology stack and deployment cadence look like at {company}?",
                "How does the engineering team balance new feature velocity with technical debt?",
                "What are the biggest scalability challenges planned for the next 12 months?"
            ],
            key_focus_areas=[
                "System architecture & scalability",
                "Code quality & automated testing",
                "Cross-functional collaboration"
            ]
        )

        tech_qs = [
            TechnicalQuestion(
                id="tech_q1",
                question=f"How would you design a resilient, low-latency API service suitable for {company}'s workloads?",
                target_skill="System Design",
                difficulty="Intermediate",
                expected_concepts=["Horizontal scaling", "Caching with Redis", "Database indexing", "Circuit breakers"],
                sample_answer_outline="Discuss layered architecture, stateless REST/gRPC endpoints, connection pooling, and circuit breaker degradation."
            ),
            TechnicalQuestion(
                id="tech_q2",
                question="Can you explain how concurrency and asynchronous I/O operate under heavy load?",
                target_skill="Backend Concurrency",
                difficulty="Intermediate",
                expected_concepts=["Event loops", "Async/Await vs Threads", "Race condition prevention", "Deadlock avoidance"],
                sample_answer_outline="Explain non-blocking event loops vs worker thread pools and locking primitives."
            ),
            TechnicalQuestion(
                id="tech_q3",
                question="How do you handle database migrations and schema evolution in production with zero downtime?",
                target_skill="Database Engineering",
                difficulty="Advanced",
                expected_concepts=["Expand-Contract pattern", "Backward-compatible migrations", "Shadow tables", "Rollback strategies"],
                sample_answer_outline="Outline multi-phase migrations: add nullable column, double-write, backfill, make non-nullable, drop old column."
            )
        ]

        # Extract real facts for STAR stories
        stories = []
        for i, fact in enumerate(verified_facts[:3], start=1):
            stories.append(
                StarBehavioralStory(
                    id=f"star_{i}",
                    prompt=f"Tell me about a time you applied your expertise in {fact.subject}.",
                    situation=f"In a previous role, our system required high reliability regarding {fact.subject}.",
                    task=f"I was tasked with implementing and optimizing our {fact.subject} capabilities.",
                    action=f"Researched best practices, established automated testing, and integrated {fact.value}.",
                    result="Achieved robust system stability and improved engineering velocity.",
                    relevant_fact_id=fact.fact_id
                )
            )

        if not stories:
            stories.append(
                StarBehavioralStory(
                    id="star_default",
                    prompt="Tell me about a time you solved a complex production bug under tight deadlines.",
                    situation="A critical service started dropping incoming requests due to connection exhaustion.",
                    task="Identify root cause and restore full traffic throughput without data loss.",
                    action="Isolated database connection pooling limits, increased worker threads, and added circuit breaking.",
                    result="Traffic stabilized in 20 minutes with zero data corruption."
                )
            )

        return InterviewPrepPackage(
            job_id=job_id,
            job_title=job_title,
            company=company,
            dossier=dossier,
            technical_questions=tech_qs,
            behavioral_stories=stories
        )

    async def generate_prep_package(
        self,
        job_id: str,
        job_title: str,
        company: str,
        job_description: str = ""
    ) -> InterviewPrepPackage:
        """Creates or retrieves a comprehensive interview prep package for the role."""
        if job_id in self._cached_packages:
            return self._cached_packages[job_id]

        verified_facts = fact_ledger_service.ledger.facts
        sanitized_jd = prompt_guard.sanitize(job_description, max_len=1500)

        # Attempt generative synthesis if LLM is active
        try:
            prompt = f"""
            Generate an interview preparation package for:
            Role: {job_title}
            Company: {company}
            Job Description Summary: {sanitized_jd}
            Verified Candidate Skills: {[f.subject for f in verified_facts[:10]]}

            Respond in JSON with schema matching:
            {{
                "dossier": {{
                    "company": "{company}",
                    "industry": "Tech",
                    "suggested_questions_to_ask": ["q1", "q2", "q3"],
                    "key_focus_areas": ["area1", "area2"]
                }},
                "technical_questions": [
                    {{
                        "id": "q1",
                        "question": "question text",
                        "target_skill": "skill",
                        "difficulty": "Intermediate",
                        "expected_concepts": ["c1", "c2"],
                        "sample_answer_outline": "outline"
                    }},
                    {{
                        "id": "q2",
                        "question": "question text",
                        "target_skill": "skill",
                        "difficulty": "Intermediate",
                        "expected_concepts": ["c1", "c2"],
                        "sample_answer_outline": "outline"
                    }},
                    {{
                        "id": "q3",
                        "question": "question text",
                        "target_skill": "skill",
                        "difficulty": "Advanced",
                        "expected_concepts": ["c1", "c2"],
                        "sample_answer_outline": "outline"
                    }}
                ],
                "behavioral_stories": [
                    {{
                        "id": "b1",
                        "prompt": "prompt text",
                        "situation": "...",
                        "task": "...",
                        "action": "...",
                        "result": "..."
                    }}
                ]
            }}
            """
            res = await llm_client.generate_json(prompt, system_prompt="You are an expert technical interview coach.")
            if res and "dossier" in res and "technical_questions" in res:
                tech_qs = [TechnicalQuestion(**q) for q in res["technical_questions"]]
                fallback = self._generate_fallback_package(job_id, job_title, company, verified_facts)
                if len(tech_qs) < 3:
                    for fb_q in fallback.technical_questions:
                        if len(tech_qs) >= 3:
                            break
                        if fb_q.id not in [q.id for q in tech_qs]:
                            tech_qs.append(fb_q)

                stories = [StarBehavioralStory(**b) for b in res.get("behavioral_stories", [])]
                if not stories:
                    stories = fallback.behavioral_stories

                pkg = InterviewPrepPackage(
                    job_id=job_id,
                    job_title=job_title,
                    company=company,
                    dossier=CompanyDossier(**res["dossier"]),
                    technical_questions=tech_qs,
                    behavioral_stories=stories
                )
                self._cached_packages[job_id] = pkg
                return pkg
        except Exception as e:
            logger.debug(f"[InterviewCoach] Fallback to deterministic prep generator: {e}")

        pkg = self._generate_fallback_package(job_id, job_title, company, verified_facts)
        self._cached_packages[job_id] = pkg
        return pkg

    async def evaluate_practice_response(
        self,
        question: str,
        user_answer: str,
        expected_concepts: Optional[List[str]] = None
    ) -> PracticeFeedback:
        """Scores a candidate's answer and provides constructive feedback."""
        clean_answer = prompt_guard.sanitize(user_answer, max_len=2000)

        # Quick heuristic evaluation
        length = len(clean_answer.split())
        score = 7
        strengths = []
        improvements = []

        if length < 25:
            score = 5
            improvements.append("Answer is too brief. Elaborate with concrete architectural examples or metrics.")
        else:
            strengths.append("Good answer depth and structured communication.")

        if expected_concepts:
            matched_concepts = [c for c in expected_concepts if c.lower() in clean_answer.lower()]
            if matched_concepts:
                score = min(10, score + 2)
                strengths.append(f"Successfully highlighted key technical concepts: {', '.join(matched_concepts)}.")
            else:
                improvements.append(f"Consider referencing key concepts such as: {', '.join(expected_concepts[:2])}.")

        # Check for STAR framing keywords
        star_markers = ["situation", "task", "action", "result", "metric", "improved", "led to"]
        has_star = any(m in clean_answer.lower() for m in star_markers)
        if has_star:
            strengths.append("Incorporated strong action-oriented, result-focused framing.")

        return PracticeFeedback(
            score=max(1, min(10, score)),
            strengths=strengths,
            improvement_areas=improvements or ["Practice delivering this response smoothly within 90 seconds."],
            sample_polished_answer=(
                f"In addressing {question[:60]}..., focus directly on the trade-offs: "
                f"state the business context, your technical implementation decision, and the measurable impact."
            )
        )


interview_coach_service = InterviewCoachService()
