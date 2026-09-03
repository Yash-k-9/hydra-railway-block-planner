"""
HYDRA - Data Loader
Reads TMS, SMMS, TDMS and COA CSV files into lists of dicts.
"""

import csv
import os


def _read_csv(filepath):
    """Read a CSV file and return a list of dicts."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Data file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _to_int(val, default=0):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _to_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _to_bool(val):
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes")
    return bool(val)


def load_tms(filepath):
    """Load TMS (Engineering/Track) tasks from CSV."""
    rows = _read_csv(filepath)
    tasks = []
    for row in rows:
        tasks.append({
            "task_id": row["task_id"].strip(),
            "asset_id": row.get("asset_id", "").strip(),
            "location_km": _to_float(row.get("location_km")),
            "corridor_id": row["corridor_id"].strip(),
            "defect_type": row.get("defect_type", "").strip(),
            "severity": _to_int(row.get("severity"), 1),
            "duration_minutes": _to_int(row.get("duration_minutes"), 60),
            "overdue_days": _to_int(row.get("overdue_days")),
            "asset_criticality": _to_int(row.get("asset_criticality"), 1),
            "safety_impact": _to_int(row.get("safety_impact"), 1),
            "due_date": row.get("due_date", "").strip(),
        })
    return tasks


def load_smms(filepath):
    """Load SMMS (Signal & Telecom) tasks from CSV."""
    rows = _read_csv(filepath)
    tasks = []
    for row in rows:
        tasks.append({
            "task_id": row["task_id"].strip(),
            "asset_id": row.get("asset_id", "").strip(),
            "location_km": _to_float(row.get("location_km")),
            "corridor_id": row["corridor_id"].strip(),
            "defect_type": row.get("defect_type", "").strip(),
            "severity": _to_int(row.get("severity"), 1),
            "duration_minutes": _to_int(row.get("duration_minutes"), 60),
            "overdue_days": _to_int(row.get("overdue_days")),
            "asset_criticality": _to_int(row.get("asset_criticality"), 1),
            "safety_impact": _to_int(row.get("safety_impact"), 1),
            "due_date": row.get("due_date", "").strip(),
        })
    return tasks


def load_tdms(filepath):
    """Load TDMS (Traction/OHE) tasks from CSV."""
    rows = _read_csv(filepath)
    tasks = []
    for row in rows:
        tasks.append({
            "task_id": row["task_id"].strip(),
            "asset_id": row.get("asset_id", "").strip(),
            "location_km": _to_float(row.get("location_km")),
            "corridor_id": row["corridor_id"].strip(),
            "defect_type": row.get("defect_type", "").strip(),
            "severity": _to_int(row.get("severity"), 1),
            "duration_minutes": _to_int(row.get("duration_minutes"), 60),
            "overdue_days": _to_int(row.get("overdue_days")),
            "asset_criticality": _to_int(row.get("asset_criticality"), 1),
            "safety_impact": _to_int(row.get("safety_impact"), 1),
            "requires_isolation": _to_bool(row.get("requires_isolation", False)),
            "due_date": row.get("due_date", "").strip(),
        })
    return tasks


def load_coa(filepath):
    """Load COA (train movements) from CSV."""
    rows = _read_csv(filepath)
    trains = []
    for row in rows:
        trains.append({
            "train_id": row["train_id"].strip(),
            "train_type": row.get("train_type", "").strip(),
            "corridor_id": row["corridor_id"].strip(),
            "date": row["date"].strip(),
            "start_time": row["start_time"].strip(),
            "end_time": row["end_time"].strip(),
            "is_confirmed": _to_bool(row.get("is_confirmed", True)),
        })
    return trains
