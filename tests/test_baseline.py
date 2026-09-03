import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from backend.services.baseline import schedule_baseline

def test_baseline_scheduler():
    tasks = [
        {"task_id": "T1", "corridor_id": "C1", "department": "ENGINEERING", "duration_minutes": 120, "priority_score": 80, "priority_level": "HIGH", "location_km": 10},
        {"task_id": "T2", "corridor_id": "C1", "department": "ENGINEERING", "duration_minutes": 60, "priority_score": 90, "priority_level": "CRITICAL", "location_km": 15},
    ]
    windows = [
        {"window_id": "W1", "corridor_id": "C1", "date": "D1", "start_time": "08:00", "end_time": "10:00", "duration_minutes": 120},
    ]
    
    result = schedule_baseline(tasks, windows)
    
    # Baseline assigns highest priority first
    # T2 (CRITICAL) gets assigned to W1 (uses 60 mins).
    # Then T1 (HIGH, 120 mins) cannot fit in the remaining 60 mins of W1.
    assert len(result["blocks"]) == 1
    assert len(result["blocks"][0]["tasks"]) == 1
    assert result["blocks"][0]["tasks"][0]["task_id"] == "T2"
    
    assert result["stats"]["tasks_completed"] == 1
    assert result["stats"]["tasks_deferred"] == 1
