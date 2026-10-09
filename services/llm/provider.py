"""
services/llm/provider.py
Concrete LLM adapters: StubProvider (context-aware, uses real profile data),
OpenAIProvider (real API calls), and the factory function get_provider().
"""

import os
import time

from services.llm.base import LLMBase


# ── Stub Provider (development / offline fallback) ────────────────────────────

class StubProvider(LLMBase):
    """
    Context-aware deterministic fallback provider — no external calls, zero cost.
    Accepts the full structured context dict so replies reference real user data.
    """

    def chat(self, messages: list[dict], max_tokens: int = 512) -> dict:
        # Pull the [CONTEXT] block and the [QUESTION] from the last user message
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        # Parse context block and question from the structured message
        context_block = ""
        question = last_user
        if "[CONTEXT]" in last_user and "[QUESTION]" in last_user:
            parts = last_user.split("[QUESTION]", 1)
            context_block = parts[0].replace("[CONTEXT]", "").strip()
            question = parts[1].strip()

        content = _context_aware_reply(question, context_block)
        return {
            "content": content,
            "tokens_in": len(last_user.split()),
            "tokens_out": len(content.split()),
            "cost": 0.0,
            "model": "stub",
            "latency_ms": 5,
        }

    def is_available(self) -> bool:
        return True


