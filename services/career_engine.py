"""
services/career_engine.py
Hybrid Career Ranking Engine (PRD Section 9).
KB Coverage Scorer (deterministic baseline B0) +
ML Scorer (Logistic Regression, one-vs-rest) →
Final hybrid score → Band → Explanation
"""

import os
import json
import joblib
import numpy as np
from typing import Optional
from flask import current_app

from database.models import db, CareerRole, RoleSkill, Skill, UserSkill, CareerPrediction


# ── Band thresholds ───────────────────────────────────────────────────────────
BAND_STRONG    = 0.65
BAND_GOOD      = 0.40
# below BAND_GOOD → exploratory


# ── KB Coverage Scorer (deterministic baseline) ───────────────────────────────

def kb_coverage_score(user_skill_map: dict, role_id: int) -> dict:
    """
    user_skill_map: {skill_id: confidence}
    Returns {score, matched_skills, missing_core, weight_total}
    """
    role_skills = RoleSkill.query.filter_by(role_id=role_id).all()
    if not role_skills:
        return {"score": 0.0, "matched_skills": [], "missing_core": [], "weight_total": 0.0}

    importance_weight = {"core": 3.0, "recommended": 2.0, "optional": 1.0}
    total_weight = 0.0
    earned_weight = 0.0
    matched = []
    missing_core = []

    for rs in role_skills:
        w = rs.weight * importance_weight.get(rs.importance, 1.0)
        total_weight += w
        conf = user_skill_map.get(rs.skill_id, 0.0)
        coverage = min(conf, 1.0)
        earned_weight += w * coverage

        skill_name = rs.skill.canonical_name if rs.skill else f"skill_{rs.skill_id}"

        if conf >= 0.40:
            matched.append({
                "skill_id": rs.skill_id,
                "canonical_name": skill_name,
                "importance": rs.importance,
                "confidence": round(conf, 2),
                "evidence_hint": rs.evidence_hint,
            })
        elif rs.importance == "core":
            missing_core.append({
                "skill_id": rs.skill_id,
                "canonical_name": skill_name,
                "importance": rs.importance,
            })

    score = earned_weight / total_weight if total_weight > 0 else 0.0
    return {
        "score": round(score, 4),
        "matched_skills": matched,
        "missing_core": missing_core,
        "weight_total": round(total_weight, 2),
    }


# ── ML Scorer ────────────────────────────────────────────────────────────────

class MLCareerScorer:
    """Loads and applies the trained multi-label Logistic Regression model."""

    def __init__(self):
        self._model = None
        self._roles = None
        self._skill_ids = None

    def _load(self):
        model_version = os.environ.get("MODEL_VERSION", "v0.1-kb-baseline")
        model_path = os.path.join("models", model_version, "career_model.joblib")
        meta_path  = os.path.join("models", model_version, "meta.json")
        if os.path.exists(model_path) and os.path.exists(meta_path):
            self._model = joblib.load(model_path)
            with open(meta_path) as f:
                meta = json.load(f)
            self._roles = meta.get("roles", [])
            self._skill_ids = meta.get("skill_ids", [])
        # else: no model yet; will fall back to KB-only

    def predict(self, user_skill_map: dict, all_role_ids: list[int]) -> dict:
        """
        Returns {role_id: ml_score (0-1)} or empty dict if no model.
        """
        if self._model is None:
            self._load()
        if self._model is None:
            return {}  # KB baseline will be primary
        # Build feature vector
        vec = np.zeros(len(self._skill_ids))
        for i, sid in enumerate(self._skill_ids):
            vec[i] = user_skill_map.get(sid, 0.0)
        proba = self._model.predict_proba([vec])[0]  # shape (n_roles,)
        result = {}
        for i, role_id in enumerate(self._roles):
            if i < len(proba):
                result[role_id] = float(proba[i])
        return result


_ml_scorer = MLCareerScorer()


# ── Hybrid Ranking ────────────────────────────────────────────────────────────

def get_career_recommendations(user_id: int, force_refresh: bool = False) -> dict:
    """
    Main entry point. Returns ranked career recommendations for the user.
    """
    from flask import current_app
    alpha = float(os.environ.get("HYBRID_ALPHA", "0.4"))
    kb_version = os.environ.get("KB_VERSION", "v0.1")
    model_version = os.environ.get("MODEL_VERSION", "v0.1-kb-baseline")

    # Get confirmed user skills
    user_skills = UserSkill.query.filter_by(user_id=user_id, user_confirmed=True).all()

    # Abstention check (PRD Section 9)
    min_skills = int(os.environ.get("MIN_CONFIRMED_SKILLS", "3"))
    if len(user_skills) < min_skills:
        return {
            "abstained": True,
            "reason": f"Profile has fewer than {min_skills} confirmed skills. Please add more information.",
            "recommendations": []
        }

    user_skill_map = {us.skill_id: us.confidence for us in user_skills}
    roles = CareerRole.query.all()
    all_role_ids = [r.role_id for r in roles]

    # ML scores
    ml_scores = _ml_scorer.predict(user_skill_map, all_role_ids)

    # KB scores + explanations
    results = []
    for role in roles:
        kb_result = kb_coverage_score(user_skill_map, role.role_id)
        kb_s = kb_result["score"]
        ml_s = ml_scores.get(role.role_id, 0.0)

        # If no ML model, KB is primary (alpha=0)
        if not ml_scores:
            alpha = 0.0
        final_s = alpha * ml_s + (1 - alpha) * kb_s

        band = _score_to_band(final_s)
        explanation = {
            "kb_score": round(kb_s, 4),
            "ml_score": round(ml_s, 4),
            "final_score": round(final_s, 4),
            "matched_skills": kb_result["matched_skills"],
            "missing_core": kb_result["missing_core"],
            "limitation_note": (
                "This match is based on your confirmed skills and the role knowledge base. "
                "Scores are guidance, not a guarantee of employment."
            ),
        }
        results.append({
            "role_id": role.role_id,
            "role_name": role.name,
            "description": role.description,
            "final_score": final_s,
            "kb_score": kb_s,
            "ml_score": ml_s,
            "band": band,
            "explanation": explanation,
            "related_roles": role.related_roles or [],
        })

    # Sort descending
    results.sort(key=lambda x: x["final_score"], reverse=True)

    # Abstain if top score too low
    abstention_threshold = float(os.environ.get("ABSTENTION_THRESHOLD", "0.20"))
    if results and results[0]["final_score"] < abstention_threshold:
        return {
            "abstained": True,
            "reason": "Your profile does not have enough matching skills for confident recommendations. Please review and confirm more skills.",
            "recommendations": []
        }

    # Persist predictions (upsert)
    _persist_predictions(user_id, results, model_version, kb_version)

    return {
        "abstained": False,
        "recommendations": results,
        "model_version": model_version,
        "kb_version": kb_version,
    }


def _score_to_band(score: float) -> str:
    if score >= BAND_STRONG:
        return "strong_match"
    if score >= BAND_GOOD:
        return "good_match"
    return "exploratory"


def _persist_predictions(user_id: int, results: list, model_version: str, kb_version: str):
    """Upsert CareerPrediction rows."""
    # Delete old predictions for this user
    CareerPrediction.query.filter_by(user_id=user_id).delete()
    for r in results:
        pred = CareerPrediction(
            user_id=user_id,
            role_id=r["role_id"],
            ml_score=r["ml_score"],
            kb_score=r["kb_score"],
            final_score=r["final_score"],
            band=r["band"],
            explanation_json=r["explanation"],
            model_version=model_version,
            kb_version=kb_version,
        )
        db.session.add(pred)
    db.session.commit()
