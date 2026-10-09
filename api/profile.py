"""
api/profile.py – User profile management.
GET   /api/profile
PATCH /api/profile
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from database.models import db, UserProfile, CareerRole

profile_bp = Blueprint("profile", __name__)


def _ok(data=None):
    return jsonify({"status": "ok", "data": data or {}})

def _err(code, msg, status=400):
    return jsonify({"status": "error", "error": {"code": code, "message": msg}}), status


@profile_bp.route("/", methods=["GET"])
@profile_bp.route("", methods=["GET"])
@login_required
def get_profile():
    profile = UserProfile.query.filter_by(user_id=current_user.id).first()
    target_role = None
    if profile and profile.target_role_id:
        role = db.session.get(CareerRole, profile.target_role_id)
        if role:
            target_role = role.to_dict()

    return _ok({
        "user": current_user.to_dict(),
        "profile": {
            "education_summary": profile.education_summary if profile else None,
            "goals": profile.goals if profile else None,
            "target_role": target_role,
        }
    })


@profile_bp.route("/", methods=["PATCH"])
@profile_bp.route("", methods=["PATCH"])
@login_required
def update_profile():
    body = request.get_json(silent=True) or {}
    profile = UserProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.session.add(profile)

    if "education_summary" in body:
        profile.education_summary = (body["education_summary"] or "")[:1000]
    if "goals" in body:
        profile.goals = (body["goals"] or "")[:1000]
    if "name" in body:
        current_user.name = (body["name"] or "").strip()[:120]

    db.session.commit()
    return _ok({"message": "Profile updated."})
