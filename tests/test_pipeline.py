import os
import sys
import pytest

# Ensure backend/ is on the import path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from backend.services.normalizer import normalize_tms, normalize_all
from backend.services.priority import calculate_priority, _urgency_from_due_date, _classify
from backend.services.block_windows import find_windows_for_corridor_date, check_conflict, _time_to_minutes
from backend.services.coordination import find_coordination_groups, _tasks_compatible
from backend.services.simulation import inject_train_delay
from backend.services.baseline import schedule_baseline
from backend.services.optimizer import optimize, validate_schedule

# ── Test Normalizer ────────────────────────────────────────────────────────

def test_normalize_tms():
    """Test TMS data normalization."""
    raw = [{
        "task_id": "TMS-001",
        "corridor_id": "C1",
        "severity": 4,
        "location_km": 10.5
    }]
    unified = normalize_tms(raw)
    assert len(unified) == 1
    assert unified[0]["department"] == "ENGINEERING"
    assert unified[0]["source_system"] == "TMS"
    assert unified[0]["severity"] == 4
    assert unified[0]["location_km"] == 10.5


def test_normalize_all_dedup():
    """Test deduplication in normalize_all."""
    tms = [{"task_id": "T1", "corridor_id": "C1"}]
    smms = [{"task_id": "T1", "corridor_id": "C1"}]  # Duplicate ID
    tdms = [{"task_id": "T2", "corridor_id": "C1", "requires_isolation": True}]
    
    tasks, counts = normalize_all(tms, smms, tdms)
    assert len(tasks) == 2
    assert counts["total"] == 2


# ── Test Priority Engine ───────────────────────────────────────────────────

def test_urgency_calculation():
    """Test urgency scoring logic."""
    # Overdue
    assert _urgency_from_due_date("2026-09-01", 5) == 1.0
    # Far in future (>14 days from 2026-09-07)
    assert _urgency_from_due_date("2026-10-01", 0) == 0.1
    # Invalid date
    assert _urgency_from_due_date("invalid", 0) == 0.5


def test_priority_score():
    """Test end-to-end priority score calculation."""
    task = {
        "severity": 5,
        "asset_criticality": 5,
        "safety_impact": 5,
        "overdue_days": 10,
        "due_date": "2026-09-01",
        "corridor_id": "C1"
    }
    # Weights: 0.25*1 + 0.20*1 + 0.15*(10/30) + 0.15*1 + 0.15*1 + 0.10*1 (if max train impact)
    train_counts = {"C1": 10}
    calculate_priority(task, train_counts)
    
    assert task["priority_score"] > 85
    assert task["priority_level"] == "CRITICAL"


# ── Test Block Windows ─────────────────────────────────────────────────────

def test_time_to_minutes():
    """Test time string conversion."""
    assert _time_to_minutes("06:00") == 360
    assert _time_to_minutes("22:30") == 1350


def test_find_windows():
    """Test finding gaps between trains."""
    trains = [
        {"corridor_id": "C1", "date": "2026-09-07", "start_time": "08:00", "end_time": "10:00", "is_confirmed": True},
        {"corridor_id": "C1", "date": "2026-09-07", "start_time": "14:00", "end_time": "16:00", "is_confirmed": True},
    ]
    # Operating hours: 06:00 to 22:00
    # Expected gaps: 06:00-08:00 (120m), 10:00-14:00 (240m), 16:00-22:00 (360m)
    windows = find_windows_for_corridor_date("C1", "2026-09-07", trains)
    
    assert len(windows) == 3
    assert windows[0]["duration_minutes"] == 120
    assert windows[1]["duration_minutes"] == 240
    assert windows[2]["duration_minutes"] == 360


def test_conflict_check():
    """Test train conflict detection."""
    trains = [{"train_id": "1", "corridor_id": "C1", "date": "D1", "start_time": "10:00", "end_time": "12:00"}]
    
    # Overlap
    assert len(check_conflict("09:00", "11:00", trains, "C1", "D1")) == 1
    assert len(check_conflict("11:00", "13:00", trains, "C1", "D1")) == 1
    assert len(check_conflict("10:30", "11:30", trains, "C1", "D1")) == 1
    
    # No overlap
    assert len(check_conflict("08:00", "10:00", trains, "C1", "D1")) == 0
    assert len(check_conflict("12:00", "14:00", trains, "C1", "D1")) == 0


