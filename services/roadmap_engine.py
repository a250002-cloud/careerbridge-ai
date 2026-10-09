"""
services/roadmap_engine.py
Deterministic Personalized Career Roadmap (PRD Section 13).
Uses topological sort over the skill-prerequisite graph.
"""

import os
from collections import defaultdict, deque
from database.models import db, SkillGap, SkillPrerequisite, CareerRoadmap, RoadmapItem, Skill


# Stage assignment by priority
PRIORITY_TO_STAGE = {
    "high": "Fundamentals",
    "medium": "Tools",
    "low": "Practice",
}

# Final stages for completeness
STAGE_ORDER = ["Fundamentals", "Tools", "Practice", "Portfolio", "Job Readiness"]


def generate_roadmap(user_id: int, role_id: int) -> dict:
    """
    Generate and persist a roadmap for (user, role) from their skill gaps.
    Preserves completed items if a roadmap already exists.
    """
    # Get gaps for this role (must run skill_gap_engine first)
    gaps = SkillGap.query.filter_by(user_id=user_id, role_id=role_id).all()

    # Only include gap and partial items
    gap_skill_ids = {
        g.skill_id: g
        for g in gaps
        if g.status in ("gap", "partial")
    }

    if not gap_skill_ids:
        return {"roadmap_items": [], "message": "No gaps found for this role. You're well prepared!"}

    # Expand prerequisites transitively
    all_skill_ids = _expand_prerequisites(set(gap_skill_ids.keys()))

    # Build prerequisite graph for topo sort
    prereq_map = _build_prereq_map(all_skill_ids)

    # Topological sort
    ordered = _topological_sort(all_skill_ids, prereq_map)

    # Fetch effort hours
    effort_map = _get_effort_map(all_skill_ids)

    # Preserve completed items from existing roadmap
    existing_map = {}
    existing_roadmap = CareerRoadmap.query.filter_by(user_id=user_id, role_id=role_id).first()
    if existing_roadmap:
        for item in existing_roadmap.items:
            if item.status == "completed":
                existing_map[item.skill_id] = item.status

    # Build ordered roadmap items
    items = []
    for order_idx, skill_id in enumerate(ordered):
        skill = db.session.get(Skill, skill_id)
        if not skill:
            continue
        gap = gap_skill_ids.get(skill_id)
        priority = gap.priority if gap else "low"
        stage = _assign_stage(priority, order_idx, len(ordered))
        est_hours = effort_map.get(skill_id, 20)
        status = existing_map.get(skill_id, "pending")
        items.append({
            "order": order_idx + 1,
            "skill_id": skill_id,
            "skill_name": skill.canonical_name,
            "stage": stage,
            "est_hours": est_hours,
            "status": status,
            "priority": priority,
        })

    # Persist roadmap
    _persist_roadmap(user_id, role_id, items)

    return {
        "roadmap_items": items,
        "total_items": len(items),
        "total_est_hours": sum(i["est_hours"] for i in items if i["status"] != "completed"),
    }


def _expand_prerequisites(skill_ids: set) -> set:
    """BFS expansion of unmet prerequisites."""
    all_prereqs = SkillPrerequisite.query.all()
    prereq_lookup = defaultdict(set)
    for p in all_prereqs:
        prereq_lookup[p.skill_id].add(p.prerequisite_skill_id)

    expanded = set(skill_ids)
    queue = deque(skill_ids)
    while queue:
        sid = queue.popleft()
        for prereq_id in prereq_lookup.get(sid, set()):
            if prereq_id not in expanded:
                expanded.add(prereq_id)
                queue.append(prereq_id)
    return expanded


def _build_prereq_map(skill_ids: set) -> dict:
    """Returns {skill_id: set_of_prerequisites} for all skills in scope."""
    prereqs = SkillPrerequisite.query.filter(
        SkillPrerequisite.skill_id.in_(skill_ids)
    ).all()
    prereq_map = defaultdict(set)
    for p in prereqs:
        if p.prerequisite_skill_id in skill_ids:
            prereq_map[p.skill_id].add(p.prerequisite_skill_id)
    return prereq_map


def _topological_sort(skill_ids: set, prereq_map: dict) -> list:
    """
    Kahn's algorithm. Items with no prerequisites come first.
    Among equal items, order by priority (high first).
    """
    in_degree = {sid: 0 for sid in skill_ids}
    dependents = defaultdict(set)  # prereq → skills that need it

    for sid, prereqs in prereq_map.items():
        for p in prereqs:
            in_degree[sid] = in_degree.get(sid, 0) + 1
            dependents[p].add(sid)

    queue = deque(sid for sid in skill_ids if in_degree.get(sid, 0) == 0)
    ordered = []
    while queue:
        sid = queue.popleft()
        ordered.append(sid)
        for dep in dependents.get(sid, set()):
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    # Any remaining (cycles – shouldn't happen in a well-formed KB)
    for sid in skill_ids:
        if sid not in ordered:
            ordered.append(sid)
    return ordered


def _get_effort_map(skill_ids: set) -> dict:
    prereqs = SkillPrerequisite.query.filter(
        SkillPrerequisite.skill_id.in_(skill_ids)
    ).all()
    effort = {}
    for p in prereqs:
        effort[p.skill_id] = p.est_effort_hours
    return effort


def _assign_stage(priority: str, order_idx: int, total: int) -> str:
    if priority == "high":
        return "Fundamentals"
    if priority == "medium":
        return "Tools"
    ratio = order_idx / max(total, 1)
    if ratio >= 0.85:
        return "Job Readiness"
    if ratio >= 0.65:
        return "Portfolio"
    return "Practice"


def _persist_roadmap(user_id: int, role_id: int, items: list):
    """Upsert roadmap."""
    roadmap = CareerRoadmap.query.filter_by(user_id=user_id, role_id=role_id).first()
    if not roadmap:
        roadmap = CareerRoadmap(user_id=user_id, role_id=role_id)
        db.session.add(roadmap)
        db.session.flush()
    else:
        # Remove non-completed items (re-generate)
        RoadmapItem.query.filter_by(roadmap_id=roadmap.id).filter(
            RoadmapItem.status != "completed"
        ).delete()

    for item in items:
        if item["status"] == "completed":
            continue  # already persisted
        ri = RoadmapItem(
            roadmap_id=roadmap.id,
            order=item["order"],
            stage=item["stage"],
            skill_id=item["skill_id"],
            est_hours=item["est_hours"],
            status=item["status"],
        )
        db.session.add(ri)
    db.session.commit()
