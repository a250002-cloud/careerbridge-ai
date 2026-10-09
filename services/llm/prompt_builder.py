"""
services/llm/prompt_builder.py
Builds structured, grounded prompts from profile + KB context.
PII is stripped before sending (PRD Section 14).

Context labels are consistent between this file and provider.py's _extract_list/_extract_value
so the stub provider can parse them without a real LLM.
"""

import re


# ── PII Redaction ─────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d[\d\s\-().]{7,}\d)")
_URL_RE   = re.compile(r"https?://\S+|www\.\S+")
_NAME_RE  = re.compile(r"\b[A-Z][a-z]{1,20}\s[A-Z][a-z]{1,20}\b")


def redact_pii(text: str) -> str:
    """Remove emails, phones, URLs, and potential full names from text."""
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _PHONE_RE.sub("[PHONE]", text)
    text = _URL_RE.sub("[URL]", text)
    text = _NAME_RE.sub("[NAME]", text)
    return text


# ── System Prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are CareerBridge AI Career Copilot — a precise, helpful, and honest career guidance assistant.

STRICT RULES (never break these):
1. Only mention skills the user actually has — listed under "User confirmed skills" in the context.
2. Only mention role requirements from the "Role skills required" section in the context.
3. Never invent skills, qualifications, employers, dates, achievements, or scores not in the context.
4. Never guarantee employment, salary, job offers, or career outcomes. Say "can strengthen candidacy" instead.
5. If information is missing from context, say so clearly and suggest what the user should do.
6. Never change or assign match scores, readiness percentages, or confidence values — only explain them.
7. Be specific and actionable. Reference the user's actual skills, gaps and role by name.
8. Keep answers focused — 3–6 sentences or a short bullet list is ideal unless detail is requested.
9. When the user asks about their gaps, always list them by name from context.
10. When the user asks about their roadmap, list the next items in order from context."""


def build_system_prompt() -> str:
    return SYSTEM_PROMPT


# ── Main Context Builder ──────────────────────────────────────────────────────

def build_user_context(
    target_role: dict | None,
    confirmed_skills: list[dict],
    gaps: list[dict] | None,
    roadmap_items: list[dict] | None,
    user_message: str,
    intent: str = "",
    chat_history: list[dict] | None = None,
    predictions: list[dict] | None = None,
) -> list[dict]:
    """
    Build a messages list: [system, ...history, user_with_context].
    All text is PII-redacted. Labels must match the extractor in provider.py.
    """
    context_lines = _build_context_block(
        target_role, confirmed_skills, gaps, roadmap_items, predictions, intent
    )
    context_text = "\n".join(context_lines) if context_lines else "No profile context available."
    context_text = redact_pii(context_text)
    user_msg_clean = redact_pii(user_message)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Inject up to 6 recent history turns (3 exchanges) for continuity
    if chat_history:
        for turn in chat_history[-6:]:
            role = turn.get("role", "user")
            content = redact_pii(turn.get("content", ""))
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    # Final user message with full context block
    messages.append({
        "role": "user",
        "content": f"[CONTEXT]\n{context_text}\n\n[QUESTION]\n{user_msg_clean}"
    })
    return messages


# ── Context Block Builder ─────────────────────────────────────────────────────

def _build_context_block(
    target_role: dict | None,
    confirmed_skills: list[dict],
    gaps: list[dict] | None,
    roadmap_items: list[dict] | None,
    predictions: list[dict] | None,
    intent: str,
) -> list[str]:
    lines = []

    # ── Skills breakdown ──────────────────────────────────────────────────────
    if confirmed_skills:
        all_names   = [s.get("canonical_name", "") for s in confirmed_skills if s.get("canonical_name")]
        strong      = [s.get("canonical_name") for s in confirmed_skills if s.get("confidence", 0) >= 0.70]
        partial     = [s.get("canonical_name") for s in confirmed_skills if 0.40 <= s.get("confidence", 0) < 0.70]

        lines.append(f"User confirmed skills: {', '.join(all_names)}")
        if strong:
            lines.append(f"Strong skills (≥70%): {', '.join(strong)}")
        if partial:
            lines.append(f"Skills to improve (40-70%): {', '.join(partial)}")
        lines.append(f"Total confirmed skills: {len(all_names)}")

    # ── Target role ───────────────────────────────────────────────────────────
    if target_role:
        lines.append(f"Target role: {target_role.get('name', '')}")
        if target_role.get("description"):
            lines.append(f"Role description: {target_role['description']}")
        if target_role.get("interview_topics"):
            topics = target_role["interview_topics"]
            if isinstance(topics, list):
                lines.append(f"Interview topics for this role: {', '.join(topics)}")
        if target_role.get("typical_projects"):
            projs = target_role["typical_projects"]
            if isinstance(projs, list):
                lines.append(f"Typical projects for this role: {', '.join(projs)}")

    # ── Match band (from predictions) ─────────────────────────────────────────
    if predictions and target_role:
        target_name = target_role.get("name", "")
        for p in predictions:
            if p.get("role_name") == target_name:
                lines.append(f"Match band: {p.get('band', '').replace('_', ' ')}")
                break

    # ── Skill gaps (structured) ───────────────────────────────────────────────
    if gaps and target_role:
        gap_list     = [g["skill_name"] for g in gaps if g.get("status") == "gap" and g.get("skill_name")]
        partial_list = [g["skill_name"] for g in gaps if g.get("status") == "partial" and g.get("skill_name")]
        strong_list  = [g["skill_name"] for g in gaps if g.get("status") == "strong" and g.get("skill_name")]
        high_gaps    = [g["skill_name"] for g in gaps if g.get("priority") == "high" and g.get("status") in ("gap", "partial") and g.get("skill_name")]

        if gap_list:
            lines.append(f"Missing skills (gaps): {', '.join(gap_list)}")
        if partial_list:
            lines.append(f"Skills needing improvement: {', '.join(partial_list)}")
        if strong_list:
            lines.append(f"Strong skills for role: {', '.join(strong_list)}")
        if high_gaps:
            lines.append(f"High-priority gaps: {', '.join(high_gaps)}")
        # Backward-compat label used by stub
        all_gap_names = gap_list + partial_list
        if all_gap_names:
            lines.append(f"Skill gaps for target role: {', '.join(all_gap_names[:15])}")

        # Readiness from gap data
        readiness = _compute_readiness_from_gaps(gaps)
        if readiness is not None:
            lines.append(f"Career readiness: {int(readiness * 100)}%")

    # ── Roadmap ───────────────────────────────────────────────────────────────
    if roadmap_items:
        pending    = [r.get("skill_name", "") for r in roadmap_items if r.get("status") == "pending" and r.get("skill_name")]
        in_prog    = [r.get("skill_name", "") for r in roadmap_items if r.get("status") == "in_progress" and r.get("skill_name")]
        completed  = [r.get("skill_name", "") for r in roadmap_items if r.get("status") == "completed" and r.get("skill_name")]
        total      = len(roadmap_items)
        done_count = len(completed)

        if pending:
            lines.append(f"Next roadmap items: {', '.join(pending[:5])}")
        if in_prog:
            lines.append(f"Currently in progress: {', '.join(in_prog[:3])}")
        if done_count > 0:
            lines.append(f"Roadmap progress: {done_count}/{total} items completed")

    # ── Intent hint (helps the LLM focus) ────────────────────────────────────
    if intent and intent != "out_of_scope":
        lines.append(f"User intent: {intent.replace('_', ' ')}")

    return lines


def _compute_readiness_from_gaps(gaps: list[dict]) -> float | None:
    """Recompute readiness from gap rows (mirrors skill_gap_engine logic)."""
    if not gaps:
        return None
    importance_w = {"high": 3, "medium": 2, "low": 1}
    status_s     = {"strong": 1.0, "partial": 0.5, "gap": 0.0}
    total_w, earned_w = 0, 0.0
    for g in gaps:
        w = importance_w.get(g.get("priority", "medium"), 2)
        s = status_s.get(g.get("status", "gap"), 0.0)
        total_w  += w
        earned_w += w * s
    return earned_w / total_w if total_w > 0 else None
