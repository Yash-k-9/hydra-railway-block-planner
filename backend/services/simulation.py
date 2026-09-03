"""
HYDRA - Simulation / Test Mode Engine
Handles disruption injection and re-optimization for test scenarios.
"""

import copy
import uuid
from datetime import datetime


def inject_train_delay(trains, train_id, delay_minutes):
    """Inject a train delay into the simulation.

    Args:
        trains: list of train movement dicts (will be modified)
        train_id: ID of the delayed train
        delay_minutes: minutes of delay

    Returns:
        dict with event details and affected movements
    """
    affected = []
    for t in trains:
        if t["train_id"] == train_id:
            # Shift both start and end times
            old_start = t["start_time"]
            old_end = t["end_time"]

            parts_s = old_start.split(":")
            new_start_min = int(parts_s[0]) * 60 + int(parts_s[1]) + delay_minutes
            h, m = divmod(new_start_min, 60)
            t["start_time"] = f"{h:02d}:{m:02d}"

            parts_e = old_end.split(":")
            new_end_min = int(parts_e[0]) * 60 + int(parts_e[1]) + delay_minutes
            h, m = divmod(new_end_min, 60)
            t["end_time"] = f"{h:02d}:{m:02d}"

            affected.append({
                "train_id": train_id,
                "date": t["date"],
                "corridor_id": t["corridor_id"],
                "old_start": old_start,
                "old_end": old_end,
                "new_start": t["start_time"],
                "new_end": t["end_time"],
            })

    return {
        "event_type": "train_delay",
        "train_id": train_id,
        "delay_minutes": delay_minutes,
        "affected_movements": affected,
    }


def inject_new_defect(tasks, defect):
    """Inject a new critical maintenance defect.

    Args:
        tasks: list of unified task dicts (will be modified)
        defect: dict with task properties

    Returns:
        The new task dict
    """
    new_task = {
        "task_id": defect.get("task_id", f"EMR-{uuid.uuid4().hex[:6].upper()}"),
        "source_system": "EMERGENCY",
        "department": defect.get("department", "ENGINEERING"),
        "asset_id": defect.get("asset_id", "EMR-ASSET"),
        "location_km": defect.get("location_km", 0.0),
        "corridor_id": defect.get("corridor_id", "C124"),
        "task_type": defect.get("defect_type", "Emergency defect"),
        "description": defect.get("description", "Emergency maintenance required"),
        "severity": defect.get("severity", 5),
        "asset_criticality": defect.get("criticality", 5),
        "safety_impact": defect.get("safety_impact", 5),
        "overdue_days": 0,
        "urgency": 1.0,
        "train_impact": 0.5,
        "duration_minutes": defect.get("duration_minutes", 90),
        "requires_isolation": defect.get("requires_isolation", False),
        "due_date": defect.get("due_date", "2026-09-07"),
        "priority_score": 0.0,   # will be recalculated
        "priority_level": "",
        "status": "pending",
    }

    tasks.append(new_task)
    return new_task


def find_affected_blocks(blocks, trains, corridor_id=None):
    """Find blocks that conflict with (possibly modified) train movements.

    Returns list of block dicts that now have conflicts.
    """
    from services.block_windows import check_conflict

    affected = []
    for block in blocks:
        if corridor_id and block["corridor_id"] != corridor_id:
            continue
        conflicts = check_conflict(
            block["start_time"], block["end_time"],
            trains, block["corridor_id"], block["date"]
        )
        if conflicts:
            affected.append({
                "block": block,
                "conflicting_trains": conflicts,
            })
    return affected


def create_simulation_snapshot(tasks, trains):
    """Create a deep copy of the current state for simulation."""
    return {
        "tasks": copy.deepcopy(tasks),
        "trains": copy.deepcopy(trains),
        "created_at": datetime.now().isoformat(),
    }
