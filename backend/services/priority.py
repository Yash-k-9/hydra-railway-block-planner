"""
HYDRA - Priority Scoring Engine
Transparent, rule-based priority scoring. No ML.

Formula:
    priority_score = 0.25 * severity_norm
                   + 0.20 * criticality_norm
                   + 0.15 * overdue_norm
                   + 0.15 * safety_norm
                   + 0.15 * urgency_norm
                   + 0.10 * train_impact_norm

All sub-scores are normalized to [0, 1].
Final score is scaled to 0–100.

Classification:
    90–100  →  CRITICAL
    75–89   →  HIGH
    50–74   →  MEDIUM
     0–49   →  LOW
"""

from datetime import datetime, date
from collections import Counter

# ── Weights ────────────────────────────────────────────────────────────────
WEIGHTS = {
    "severity": 0.25,
    "criticality": 0.20,
    "overdue": 0.15,
    "safety": 0.15,
    "urgency": 0.15,
    "train_impact": 0.10,
}

PLANNING_START = date(2026, 9, 7)


def _classify(score):
    if score >= 85:
        return "CRITICAL"
    elif score >= 70:
        return "HIGH"
    elif score >= 50:
        return "MEDIUM"
    return "LOW"


def _urgency_from_due_date(due_date_str, overdue_days=0):
    """Calculate urgency score from due date.

    Overdue → 1.0
    Due today → 0.9
    1-3 days → 0.7
    4-7 days → 0.5
    7-14 days → 0.3
    >14 days → 0.1
    """
    if overdue_days > 0:
        return 1.0

    if not due_date_str:
        return 0.5

    try:
        due = datetime.strptime(due_date_str, "%Y-%m-%d").date()
    except ValueError:
        return 0.5

    days_remaining = (due - PLANNING_START).days

    if days_remaining <= 0:
        return 0.9
    elif days_remaining <= 3:
        return 0.7
    elif days_remaining <= 7:
        return 0.5
    elif days_remaining <= 14:
        return 0.3
    return 0.1


def _train_impact_for_corridor(corridor_id, train_counts):
    """Normalize train impact: busier corridors → higher impact.

    train_counts: dict mapping corridor_id → number of daily trains.
    """
    if not train_counts:
        return 0.5
    max_count = max(train_counts.values()) if train_counts else 1
    count = train_counts.get(corridor_id, 0)
    return min(count / max(max_count, 1), 1.0)


def calculate_priority(task, train_counts=None):
    """Calculate and assign priority_score and priority_level to a task dict.

    Modifies the task dict in-place and returns it.
    """
    severity_norm = min(task.get("severity", 1) / 5.0, 1.0)
    criticality_norm = min(task.get("asset_criticality", 1) / 5.0, 1.0)
    safety_norm = min(task.get("safety_impact", 1) / 5.0, 1.0)
    overdue_norm = min(task.get("overdue_days", 0) / 30.0, 1.0)
    urgency_norm = _urgency_from_due_date(
        task.get("due_date", ""), task.get("overdue_days", 0)
    )
    train_impact_norm = _train_impact_for_corridor(
        task.get("corridor_id", ""), train_counts or {}
    )

    raw = (
        WEIGHTS["severity"] * severity_norm
        + WEIGHTS["criticality"] * criticality_norm
        + WEIGHTS["overdue"] * overdue_norm
        + WEIGHTS["safety"] * safety_norm
        + WEIGHTS["urgency"] * urgency_norm
        + WEIGHTS["train_impact"] * train_impact_norm
    )

    score = round(raw * 100, 1)
    score = max(0, min(100, score))

    task["urgency"] = round(urgency_norm, 3)
    task["train_impact"] = round(train_impact_norm, 3)
    task["priority_score"] = score
    task["priority_level"] = _classify(score)

    return task


def calculate_all_priorities(tasks, trains=None):
    """Calculate priorities for all tasks.

    Args:
        tasks: list of unified task dicts
        trains: list of train movement dicts (for train_impact)

    Returns:
        tasks (modified in-place), summary dict
    """
    # Count trains per corridor per day, then average
    train_counts = {}
    if trains:
        corridor_dates = Counter()
        corridor_days = Counter()
        for tr in trains:
            cid = tr["corridor_id"]
            corridor_dates[cid] += 1
            corridor_days[cid] = corridor_days.get(cid, set()) if isinstance(
                corridor_days.get(cid), set
            ) else set()

        # Simple: total trains per corridor / 7 days
        from collections import defaultdict
        daily = defaultdict(int)
        for tr in trains:
            daily[tr["corridor_id"]] += 1
        train_counts = {cid: count / 7.0 for cid, count in daily.items()}

    for task in tasks:
        calculate_priority(task, train_counts)

    # Build summary
    levels = Counter(t["priority_level"] for t in tasks)
    summary = {
        "CRITICAL": levels.get("CRITICAL", 0),
        "HIGH": levels.get("HIGH", 0),
        "MEDIUM": levels.get("MEDIUM", 0),
        "LOW": levels.get("LOW", 0),
    }
    return tasks, summary