# ── Test Coordination ──────────────────────────────────────────────────────

def test_coordination_compatibility():
    """Test task grouping rules."""
    # Compatible (different dept, same corridor, < 1km)
    t1 = {"task_id": "1", "corridor_id": "C1", "location_km": 10.0, "department": "A"}
    t2 = {"task_id": "2", "corridor_id": "C1", "location_km": 10.8, "department": "B"}
    assert _tasks_compatible([t1, t2]) == True
    
    # Incompatible (distance > 1km)
    t3 = {"task_id": "3", "corridor_id": "C1", "location_km": 11.1, "department": "B"}
    assert _tasks_compatible([t1, t3]) == False
    
    # Incompatible (different corridor)
    t4 = {"task_id": "4", "corridor_id": "C2", "location_km": 10.0, "department": "B"}
    assert _tasks_compatible([t1, t4]) == False


def test_coordination_group_generation():
    """Test greedy clustering logic."""
    tasks = [
        {"task_id": "1", "corridor_id": "C1", "location_km": 10.0, "department": "ENGINEERING", "duration_minutes": 60, "priority_score": 50},
        {"task_id": "2", "corridor_id": "C1", "location_km": 10.2, "department": "SIGNALLING", "duration_minutes": 90, "priority_score": 60},
        {"task_id": "3", "corridor_id": "C1", "location_km": 50.0, "department": "ENGINEERING", "duration_minutes": 60, "priority_score": 50},
    ]
    groups = find_coordination_groups(tasks)
    
    assert len(groups) == 1
    assert len(groups[0]["task_ids"]) == 2
    assert "1" in groups[0]["task_ids"]
    assert "2" in groups[0]["task_ids"]
    assert groups[0]["joint_duration"] == 90
    assert groups[0]["serial_duration"] == 150


# ── Test Simulation ────────────────────────────────────────────────────────

def test_train_delay_injection():
    """Test simulation disruption logic."""
    trains = [{"train_id": "EXP1", "start_time": "10:00", "end_time": "12:00", "date": "D", "corridor_id": "C"}]
    event = inject_train_delay(trains, "EXP1", 30)
    
    assert trains[0]["start_time"] == "10:30"
    assert trains[0]["end_time"] == "12:30"
    assert event["delay_minutes"] == 30
    assert len(event["affected_movements"]) == 1


# ── Test Optimizer Basics ──────────────────────────────────────────────────

def test_baseline_scheduler():
    """Test baseline decentralized scheduling logic."""
    tasks = [
        {"task_id": "1", "corridor_id": "C1", "department": "ENGINEERING", "duration_minutes": 120, "priority_score": 80, "priority_level": "HIGH", "location_km": 10}
    ]
    windows = [
        {"window_id": "W1", "corridor_id": "C1", "date": "D1", "start_time": "08:00", "end_time": "10:00", "duration_minutes": 120}
    ]
    
    result = schedule_baseline(tasks, windows)
    assert len(result["blocks"]) == 1
    assert result["stats"]["tasks_completed"] == 1
    assert result["stats"]["tasks_deferred"] == 0


def test_optimizer_valid_schedule():
    """Test simple optimization scenario."""
    tasks = [
        {"task_id": "T1", "corridor_id": "C1", "department": "ENG", "duration_minutes": 60, "priority_score": 90, "priority_level": "CRITICAL", "location_km": 10}
    ]
    groups = []
    windows = [
        {"window_id": "W1", "corridor_id": "C1", "date": "D1", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120}
    ]
    
    result = optimize(tasks, groups, windows, time_limit=2)
    assert result["status"] in ("OPTIMAL", "FEASIBLE")
    assert len(result["blocks"]) == 1
    assert result["blocks"][0]["utilization"] == 50.0  # 60 / 120 * 100
