"""
api/resume.py – Resume upload, parse, review, confirm.
POST /api/resume/upload
GET  /api/resume
GET  /api/resume/:id
DELETE /api/resume/:id
PATCH /api/resume/:id/profile  (edit extracted profile)
POST  /api/resume/:id/confirm  (FR-16: mandatory confirmation)
"""
import os
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from database.models import db, Resume, ResumeAnalysis, UserSkill, Skill
from services.resume_parser import validate_and_save, parse_resume, ResumeParserError

resume_bp = Blueprint("resume", __name__)


def _ok(data=None, status=200):
    return jsonify({"status": "ok", "data": data or {}}), status

def _err(code, message, status=400):
    return jsonify({"status": "error", "error": {"code": code, "message": message}}), status


@resume_bp.route("/upload", methods=["POST"])
@login_required
def upload():
    if "file" not in request.files:
        return _err("NO_FILE", "No file provided.")

    file = request.files["file"]
    if not file.filename:
        return _err("NO_FILENAME", "No filename.")

    upload_folder = current_app.config["UPLOAD_FOLDER"]

    try:
        saved = validate_and_save(file, upload_folder)
    except ResumeParserError as e:
        return _err(e.code, str(e))
    except Exception as e:
        return _err("UPLOAD_ERROR", f"Upload failed: {e}")

    # Save Resume record
    resume = Resume(
        user_id=current_user.id,
        file_name=saved["original_name"],
        file_type=saved["file_type"],
        storage_key=saved["storage_key"],
    )
    db.session.add(resume)
    db.session.flush()

    # Parse and create draft analysis
    try:
        profile = parse_resume(saved["storage_key"], upload_folder)
    except ResumeParserError as e:
        db.session.rollback()
        # Remove saved file
        try:
            os.remove(os.path.join(upload_folder, saved["storage_key"]))
        except Exception:
            pass
        return _err(e.code, str(e))

    analysis = ResumeAnalysis(
        resume_id=resume.id,
        profile_json=profile,
        section_confidence=profile.get("section_confidence", {}),
        status="draft",
    )
    db.session.add(analysis)
    db.session.commit()

    return _ok({
        "resume_id": resume.id,
        "analysis_id": analysis.id,
        "status": "draft",
        "profile": _sanitize_profile(profile),
    }, 201)


@resume_bp.route("/", methods=["GET"])
@resume_bp.route("", methods=["GET"])
@login_required
def list_resumes():
    resumes = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.uploaded_at.desc()).all()
    data = []
    for r in resumes:
        row = {
            "id": r.id, "file_name": r.file_name, "file_type": r.file_type,
            "uploaded_at": r.uploaded_at.isoformat(),
            "analysis_status": r.analysis.status if r.analysis else None,
        }
        data.append(row)
    return _ok({"resumes": data})


@resume_bp.route("/<int:resume_id>", methods=["GET"])
@login_required
def get_resume(resume_id):
    resume = Resume.query.filter_by(id=resume_id, user_id=current_user.id).first()
    if not resume:
        return _err("NOT_FOUND", "Resume not found.", 404)
    analysis = resume.analysis
    return _ok({
        "id": resume.id,
        "file_name": resume.file_name,
        "file_type": resume.file_type,
        "uploaded_at": resume.uploaded_at.isoformat(),
        "analysis": {
            "id": analysis.id if analysis else None,
            "status": analysis.status if analysis else None,
            "profile": _sanitize_profile(analysis.profile_json) if analysis else None,
            "section_confidence": analysis.section_confidence if analysis else None,
        } if analysis else None,
    })


@resume_bp.route("/<int:resume_id>", methods=["DELETE"])
@login_required
def delete_resume(resume_id):
    resume = Resume.query.filter_by(id=resume_id, user_id=current_user.id).first()
    if not resume:
        return _err("NOT_FOUND", "Resume not found.", 404)

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    try:
        os.remove(os.path.join(upload_folder, resume.storage_key))
    except FileNotFoundError:
        pass

    db.session.delete(resume)
    # Also remove user skills extracted from this resume
    UserSkill.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return _ok({"message": "Resume and all derived data deleted."})


@resume_bp.route("/<int:resume_id>/profile", methods=["PATCH"])
@login_required
def edit_profile(resume_id):
    """User edits extracted skills before confirming (FR-16)."""
    resume = Resume.query.filter_by(id=resume_id, user_id=current_user.id).first()
    if not resume or not resume.analysis:
        return _err("NOT_FOUND", "Resume or analysis not found.", 404)

    body = request.get_json(silent=True) or {}
    # Allowed edits: skills list update
    skills_update = body.get("skills")  # list of {skill_id, confidence, action: add|remove|update}

    analysis = resume.analysis
    profile = analysis.profile_json or {}

    if skills_update:
        current_skills = {s["skill_id"]: s for s in profile.get("skills", [])}
        for upd in skills_update:
            action = upd.get("action", "update")
            sid = upd.get("skill_id")
            if action == "remove" and sid in current_skills:
                del current_skills[sid]
            elif action in ("add", "update"):
                current_skills[sid] = {
                    "skill_id": sid,
                    "canonical_name": upd.get("canonical_name", f"skill_{sid}"),
                    "confidence": upd.get("confidence", 0.60),
                    "source": "self_reported" if action == "add" else current_skills.get(sid, {}).get("source", "extracted"),
                    "section": upd.get("section", "other"),
                    "evidence_snippet": upd.get("evidence_snippet", ""),
                    "user_confirmed": False,
                }
        profile["skills"] = list(current_skills.values())
        analysis.profile_json = profile
        db.session.commit()

    return _ok({"profile": _sanitize_profile(profile), "status": analysis.status})


@resume_bp.route("/<int:resume_id>/confirm", methods=["POST"])
@login_required
def confirm_profile(resume_id):
    """
    Mandatory confirmation step (PRD FR-16).
    Saves skills to user_skills table, marks analysis confirmed.
    Analysis is LOCKED until confirmed; career engine checks this.
    """
    resume = Resume.query.filter_by(id=resume_id, user_id=current_user.id).first()
    if not resume or not resume.analysis:
        return _err("NOT_FOUND", "Resume or analysis not found.", 404)

    analysis = resume.analysis
    profile = analysis.profile_json or {}
    skills = profile.get("skills", [])

    # Clear previous extracted skills
    UserSkill.query.filter_by(user_id=current_user.id).filter(
        UserSkill.source != "self_reported"
    ).delete()

    confirmed_count = 0
    for s in skills:
        skill_id = s.get("skill_id")
        if not skill_id:
            continue
        skill_obj = db.session.get(Skill, skill_id)
        if not skill_obj:
            continue
        us = UserSkill(
            user_id=current_user.id,
            skill_id=skill_id,
            confidence=float(s.get("confidence", 0.45)),
            source=s.get("source", "extracted"),
            section=s.get("section", ""),
            evidence_snippet=s.get("evidence_snippet", "")[:500],
            extraction_method=s.get("extraction_method", "dictionary"),
            user_confirmed=True,
        )
        db.session.add(us)
        confirmed_count += 1

    analysis.status = "confirmed"
    db.session.commit()

    return _ok({
        "status": "confirmed",
        "confirmed_skills": confirmed_count,
        "message": "Profile confirmed. You can now view your career matches."
    })


def _sanitize_profile(profile: dict | None) -> dict:
    """Strip raw_text (too large) before sending to client."""
    if not profile:
        return {}
    p = dict(profile)
    p.pop("raw_text", None)
    return p
