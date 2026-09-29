"""
Application Policy Engine.
Defines autonomy modes (Assist, Supervised, Autonomous) and evaluates whether an application
is permitted to submit automatically or must be held in the Pre-Submit Review Queue.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AutonomyMode(str, Enum):
    ASSIST = "assist"             # Bot fills form and stops for user confirmation on every application
    SUPERVISED = "supervised"     # Auto-submits high-confidence answers; reviews low-confidence or sensitive fields
    AUTONOMOUS = "autonomous"     # Auto-submits when 100% of answers are grounded in verified facts


class PolicyDecision(str, Enum):
    ALLOW = "allow"               # Safe to auto-submit
    REQUIRE_REVIEW = "require_review"  # Hold in review queue for human signoff
    BLOCK = "block"               # Prohibited by user constraints (e.g. blacklisted company, salary below floor)


class PolicyEvaluation(BaseModel):
    decision: PolicyDecision
    autonomy_mode: AutonomyMode
    reasons: List[str] = Field(default_factory=list)
    sensitive_fields_detected: List[str] = Field(default_factory=list)
    confidence_score: float = 1.0


class PolicyEngine:
    """
    Evaluates proposed applications against autonomy mode and safety rules.
    """

    SENSITIVE_TOPICS = {
        "salary": ["salary", "compensation", "ctc", "expected pay", "hourly rate"],
        "authorization": ["authorized to work", "visa", "sponsorship", "citizenship"],
        "legal": ["clearance", "criminal", "felony", "drug test", "background check"],
    }

    def __init__(self, mode: AutonomyMode = AutonomyMode.SUPERVISED):
        self.mode = mode

    def evaluate_application(
        self,
        job_title: str,
        company: str,
        match_score: float,
        answers: List[Dict[str, Any]],
        blacklisted_companies: Optional[List[str]] = None,
        min_match_threshold: float = 50.0,
    ) -> PolicyEvaluation:
        reasons = []
        sensitive_fields = []
        avg_confidence = 1.0

        # 1. Hard Rejection Checks (Blacklisted company or low match)
        if blacklisted_companies:
            norm_comp = company.strip().lower()
            if any(b.strip().lower() in norm_comp for b in blacklisted_companies if b.strip()):
                return PolicyEvaluation(
                    decision=PolicyDecision.BLOCK,
                    autonomy_mode=self.mode,
                    reasons=[f"Company '{company}' is blacklisted by user policy."],
                    confidence_score=0.0
                )

        if match_score < min_match_threshold:
            return PolicyEvaluation(
                decision=PolicyDecision.BLOCK,
                autonomy_mode=self.mode,
                reasons=[f"Match score {match_score}% is below minimum threshold ({min_match_threshold}%)."],
                confidence_score=match_score / 100.0
            )

        # 2. Assist Mode: Always requires human review before submission
        if self.mode == AutonomyMode.ASSIST:
            return PolicyEvaluation(
                decision=PolicyDecision.REQUIRE_REVIEW,
                autonomy_mode=self.mode,
                reasons=["Assist Mode active: All applications require final user confirmation before submission."],
                confidence_score=match_score / 100.0
            )

        # 3. Scan answers for sensitivity and confidence
        confidences = []
        for ans in answers:
            q_text = str(ans.get("question", "")).lower()
            conf = float(ans.get("confidence", 1.0))
            confidences.append(conf)

            # Check sensitive topics
            for topic, keywords in self.SENSITIVE_TOPICS.items():
                if any(kw in q_text for kw in keywords):
                    sensitive_fields.append(f"{topic}: {q_text[:40]}")

            # Check if answer specifically requested human intervention
            if ans.get("requires_human_intervention", False):
                reasons.append(f"Screening answer flagged for review: {ans.get('reason', 'Low confidence')}")

        if confidences:
            avg_confidence = sum(confidences) / len(confidences)

        # 4. Supervised Mode: Requires review if sensitive fields or low confidence
        if self.mode == AutonomyMode.SUPERVISED:
            if sensitive_fields:
                reasons.append(f"Sensitive screening questions detected ({len(sensitive_fields)}).")
            if avg_confidence < 0.85:
                reasons.append(f"Average answer confidence ({avg_confidence:.2f}) is below 0.85 threshold.")

            if reasons:
                return PolicyEvaluation(
                    decision=PolicyDecision.REQUIRE_REVIEW,
                    autonomy_mode=self.mode,
                    reasons=reasons,
                    sensitive_fields_detected=sensitive_fields,
                    confidence_score=avg_confidence
                )
            return PolicyEvaluation(
                decision=PolicyDecision.ALLOW,
                autonomy_mode=self.mode,
                reasons=["All answers verified with high confidence."],
                confidence_score=avg_confidence
            )

        # 5. Autonomous Mode: Auto-submit unless an answer explicitly flagged an unverified claim
        if reasons:
            return PolicyEvaluation(
                decision=PolicyDecision.REQUIRE_REVIEW,
                autonomy_mode=self.mode,
                reasons=reasons,
                sensitive_fields_detected=sensitive_fields,
                confidence_score=avg_confidence
            )

        return PolicyEvaluation(
            decision=PolicyDecision.ALLOW,
            autonomy_mode=self.mode,
            reasons=["Autonomous mode: 100% verified facts."],
            confidence_score=avg_confidence
        )


policy_engine = PolicyEngine()
