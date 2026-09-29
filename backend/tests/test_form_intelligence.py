"""
Unit Tests for Phase 17: Smart Form-Filling Intelligence & Semantic Dropdown Resolver.
Tests question category classification, dropdown/radio resolution across work authorization,
sponsorship, notice period, and EEO, dynamic salary range calculation, and navigation buttons.
"""

import pytest
from app.services.form_intelligence import (
    FormIntelligenceService,
    ResolvedField,
    SalaryRecommendation,
    form_intelligence
)


def test_question_category_classification():
    service = FormIntelligenceService()
    assert service.classify_question_category("Are you legally authorized to work in the US?") == "work_authorization"
    assert service.classify_question_category("Will you now or in the future require visa sponsorship?") == "visa_sponsorship"
    assert service.classify_question_category("What is your current notice period?") == "notice_period"
    assert service.classify_question_category("Are you open to relocation?") == "relocation"
    assert service.classify_question_category("Gender Identity") == "gender"
    assert service.classify_question_category("What is your favorite color?") is None


def test_work_authorization_resolution():
    service = FormIntelligenceService()
    options = ["No", "Yes, I am authorized", "I need sponsorship"]
    vault = {"work_authorized": True}

    res = service.resolve_dropdown_or_radio(
        "Are you authorized to work in the United States?",
        options,
        vault
    )
    assert res.selected_option == "Yes, I am authorized"
    assert res.confidence >= 0.90
    assert res.canonical_category == "work_authorization"


def test_visa_sponsorship_resolution():
    service = FormIntelligenceService()
    options = ["Yes", "No, I do not require sponsorship"]
    vault = {"requires_sponsorship": False}

    res = service.resolve_dropdown_or_radio(
        "Will you require visa sponsorship now or in the future?",
        options,
        vault
    )
    assert res.selected_option == "No, I do not require sponsorship"
    assert res.confidence >= 0.90


def test_notice_period_resolution():
    service = FormIntelligenceService()
    options = ["Immediate (0-15 days)", "30 days (1 month)", "60+ days"]
    vault = {"notice_period_days": "15"}

    res = service.resolve_dropdown_or_radio(
        "How soon can you join if offered?",
        options,
        vault
    )
    assert res.selected_option == "Immediate (0-15 days)"
    assert res.confidence >= 0.85


def test_eeo_decline_to_self_identify():
    service = FormIntelligenceService()
    options = ["Male", "Female", "Non-binary", "Decline to self-identify"]
    vault = {}

    res = service.resolve_dropdown_or_radio("Gender", options, vault)
    assert res.selected_option == "Decline to self-identify"
    assert res.confidence >= 0.80


def test_salary_calculator_usd_range():
    service = FormIntelligenceService()
    jd = "The expected base salary range for this role is $120,000 - $160,000 per year plus equity."
    rec = service.calculate_competitive_salary(jd, candidate_target=130000.0, candidate_currency="USD")

    assert rec.extracted_range == (120000.0, 160000.0)
    # 75th percentile of 120k-160k is 150k
    assert rec.recommended_salary == 150000.0
    assert "75th percentile" in rec.strategy_applied


def test_salary_calculator_inr_range():
    service = FormIntelligenceService()
    jd = "Budget for this position is 12 - 20 LPA based on experience."
    rec = service.calculate_competitive_salary(jd, candidate_target=14.0, candidate_currency="INR_LPA")

    assert rec.extracted_range == (12.0, 20.0)
    # 75th percentile of 12-20 is 18.0
    assert rec.recommended_salary == 18.0


def test_salary_calculator_fallback_no_range():
    service = FormIntelligenceService()
    jd = "Competitive compensation with comprehensive benefits."
    rec = service.calculate_competitive_salary(jd, candidate_target=100000.0, candidate_currency="USD")

    assert rec.extracted_range is None
    # 100k + 10% = 110k
    assert rec.recommended_salary == 110000.0


def test_navigation_button_detector():
    service = FormIntelligenceService()
    assert service.is_navigation_button("Next") is True
    assert service.is_navigation_button("Save & Continue") is True
    assert service.is_navigation_button("Submit Application") is True
    assert service.is_navigation_button("Review") is True
    assert service.is_navigation_button("Cancel") is False
    assert service.is_navigation_button("Download Job Description") is False