def _context_aware_reply(question: str, context: str) -> str:
    """
    Generate a precise, data-driven reply using the structured context
    that was injected into the prompt by prompt_builder.py.
    Falls back to a helpful generic reply if context is sparse.
    """
    q = question.lower()
    ctx = context.lower()

    # ── Parse context values ──────────────────────────────────────────────────
    skills        = _extract_list(context, "User confirmed skills:")
    strong_skills = _extract_list(context, "Strong skills (≥70%):")
    partial_skills = _extract_list(context, "Skills to improve (40-70%):")
    gap_skills    = _extract_list(context, "Missing skills (gaps):")
    target_role   = _extract_value(context, "Target role:")
    readiness     = _extract_value(context, "Career readiness:")
    next_items    = _extract_list(context, "Next roadmap items:")
    all_gaps      = _extract_list(context, "Skill gaps for target role:")
    interview_topics = _extract_list(context, "Interview topics for this role:")
    match_band    = _extract_value(context, "Match band:")
    role_desc     = _extract_value(context, "Role description:")
    completed     = _extract_value(context, "Roadmap progress:")
    high_gaps     = _extract_list(context, "High-priority gaps:")

    has_profile = bool(skills)
    has_target  = bool(target_role)

    # ── Intent routing ────────────────────────────────────────────────────────

    # --- Skill gap / missing skills ---
    if any(w in q for w in ["gap", "missing", "lack", "don't have", "need to learn", "what skills", "required"]):
        if not has_target:
            return ("You haven't selected a target role yet. Go to Career Matches, choose a role, "
                    "and I'll show you exactly which skills you're missing.")
        if gap_skills:
            high = _extract_list(context, "High-priority gaps:")
            reply = f"For **{target_role}**, here are your skill gaps:\n\n"
            if high:
                reply += f"🔴 **High priority (core skills):** {', '.join(high)}\n"
            medium = _extract_list(context, "Skill gaps for target role:")
            remaining = [g for g in medium if g not in high][:5]
            if remaining:
                reply += f"🟡 **Medium priority:** {', '.join(remaining)}\n"
            if readiness:
                reply += f"\nYour current readiness is **{readiness}**. "
            reply += "\nFocus on the high-priority gaps first — they are the core skills employers test."
            return reply
        return (f"Great news — no major gaps found for {target_role}! "
                "Your confirmed skills cover the role well. Consider deepening "
                "expertise in optional skills to stand out.")

    # --- Roadmap / learning path ---
    if any(w in q for w in ["roadmap", "learning path", "plan", "what next", "next step", "study", "how to learn"]):
        if not has_target:
            return ("Select a target role first (Career Matches page) and I'll generate "
                    "a prerequisite-ordered roadmap just for you.")
        if next_items:
            reply = f"Your next steps on the roadmap for **{target_role}**:\n\n"
            for i, item in enumerate(next_items[:5], 1):
                reply += f"{i}. {item}\n"
            if completed:
                reply += f"\nProgress so far: {completed}"
            reply += ("\n\nItems are ordered so prerequisites come first. "
                      "Mark each done on the Roadmap page and your readiness score updates automatically.")
            return reply
        return (f"Your roadmap for {target_role} is ready on the Roadmap page. "
                "It's ordered by prerequisites — complete Fundamentals before moving to Tools and Practice stages.")

    # --- Career matches / recommendations ---
    if any(w in q for w in ["match", "recommend", "best role", "which role", "suitable", "career for me", "career match"]):
        if not has_profile:
            return ("Upload and confirm your resume first. Once I have your skill profile, "
                    "I'll rank all 10 tech roles by how well they match your confirmed skills.")
        if target_role and match_band:
            reply = f"Your top match is **{target_role}** ({match_band})."
            if strong_skills:
                reply += f"\n\n✅ **Your strong skills for this role:** {', '.join(strong_skills[:6])}"
            if gap_skills:
                reply += f"\n❌ **Core skills still needed:** {', '.join(gap_skills[:4])}"
            reply += ("\n\nGo to Career Matches to see the full ranked list with evidence "
                      "and to compare roles side by side.")
            return reply
        return ("Go to Career Matches to see your ranked roles. Each card shows matched skills, "
                "missing core skills, and a match band (Strong / Good / Exploratory). "
                "Select one as your target to unlock gap analysis and roadmap.")

    # --- Readiness / progress ---
    if any(w in q for w in ["readiness", "progress", "how ready", "score", "percentage", "how far"]):
        if readiness and target_role:
            pct = readiness
            reply = f"Your career readiness for **{target_role}** is **{pct}**.\n\n"
            if strong_skills:
                reply += f"✅ Strong skills: {', '.join(strong_skills[:5])}\n"
            if partial_skills:
                reply += f"🟡 Skills to improve: {', '.join(partial_skills[:4])}\n"
            if gap_skills:
                reply += f"❌ Gaps: {', '.join(gap_skills[:4])}\n"
            reply += ("\n*This is a profile-match indicator based on your confirmed skills — "
                      "not a measure of employability.*")
            return reply
        return ("Your readiness score is on the Dashboard and Skill Gap pages. "
                "It's calculated from how well your confirmed skills cover the target role's "
                "core, recommended, and optional requirements.")

    # --- Interview preparation ---
    if any(w in q for w in ["interview", "prepare", "practice", "questions", "how to interview", "tips"]):
        if target_role and interview_topics:
            reply = f"For a **{target_role}** interview, focus on these topics:\n\n"
            for topic in interview_topics[:6]:
                reply += f"• {topic}\n"
            reply += ("\n**Tips:**\n"
                      "• Use the STAR method for behavioural questions (Situation, Task, Action, Result)\n"
                      "• Walk through a project that demonstrates each core skill\n"
                      "• Be ready to explain your problem-solving approach, not just the answer\n\n"
                      "Visit the Interview Prep page for role-specific practice questions.")
            return reply
        return ("For technical interviews:\n"
                "• Review core data structures and algorithms\n"
                "• Practice explaining your projects clearly\n"
                "• Use STAR method for behavioural questions\n"
                "• Select a target role first so I can give you role-specific topics.")

    # --- Resume improvement ---
    if any(w in q for w in ["resume", "cv", "improve resume", "rewrite", "ats", "cover letter"]):
        reply = "Here's how to strengthen your resume:\n\n"
        reply += "• **Lead with impact:** Start each bullet with a strong action verb (Built, Designed, Improved)\n"
        reply += "• **Quantify:** Add numbers wherever possible (e.g. 'reduced load time by 40%')\n"
        reply += "• **Keywords:** Match your skills section to the job description\n"
        reply += "• **ATS friendly:** Single column, standard headings, no tables or images\n"
        if skills:
            reply += f"\nYour confirmed skills to highlight: {', '.join(skills[:8])}\n"
        reply += "\nUse the **Resume Builder** to generate a clean ATS-ready PDF from your profile."
        return reply

    # --- Role information ---
    if any(w in q for w in ["what is", "tell me about", "describe", "explain", "role", "what does a"]):
        if target_role and role_desc:
            reply = f"**{target_role}**\n\n{role_desc}\n\n"
            if interview_topics:
                reply += f"Key areas: {', '.join(interview_topics[:5])}"
            return reply
        return ("I have information on these 10 tech roles in the knowledge base:\n"
                "Python Developer, Java Developer, Backend Developer, Frontend Developer, "
                "Full Stack Developer, Data Analyst, Data Scientist, ML Engineer, "
                "QA/Test Engineer, Database Developer.\n\n"
                "Select a target role on the Career Matches page for detailed information.")

    # --- Career switch ---
    if any(w in q for w in ["switch", "transition", "change career", "move from", "move to", "switch to"]):
        if target_role and gap_skills:
            reply = (f"Transitioning to **{target_role}** — here's what you need to build:\n\n"
                     f"**Core skills to acquire:** {', '.join(gap_skills[:5])}\n")
            if next_items:
                reply += f"**Start with:** {next_items[0]}\n"
            reply += ("\n**Realistic timeline:** Most career transitions in tech take 3–12 months "
                      "of focused learning, depending on your starting point.\n\n"
                      "Your roadmap on this platform is ordered by prerequisites — follow it step by step.")
            return reply
        return ("For a career switch:\n"
                "1. Select your target role on the Career Matches page\n"
                "2. Review your skill gap analysis\n"
                "3. Follow the prerequisite-ordered roadmap\n"
                "4. Build 1–2 portfolio projects demonstrating the new skills\n\n"
                "Your existing skills may transfer more than you think — check the matches page.")

    # --- Project guidance ---
    if any(w in q for w in ["project", "build", "portfolio", "project idea", "what to build", "side project"]):
        if target_role:
            role_projects = {
                "Python Developer":      ["Build a REST API with Flask + MySQL", "Create a CLI automation tool", "Write a web scraper with data export"],
                "Backend Developer":     ["User authentication service with JWT", "Rate-limited REST API with Docker", "Database-backed task manager API"],
                "Frontend Developer":    ["Portfolio site with React", "Weather dashboard consuming a public API", "Accessible component library"],
                "Full Stack Developer":  ["Full-stack to-do app (React + Flask + MySQL)", "E-commerce site with cart and checkout", "Real-time chat app"],
                "Data Analyst":          ["Sales dashboard in Python/Tableau", "EDA notebook on a Kaggle dataset", "Automated reporting script"],
                "Data Scientist":        ["Predictive model on a public dataset", "NLP sentiment analysis project", "A/B testing analysis notebook"],
                "Machine Learning Engineer": ["Deploy a scikit-learn model as a REST API", "MLOps pipeline with versioned models", "Feature store prototype"],
                "QA / Test Engineer":    ["Selenium test suite for a demo website", "API test framework with pytest", "CI/CD pipeline with automated tests"],
                "Database Developer":    ["Schema design for an e-commerce database", "Query optimization challenge on a large dataset", "ETL pipeline from CSV to MySQL"],
                "Java Developer":        ["Spring Boot REST API with auth", "Microservices demo with Spring Cloud", "Console-based inventory management system"],
            }
            projects = role_projects.get(target_role, [])
            if projects:
                reply = f"Recommended portfolio projects for **{target_role}**:\n\n"
                for p in projects:
                    reply += f"• {p}\n"
                reply += "\nEach project should demonstrate at least one core skill from your roadmap."
                return reply
        return ("Strong portfolio projects:\n"
                "• Solve a real problem you personally have\n"
                "• Demonstrate the core skills of your target role\n"
                "• Include a README explaining what it does and how you built it\n"
                "• Deploy it (GitHub Pages, Heroku, Render) so it's accessible\n\n"
                "Select a target role and I'll suggest specific projects for that role.")

    # --- Skills comparison / what do I have ---
    if any(w in q for w in ["what skills do i have", "my skills", "my profile", "skills i have", "show my skills"]):
        if skills:
            reply = f"Your confirmed skills ({len(skills)} total):\n\n"
            if strong_skills:
                reply += f"✅ **Strong:** {', '.join(strong_skills)}\n"
            if partial_skills:
                reply += f"🟡 **Improving:** {', '.join(partial_skills)}\n"
            return reply
        return ("I don't see any confirmed skills yet. Upload your resume and confirm the extracted profile, "
                "or add skills manually on the Skills page.")

    # --- Generic greeting or help ---
    if any(w in q for w in ["hi", "hello", "hey", "help", "what can you do", "start"]):
        intro = "👋 I'm your **AI Career Copilot**. Here's what I can help with:\n\n"
        intro += "• 🎯 **Career matches** — which tech roles suit your skills\n"
        intro += "• 📊 **Skill gaps** — what you're missing for your target role\n"
        intro += "• 🗺️ **Roadmap** — what to learn next and in what order\n"
        intro += "• 📝 **Resume** — how to improve your resume\n"
        intro += "• 🎤 **Interview prep** — topics and tips for your target role\n"
        intro += "• 💡 **Project ideas** — portfolio projects to build\n\n"
        if target_role:
            intro += f"Your current target role is **{target_role}**. Ask me anything about it!"
        else:
            intro += "Start by selecting a target role on the Career Matches page."
        return intro

    # --- Default fallback ---
    fallback = "I can help with your career matches, skill gaps, learning roadmap, resume, interview prep, and project ideas."
    if target_role:
        fallback += f" Your current target is **{target_role}**."
    if next_items:
        fallback += f" Your next roadmap item is **{next_items[0]}**."
    fallback += " What would you like to explore?"
    return fallback


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_list(context: str, label: str) -> list[str]:
    """Extract a comma-separated list value after a label in the context block."""
    for line in context.splitlines():
        if line.lower().startswith(label.lower()):
            value = line[len(label):].strip()
            return [v.strip() for v in value.split(",") if v.strip()]
    return []


