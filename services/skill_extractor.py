"""
services/skill_extractor.py
Layered, precision-first skill extraction (PRD Section 7).
Layer 1: dictionary + alias matching
Layer 2: ambiguity resolution
Layer 3: (optional) embedding fallback – flagged as suggested, never auto-confirmed
"""

import re
import csv
import os
import json
from typing import Optional

# ── Load KB ──────────────────────────────────────────────────────────────────

def _load_skills_kb() -> dict:
    """Load skills.csv from kb/ and build alias → skill_id map."""
    kb_path = os.path.join(os.path.dirname(__file__), "..", "kb", "skills.csv")
    kb_path = os.path.normpath(kb_path)
    skills = {}
    alias_map = {}  # lowercase alias → skill_id
    try:
        with open(kb_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sid = int(row["skill_id"])
                canonical = row["canonical_name"].strip()
                aliases_raw = row.get("aliases", "")
                ambiguity_raw = row.get("ambiguity_rules", "{}")

                try:
                    ambiguity = json.loads(ambiguity_raw) if ambiguity_raw.strip().startswith("{") else {}
                except Exception:
                    ambiguity = {}

                skills[sid] = {
                    "skill_id": sid,
                    "canonical_name": canonical,
                    "category": row.get("category", ""),
                    "aliases": [a.strip().lower() for a in aliases_raw.split(",") if a.strip()],
                    "ambiguity_rules": ambiguity,
                }
                # Add canonical + all aliases to the lookup
                alias_map[canonical.lower()] = sid
                for alias in skills[sid]["aliases"]:
                    if alias not in alias_map:   # canonical wins on conflict
                        alias_map[alias] = sid
    except FileNotFoundError:
        pass
    return skills, alias_map


_SKILLS_KB, _ALIAS_MAP = _load_skills_kb()

# Ambiguous single-token skills that need context
_AMBIGUOUS_TOKENS = {
    "r": 32,        # could be R language (stats) – map to Statistics
    "c": None,      # too ambiguous, skip unless context has programming
    "go": None,     # Golang – skip without context
    "swift": None,
    "spring": 12,   # map to Spring Boot with context
    "excel": 31,    # map to Data Visualization / Data Analysis
    "express": 41,  # Express.js
}

# Confidence base values (PRD Table, Section 7)
_CONF_BASE = {
    "skills": 0.45,
    "experience": 0.85,
    "projects": 0.75,
    "certifications": 0.70,
    "other": 0.45,
    "summary": 0.50,
    "achievements": 0.55,
}
_CONF_ADDITIONAL = 0.10
_CONF_MAX = 1.00


# ── Public API ────────────────────────────────────────────────────────────────

def extract_skills(sections: dict) -> list[dict]:
    """
    Main entry point. sections is the dict returned by section_detector.
    Returns a list of skill dicts with confidence, section, evidence_snippet.
    """
    # evidence_map: skill_id → {sections_seen, snippets}
    evidence_map: dict = {}

    for section_name, lines in sections.items():
        section_text = " ".join(lines)
        tokens = _tokenize(section_text)

        for match_text, skill_id in _layer1_matches(section_text, tokens, section_name):
            _add_evidence(evidence_map, skill_id, section_name, match_text)

    # Build result list
    results = []
    for skill_id, ev in evidence_map.items():
        skill = _SKILLS_KB.get(skill_id)
        if not skill:
            continue
        # Compute confidence from evidence sources
        sections_seen = ev["sections_seen"]
        primary_section = max(sections_seen, key=lambda s: _CONF_BASE.get(s, 0.45))
        base_conf = _CONF_BASE.get(primary_section, 0.45)
        extra = min(len(sections_seen) - 1, 3) * _CONF_ADDITIONAL
        confidence = min(base_conf + extra, _CONF_MAX)

        results.append({
            "skill_id": skill_id,
            "canonical_name": skill["canonical_name"],
            "category": skill["category"],
            "confidence": round(confidence, 2),
            "source": "extracted",
            "section": primary_section,
            "evidence_snippet": ev["snippets"][0][:200] if ev["snippets"] else "",
            "extraction_method": "dictionary",
            "user_confirmed": False,
        })

    return results


def normalize_skill_name(name: str) -> Optional[int]:
    """Return skill_id for a canonical name or alias, or None."""
    return _ALIAS_MAP.get(name.strip().lower())


# ── Internal helpers ──────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_.#+/]+", text)


def _layer1_matches(text: str, tokens: list[str], section: str):
    """
    Yield (matched_text, skill_id) for all dictionary matches in the text.
    Uses multi-word phrase matching first, then single-token.
    """
    lower_text = text.lower()
    matched_ids = set()

    # Multi-word phrases (longest match first)
    sorted_aliases = sorted(_ALIAS_MAP.keys(), key=lambda x: -len(x))
    for alias in sorted_aliases:
        if len(alias.split()) < 2:
            continue  # handle single tokens separately
        if alias in lower_text:
            sid = _ALIAS_MAP[alias]
            if sid not in matched_ids:
                matched_ids.add(sid)
                yield (alias, sid)

    # Single tokens
    for tok in tokens:
        lower_tok = tok.lower()
        # Skip very short tokens without explicit disambiguation
        if len(lower_tok) <= 1:
            continue
        if lower_tok in _AMBIGUOUS_TOKENS:
            resolved = _resolve_ambiguous(lower_tok, text, section)
            if resolved and resolved not in matched_ids:
                matched_ids.add(resolved)
                yield (tok, resolved)
        elif lower_tok in _ALIAS_MAP:
            sid = _ALIAS_MAP[lower_tok]
            if sid not in matched_ids:
                matched_ids.add(sid)
                yield (tok, sid)


def _resolve_ambiguous(token: str, context_text: str, section: str) -> Optional[int]:
    """Layer 2: resolve ambiguous tokens using surrounding context."""
    lower_ctx = context_text.lower()
    rules = {
        "r": lambda: _ALIAS_MAP.get("statistics") if re.search(r"r\s+programming|r\s+language|rstudio", lower_ctx) else None,
        "spring": lambda: _ALIAS_MAP.get("spring boot") if re.search(r"spring\s+boot|spring\s+mvc|springboot", lower_ctx) else None,
        "excel": lambda: _ALIAS_MAP.get("data visualization") if section in ("skills", "experience") else None,
        "express": lambda: _ALIAS_MAP.get("express.js") if re.search(r"node|express\.js|expressjs", lower_ctx) else None,
    }
    resolver = rules.get(token)
    return resolver() if resolver else None


def _add_evidence(evidence_map: dict, skill_id: int, section: str, snippet: str):
    if skill_id not in evidence_map:
        evidence_map[skill_id] = {"sections_seen": set(), "snippets": []}
    evidence_map[skill_id]["sections_seen"].add(section)
    if snippet not in evidence_map[skill_id]["snippets"]:
        evidence_map[skill_id]["snippets"].append(snippet)
