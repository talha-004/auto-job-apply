import pytest
from pathlib import Path
from app.services.multi_resume_router import MultiResumeRouterService


@pytest.fixture
def tmp_router(tmp_path):
    resumes_dir = tmp_path / "resumes"
    registry_file = resumes_dir / "variants.json"
    return MultiResumeRouterService(registry_file=registry_file, resumes_dir=resumes_dir)


def test_register_and_list_variants(tmp_router, tmp_path):
    f1 = tmp_path / "backend_dev.pdf"
    f1.write_bytes(b"%PDF-1.4 dummy backend")

    f2 = tmp_path / "frontend_dev.pdf"
    f2.write_bytes(b"%PDF-1.4 dummy frontend")

    v1 = tmp_router.register_variant(
        variant_id="backend",
        label="Backend Python Engineer",
        file_path=f1,
        target_keywords=["python", "fastapi", "django", "postgresql", "docker"],
        skills=["Python", "FastAPI", "PostgreSQL"]
    )
    assert v1["id"] == "backend"

    v2 = tmp_router.register_variant(
        variant_id="frontend",
        label="Frontend React Developer",
        file_path=f2,
        target_keywords=["react", "typescript", "javascript", "tailwind", "next.js"],
        skills=["React", "TypeScript", "HTML", "CSS"]
    )
    assert v2["id"] == "frontend"

    variants = tmp_router.list_variants()
    assert len(variants) == 2


def test_dynamic_routing_selection(tmp_router, tmp_path):
    f1 = tmp_path / "backend.pdf"
    f1.write_bytes(b"%PDF-1.4 dummy backend")
    f2 = tmp_path / "frontend.pdf"
    f2.write_bytes(b"%PDF-1.4 dummy frontend")
    f3 = tmp_path / "ai_ml.pdf"
    f3.write_bytes(b"%PDF-1.4 dummy ai")

    tmp_router.register_variant(
        variant_id="backend",
        label="Backend Engineer",
        file_path=f1,
        target_keywords=["python", "fastapi", "postgresql", "docker", "redis"],
        skills=["Python", "FastAPI", "SQL"]
    )
    tmp_router.register_variant(
        variant_id="frontend",
        label="Frontend Engineer",
        file_path=f2,
        target_keywords=["react", "typescript", "next.js", "tailwind", "css"],
        skills=["React", "JavaScript"]
    )
    tmp_router.register_variant(
        variant_id="ai_ml",
        label="AI/ML Engineer",
        file_path=f3,
        target_keywords=["machine learning", "deep learning", "llm", "pytorch", "tensorflow", "nlp"],
        skills=["Machine Learning", "PyTorch"]
    )

    # 1. Python Backend Job
    route_back = tmp_router.route_best_resume(
        job_title="Senior Python FastAPI Developer",
        job_description="We are seeking an engineer experienced with Python, FastAPI, Docker, and PostgreSQL microservices."
    )
    assert route_back["selected_variant_id"] == "backend"
    assert "Backend Engineer" in route_back["label"]
    assert route_back["match_score"] > 60.0

    # 2. React Frontend Job
    route_front = tmp_router.route_best_resume(
        job_title="Lead Frontend React Architect",
        job_description="Looking for expertise in React, Next.js, TypeScript, and modern CSS architecture."
    )
    assert route_front["selected_variant_id"] == "frontend"
    assert "Frontend Engineer" in route_front["label"]

    # 3. AI / ML Job
    route_ai = tmp_router.route_best_resume(
        job_title="Generative AI Research Engineer",
        job_description="Seeking a candidate with strong machine learning, PyTorch, and LLM fine-tuning experience."
    )
    assert route_ai["selected_variant_id"] == "ai_ml"
    assert "AI/ML Engineer" in route_ai["label"]
