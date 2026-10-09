"""
services/skill_gap_engine.py
Deterministic Skill Gap Engine (PRD Section 12).
"""

import os
from database.models import db, RoleSkill, UserSkill, SkillGap, Skill


# Thresholds (configurable via env / PRD table)
CONF_STRONG   = float(os.environ.get("SKILL_CONF_STRONG", "0.70"))
CONF_PARTIAL_LOW = float(os.environ.get("SKILL_CONF_PARTIAL_LOW", "0.40"))

# Importance → priority mapping
IMPORTANCE_TO_PRIORITY = {"core": "high", "recommended": "medium", "optional": "low"}


def compute_skill_gaps(user_id: int, role_id: int) -> dict:
    """
    Compute and persist skill gaps for (user, role).
    Returns a structured gap report.
    """
    kb_version = os.environ.get("KB_VERSION", "v0.1")

    # User's confirmed skills
    user_skills = UserSkill.query.filter_by(user_id=user_id, user_confirmed=True).all()
    user_skill_map = {us.skill_id: us.confidence for us in user_skills}

    # Role's required skills
    role_skill_rows = RoleSkill.query.filter_by(role_id=role_id).all()

    gaps = []
    statuses = {"strong": 0, "partial": 0, "gap": 0}

    for rs in role_skill_rows:
        conf = user_skill_map.get(rs.skill_id, 0.0)
        status = _confidence_to_status(conf)
        priority = IMPORTANCE_TO_PRIORITY.get(rs.importance, "medium")

        statuses[status] += 1
        gaps.append({
            "skill_id": rs.skill_id,
            "skill_name": rs.skill.canonical_name if rs.skill else f"skill_{rs.skill_id}",
            "category": rs.skill.category if rs.skill else "",
            "confidence": round(conf, 2),
            "status": status,
            "priority": priority,
            "importance": rs.importance,
        })

    # Readiness indicator (PRD Section 12 formula)
    readiness = _compute_readiness(role_skill_rows, user_skill_map)

    # Persist to DB (upsert for this user/role)
    _persist_gaps(user_id, role_id, gaps, kb_version)

    return {
        "role_id": role_id,
        "gaps": gaps,
        "readiness": round(readiness, 3),
        "summary": statuses,
        "kb_version": kb_version,
    }


def _confidence_to_status(conf: float) -> str:
    if conf >= CONF_STRONG:
        return "strong"
    if conf >= CONF_PARTIAL_LOW:
        return "partial"
    return "gap"


def _compute_readiness(role_skills: list, user_skill_map: dict) -> float:
    """
    Readiness = Σ(wᵢ · sᵢ) / Σ(wᵢ)
    wᵢ = 3/2/1 for core/recommended/optional
    sᵢ = 1.0/0.5/0 for strong/partial/gap
    """
    importance_w = {"core": 3, "recommended": 2, "optional": 1}
    status_s = {"strong": 1.0, "partial": 0.5, "gap": 0.0}

    total_w = 0
    earned_w = 0.0
    for rs in role_skills:
        w = importance_w.get(rs.importance, 1)
        conf = user_skill_map.get(rs.skill_id, 0.0)
        s = status_s[_confidence_to_status(conf)]
        total_w += w
        earned_w += w * s

    return earned_w / total_w if total_w > 0 else 0.0


def _persist_gaps(user_id: int, role_id: int, gaps: list, kb_version: str):
    SkillGap.query.filter_by(user_id=user_id, role_id=role_id).delete()
    for g in gaps:
        sg = SkillGap(
            user_id=user_id,
            role_id=role_id,
            skill_id=g["skill_id"],
            status=g["status"],
            priority=g["priority"],
            confidence=g["confidence"],
            kb_version=kb_version,
        )
        db.session.add(sg)
    db.session.commit()
