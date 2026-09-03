"""
HYDRA - Synthetic Railway Data Generator
Generates fictional maintenance tasks and train movements for demonstration.
All data is completely fictional - no real railway systems are used.
"""

import csv
import os
import random
from datetime import datetime, timedelta

random.seed(42)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")

# ── Corridors ──────────────────────────────────────────────────────────────
CORRIDORS = ["C124", "C130", "C145", "C160", "C175"]

CORRIDOR_INFO = {
    "C124": {"name": "Rajpur–Shivnagar", "km_start": 120.0, "km_end": 130.0},
    "C130": {"name": "Devgarh–Kundanpur", "km_start": 200.0, "km_end": 215.0},
    "C145": {"name": "Amravalli–Bhairavpur", "km_start": 300.0, "km_end": 315.0},
    "C160": {"name": "Chandrapur–Lokeshwaram", "km_start": 400.0, "km_end": 412.0},
    "C175": {"name": "Trivenipur–Siddharth Nagar", "km_start": 500.0, "km_end": 515.0},
}

# Bundle cluster KM points – tasks from all 3 departments are placed near these
# so the coordination engine can discover bundling opportunities.
BUNDLE_CLUSTERS = {
    "C124": [124.5, 127.0],
    "C130": [205.0, 210.0],
    "C145": [305.0, 310.0],
    "C160": [405.0, 408.0],
    "C175": [505.0, 510.0],
}

PLANNING_DATES = [f"2026-09-{d:02d}" for d in range(7, 14)]

# ── Defect catalogues ─────────────────────────────────────────────────────
TMS_DEFECTS = [
    "Rail defect", "Sleeper replacement", "Ballast maintenance",
    "Weld repair", "Track geometry issue",
]
SMMS_DEFECTS = [
    "Signal fault", "Relay issue", "Cable damage",
    "Signal lamp failure", "Telecom equipment fault",
]
TDMS_DEFECTS = [
    "Catenary issue", "Insulator defect", "OHE wire damage",
    "Mast foundation issue", "Pantograph interaction issue",
]

# ── Train schedule templates (per corridor per day) ────────────────────────
# base_hour/base_min = nominal departure, duration = minutes the corridor is occupied
TRAIN_TEMPLATES = {
    "C124": [  # Busy corridor – 4 trains/day
        {"base_hour": 8, "base_min": 0, "dur": 20, "type": "Express"},
        {"base_hour": 11, "base_min": 30, "dur": 15, "type": "Passenger"},
        {"base_hour": 14, "base_min": 0, "dur": 20, "type": "Express"},
        {"base_hour": 18, "base_min": 30, "dur": 25, "type": "Goods"},
    ],
    "C130": [  # 3 trains/day
        {"base_hour": 7, "base_min": 30, "dur": 15, "type": "Passenger"},
        {"base_hour": 13, "base_min": 0, "dur": 20, "type": "Express"},
        {"base_hour": 17, "base_min": 0, "dur": 15, "type": "Goods"},
    ],
    "C145": [  # 3 trains/day
        {"base_hour": 9, "base_min": 0, "dur": 15, "type": "Express"},
        {"base_hour": 12, "base_min": 30, "dur": 20, "type": "Passenger"},
        {"base_hour": 16, "base_min": 30, "dur": 15, "type": "Goods"},
    ],
    "C160": [  # 2 trains/day
        {"base_hour": 10, "base_min": 0, "dur": 20, "type": "Passenger"},
        {"base_hour": 15, "base_min": 0, "dur": 15, "type": "Goods"},
    ],
    "C175": [  # 2 trains/day
        {"base_hour": 8, "base_min": 30, "dur": 15, "type": "Express"},
        {"base_hour": 16, "base_min": 0, "dur": 20, "type": "Passenger"},
    ],
}

TRAIN_TYPE_PREFIX = {"Express": "EXP", "Passenger": "PASS", "Goods": "GDS"}


# ── Helpers ────────────────────────────────────────────────────────────────

def _random_due_date():
    """Due date within planning window, ~30% chance of being past-due."""
    base = datetime(2026, 9, 7)
    offset = random.randint(-3, 6)
    return (base + timedelta(days=offset)).strftime("%Y-%m-%d")


def _random_overdue():
    """30% chance of being overdue (1-15 days), otherwise 0."""
    return random.randint(1, 15) if random.random() < 0.3 else 0


def _scattered_km(info, clusters, count=4):
    """Generate KM points that avoid bundle-cluster zones (>1.5 km away)."""
    kms = []
    for _ in range(count):
        for _attempt in range(200):
            km = round(random.uniform(info["km_start"], info["km_end"]), 1)
            if all(abs(km - c) > 1.5 for c in clusters):
                kms.append(km)
                break
        else:
            # Fallback: just use the endpoints
            kms.append(round(info["km_start"] + 0.5, 1))
    return kms


