"""
services/chatbot.py
AI Career Copilot (PRD Section 14).
Intent classification → context retrieval → prompt build → LLM → validation.

Enhancements v2:
- Richer intent classifier with bigram matching and weighted scoring
- Full chat history injected into prompt for conversational continuity
- Intent + predictions passed to prompt_builder for targeted context
- Gap detail (priority, status) passed through for precise stub/LLM replies
"""

import os
import re
import joblib
import numpy as np
from database.models import (
    db, ChatSession, ChatMessage, UserSkill, UserProfile,
    CareerRole, SkillGap, RoadmapItem, CareerRoadmap, LlmUsage, CareerPrediction
)
from services.llm.provider import get_provider
from services.llm.prompt_builder import build_user_context
from services.llm.response_validator import validate_response


# ── Intent Definitions ────────────────────────────────────────────────────────

INTENTS = [
    "career_recommendation", "career_comparison", "required_skills",
    "skill_gap", "learning_path", "resume_analysis", "career_switch",
    "role_information", "interview_preparation", "project_guidance",
    "out_of_scope",
]

# Weighted keyword patterns: (pattern, weight)
# Higher weight = stronger signal for that intent
_INTENT_PATTERNS: dict[str, list[tuple[str, float]]] = {
    "career_recommendation": [
        ("recommend", 1.0), ("suggest", 1.0), ("best role", 2.0), ("which role", 2.0),
        ("career for me", 2.0), ("suitable role", 2.0), ("what role", 1.5),
        ("match", 0.8), ("career match", 2.0), ("best fit", 2.0), ("good for me", 1.5),
        ("what career", 1.5), ("my matches", 2.0),
    ],
    "career_comparison": [
        ("compare", 1.5), ("difference between", 2.0), (" vs ", 2.0), ("versus", 2.0),
        ("better than", 1.5), ("which is better", 2.0), ("or a ", 0.5),
        ("backend vs", 2.0), ("data scientist vs", 2.0),
    ],
    "required_skills": [
        ("required skills", 2.0), ("what skills", 1.5), ("skills needed", 2.0),
        ("must know", 2.0), ("need to know", 2.0), ("skills for", 1.5),
        ("need for", 1.0), ("skills to become", 2.0), ("what do i need", 1.5),
        ("prerequisites", 1.5),
    ],
    "skill_gap": [
        ("gap", 1.5), ("missing", 1.5), ("lack", 1.0), ("don't have", 1.5),
        ("need to learn", 1.5), ("what am i missing", 2.0), ("skill gap", 2.0),
        ("not yet", 1.0), ("what's missing", 2.0), ("what is missing", 2.0),
        ("gaps", 1.5), ("my gaps", 2.0), ("missing skills", 2.0),
    ],
    "learning_path": [
        ("roadmap", 2.0), ("learning path", 2.0), ("plan", 1.0), ("what next", 2.0),
        ("next step", 2.0), ("study", 1.0), ("how to learn", 2.0), ("where to start", 2.0),
        ("sequence", 1.5), ("order to learn", 2.0), ("learning order", 2.0),
        ("next item", 2.0), ("what should i learn", 2.0), ("start learning", 1.5),
    ],
    "resume_analysis": [
        ("resume", 1.5), ("cv", 1.5), ("improve resume", 2.0), ("my profile", 1.0),
        ("ats", 2.0), ("rewrite", 1.5), ("cover letter", 1.5), ("resume tips", 2.0),
        ("my resume", 2.0), ("make resume", 1.5), ("resume better", 2.0),
    ],
    "career_switch": [
        ("switch", 1.5), ("transition", 1.5), ("change career", 2.0), ("move to", 1.5),
        ("move from", 1.5), ("switch to", 2.0), ("career change", 2.0), ("pivot", 1.5),
        ("change field", 2.0), ("switch field", 2.0), ("from x to", 1.5),
    ],
    "role_information": [
        ("what is", 1.0), ("tell me about", 1.5), ("describe", 1.0), ("explain", 1.0),
        ("what does a", 2.0), ("day in the life", 2.0), ("about backend", 1.5),
        ("about data scientist", 1.5), ("about ml engineer", 1.5), ("role mean", 1.5),
        ("what do they do", 1.5),
    ],
    "interview_preparation": [
        ("interview", 2.0), ("prepare", 1.0), ("practice", 1.0), ("questions for", 1.5),
        ("interview tips", 2.0), ("interview prep", 2.0), ("how to interview", 2.0),
        ("mock interview", 2.0), ("interview questions", 2.0), ("crack interview", 2.0),
        ("technical interview", 2.0), ("prepare for interview", 2.0),
    ],
    "project_guidance": [
        ("project", 1.5), ("build", 1.0), ("portfolio", 2.0), ("project idea", 2.0),
        ("what to build", 2.0), ("side project", 2.0), ("project for", 1.5),
        ("project ideas", 2.0), ("beginner project", 2.0), ("capstone", 1.5),
        ("demo project", 2.0), ("portfolio project", 2.0),
    ],
}

