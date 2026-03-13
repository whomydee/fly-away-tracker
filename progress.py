"""Progress calculation and status derivation — mirrors the Next.js logic."""

from datetime import datetime


STATUS_COMPLETION = {"complete": 1.0, "in_progress": 0.5, "not_started": 0.0}


def calculate_task_progress(tasks: list[dict]) -> float:
    if not tasks:
        return 0.0
    total_weight = sum(t["weight"] for t in tasks)
    if total_weight == 0:
        return sum(STATUS_COMPLETION[t["status"]] for t in tasks) / len(tasks)
    return sum(t["weight"] * STATUS_COMPLETION[t["status"]] for t in tasks) / total_weight


def calculate_weighted_progress(items: list[dict]) -> float:
    """Generic weighted average for milestones or sections with a 'progress' key."""
    if not items:
        return 0.0
    total_weight = sum(i["weight"] for i in items)
    if total_weight == 0:
        return sum(i["progress"] for i in items) / len(items)
    return sum(i["weight"] * i["progress"] for i in items) / total_weight


def derive_status_label(milestones: list[dict]) -> str:
    with_deadlines = [m for m in milestones if m.get("deadline")]
    if not with_deadlines:
        return "on_track"

    now = datetime.now()
    for m in with_deadlines:
        dl = m["deadline"]
        if isinstance(dl, str):
            dl = datetime.fromisoformat(dl)
        if dl < now and m["status"] != "complete":
            return "behind"

    all_deadlined_complete = all(m["status"] == "complete" for m in with_deadlines)
    has_remaining = any(m["status"] != "complete" for m in milestones)
    if all_deadlined_complete and has_remaining:
        return "ahead"

    return "on_track"


def get_progress_color(pct: float) -> str:
    if pct <= 0.24:
        return "#ef4444"
    if pct <= 0.49:
        return "#f59e0b"
    if pct <= 0.74:
        return "#eab308"
    return "#22c55e"


SECTION_COLORS = [
    "#8b5cf6", "#10b981", "#f43f5e", "#0ea5e9",
    "#f59e0b", "#06b6d4", "#d946ef", "#14b8a6",
]

USER_ACCENT_COLORS = [
    {"gradient_start": "#7c3aed", "gradient_end": "#a78bfa"},
    {"gradient_start": "#059669", "gradient_end": "#2dd4bf"},
    {"gradient_start": "#e11d48", "gradient_end": "#f472b6"},
    {"gradient_start": "#0284c7", "gradient_end": "#22d3ee"},
]

STATUS_BADGES = {
    "ahead": ("Ahead", "#22c55e"),
    "on_track": ("On Track", "#3b82f6"),
    "behind": ("Behind", "#ef4444"),
}