def _fmt_time(hour, minute):
    return f"{hour:02d}:{minute:02d}"


# ── TMS Generator ─────────────────────────────────────────────────────────

def generate_tms():
    """Generate 30 TMS (Engineering / Track) maintenance tasks."""
    tasks = []
    n = 1

    for cid in CORRIDORS:
        info = CORRIDOR_INFO[cid]
        clusters = BUNDLE_CLUSTERS[cid]

        # 2 tasks at cluster points (bundling targets)
        for ckm in clusters:
            km = round(ckm + random.uniform(-0.2, 0.2), 1)
            sev = random.choice([3, 4, 5])
            tasks.append({
                "task_id": f"TMS-{n:03d}",
                "asset_id": f"TRK-{n:03d}",
                "location_km": km,
                "corridor_id": cid,
                "defect_type": random.choice(TMS_DEFECTS),
                "severity": sev,
                "duration_minutes": random.choice([90, 120, 150]),
                "overdue_days": _random_overdue(),
                "asset_criticality": random.randint(3, 5),
                "safety_impact": random.randint(3, 5),
                "due_date": _random_due_date(),
            })
            n += 1

        # 4 scattered tasks
        for km in _scattered_km(info, clusters, 4):
            tasks.append({
                "task_id": f"TMS-{n:03d}",
                "asset_id": f"TRK-{n:03d}",
                "location_km": km,
                "corridor_id": cid,
                "defect_type": random.choice(TMS_DEFECTS),
                "severity": random.randint(1, 5),
                "duration_minutes": random.choice([60, 90, 120, 150, 180]),
                "overdue_days": _random_overdue(),
                "asset_criticality": random.randint(1, 5),
                "safety_impact": random.randint(1, 5),
                "due_date": _random_due_date(),
            })
            n += 1

    # Hardcode first task to match spec example
    tasks[0].update({
        "task_id": "TMS-001", "asset_id": "TRK-001",
        "location_km": 124.5, "corridor_id": "C124",
        "defect_type": "Rail defect", "severity": 5,
        "duration_minutes": 120, "overdue_days": 7,
        "asset_criticality": 5, "safety_impact": 5,
        "due_date": "2026-09-08",
    })
    return tasks


# ── SMMS Generator ────────────────────────────────────────────────────────

def generate_smms():
    """Generate 30 SMMS (Signal & Telecom) maintenance tasks."""
    tasks = []
    n = 1

    for cid in CORRIDORS:
        info = CORRIDOR_INFO[cid]
        clusters = BUNDLE_CLUSTERS[cid]

        # 2 tasks near cluster points (slight offset for bundling)
        for ckm in clusters:
            km = round(ckm + random.uniform(0.0, 0.4), 1)
            sev = random.choice([3, 4, 5])
            tasks.append({
                "task_id": f"SMMS-{n:03d}",
                "asset_id": f"SIG-{n:03d}",
                "location_km": km,
                "corridor_id": cid,
                "defect_type": random.choice(SMMS_DEFECTS),
                "severity": sev,
                "duration_minutes": random.choice([45, 60, 90]),
                "overdue_days": _random_overdue(),
                "asset_criticality": random.randint(3, 5),
                "safety_impact": random.randint(3, 5),
                "due_date": _random_due_date(),
            })
            n += 1

        # 4 scattered
        for km in _scattered_km(info, clusters, 4):
            tasks.append({
                "task_id": f"SMMS-{n:03d}",
                "asset_id": f"SIG-{n:03d}",
                "location_km": km,
                "corridor_id": cid,
                "defect_type": random.choice(SMMS_DEFECTS),
                "severity": random.randint(1, 5),
                "duration_minutes": random.choice([30, 45, 60, 90]),
                "overdue_days": _random_overdue(),
                "asset_criticality": random.randint(1, 5),
                "safety_impact": random.randint(1, 5),
                "due_date": _random_due_date(),
            })
            n += 1

    # Hardcode first task to match spec example
    tasks[0].update({
        "task_id": "SMMS-001", "asset_id": "SIG-001",
        "location_km": 124.6, "corridor_id": "C124",
        "defect_type": "Signal fault", "severity": 5,
        "duration_minutes": 60, "overdue_days": 4,
        "asset_criticality": 5, "safety_impact": 5,
        "due_date": "2026-09-08",
    })
    return tasks


# ── TDMS Generator ────────────────────────────────────────────────────────

