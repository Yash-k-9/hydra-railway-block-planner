"""
HYDRA - Data Normalizer
Converts TMS, SMMS and TDMS tasks into a unified MaintenanceTask schema.
"""


DEPARTMENT_MAP = {
    "TMS": "ENGINEERING",
    "SMMS": "SIGNALLING",
    "TDMS": "TRACTION",
}


def normalize_tms(tasks):
    """Convert raw TMS task dicts to unified schema."""
    unified = []
    for t in tasks:
        unified.append({
            "task_id": t["task_id"],
            "source_system": "TMS",
            "department": "ENGINEERING",
            "asset_id": t.get("asset_id", ""),
            "location_km": t.get("location_km", 0.0),
            "corridor_id": t["corridor_id"],
            "task_type": t.get("defect_type", "Track maintenance"),
            "description": f"{t.get('defect_type', 'Maintenance')} at KM {t.get('location_km', '?')}",
            "severity": t.get("severity", 1),
            "asset_criticality": t.get("asset_criticality", 1),
            "safety_impact": t.get("safety_impact", 1),
            "overdue_days": t.get("overdue_days", 0),
            "urgency": 0.0,        # calculated by priority engine
            "train_impact": 0.0,   # calculated by priority engine
            "duration_minutes": t.get("duration_minutes", 60),
            "requires_isolation": False,
            "due_date": t.get("due_date", ""),
            "priority_score": 0.0,
            "priority_level": "",
            "status": "pending",
        })
    return unified


def normalize_smms(tasks):
    """Convert raw SMMS task dicts to unified schema."""
    unified = []
    for t in tasks:
        unified.append({
            "task_id": t["task_id"],
            "source_system": "SMMS",
            "department": "SIGNALLING",
            "asset_id": t.get("asset_id", ""),
            "location_km": t.get("location_km", 0.0),
            "corridor_id": t["corridor_id"],
            "task_type": t.get("defect_type", "Signal maintenance"),
            "description": f"{t.get('defect_type', 'Maintenance')} at KM {t.get('location_km', '?')}",
            "severity": t.get("severity", 1),
            "asset_criticality": t.get("asset_criticality", 1),
            "safety_impact": t.get("safety_impact", 1),
            "overdue_days": t.get("overdue_days", 0),
            "urgency": 0.0,
            "train_impact": 0.0,
            "duration_minutes": t.get("duration_minutes", 60),
            "requires_isolation": False,
            "due_date": t.get("due_date", ""),
            "priority_score": 0.0,
            "priority_level": "",
            "status": "pending",
        })
    return unified


def normalize_tdms(tasks):
    """Convert raw TDMS task dicts to unified schema."""
    unified = []
    for t in tasks:
        unified.append({
            "task_id": t["task_id"],
            "source_system": "TDMS",
            "department": "TRACTION",
            "asset_id": t.get("asset_id", ""),
            "location_km": t.get("location_km", 0.0),
            "corridor_id": t["corridor_id"],
            "task_type": t.get("defect_type", "OHE maintenance"),
            "description": f"{t.get('defect_type', 'Maintenance')} at KM {t.get('location_km', '?')}",
            "severity": t.get("severity", 1),
            "asset_criticality": t.get("asset_criticality", 1),
            "safety_impact": t.get("safety_impact", 1),
            "overdue_days": t.get("overdue_days", 0),
            "urgency": 0.0,
            "train_impact": 0.0,
            "duration_minutes": t.get("duration_minutes", 60),
            "requires_isolation": bool(t.get("requires_isolation", False)),
            "due_date": t.get("due_date", ""),
            "priority_score": 0.0,
            "priority_level": "",
            "status": "pending",
        })
    return unified


def normalize_all(tms_tasks, smms_tasks, tdms_tasks):
    """Normalize and combine all three department task lists.

    Returns:
        list[dict]: Combined unified task list.
        dict: Counts per source system.
    """
    tms_unified = normalize_tms(tms_tasks)
    smms_unified = normalize_smms(smms_tasks)
    tdms_unified = normalize_tdms(tdms_tasks)

    combined = tms_unified + smms_unified + tdms_unified

    # Deduplicate by task_id (keep first occurrence)
    seen = set()
    deduped = []
    for task in combined:
        if task["task_id"] not in seen:
            seen.add(task["task_id"])
            deduped.append(task)

    counts = {
        "TMS": len(tms_unified),
        "SMMS": len(smms_unified),
        "TDMS": len(tdms_unified),
        "total": len(deduped),
    }

    return deduped, counts
