"""
api/resume_builder.py – Resume Builder.
POST /api/resume-builder/generate
POST /api/resume-builder/suggest
"""
import os
import uuid
from flask import Blueprint, request, jsonify, current_app, send_file
from flask_login import login_required, current_user
from database.models import db, GeneratedResume, ResumeTemplate, UserSkill, UserProfile, CareerRole

builder_bp = Blueprint("builder", __name__)


def _ok(data=None, status=200):
    return jsonify({"status": "ok", "data": data or {}}), status

def _err(code, msg, status=400):
    return jsonify({"status": "error", "error": {"code": code, "message": msg}}), status


TEMPLATES = {
    1: "minimal_ats",
    2: "student_fresher",
    3: "technical",
}


@builder_bp.route("/generate", methods=["POST"])
@login_required
def generate():
    body = request.get_json(silent=True) or {}
    template_id = int(body.get("template_id", 1))
    if template_id not in TEMPLATES:
        return _err("INVALID_TEMPLATE", "template_id must be 1, 2, or 3.")

    resume_data = body.get("resume_data", {})
    if not resume_data:
        return _err("MISSING_DATA", "resume_data is required.")

    try:
        pdf_bytes = _generate_pdf(resume_data, TEMPLATES[template_id])
    except Exception as e:
        return _err("GENERATION_FAILED", f"Could not generate resume: {e}")

    storage_key = f"gen_{uuid.uuid4().hex}.pdf"
    dest_path = os.path.join(current_app.config["GENERATED_FOLDER"], storage_key)
    with open(dest_path, "wb") as f:
        f.write(pdf_bytes)

    gen = GeneratedResume(
        user_id=current_user.id,
        template_id=template_id,
        storage_key=storage_key,
    )
    db.session.add(gen)
    db.session.commit()

    return _ok({"generated_resume_id": gen.id, "storage_key": storage_key}), 201


@builder_bp.route("/download/<int:gen_id>", methods=["GET"])
@login_required
def download(gen_id):
    gen = GeneratedResume.query.filter_by(id=gen_id, user_id=current_user.id).first()
    if not gen:
        return _err("NOT_FOUND", "Generated resume not found.", 404)
    path = os.path.join(current_app.config["GENERATED_FOLDER"], gen.storage_key)
    if not os.path.exists(path):
        return _err("FILE_MISSING", "File not found on server.", 404)
    return send_file(path, as_attachment=True, download_name="resume.pdf", mimetype="application/pdf")


@builder_bp.route("/suggest", methods=["POST"])
@login_required
def suggest():
    """
    Return diff-based wording suggestions (LLM, fact-preserving).
    The user must accept/reject each suggestion — nothing applied silently.
    """
    body = request.get_json(silent=True) or {}
    section = body.get("section", "")
    content = body.get("content", "")
    if not content.strip():
        return _err("MISSING_CONTENT", "content is required.")

    from services.llm.provider import get_provider
    from services.llm.prompt_builder import redact_pii, SYSTEM_PROMPT
    from services.llm.response_validator import validate_response

    provider = get_provider()
    user_msg = (
        f"Improve the wording of this resume {section} section. "
        f"Do NOT add, invent, or change any facts, skills, employers, or dates. "
        f"Only improve clarity and impact.\n\nSection content:\n{content}"
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": redact_pii(user_msg)},
    ]

    try:
        result = provider.chat(messages, max_tokens=600)
        suggestion = result["content"]
    except Exception:
        suggestion = content  # fallback: return original unchanged

    return _ok({"original": content, "suggestion": suggestion})


@builder_bp.route("/templates", methods=["GET"])
@login_required
def list_templates():
    return _ok({
        "templates": [
            {"id": 1, "name": "Minimal ATS", "description": "Clean single-column, ATS-optimized"},
            {"id": 2, "name": "Student / Fresher", "description": "Projects & education first"},
            {"id": 3, "name": "Technical", "description": "Skills-forward with tech stack highlight"},
        ]
    })


# ── PDF Generation ────────────────────────────────────────────────────────────

def _generate_pdf(data: dict, template: str) -> bytes:
    """Generate a PDF resume using ReportLab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib import colors
        import io

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                 rightMargin=2*cm, leftMargin=2*cm,
                                 topMargin=2*cm, bottomMargin=2*cm)

        styles = getSampleStyleSheet()
        name_style = ParagraphStyle("Name", parent=styles["Heading1"], fontSize=18, spaceAfter=4)
        contact_style = ParagraphStyle("Contact", parent=styles["Normal"], fontSize=9, spaceAfter=8, textColor=colors.grey)
        section_style = ParagraphStyle("Section", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4,
                                        textColor=colors.HexColor("#1a3c6e"))
        body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, spaceAfter=4, leading=14)

        story = []

        # Header
        name = data.get("name", "")
        if name:
            story.append(Paragraph(name, name_style))
        contacts = [data.get("email", ""), data.get("phone", ""), data.get("location", "")]
        contact_str = "  |  ".join(c for c in contacts if c)
        if contact_str:
            story.append(Paragraph(contact_str, contact_style))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3c6e")))

        # Summary
        if data.get("summary"):
            story.append(Paragraph("Summary", section_style))
            story.append(Paragraph(data["summary"], body_style))

        # Skills
        if data.get("skills"):
            story.append(Paragraph("Skills", section_style))
            skill_text = "  •  ".join(data["skills"]) if isinstance(data["skills"], list) else data["skills"]
            story.append(Paragraph(skill_text, body_style))

        # Experience
        if data.get("experience"):
            story.append(Paragraph("Experience", section_style))
            for exp in data["experience"]:
                if isinstance(exp, dict):
                    story.append(Paragraph(f"<b>{exp.get('title','')}</b> – {exp.get('company','')} ({exp.get('duration','')})", body_style))
                    if exp.get("bullets"):
                        for b in exp["bullets"]:
                            story.append(Paragraph(f"• {b}", body_style))
                else:
                    story.append(Paragraph(str(exp), body_style))

        # Education
        if data.get("education"):
            story.append(Paragraph("Education", section_style))
            for edu in data["education"]:
                text = edu if isinstance(edu, str) else edu.get("raw", str(edu))
                story.append(Paragraph(f"• {text}", body_style))

        # Projects
        if data.get("projects"):
            story.append(Paragraph("Projects", section_style))
            for proj in data["projects"]:
                if isinstance(proj, dict):
                    story.append(Paragraph(f"<b>{proj.get('name','')}</b>: {proj.get('description','')}", body_style))
                else:
                    story.append(Paragraph(f"• {proj}", body_style))

        # Certifications
        if data.get("certifications"):
            story.append(Paragraph("Certifications", section_style))
            for cert in data["certifications"]:
                story.append(Paragraph(f"• {cert}", body_style))

        doc.build(story)
        return buffer.getvalue()

    except ImportError:
        raise RuntimeError("ReportLab not installed. Run: pip install reportlab")