def generate_tdms():
    """Generate 30 TDMS (Traction / OHE) maintenance tasks."""
    tasks = []
    n = 1

    for cid in CORRIDORS:
        info = CORRIDOR_INFO[cid]
        clusters = BUNDLE_CLUSTERS[cid]

        # 2 tasks near cluster points
        for ckm in clusters:
            km = round(ckm + random.uniform(0.1, 0.5), 1)
            sev = random.choice([3, 4, 5])
            tasks.append({
                "task_id": f"TDMS-{n:03d}",
                "asset_id": f"OHE-{n:03d}",
                "location_km": km,
                "corridor_id": cid,
                "defect_type": random.choice(TDMS_DEFECTS),
                "severity": sev,
                "duration_minutes": random.choice([90, 120, 150]),
                "overdue_days": _random_overdue(),
                "asset_criticality": random.randint(3, 5),
                "safety_impact": random.randint(3, 5),
                "requires_isolation": random.choice([True, True, False]),
                "due_date": _random_due_date(),
            })
            n += 1

        # 4 scattered
        for km in _scattered_km(info, clusters, 4):
            tasks.append({
                "task_id": f"TDMS-{n:03d}",
                "asset_id": f"OHE-{n:03d}",
                "location_km": km,
                "corridor_id": cid,
                "defect_type": random.choice(TDMS_DEFECTS),
                "severity": random.randint(1, 5),
                "duration_minutes": random.choice([60, 90, 120, 150]),
                "overdue_days": _random_overdue(),
                "asset_criticality": random.randint(1, 5),
                "safety_impact": random.randint(1, 5),
                "requires_isolation": random.choice([True, False]),
                "due_date": _random_due_date(),
            })
            n += 1

    # Hardcode first task to match spec example
    tasks[0].update({
        "task_id": "TDMS-001", "asset_id": "OHE-001",
        "location_km": 124.7, "corridor_id": "C124",
        "defect_type": "Catenary issue", "severity": 4,
        "duration_minutes": 120, "overdue_days": 5,
        "asset_criticality": 5, "safety_impact": 4,
        "requires_isolation": True,
        "due_date": "2026-09-08",
    })
    return tasks


# ── COA Generator ─────────────────────────────────────────────────────────

def generate_coa():
    """Generate ~98 train movements across 5 corridors over 7 days."""
    movements = []
    train_counter = 100

    for cid in CORRIDORS:
        for tmpl in TRAIN_TEMPLATES[cid]:
            train_counter += 1
            prefix = TRAIN_TYPE_PREFIX[tmpl["type"]]
            train_id = f"{prefix}-{train_counter}"

            for date_str in PLANNING_DATES:
                # Add ±10 min random variation per day
                offset = random.randint(-10, 10)
                start_h = tmpl["base_hour"]
                start_m = tmpl["base_min"] + offset
                # Handle minute overflow/underflow
                if start_m < 0:
                    start_h -= 1
                    start_m += 60
                elif start_m >= 60:
                    start_h += 1
                    start_m -= 60

                end_total = start_h * 60 + start_m + tmpl["dur"]
                end_h, end_m = divmod(end_total, 60)

                movements.append({
                    "train_id": train_id,
                    "train_type": tmpl["type"],
                    "corridor_id": cid,
                    "date": date_str,
                    "start_time": _fmt_time(start_h, start_m),
                    "end_time": _fmt_time(end_h, end_m),
                    "is_confirmed": True,
                })

    return movements


# ── CSV Writers ────────────────────────────────────────────────────────────

def _write_csv(filepath, rows, fieldnames):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


TMS_FIELDS = [
    "task_id", "asset_id", "location_km", "corridor_id", "defect_type",
    "severity", "duration_minutes", "overdue_days", "asset_criticality",
    "safety_impact", "due_date",
]

SMMS_FIELDS = TMS_FIELDS  # identical schema

TDMS_FIELDS = [
    "task_id", "asset_id", "location_km", "corridor_id", "defect_type",
    "severity", "duration_minutes", "overdue_days", "asset_criticality",
    "safety_impact", "requires_isolation", "due_date",
]

COA_FIELDS = [
    "train_id", "train_type", "corridor_id", "date",
    "start_time", "end_time", "is_confirmed",
]


# ── Main ───────────────────────────────────────────────────────────────────

def generate_all():
    """Generate all synthetic datasets and write to data/ directory."""
    tms = generate_tms()
    smms = generate_smms()
    tdms = generate_tdms()
    coa = generate_coa()

    _write_csv(os.path.join(DATA_DIR, "tms.csv"), tms, TMS_FIELDS)
    _write_csv(os.path.join(DATA_DIR, "smms.csv"), smms, SMMS_FIELDS)
    _write_csv(os.path.join(DATA_DIR, "tdms.csv"), tdms, TDMS_FIELDS)
    _write_csv(os.path.join(DATA_DIR, "coa.csv"), coa, COA_FIELDS)

    print(f"TMS tasks generated  : {len(tms)}")
    print(f"SMMS tasks generated : {len(smms)}")
    print(f"TDMS tasks generated : {len(tdms)}")
    print(f"Train movements      : {len(coa)}")
    print(f"Data written to      : {DATA_DIR}")

    return {"tms": tms, "smms": smms, "tdms": tdms, "coa": coa}


if __name__ == "__main__":
    generate_all()