# Low-confidence threshold — route to clarification instead of guessing
CONFIDENCE_THRESHOLD = 0.40


class IntentClassifier:
    """
    Two-layer classifier:
    1. Try to load a trained scikit-learn model from disk (if available).
    2. Fall back to weighted keyword + bigram matching.
    """

    def __init__(self):
        self._model = None
        self._vectorizer = None
        self._loaded = False

    def _try_load(self):
        if self._loaded:
            return
        self._loaded = True
        model_version = os.environ.get("MODEL_VERSION", "v0.1-kb-baseline")
        model_path = os.path.join("models", model_version, "intent_model.joblib")
        vec_path   = os.path.join("models", model_version, "intent_vectorizer.joblib")
        if os.path.exists(model_path) and os.path.exists(vec_path):
            try:
                self._model = joblib.load(model_path)
                self._vectorizer = joblib.load(vec_path)
            except Exception:
                self._model = None
                self._vectorizer = None

    def classify(self, text: str) -> tuple[str, float]:
        """Return (intent_name, confidence 0–1)."""
        self._try_load()
        if self._model is not None and self._vectorizer is not None:
            try:
                vec  = self._vectorizer.transform([text])
                proba = self._model.predict_proba(vec)[0]
                idx   = int(np.argmax(proba))
                return self._model.classes_[idx], float(proba[idx])
            except Exception:
                pass
        return self._keyword_classify(text)

    def _keyword_classify(self, text: str) -> tuple[str, float]:
        """Weighted keyword + bigram matching."""
        text_lower = text.lower()
        scores: dict[str, float] = {}

        for intent, patterns in _INTENT_PATTERNS.items():
            score = 0.0
            for keyword, weight in patterns:
                if keyword in text_lower:
                    score += weight
            if score > 0:
                scores[intent] = score

        if not scores:
            return "out_of_scope", 0.25

        best_intent = max(scores, key=lambda k: scores[k])
        raw_score   = scores[best_intent]

        # Normalise to a 0–0.95 confidence range
        confidence = min(0.40 + raw_score * 0.08, 0.95)
        return best_intent, round(confidence, 3)


_intent_clf = IntentClassifier()


# ── Main Chat Handler ─────────────────────────────────────────────────────────

