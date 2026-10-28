import os
import sys
import copy

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from backend.services.priority import calculate_priority, _urgency_from_due_date, _classify

def test_priority_bounds():
    task = {
        "severity": 5, "asset_criticality": 5, "safety_impact": 5,
        "overdue_days": 100, "due_date": "2020-01-01", "corridor_id": "C1"
    }
    train_counts = {"C1": 100}
    calculate_priority(task, train_counts)
    
    assert 0 <= task["priority_score"] <= 100

def test_severity_scoring():
    task_critical = {"severity": 5, "asset_criticality": 5, "safety_impact": 5}
    task_low = {"severity": 1, "asset_criticality": 1, "safety_impact": 1}
    
    calculate_priority(task_critical, {})
    calculate_priority(task_low, {})
    
    assert task_critical["priority_score"] > task_low["priority_score"]

def test_classification():
    assert _classify(95) == "CRITICAL"
    assert _classify(80) == "HIGH"
    assert _classify(60) == "MEDIUM"
    assert _classify(20) == "LOW"

def test_urgency_calculation():
    # Overdue
    assert _urgency_from_due_date("2026-09-01", 5) == 1.0
    # Far in future
    assert _urgency_from_due_date("2026-10-01", 0) == 0.1

def test_determinism():
    task1 = {"severity": 3, "asset_criticality": 4, "corridor_id": "C1"}
    task2 = copy.deepcopy(task1)
    
    calculate_priority(task1, {"C1": 5})
    calculate_priority(task2, {"C1": 5})
    
    assert task1["priority_score"] == task2["priority_score"]

def test_classification_boundaries():
    assert _classify(85) == "CRITICAL"
    assert _classify(84.5) == "HIGH"
    assert _classify(70) == "HIGH"
    assert _classify(69.5) == "MEDIUM"
    assert _classify(50) == "MEDIUM"
    assert _classify(49.5) == "LOW"

def test_hyderabad_tasks_vary_criticality():
    from backend.services.hyderabad_adapter import load_hyderabad_tasks, load_hyderabad_trains
    from backend.services.priority import calculate_all_priorities

    tasks = load_hyderabad_tasks()
    assert len({t["asset_criticality"] for t in tasks}) > 1
    assert len({t["safety_impact"] for t in tasks}) > 1
    assert any(t["overdue_days"] > 0 for t in tasks)

    _, summary = calculate_all_priorities(tasks, load_hyderabad_trains())
    assert summary["CRITICAL"] > 0
