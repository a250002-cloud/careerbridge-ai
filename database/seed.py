"""
database/seed.py
Loads the Knowledge Base (skills, roles, role_skills, prerequisites)
from CSV files into the database.
Run: flask seed-db
"""
import os
import csv
import json
import click
from flask import Flask
from flask.cli import with_appcontext

from database.models import db, Skill, CareerRole, RoleSkill, SkillPrerequisite, KbVersion, ResumeTemplate


KB_DIR = os.path.join(os.path.dirname(__file__), "..", "kb")


def _load_csv(filename: str) -> list[dict]:
    path = os.path.join(KB_DIR, filename)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def seed_kb(verbose: bool = True):
    def log(msg):
        if verbose:
            print(msg)

    # Skills
    skill_rows = _load_csv("skills.csv")
    skill_id_map = {}
    for row in skill_rows:
        sid = int(row["skill_id"])
        aliases = [a.strip() for a in row.get("aliases", "").split(",") if a.strip()]
        existing = db.session.get(Skill, sid)
        if existing:
            skill_id_map[sid] = existing
            continue
        skill = Skill(
            id=sid,
            canonical_name=row["canonical_name"].strip(),
            category=row.get("category", "").strip(),
            aliases=aliases,
            description=row.get("description", "").strip(),
            ambiguity_rules={},
        )
        db.session.add(skill)
        skill_id_map[sid] = skill
    db.session.flush()
    log(f"  Loaded {len(skill_rows)} skills.")

    # Career Roles
    role_rows = _load_csv("career_roles.csv")
    for row in role_rows:
        rid = int(row["role_id"])
        if db.session.get(CareerRole, rid):
            continue
        try:
            related = json.loads(row.get("related_roles", "[]"))
            projects = json.loads(row.get("typical_projects", "[]"))
            topics = json.loads(row.get("interview_topics", "[]"))
        except Exception:
            related, projects, topics = [], [], []

        role = CareerRole(
            role_id=rid,
            name=row["name"].strip(),
            description=row.get("description", "").strip(),
            entry_level_relevance=float(row.get("entry_level_relevance", 1.0)),
            related_roles=related,
            typical_projects=projects,
            interview_topics=topics,
        )
        db.session.add(role)
    db.session.flush()
    log(f"  Loaded {len(role_rows)} roles.")

    # Role-Skills
    rs_rows = _load_csv("role_skills.csv")
    for row in rs_rows:
        rid = int(row["role_id"])
        sid = int(row["skill_id"])
        existing = RoleSkill.query.filter_by(role_id=rid, skill_id=sid).first()
        if existing:
            continue
        rs = RoleSkill(
            role_id=rid,
            skill_id=sid,
            importance=row.get("importance", "recommended"),
            weight=float(row.get("weight", 1.0)),
            evidence_hint=row.get("evidence_hint", ""),
        )
        db.session.add(rs)
    db.session.flush()
    log(f"  Loaded {len(rs_rows)} role-skill rows.")

    # Skill Prerequisites
    prereq_rows = _load_csv("skill_prerequisites.csv")
    for row in prereq_rows:
        sid  = int(row["skill_id"])
        psid = int(row["prerequisite_skill_id"])
        existing = SkillPrerequisite.query.filter_by(skill_id=sid, prerequisite_skill_id=psid).first()
        if existing:
            continue
        prereq = SkillPrerequisite(
            skill_id=sid,
            prerequisite_skill_id=psid,
            est_effort_hours=int(row.get("est_effort_hours", 20)),
            suggested_practice=row.get("suggested_practice", ""),
        )
        db.session.add(prereq)
    log(f"  Loaded {len(prereq_rows)} prerequisite rows.")

    # KB Version
    kb_ver = "v0.1"
    if not KbVersion.query.filter_by(kb_version=kb_ver).first():
        db.session.add(KbVersion(kb_version=kb_ver, reviewers=["seed"], change_note="Initial KB v0.1"))

    # Resume templates
    for name, desc in [
        ("Minimal ATS", "Clean single-column ATS-optimized layout"),
        ("Student / Fresher", "Projects and education front"),
        ("Technical", "Skills-forward with tech stack highlight"),
    ]:
        if not ResumeTemplate.query.filter_by(name=name).first():
            db.session.add(ResumeTemplate(name=name, description=desc))

    db.session.commit()
    log("  KB seed complete.")


def register_commands(app: Flask):
    @app.cli.command("seed-db")
    @with_appcontext
    def seed_db_command():
        """Seed the database with KB data."""
        click.echo("Creating tables and seeding KB...")
        db.create_all()
        seed_kb()
        click.echo("Done.")

    @app.cli.command("init-db")
    @with_appcontext
    def init_db_command():
        """Create all tables (no data)."""
        db.create_all()
        click.echo("Tables created.")
