import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from backend.services.optimizer import optimize, validate_schedule

def test_feasible_task():
    tasks = [{"task_id": "T1", "corridor_id": "C1", "department": "ENG", "duration_minutes": 60, "priority_score": 90, "priority_level": "CRITICAL", "location_km": 10}]
    windows = [{"window_id": "W1", "corridor_id": "C1", "date": "D1", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120}]
    
    result = optimize(tasks, [], windows, time_limit=2)
    assert result["status"] in ("OPTIMAL", "FEASIBLE")
    assert "T1" in result["scheduled_tasks"]

def test_task_too_long():
    tasks = [{"task_id": "T1", "corridor_id": "C1", "department": "ENG", "duration_minutes": 150, "priority_score": 90, "priority_level": "CRITICAL", "location_km": 10}]
    windows = [{"window_id": "W1", "corridor_id": "C1", "date": "D1", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120}]
    
    result = optimize(tasks, [], windows, time_limit=2)
    assert "T1" not in result["scheduled_tasks"]

def test_corridor_mismatch():
    tasks = [{"task_id": "T1", "corridor_id": "C124", "department": "ENG", "duration_minutes": 60, "priority_score": 90, "priority_level": "CRITICAL", "location_km": 10}]
    windows = [{"window_id": "W1", "corridor_id": "C130", "date": "D1", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120}]
    
    result = optimize(tasks, [], windows, time_limit=2)
    assert "T1" not in result["scheduled_tasks"]

def test_bundled_task_assignment():
    tasks = [
        {"task_id": "T1", "department": "ENG", "corridor_id": "C1", "location_km": 124.5, "duration_minutes": 120, "priority_score": 50, "priority_level": "MEDIUM"},
        {"task_id": "T2", "department": "SIG", "corridor_id": "C1", "location_km": 124.6, "duration_minutes": 60, "priority_score": 50, "priority_level": "MEDIUM"},
    ]
    groups = [{
        "group_id": "G1", "task_ids": ["T1", "T2"], "tasks": tasks, "corridor_id": "C1", 
        "joint_duration": 120, "serial_duration": 180, "departments": ["ENG", "SIG"], 
        "requires_isolation": False, "avg_priority": 50
    }]
    windows = [{"window_id": "W1", "corridor_id": "C1", "date": "D1", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120}]
    
    result = optimize(tasks, groups, windows, time_limit=2)
    assert "T1" in result["scheduled_tasks"]
    assert "T2" in result["scheduled_tasks"]
    
    # Must be in same block
    assert len(result["blocks"]) == 1
    t_ids = [t["task_id"] for t in result["blocks"][0]["tasks"]]
    assert "T1" in t_ids
    assert "T2" in t_ids

def test_validation():
    result = {
        "blocks": [
            {
                "block_id": "B1", "duration_minutes": 120, "corridor_id": "C1", "date": "D1", "start_time": "10:00", "end_time": "12:00",
                "tasks": [
                    {"task_id": "T1", "duration_minutes": 150, "bundled": False}, # Capacity violation
                ]
            }
        ]
    }
    val = validate_schedule(result, [])
    assert val["valid"] is False
    assert val["checks"]["capacity_violations"] == 1
    
    # Duplicate
    result["blocks"][0]["tasks"] = [{"task_id": "T1", "duration_minutes": 60, "bundled": False}, {"task_id": "T1", "duration_minutes": 60, "bundled": False}]
    val = validate_schedule(result, [])
    assert val["valid"] is False
    assert val["checks"]["duplicate_tasks"] == 1

def test_no_feasible_window():
    tasks = [{"task_id": "T1", "corridor_id": "C1", "department": "ENG", "duration_minutes": 60, "priority_score": 90, "priority_level": "CRITICAL", "location_km": 10}]
    windows = []
    
    result = optimize(tasks, [], windows, time_limit=2)
    assert result["status"] in ("OPTIMAL", "FEASIBLE")
    assert len(result["blocks"]) == 0
    assert "T1" not in result["scheduled_tasks"]
