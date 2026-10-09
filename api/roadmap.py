"""
api/roadmap.py – Roadmap and progress.
GET   /api/roadmap
PATCH /api/roadmap/items/:id
GET   /api/progress
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from database.models import db, CareerRoadmap, RoadmapItem, UserProfile

roadmap_bp = Blueprint("roadmap", __name__)


def _ok(data=None):
    return jsonify({"status": "ok", "data": data or {}})

def _err(code, msg, status=400):
    return jsonify({"status": "error", "error": {"code": code, "message": msg}}), status


@roadmap_bp.route("/", methods=["GET"])
@roadmap_bp.route("", methods=["GET"])
@login_required
def get_roadmap():
    profile = UserProfile.query.filter_by(user_id=current_user.id).first()
    if not profile or not profile.target_role_id:
        return _err("NO_TARGET", "Please select a target role first.")

    roadmap = CareerRoadmap.query.filter_by(
        user_id=current_user.id, role_id=profile.target_role_id
    ).first()

    if not roadmap:
        # Generate on demand
        from services.skill_gap_engine import compute_skill_gaps
        from services.roadmap_engine import generate_roadmap
        compute_skill_gaps(current_user.id, profile.target_role_id)
        result = generate_roadmap(current_user.id, profile.target_role_id)
        return _ok(result)

    items = [item.to_dict() for item in roadmap.items]
    total = len(items)
    completed = sum(1 for i in items if i["status"] == "completed")

    return _ok({
        "roadmap_id": roadmap.id,
        "role_id": profile.target_role_id,
        "items": items,
        "total": total,
        "completed": completed,
        "progress_pct": round(completed / total * 100, 1) if total > 0 else 0,
    })


@roadmap_bp.route("/items/<int:item_id>", methods=["PATCH"])
@login_required
def update_item(item_id):
    item = db.session.get(RoadmapItem, item_id)
    if not item:
        return _err("NOT_FOUND", "Roadmap item not found.", 404)

    # Authorization: ensure item belongs to this user
    if item.roadmap.user_id != current_user.id:
        return _err("FORBIDDEN", "Access denied.", 403)

    body = request.get_json(silent=True) or {}
    new_status = body.get("status")
    if new_status not in ("pending", "in_progress", "completed"):
        return _err("INVALID_STATUS", "Status must be pending, in_progress or completed.")

    item.status = new_status
    db.session.commit()
    return _ok({"item": item.to_dict()})


@roadmap_bp.route("/progress", methods=["GET"])
@login_required
def progress():
    profile = UserProfile.query.filter_by(user_id=current_user.id).first()
    if not profile or not profile.target_role_id:
        return _ok({"progress_pct": 0, "completed": 0, "total": 0})

    roadmap = CareerRoadmap.query.filter_by(
        user_id=current_user.id, role_id=profile.target_role_id
    ).first()

    if not roadmap:
        return _ok({"progress_pct": 0, "completed": 0, "total": 0})

    items = roadmap.items
    total = len(items)
    completed = sum(1 for i in items if i.status == "completed")

    return _ok({
        "progress_pct": round(completed / total * 100, 1) if total > 0 else 0,
        "completed": completed,
        "total": total,
        "in_progress": sum(1 for i in items if i.status == "in_progress"),
    })