def handle_message(user_id: int, session_id: int | None, user_message: str) -> dict:
    """
    Process a user message and return the assistant response.
    Always works even if the LLM is down (deterministic fallback, FR-19).
    """
    # ── Session ───────────────────────────────────────────────────────────────
    session = None
    if session_id:
        session = db.session.get(ChatSession, session_id)
        if not session or session.user_id != user_id:
            session = None
    if not session:
        session = ChatSession(user_id=user_id)
        db.session.add(session)
        db.session.flush()

    # ── Intent ────────────────────────────────────────────────────────────────
    intent, intent_conf = _intent_clf.classify(user_message)

    # Low-confidence clarification (avoids wrong-intent replies)
    clarification_response = None
    if intent_conf < CONFIDENCE_THRESHOLD:
        clarification_response = (
            "I want to make sure I help you correctly. Could you be more specific? "
            "I can help with: career matches, skill gaps, learning roadmap, "
            "resume tips, interview prep, or project ideas."
        )

    # ── Profile context ───────────────────────────────────────────────────────
    profile_context = _get_profile_context(user_id)

    # ── Chat history (last 6 messages for continuity) ─────────────────────────
    history_rows = ChatMessage.query.filter_by(session_id=session.id)\
        .order_by(ChatMessage.created_at.desc()).limit(6).all()
    chat_history = [
        {"role": m.role, "content": m.content}
        for m in reversed(history_rows)
    ]

    # ── Predictions (for match band in context) ───────────────────────────────
    predictions = _get_predictions(user_id)

    # ── Build prompt ──────────────────────────────────────────────────────────
    messages = build_user_context(
        target_role=profile_context.get("target_role"),
        confirmed_skills=profile_context.get("confirmed_skills", []),
        gaps=profile_context.get("gaps", []),
        roadmap_items=profile_context.get("roadmap_items", []),
        user_message=user_message,
        intent=intent,
        chat_history=chat_history,
        predictions=predictions,
    )

    # ── LLM call (with deterministic fallback) ────────────────────────────────
    provider = get_provider()
    llm_result = None
    validator_result = {"valid": True, "issues": []}

    if clarification_response:
        response_text = clarification_response
        llm_result = {"content": response_text, "tokens_in": 0, "tokens_out": 0,
                      "cost": 0.0, "model": "stub", "latency_ms": 0}
    else:
        try:
            if not provider.is_available():
                raise RuntimeError("Provider unavailable")
            max_tok = int(os.environ.get("LLM_MAX_TOKENS", "600"))
            llm_result = provider.chat(messages, max_tokens=max_tok)
            response_text = llm_result["content"]

            # Validate response (groundedness + guarantee check)
            confirmed_names = [s.get("canonical_name", "") for s in profile_context.get("confirmed_skills", [])]
            role_skill_names = [s.get("canonical_name", "") for s in profile_context.get("role_skills", [])]
            is_valid, issues, response_text = validate_response(response_text, confirmed_names, role_skill_names)
            validator_result = {"valid": is_valid, "issues": issues}

        except Exception:
            # Deterministic fallback — FR-19: core features always work
            from services.llm.provider import _stub_reply
            response_text = _stub_reply(user_message)
            llm_result = {
                "content": response_text, "tokens_in": 0, "tokens_out": 0,
                "cost": 0.0, "model": "fallback", "latency_ms": 0
            }

    # ── Render any markdown bold (**text**) for the response ──────────────────
    # Keep markdown in response — frontend can handle it or strip it

    # ── Persist ───────────────────────────────────────────────────────────────
    user_msg_row = ChatMessage(
        session_id=session.id, role="user", content=user_message,
        intent=intent, intent_confidence=intent_conf
    )
    asst_msg_row = ChatMessage(
        session_id=session.id, role="assistant", content=response_text,
        tokens=llm_result.get("tokens_out", 0) if llm_result else 0,
        validator_result=validator_result,
    )
    db.session.add_all([user_msg_row, asst_msg_row])

    # Log real LLM usage only
    if llm_result and llm_result.get("model") not in ("stub", "fallback"):
        db.session.add(LlmUsage(
            user_id=user_id,
            model=llm_result.get("model"),
            tokens_in=llm_result.get("tokens_in", 0),
            tokens_out=llm_result.get("tokens_out", 0),
            cost=llm_result.get("cost", 0.0),
            latency_ms=llm_result.get("latency_ms", 0),
        ))

    db.session.commit()

    return {
        "session_id": session.id,
        "response": response_text,
        "intent": intent,
        "intent_confidence": round(intent_conf, 3),
        "validator_result": validator_result,
    }


# ── Context Retrieval ─────────────────────────────────────────────────────────

def _get_profile_context(user_id: int) -> dict:
    """Retrieve compact, structured context — gaps include priority and status."""
    confirmed_skills = UserSkill.query.filter_by(user_id=user_id, user_confirmed=True).all()
    profile = UserProfile.query.filter_by(user_id=user_id).first()
    target_role = None
    gaps = []
    roadmap_items = []
    role_skills = []

    if profile and profile.target_role_id:
        role_obj = db.session.get(CareerRole, profile.target_role_id)
        if role_obj:
            role_skills = [rs.skill for rs in role_obj.role_skills if rs.skill]
            target_role = role_obj.to_dict()

        # Rich gap data including priority for the prompt
        gap_rows = SkillGap.query.filter_by(
            user_id=user_id, role_id=profile.target_role_id
        ).all()
        gaps = [
            {
                "skill_name": g.skill.canonical_name if g.skill else "",
                "status":   g.status,
                "priority": g.priority,
                "confidence": g.confidence,
            }
            for g in gap_rows
            if g.skill
        ]

        roadmap = CareerRoadmap.query.filter_by(
            user_id=user_id, role_id=profile.target_role_id
        ).first()
        if roadmap:
            roadmap_items = [item.to_dict() for item in roadmap.items[:12]]

    return {
        "confirmed_skills": [us.to_dict() for us in confirmed_skills],
        "target_role":      target_role,
        "gaps":             gaps,
        "roadmap_items":    roadmap_items,
        "role_skills":      [{"canonical_name": s.canonical_name} for s in role_skills],
    }


def _get_predictions(user_id: int) -> list[dict]:
    """Return the user's cached career predictions for match-band context."""
    rows = CareerPrediction.query.filter_by(user_id=user_id)\
        .order_by(CareerPrediction.final_score.desc()).limit(5).all()
    return [
        {
            "role_id":   r.role_id,
            "role_name": r.role.name if r.role else "",
            "band":      r.band,
            "final_score": r.final_score,
        }
        for r in rows
    ]
