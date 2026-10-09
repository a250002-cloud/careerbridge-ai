"""
tests/test_services.py
Basic unit tests for deterministic services.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Skill extractor ───────────────────────────────────────────────────────────
def test_skill_extractor_basic():
    from services.skill_extractor import extract_skills
    sections = {
        "skills": ["Python, Flask, MySQL, Git, Docker"],
        "projects": ["Built a REST API with Flask and deployed it using Docker"],
    }
    skills = extract_skills(sections)
    names = [s["canonical_name"] for s in skills]
    assert "Python" in names, f"Python not found in {names}"
    assert "Flask" in names, f"Flask not found in {names}"
    assert "Git" in names, f"Git not found in {names}"


def test_skill_confidence_project():
    """Skills found in projects should get higher base confidence than skills-only."""
    from services.skill_extractor import extract_skills
    sections = {
        "skills": ["Python"],
        "projects": ["Built a REST API with Python and Flask"],
    }
    skills = extract_skills(sections)
    python_skill = next((s for s in skills if s["canonical_name"] == "Python"), None)
    assert python_skill is not None
    # Evidence in both sections → higher than skills-only base (0.45)
    assert python_skill["confidence"] > 0.45, f"Expected > 0.45, got {python_skill['confidence']}"


# ── Section detector ──────────────────────────────────────────────────────────
def test_section_detector():
    from services.section_detector import detect_sections
    lines = [
        "John Doe", "john@example.com",
        "Skills", "Python, Flask, MySQL",
        "Experience", "Backend Developer at Acme Corp",
        "Education", "B.Tech Computer Science",
    ]
    result = detect_sections(lines)
    sections = result["sections"]
    assert "skills" in sections
    assert "experience" in sections
    assert "education" in sections


def test_section_detector_case_insensitive():
    from services.section_detector import detect_sections
    lines = ["TECHNICAL SKILLS", "Python, Java"]
    result = detect_sections(lines)
    # "technical skills" → should map to skills
    sections = result["sections"]
    # Heading itself won't appear as content, Python/Java will be in skills
    assert len(sections) > 0


# ── Skill gap engine (oracle) ─────────────────────────────────────────────────
def test_gap_status_mapping():
    """Confidence → status mapping must be exact (PRD Section 12, 100% floor)."""
    from services.skill_gap_engine import _confidence_to_status
    assert _confidence_to_status(0.80) == "strong"
    assert _confidence_to_status(0.70) == "strong"
    assert _confidence_to_status(0.69) == "partial"
    assert _confidence_to_status(0.40) == "partial"
    assert _confidence_to_status(0.39) == "gap"
    assert _confidence_to_status(0.00) == "gap"


def test_readiness_formula():
    """Readiness formula verified against hand-computed oracle."""
    from services.skill_gap_engine import _compute_readiness

    class MockRoleSkill:
        def __init__(self, skill_id, importance):
            self.skill_id = skill_id
            self.importance = importance

    role_skills = [
        MockRoleSkill(1, "core"),           # w=3
        MockRoleSkill(2, "recommended"),    # w=2
        MockRoleSkill(3, "optional"),       # w=1
    ]
    # skill 1: strong (1.0), skill 2: partial (0.5), skill 3: gap (0.0)
    user_skill_map = {1: 0.80, 2: 0.55, 3: 0.10}
    readiness = _compute_readiness(role_skills, user_skill_map)
    # Expected: (3*1.0 + 2*0.5 + 1*0.0) / (3+2+1) = 4/6 = 0.6667
    assert abs(readiness - (4.0/6.0)) < 0.001, f"Got {readiness}, expected {4/6:.4f}"


# ── Response validator ────────────────────────────────────────────────────────
def test_response_validator_blocks_guarantee():
    from services.llm.response_validator import validate_response
    text = "Apply now, you will get hired immediately."
    is_valid, issues, sanitized = validate_response(text, ["Python"], ["Flask"])
    assert "outcome_guarantee_detected" in issues
    assert "you will get hired" not in sanitized


def test_response_validator_allows_valid():
    from services.llm.response_validator import validate_response
    text = "Focus on improving your Flask skills by building a REST API project."
    is_valid, issues, sanitized = validate_response(text, ["Python"], ["Flask"])
    assert "outcome_guarantee_detected" not in issues


# ── Roadmap topological sort ──────────────────────────────────────────────────
def test_topo_sort_ordering():
    """Prerequisites must always come before their dependents."""
    from services.roadmap_engine import _topological_sort
    # skill 2 requires skill 1
    skill_ids = {1, 2, 3}
    prereq_map = {2: {1}}  # 2 depends on 1
    ordered = _topological_sort(skill_ids, prereq_map)
    assert ordered.index(1) < ordered.index(2), "Prerequisite 1 must come before 2"
