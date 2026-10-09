"""
api/feedback.py – User feedback on recommendations and extraction.
POST /api/feedback
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from database.models import db, Feedback
import os

feedback_bp = Blueprint("feedback", __name__)


def _ok(data=None):
    return jsonify({"status": "ok", "data": data or {}})

def _err(code, msg, status=400):
    return jsonify({"status": "error", "error": {"code": code, "message": msg}}), status


@feedback_bp.route("/", methods=["POST"])
@feedback_bp.route("", methods=["POST"])
@login_required
def submit_feedback():
    body = request.get_json(silent=True) or {}
    target_type = body.get("target_type", "")
    if target_type not in ("recommendation", "skill", "roadmap", "extraction", "general"):
        return _err("INVALID_TARGET", "target_type must be recommendation, skill, roadmap, extraction, or general.")

    rating = body.get("rating")
    if rating is not None and rating not in (1, -1):
        return _err("INVALID_RATING", "rating must be 1 (positive) or -1 (negative).")

    fb = Feedback(
        user_id=current_user.id,
        target_type=target_type,
        target_id=body.get("target_id"),
        rating=rating,
        comment=(body.get("comment") or "")[:1000],
        model_version=os.environ.get("MODEL_VERSION"),
        kb_version=os.environ.get("KB_VERSION"),
    )
    db.session.add(fb)
    db.session.commit()
    return _ok({"feedback_id": fb.id})
