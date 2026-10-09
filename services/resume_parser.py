"""
services/resume_parser.py
Handles PDF and DOCX text extraction, validation, section detection,
and skill extraction. Produces the Draft Structured Profile (PRD Section 7).
"""

import os
import io
import uuid
import hashlib
import re
from typing import Optional
from flask import current_app

from services.section_detector import detect_sections
from services.skill_extractor import extract_skills


# ── Constants ─────────────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {"pdf", "docx"}
MAX_PAGES = 10
MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Magic bytes for validation
_MAGIC = {
    b"%PDF": "pdf",
    b"PK\x03\x04": "docx",  # ZIP container (DOCX is a ZIP)
}


# ── Public API ────────────────────────────────────────────────────────────────

class ResumeParserError(Exception):
    """Raised on any validation or parsing failure."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def validate_and_save(file_storage, upload_folder: str) -> dict:
    """
    Validate the uploaded FileStorage object, save privately under a UUID key.
    Returns {"storage_key": ..., "file_type": ..., "original_name": ...}.
    Raises ResumeParserError on any problem.
    """
    # Size check (Flask also enforces MAX_CONTENT_LENGTH but belt-and-suspenders)
    data = file_storage.read()
    if len(data) > MAX_SIZE_BYTES:
        raise ResumeParserError("FILE_TOO_LARGE", "File exceeds 5 MB limit.")
    if len(data) == 0:
        raise ResumeParserError("EMPTY_FILE", "Uploaded file is empty.")

    # Magic byte check
    detected_type = None
    for magic, ftype in _MAGIC.items():
        if data[:len(magic)] == magic:
            detected_type = ftype
            break

    if detected_type not in ALLOWED_EXTENSIONS:
        raise ResumeParserError(
            "INVALID_TYPE",
            "Only PDF and DOCX files are accepted. Ensure the file is not corrupted."
        )

    # Extension vs magic consistency
    original_name = file_storage.filename or "resume"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ResumeParserError("INVALID_EXTENSION", "File extension must be .pdf or .docx.")
    if ext != detected_type and not (ext == "docx" and detected_type == "docx"):
        raise ResumeParserError("SPOOFED_EXTENSION", "File extension does not match file content.")

    # DOCX: check for macro-enabled (.docm) attempts
    if detected_type == "docx" and original_name.lower().endswith(".docm"):
        raise ResumeParserError("MACRO_FILE", "Macro-enabled documents are not accepted.")

    # Unique storage key
    storage_key = f"{uuid.uuid4().hex}.{detected_type}"
    dest_path = os.path.join(upload_folder, storage_key)
    with open(dest_path, "wb") as f:
        f.write(data)

    return {
        "storage_key": storage_key,
        "file_type": detected_type,
        "original_name": original_name,
        "size_bytes": len(data),
    }


def parse_resume(storage_key: str, upload_folder: str) -> dict:
    """
    Parse a saved resume file. Returns a structured profile dict.
    Raises ResumeParserError on failure.
    """
    path = os.path.join(upload_folder, storage_key)
    if not os.path.exists(path):
        raise ResumeParserError("FILE_NOT_FOUND", "Resume file not found.")

    ext = storage_key.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        lines, is_scanned = _extract_pdf(path)
        if is_scanned:
            raise ResumeParserError(
                "SCANNED_PDF",
                "This appears to be a scanned/image PDF. Please upload a text-based PDF or DOCX."
            )
    elif ext == "docx":
        lines = _extract_docx(path)
    else:
        raise ResumeParserError("UNSUPPORTED", "Unsupported file type.")

    if not lines:
        raise ResumeParserError("EMPTY_CONTENT", "No readable text found in the file.")

    # Section detection
    result = detect_sections(lines)
    sections = result["sections"]
    section_confidence = result["confidence"]

    # Skill extraction
    skills = extract_skills(sections)

    # Extract education, experience, projects metadata
    education = _extract_education(sections.get("education", []))
    experience = _extract_experience(sections.get("experience", []))
    projects = _extract_projects(sections.get("projects", []))
    certifications = sections.get("certifications", [])
    achievements = sections.get("achievements", [])
    summary = " ".join(sections.get("summary", []))

    return {
        "raw_text": "\n".join(lines),
        "sections_found": list(sections.keys()),
        "section_confidence": section_confidence,
        "skills": skills,
        "education": education,
        "experience": experience,
        "projects": projects,
        "certifications": certifications,
        "achievements": achievements,
        "summary": summary,
    }


# ── Extraction helpers ────────────────────────────────────────────────────────

def _extract_pdf(path: str):
    """Extract text lines from a digital PDF. Returns (lines, is_scanned)."""
    try:
        import pymupdf as fitz  # PyMuPDF >= 1.24.10 (modern API)
    except ImportError:
        try:
            import fitz  # PyMuPDF older fallback
        except ImportError:
            raise ResumeParserError("MISSING_DEP", "PyMuPDF not installed. Run: pip install PyMuPDF")

    doc = fitz.open(path)
    pages_count = max(len(doc), 1)   # save before closing
    if pages_count > MAX_PAGES:
        doc.close()
        raise ResumeParserError("TOO_MANY_PAGES", f"Resume must not exceed {MAX_PAGES} pages.")

    all_lines = []
    total_chars = 0

    for page in doc:
        blocks = page.get_text("blocks")
        # Sort by vertical then horizontal position (reading order)
        blocks.sort(key=lambda b: (round(b[1] / 20), b[0]))
        for block in blocks:
            if block[6] != 0:  # skip image blocks
                continue
            text = block[4].strip()
            if text:
                all_lines.extend(text.splitlines())
                total_chars += len(text)

    doc.close()

    # Scanned detection: very few chars per page
    is_scanned = total_chars < 100 * pages_count
    return all_lines, is_scanned


def _extract_docx(path: str):
    """Extract text lines from a DOCX file."""
    try:
        from docx import Document
    except ImportError:
        raise ResumeParserError("MISSING_DEP", "python-docx not installed.")

    try:
        doc = Document(path)
    except Exception:
        raise ResumeParserError("CORRUPT_DOCX", "DOCX file could not be opened. It may be corrupted.")

    lines = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            lines.append(text)

    # Also extract from tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                text = cell.text.strip()
                if text:
                    lines.append(text)
    return lines


def _extract_education(lines: list[str]) -> list[dict]:
    """Very light structured extraction of education entries."""
    entries = []
    degree_patterns = re.compile(
        r"\b(b\.?tech|b\.?e|b\.?sc|m\.?tech|m\.?sc|m\.?e|mba|b\.?com|bca|mca|bachelor|master|phd|diploma)\b",
        re.IGNORECASE
    )
    for line in lines:
        if degree_patterns.search(line):
            entries.append({"raw": line})
        elif any(w in line.lower() for w in ["university", "college", "institute", "school"]):
            entries.append({"raw": line})
    return entries[:10]  # cap


def _extract_experience(lines: list[str]) -> list[dict]:
    entries = []
    for line in lines:
        if len(line) > 20:
            entries.append({"raw": line})
    return entries[:30]


def _extract_projects(lines: list[str]) -> list[dict]:
    entries = []
    for line in lines:
        if len(line) > 15:
            entries.append({"raw": line})
    return entries[:20]
