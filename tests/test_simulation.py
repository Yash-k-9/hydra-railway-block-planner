import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from backend.services.simulation import inject_train_delay, inject_new_defect, create_simulation_snapshot

def test_train_delay():
    trains = [{"train_id": "EXP-101", "start_time": "10:00", "end_time": "12:00", "date": "D1", "corridor_id": "C1"}]
    tasks = []
    snapshot = create_simulation_snapshot(tasks, trains)
    
    sim_trains = snapshot["trains"]
    event = inject_train_delay(sim_trains, "EXP-101", 45)
    
    # Base trains should not be modified
    assert trains[0]["start_time"] == "10:00"
    
    # Sim trains should be modified
    assert sim_trains[0]["start_time"] == "10:45"
    assert sim_trains[0]["end_time"] == "12:45"
    assert event["delay_minutes"] == 45

def test_new_defect():
    trains = []
    tasks = []
    snapshot = create_simulation_snapshot(tasks, trains)
    sim_tasks = snapshot["tasks"]
    
    defect = {
        "department": "ENGINEERING",
        "severity": 5,
        "criticality": 5,
        "safety_impact": 5,
    }
    
    new_task = inject_new_defect(sim_tasks, defect)
    
    assert len(sim_tasks) == 1
    assert len(tasks) == 0  # Original state untouched
    assert new_task["department"] == "ENGINEERING"
    assert new_task["severity"] == 5

def test_simulation_reset():
    trains = [{"train_id": "EXP-101", "start_time": "10:00", "end_time": "12:00", "date": "D1", "corridor_id": "C1"}]
    tasks = [{"task_id": "T1"}]
    
    snapshot = create_simulation_snapshot(tasks, trains)
    sim_trains = snapshot["trains"]
    sim_tasks = snapshot["tasks"]
    
    inject_train_delay(sim_trains, "EXP-101", 45)
    inject_new_defect(sim_tasks, {})
    
    # Reset is just discarding the snapshot in the real app, but we verify base state is intact here.
    assert len(tasks) == 1
    assert trains[0]["start_time"] == "10:00"
