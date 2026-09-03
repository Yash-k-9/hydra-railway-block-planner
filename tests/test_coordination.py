import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from backend.services.coordination import find_coordination_groups, _tasks_compatible

def test_valid_bundle():
    tasks = [
        {"task_id": "T1", "department": "ENGINEERING", "corridor_id": "C1", "location_km": 124.5, "duration_minutes": 120, "priority_score": 50},
        {"task_id": "T2", "department": "SIGNALLING", "corridor_id": "C1", "location_km": 124.6, "duration_minutes": 60, "priority_score": 50},
        {"task_id": "T3", "department": "TRACTION", "corridor_id": "C1", "location_km": 124.7, "duration_minutes": 90, "priority_score": 50},
    ]
    groups = find_coordination_groups(tasks)
    assert len(groups) == 1
    assert len(groups[0]["departments"]) == 3
    assert groups[0]["joint_duration"] == 120

def test_distance_violation():
    tasks = [
        {"task_id": "T1", "department": "ENGINEERING", "corridor_id": "C1", "location_km": 124.0, "duration_minutes": 60, "priority_score": 50},
        {"task_id": "T2", "department": "SIGNALLING", "corridor_id": "C1", "location_km": 126.0, "duration_minutes": 60, "priority_score": 50},
    ]
    groups = find_coordination_groups(tasks)
    assert len(groups) == 0

def test_corridor_violation():
    tasks = [
        {"task_id": "T1", "department": "ENGINEERING", "corridor_id": "C1", "location_km": 124.5, "duration_minutes": 60, "priority_score": 50},
        {"task_id": "T2", "department": "SIGNALLING", "corridor_id": "C2", "location_km": 124.6, "duration_minutes": 60, "priority_score": 50},
    ]
    groups = find_coordination_groups(tasks)
    assert len(groups) == 0

def test_single_department_rejected():
    tasks = [
        {"task_id": "T1", "department": "ENGINEERING", "corridor_id": "C1", "location_km": 124.5, "duration_minutes": 60, "priority_score": 50},
        {"task_id": "T2", "department": "ENGINEERING", "corridor_id": "C1", "location_km": 124.6, "duration_minutes": 60, "priority_score": 50},
    ]
    groups = find_coordination_groups(tasks)
    assert len(groups) == 0