def _extract_value(context: str, label: str) -> str:
    """Extract a single value after a label in the context block."""
    for line in context.splitlines():
        if line.lower().startswith(label.lower()):
            return line[len(label):].strip()
    return ""


# ── OpenAI Provider ───────────────────────────────────────────────────────────

class OpenAIProvider(LLMBase):
    """Real OpenAI / compatible API provider."""

    def __init__(self, api_key: str, model: str, max_tokens: int):
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens

    def chat(self, messages: list[dict], max_tokens: int = 512) -> dict:
        import requests
        t0 = time.time()
        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                json={"model": self._model, "messages": messages, "max_tokens": max_tokens or self._max_tokens},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            latency_ms = int((time.time() - t0) * 1000)
            return {
                "content": content,
                "tokens_in": usage.get("prompt_tokens", 0),
                "tokens_out": usage.get("completion_tokens", 0),
                "cost": _estimate_cost(self._model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
                "model": self._model,
                "latency_ms": latency_ms,
            }
        except Exception as e:
            raise RuntimeError(f"OpenAI call failed: {e}") from e

    def is_available(self) -> bool:
        return bool(self._api_key)


def _estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    rates = {
        "gpt-4o-mini":    (0.00015, 0.00060),
        "gpt-4o":         (0.005,   0.015),
        "gpt-3.5-turbo":  (0.0005,  0.0015),
    }
    rate_in, rate_out = rates.get(model, (0.001, 0.002))
    return (tokens_in * rate_in + tokens_out * rate_out) / 1000.0


# ── Factory ───────────────────────────────────────────────────────────────────

def get_provider() -> LLMBase:
    """Return the configured LLM provider, falling back to stub on failure."""
    provider_name = os.environ.get("LLM_PROVIDER", "stub").lower()
    if provider_name == "openai":
        api_key = os.environ.get("LLM_API_KEY", "")
        model   = os.environ.get("LLM_MODEL", "gpt-4o-mini")
        max_tok = int(os.environ.get("LLM_MAX_TOKENS", "1024"))
        if api_key:
            return OpenAIProvider(api_key, model, max_tok)
    return StubProvider()


# Keep this alias for backward-compat with the fallback import in chatbot.py
def _stub_reply(user_msg: str) -> str:
    return _context_aware_reply(user_msg, "")
