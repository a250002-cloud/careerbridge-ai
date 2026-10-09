"""
api/skills.py – Skills and gaps.
GET /api/skills
GET /api/skills/gaps
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from database.models import db, Skill, UserSkill, UserProfile, SkillGap

skills_bp = Blueprint("skills", __name__)


def _ok(data=None):
    return jsonify({"status": "ok", "data": data or {}})

def _err(code, msg, status=400):
    return jsonify({"status": "error", "error": {"code": code, "message": msg}}), status


@skills_bp.route("/", methods=["GET"])
@skills_bp.route("", methods=["GET"])
@login_required
def list_skills():
    """Return all KB skills, plus user's current skill statuses."""
    all_skills = Skill.query.order_by(Skill.category, Skill.canonical_name).all()
    user_skills = UserSkill.query.filter_by(user_id=current_user.id, user_confirmed=True).all()
    user_skill_map = {us.skill_id: us for us in user_skills}

    result = []
    for skill in all_skills:
        us = user_skill_map.get(skill.id)
        result.append({
            "skill_id": skill.id,
            "canonical_name": skill.canonical_name,
            "category": skill.category,
            "description": skill.description,
            "user_confidence": us.confidence if us else None,
            "user_status": us._status() if us else "not_assessed",
            "user_source": us.source if us else None,
        })
    return _ok({"skills": result})


@skills_bp.route("/gaps", methods=["GET"])
@login_required
def skill_gaps():
    profile = UserProfile.query.filter_by(user_id=current_user.id).first()
    if not profile or not profile.target_role_id:
        return _err("NO_TARGET", "Please select a target role first.")

    gaps = SkillGap.query.filter_by(
        user_id=current_user.id, role_id=profile.target_role_id
    ).all()

    if not gaps:
        # Compute on the fly
        from services.skill_gap_engine import compute_skill_gaps
        result = compute_skill_gaps(current_user.id, profile.target_role_id)
        return _ok(result)

    # Build importance lookup from RoleSkill for the DB read path
    from database.models import RoleSkill
    rs_map = {
        rs.skill_id: rs.importance
        for rs in RoleSkill.query.filter_by(role_id=profile.target_role_id).all()
    }

    gap_list = []
    for g in gaps:
        importance = rs_map.get(g.skill_id, "recommended")
        gap_list.append({
            "skill_id": g.skill_id,
            "skill_name": g.skill.canonical_name if g.skill else "",
            "category": g.skill.category if g.skill else "",
            "status": g.status,
            "priority": g.priority,
            "confidence": g.confidence,
            "importance": importance,
        })

    # Compute readiness from persisted gap data
    from services.skill_gap_engine import _confidence_to_status, IMPORTANCE_TO_PRIORITY
    importance_w = {"core": 3, "recommended": 2, "optional": 1}
    status_s = {"strong": 1.0, "partial": 0.5, "gap": 0.0}
    total_w, earned_w = 0, 0.0
    for g in gaps:
        imp = rs_map.get(g.skill_id, "recommended")
        w = importance_w.get(imp, 2)
        s = status_s.get(g.status, 0.0)
        total_w += w
        earned_w += w * s
    readiness = round(earned_w / total_w, 3) if total_w > 0 else 0.0

    return _ok({
        "role_id": profile.target_role_id,
        "gaps": gap_list,
        "readiness": readiness,
    })


@skills_bp.route("/user", methods=["GET"])
@login_required
def user_skills():
    """Return only the authenticated user's skills."""
    skills = UserSkill.query.filter_by(user_id=current_user.id).all()
    return _ok({"skills": [s.to_dict() for s in skills]})


@skills_bp.route("/user", methods=["POST"])
@login_required
def add_user_skill():
    """Add a self-reported skill."""
    body = request.get_json(silent=True) or {}
    skill_id = body.get("skill_id")
    if not skill_id:
        return _err("MISSING_FIELD", "skill_id is required.")
    skill = db.session.get(Skill, skill_id)
    if not skill:
        return _err("NOT_FOUND", "Skill not found.", 404)

    existing = UserSkill.query.filter_by(user_id=current_user.id, skill_id=skill_id).first()
    if existing:
        return _err("DUPLICATE", "Skill already in your profile.")

    from config import Config
    us = UserSkill(
        user_id=current_user.id,
        skill_id=skill_id,
        confidence=Config.CONF_SELF_REPORTED,
        source="self_reported",
        user_confirmed=True,
    )
    db.session.add(us)
    db.session.commit()
    return _ok({"skill": us.to_dict()}), 201
