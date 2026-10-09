"""
services/section_detector.py
Detects common resume sections using heading dictionaries + layout cues.
PRD Section 7 — Section Detection.
"""

import re

# Heading dictionaries for 7 section types
SECTION_HEADINGS = {
    "experience": [
        "experience", "work experience", "employment", "professional experience",
        "work history", "career history", "internship", "internships",
        "positions held", "job history",
    ],
    "education": [
        "education", "academic background", "educational background",
        "academic qualifications", "qualifications", "degrees",
    ],
    "skills": [
        "skills", "technical skills", "key skills", "core competencies",
        "competencies", "expertise", "technologies", "tech stack",
        "programming languages", "tools", "tools & technologies",
    ],
    "projects": [
        "projects", "personal projects", "academic projects", "side projects",
        "portfolio", "work samples", "project experience",
    ],
    "certifications": [
        "certifications", "certificates", "certification", "accreditations",
        "professional certifications", "courses",
    ],
    "achievements": [
        "achievements", "accomplishments", "awards", "honors", "recognition",
        "activities", "extracurricular", "leadership", "volunteering",
    ],
    "summary": [
        "summary", "objective", "profile", "about me", "career objective",
        "professional summary", "overview", "bio", "introduction",
    ],
}

# Inverted map for fast lookup
_HEADING_TO_SECTION = {}
for _sec, _headings in SECTION_HEADINGS.items():
    for _h in _headings:
        _HEADING_TO_SECTION[_h.lower()] = _sec


def detect_sections(lines: list[str]) -> dict:
    """
    Given a list of text lines from a resume, return a dict mapping
    section_name -> list of text lines belonging to that section.

    Unknown headings are stored under 'other'.
    Section confidence is also returned.
    """
    sections: dict = {}
    current_section = "other"
    section_order = []
    confidence: dict = {}

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        detected = _identify_heading(line)
        if detected:
            current_section = detected
            if current_section not in sections:
                sections[current_section] = []
                section_order.append(current_section)
        else:
            if current_section not in sections:
                sections[current_section] = []
                if current_section not in section_order:
                    section_order.append(current_section)
            sections[current_section].append(line)

    # Compute rough confidence: how many standard sections were found
    standard = set(SECTION_HEADINGS.keys())
    found = set(sections.keys()) & standard
    for sec in found:
        confidence[sec] = 0.90 if sec in ("skills", "experience", "education") else 0.80
    for sec in (standard - found):
        confidence[sec] = 0.0

    return {"sections": sections, "section_order": section_order, "confidence": confidence}


def _identify_heading(line: str) -> str | None:
    """Return section name if line looks like a section heading, else None."""
    # Normalise: lower, strip punctuation
    clean = re.sub(r"[:\-_\|]+$", "", line.strip()).strip().lower()

    # Direct match
    if clean in _HEADING_TO_SECTION:
        return _HEADING_TO_SECTION[clean]

    # All-caps heading heuristic (e.g. "PROFESSIONAL EXPERIENCE")
    if line.isupper() and 3 <= len(line.split()) <= 6:
        if clean in _HEADING_TO_SECTION:
            return _HEADING_TO_SECTION[clean]

    # Short line entirely matching a heading pattern
    if len(line.split()) <= 5:
        if clean in _HEADING_TO_SECTION:
            return _HEADING_TO_SECTION[clean]

    return None
