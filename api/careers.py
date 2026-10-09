"""
api/careers.py – Career recommendations, comparison, target selection.
GET  /api/careers/recommendations
GET  /api/careers/:id
GET  /api/careers/compare?a=&b=
POST /api/careers/target
"""
import os
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from database.models import db, CareerRole, ResumeAnalysis, Resume, UserProfile
from services.career_engine import get_career_recommendations

careers_bp = Blueprint("careers", __name__)


def _ok(data=None):
    return jsonify({
        "status": "ok",
        "data": data or {},
        "meta": {
            "model_version": os.environ.get("MODEL_VERSION", "v0.1"),
            "kb_version": os.environ.get("KB_VERSION", "v0.1"),
        }
    })

def _err(code, message, status=400):
    return jsonify({"status": "error", "error": {"code": code, "message": message}}), status


def _require_confirmed_profile():
    """Return None if confirmed; error response if not."""
    resume = Resume.query.filter_by(user_id=current_user.id)\
        .order_by(Resume.uploaded_at.desc()).first()
    if not resume:
        return _err("NO_RESUME", "Please upload and confirm a resume first.", 400)
    analysis = resume.analysis
    if not analysis or analysis.status != "confirmed":
        return _err("PROFILE_NOT_CONFIRMED",
                    "Please review and confirm your extracted profile before viewing matches.", 400)
    return None


@careers_bp.route("/recommendations", methods=["GET"])
@login_required
def recommendations():
    err = _require_confirmed_profile()
    if err:
        return err

    force = request.args.get("refresh", "false").lower() == "true"
    result = get_career_recommendations(current_user.id, force_refresh=force)
    return _ok(result)


@careers_bp.route("/<int:role_id>", methods=["GET"])
@login_required
def role_detail(role_id):
    role = db.session.get(CareerRole, role_id)
    if not role:
        return _err("NOT_FOUND", "Role not found.", 404)
    return _ok({"role": role.to_dict()})


@careers_bp.route("/compare", methods=["GET"])
@login_required
def compare():
    err = _require_confirmed_profile()
    if err:
        return err

    a = request.args.get("a", type=int)
    b = request.args.get("b", type=int)
    if not a or not b:
        return _err("MISSING_PARAMS", "Provide both a= and b= role IDs.")

    role_a = db.session.get(CareerRole, a)
    role_b = db.session.get(CareerRole, b)
    if not role_a or not role_b:
        return _err("NOT_FOUND", "One or both roles not found.", 404)

    # Get scores from cached predictions
    from database.models import CareerPrediction
    pred_a = CareerPrediction.query.filter_by(user_id=current_user.id, role_id=a).first()
    pred_b = CareerPrediction.query.filter_by(user_id=current_user.id, role_id=b).first()

    return _ok({
        "role_a": {
            "role": role_a.to_dict(),
            "score": pred_a.final_score if pred_a else None,
            "band": pred_a.band if pred_a else None,
            "explanation": pred_a.explanation_json if pred_a else None,
        },
        "role_b": {
            "role": role_b.to_dict(),
            "score": pred_b.final_score if pred_b else None,
            "band": pred_b.band if pred_b else None,
            "explanation": pred_b.explanation_json if pred_b else None,
        }
    })


@careers_bp.route("/target", methods=["POST"])
@login_required
def set_target():
    body = request.get_json(silent=True) or {}
    role_id = body.get("role_id")
    if not role_id:
        return _err("MISSING_FIELD", "role_id is required.")

    role = db.session.get(CareerRole, role_id)
    if not role:
        return _err("NOT_FOUND", "Role not found.", 404)

    profile = UserProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.session.add(profile)

    profile.target_role_id = role_id
    db.session.commit()

    # Compute gaps and roadmap
    from services.skill_gap_engine import compute_skill_gaps
    from services.roadmap_engine import generate_roadmap
    gap_result = compute_skill_gaps(current_user.id, role_id)
    roadmap_result = generate_roadmap(current_user.id, role_id)

    return _ok({
        "target_role": role.to_dict(),
        "skill_gaps": gap_result,
        "roadmap": roadmap_result,
    })
