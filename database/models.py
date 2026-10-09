"""
CareerBridge AI – SQLAlchemy models.
All tables described in PRD Section 19.
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


@login_manager.unauthorized_handler
def unauthorized():
    """Return JSON 401 for API routes instead of redirecting to a login page."""
    from flask import request, jsonify
    if request.path.startswith("/api/"):
        return jsonify({"status": "error", "error": {"code": "UNAUTHORIZED", "message": "Authentication required."}}), 401
    from flask import redirect, url_for
    return redirect(url_for("auth.login"))


# ── Auth ─────────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = db.relationship("UserProfile", back_populates="user", uselist=False, cascade="all,delete-orphan")
    resumes = db.relationship("Resume", back_populates="user", cascade="all,delete-orphan")
    user_skills = db.relationship("UserSkill", back_populates="user", cascade="all,delete-orphan")
    predictions = db.relationship("CareerPrediction", back_populates="user", cascade="all,delete-orphan")
    skill_gaps = db.relationship("SkillGap", back_populates="user", cascade="all,delete-orphan")
    roadmaps = db.relationship("CareerRoadmap", back_populates="user", cascade="all,delete-orphan")
    chat_sessions = db.relationship("ChatSession", back_populates="user", cascade="all,delete-orphan")
    feedbacks = db.relationship("Feedback", back_populates="user", cascade="all,delete-orphan")
    generated_resumes = db.relationship("GeneratedResume", back_populates="user", cascade="all,delete-orphan")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email, "created_at": self.created_at.isoformat()}


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    token_hash = db.Column(db.String(256), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)


# ── Profiles ─────────────────────────────────────────────────────────────────

class UserProfile(db.Model):
    __tablename__ = "user_profiles"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    education_summary = db.Column(db.Text, nullable=True)
    target_role_id = db.Column(db.Integer, db.ForeignKey("career_roles.role_id"), nullable=True)
    goals = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = db.relationship("User", back_populates="profile")


# ── Resumes ───────────────────────────────────────────────────────────────────

class Resume(db.Model):
    __tablename__ = "resumes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)
    storage_key = db.Column(db.String(255), unique=True, nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", back_populates="resumes")
    analysis = db.relationship("ResumeAnalysis", back_populates="resume", uselist=False, cascade="all,delete-orphan")


class ResumeAnalysis(db.Model):
    __tablename__ = "resume_analysis"
    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id"), nullable=False, unique=True)
    parser_version = db.Column(db.String(20), default="v1.0")
    profile_json = db.Column(db.JSON, nullable=True)
    section_confidence = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(20), default="draft")   # draft | confirmed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resume = db.relationship("Resume", back_populates="analysis")


# ── Knowledge Base ────────────────────────────────────────────────────────────

class Skill(db.Model):
    __tablename__ = "skills"
    id = db.Column(db.Integer, primary_key=True)
    canonical_name = db.Column(db.String(120), unique=True, nullable=False)
    category = db.Column(db.String(60), nullable=True)
    aliases = db.Column(db.JSON, default=list)          # list of strings
    description = db.Column(db.Text, nullable=True)
    related_skills = db.Column(db.JSON, default=list)
    ambiguity_rules = db.Column(db.JSON, default=dict)  # context rules

    def to_dict(self):
        return {
            "id": self.id, "canonical_name": self.canonical_name,
            "category": self.category, "aliases": self.aliases,
            "description": self.description
        }


class CareerRole(db.Model):
    __tablename__ = "career_roles"
    role_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    entry_level_relevance = db.Column(db.Float, default=1.0)
    related_roles = db.Column(db.JSON, default=list)
    typical_projects = db.Column(db.JSON, default=list)
    interview_topics = db.Column(db.JSON, default=list)

    role_skills = db.relationship("RoleSkill", back_populates="role", cascade="all,delete-orphan")

    def to_dict(self):
        return {
            "role_id": self.role_id, "name": self.name,
            "description": self.description,
            "entry_level_relevance": self.entry_level_relevance,
            "typical_projects": self.typical_projects,
            "interview_topics": self.interview_topics
        }


class RoleSkill(db.Model):
    __tablename__ = "role_skills"
    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("career_roles.role_id"), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    importance = db.Column(db.String(20), default="recommended")  # core | recommended | optional
    weight = db.Column(db.Float, default=1.0)
    evidence_hint = db.Column(db.String(255), nullable=True)
    role = db.relationship("CareerRole", back_populates="role_skills")
    skill = db.relationship("Skill")


class SkillPrerequisite(db.Model):
    __tablename__ = "skill_prerequisites"
    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    prerequisite_skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    est_effort_hours = db.Column(db.Integer, default=20)
    suggested_practice = db.Column(db.Text, nullable=True)
    skill = db.relationship("Skill", foreign_keys=[skill_id])
    prereq = db.relationship("Skill", foreign_keys=[prerequisite_skill_id])


class KbVersion(db.Model):
    __tablename__ = "kb_versions"
    id = db.Column(db.Integer, primary_key=True)
    kb_version = db.Column(db.String(20), unique=True, nullable=False)
    released_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewers = db.Column(db.JSON, default=list)
    change_note = db.Column(db.Text, nullable=True)


# ── User Skills ───────────────────────────────────────────────────────────────

class UserSkill(db.Model):
    __tablename__ = "user_skills"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    confidence = db.Column(db.Float, default=0.45)
    source = db.Column(db.String(40), default="extracted")  # extracted | self_reported | suggested
    section = db.Column(db.String(60), nullable=True)
    evidence_snippet = db.Column(db.Text, nullable=True)
    extraction_method = db.Column(db.String(40), default="dictionary")
    user_confirmed = db.Column(db.Boolean, default=False)
    user = db.relationship("User", back_populates="user_skills")
    skill = db.relationship("Skill")

    def to_dict(self):
        return {
            "id": self.id, "skill_id": self.skill_id,
            "canonical_name": self.skill.canonical_name if self.skill else None,
            "category": self.skill.category if self.skill else None,
            "confidence": self.confidence, "source": self.source,
            "section": self.section, "evidence_snippet": self.evidence_snippet,
            "user_confirmed": self.user_confirmed,
            "status": self._status()
        }

    def _status(self):
        if self.confidence >= 0.70:
            return "strong"
        if self.confidence >= 0.40:
            return "partial"
        return "gap"


# ── Predictions ───────────────────────────────────────────────────────────────

class CareerPrediction(db.Model):
    __tablename__ = "career_predictions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("career_roles.role_id"), nullable=False)
    ml_score = db.Column(db.Float, default=0.0)
    kb_score = db.Column(db.Float, default=0.0)
    final_score = db.Column(db.Float, default=0.0)
    band = db.Column(db.String(30), default="exploratory")  # strong_match | good_match | exploratory
    explanation_json = db.Column(db.JSON, nullable=True)
    model_version = db.Column(db.String(40), nullable=True)
    kb_version = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", back_populates="predictions")
    role = db.relationship("CareerRole")


# ── Gaps & Roadmap ────────────────────────────────────────────────────────────

class SkillGap(db.Model):
    __tablename__ = "skill_gaps"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("career_roles.role_id"), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    status = db.Column(db.String(20), default="gap")        # strong | partial | gap
    priority = db.Column(db.String(20), default="medium")   # high | medium | low
    confidence = db.Column(db.Float, default=0.0)
    kb_version = db.Column(db.String(20), nullable=True)
    user = db.relationship("User", back_populates="skill_gaps")
    skill = db.relationship("Skill")
    role = db.relationship("CareerRole")


class CareerRoadmap(db.Model):
    __tablename__ = "career_roadmaps"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("career_roles.role_id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = db.relationship("User", back_populates="roadmaps")
    role = db.relationship("CareerRole")
    items = db.relationship("RoadmapItem", back_populates="roadmap", cascade="all,delete-orphan",
                             order_by="RoadmapItem.order")


class RoadmapItem(db.Model):
    __tablename__ = "roadmap_items"
    id = db.Column(db.Integer, primary_key=True)
    roadmap_id = db.Column(db.Integer, db.ForeignKey("career_roadmaps.id"), nullable=False)
    order = db.Column(db.Integer, nullable=False)
    stage = db.Column(db.String(40), default="Fundamentals")
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    est_hours = db.Column(db.Integer, default=20)
    status = db.Column(db.String(20), default="pending")  # pending | in_progress | completed
    roadmap = db.relationship("CareerRoadmap", back_populates="items")
    skill = db.relationship("Skill")

    def to_dict(self):
        return {
            "id": self.id, "order": self.order, "stage": self.stage,
            "skill_id": self.skill_id,
            "skill_name": self.skill.canonical_name if self.skill else None,
            "est_hours": self.est_hours, "status": self.status
        }


# ── Chat ─────────────────────────────────────────────────────────────────────

class ChatSession(db.Model):
    __tablename__ = "chat_sessions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", back_populates="chat_sessions")
    messages = db.relationship("ChatMessage", back_populates="session", cascade="all,delete-orphan",
                                order_by="ChatMessage.created_at")


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_sessions.id"), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # user | assistant
    content = db.Column(db.Text, nullable=False)
    intent = db.Column(db.String(60), nullable=True)
    intent_confidence = db.Column(db.Float, nullable=True)
    validator_result = db.Column(db.JSON, nullable=True)
    tokens = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    session = db.relationship("ChatSession", back_populates="messages")


# ── Resume Builder ────────────────────────────────────────────────────────────

class ResumeTemplate(db.Model):
    __tablename__ = "resume_templates"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)


class GeneratedResume(db.Model):
    __tablename__ = "generated_resumes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey("resume_templates.id"), nullable=True)
    storage_key = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", back_populates="generated_resumes")
    template = db.relationship("ResumeTemplate")


# ── LLM Usage & Feedback ──────────────────────────────────────────────────────

class LlmUsage(db.Model):
    __tablename__ = "llm_usage"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    model = db.Column(db.String(60), nullable=True)
    tokens_in = db.Column(db.Integer, default=0)
    tokens_out = db.Column(db.Integer, default=0)
    cost = db.Column(db.Float, default=0.0)
    latency_ms = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Feedback(db.Model):
    __tablename__ = "feedback"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    target_type = db.Column(db.String(40), nullable=False)  # recommendation | skill | roadmap
    target_id = db.Column(db.Integer, nullable=True)
    rating = db.Column(db.Integer, nullable=True)           # 1 (thumbs up) | -1 (thumbs down)
    comment = db.Column(db.Text, nullable=True)
    model_version = db.Column(db.String(40), nullable=True)
    kb_version = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", back_populates="feedbacks")


# ── Model Registry ────────────────────────────────────────────────────────────

class ModelRegistry(db.Model):
    __tablename__ = "model_registry"
    id = db.Column(db.Integer, primary_key=True)
    model_version = db.Column(db.String(40), unique=True, nullable=False)
    model_type = db.Column(db.String(60), nullable=True)
    dataset_version = db.Column(db.String(20), nullable=True)
    feature_version = db.Column(db.String(20), nullable=True)
    kb_version = db.Column(db.String(20), nullable=True)
    metrics_json = db.Column(db.JSON, nullable=True)
    active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
