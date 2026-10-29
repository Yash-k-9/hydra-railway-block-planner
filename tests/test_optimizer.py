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

def test_multiple_groups_in_one_window():
    # Two groups of 60 min each fill a 120-min window: utilization must count both
    tasks = [
        {"task_id": "T1", "department": "ENG", "corridor_id": "C1", "location_km": 10.0, "duration_minutes": 60, "priority_score": 50, "priority_level": "MEDIUM"},
        {"task_id": "T2", "department": "SIG", "corridor_id": "C1", "location_km": 10.2, "duration_minutes": 60, "priority_score": 50, "priority_level": "MEDIUM"},
        {"task_id": "T3", "department": "ENG", "corridor_id": "C1", "location_km": 12.0, "duration_minutes": 60, "priority_score": 50, "priority_level": "MEDIUM"},
        {"task_id": "T4", "department": "SIG", "corridor_id": "C1", "location_km": 12.2, "duration_minutes": 60, "priority_score": 50, "priority_level": "MEDIUM"},
    ]
    groups = [
        {"group_id": "G1", "task_ids": ["T1", "T2"], "corridor_id": "C1", "joint_duration": 60},
        {"group_id": "G2", "task_ids": ["T3", "T4"], "corridor_id": "C1", "joint_duration": 60},
    ]
    windows = [{"window_id": "W1", "corridor_id": "C1", "date": "D1", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120}]

    result = optimize(tasks, groups, windows, time_limit=2)
    assert len(result["blocks"]) == 1
    assert result["blocks"][0]["utilization"] == 100.0
    assert validate_schedule(result, [])["valid"] is True

def test_validation_counts_each_group():
    # Two bundled groups of 90 min in a 120-min block is an overfill
    result = {
        "blocks": [{
            "block_id": "B1", "duration_minutes": 120, "corridor_id": "C1", "date": "D1", "start_time": "10:00", "end_time": "12:00",
            "tasks": [
                {"task_id": "T1", "duration_minutes": 90, "bundled": True, "group_id": "G1"},
                {"task_id": "T2", "duration_minutes": 60, "bundled": True, "group_id": "G1"},
                {"task_id": "T3", "duration_minutes": 90, "bundled": True, "group_id": "G2"},
                {"task_id": "T4", "duration_minutes": 60, "bundled": True, "group_id": "G2"},
            ],
        }]
    }
    val = validate_schedule(result, [])
    assert val["valid"] is False
    assert val["checks"]["capacity_violations"] == 1

def _task(tid, km=10.0, dur=60, score=50, level="MEDIUM", dept="ENGINEERING", corridor="C1", due=None):
    t = {"task_id": tid, "department": dept, "corridor_id": corridor, "location_km": km,
         "duration_minutes": dur, "priority_score": score, "priority_level": level}
    if due:
        t["due_date"] = due
    return t

def _window(wid, date="2026-09-07", start="10:00", end="14:00", corridor="C1"):
    sh, sm = map(int, start.split(":")); eh, em = map(int, end.split(":"))
    return {"window_id": wid, "corridor_id": corridor, "date": date,
            "start_time": start, "end_time": end, "duration_minutes": (eh * 60 + em) - (sh * 60 + sm)}

def test_block_lasts_only_as_long_as_its_work():
    result = optimize([_task("T1", dur=60)], [], [_window("W1", start="10:00", end="14:00")], time_limit=2)
    b = result["blocks"][0]
    assert (b["start_time"], b["end_time"], b["duration_minutes"]) == ("10:00", "11:00", 60)
    assert (b["window_start"], b["window_end"]) == ("10:00", "14:00")
    assert result["stats"]["total_block_hours"] == 1.0

def test_prefers_window_before_due_date():
    windows = [_window("W1", date="2026-09-07"), _window("W2", date="2026-09-10")]
    result = optimize([_task("T1", due="2026-09-07")], [], windows, time_limit=2)
    assert result["blocks"][0]["date"] == "2026-09-07"
    assert result["stats"]["late_tasks"] == 0

def test_overdue_task_scheduled_as_early_as_possible():
    windows = [_window("W1", date="2026-09-09"), _window("W2", date="2026-09-07")]
    result = optimize([_task("T1", due="2026-09-01")], [], windows, time_limit=2)
    assert result["blocks"][0]["date"] == "2026-09-07"

def test_critical_tasks_win_over_more_lower_priority_work():
    # One window fits either the critical task or two medium tasks, not both
    tasks = [_task("C", dur=120, score=86, level="CRITICAL"), _task("M1", dur=60, score=69), _task("M2", dur=60, score=69)]
    result = optimize(tasks, [], [_window("W1", start="10:00", end="12:00")], time_limit=2)
    assert result["scheduled_tasks"] == ["C"]

def test_block_section_limit():
    # Two tasks 8 km apart cannot share a block; there is only one window
    tasks = [_task("T1", km=10.0), _task("T2", km=18.0)]
    result = optimize(tasks, [], [_window("W1")], time_limit=2)
    assert len(result["scheduled_tasks"]) == 1

def test_crew_limit_shifts_overlapping_blocks():
    # Three corridors, same day, one engineering crew: blocks must not overlap
    tasks = [_task(f"T{c}", corridor=c) for c in ("A", "B", "C")]
    windows = [_window(f"W{c}", start="10:00", end="14:00", corridor=c) for c in ("A", "B", "C")]
    result = optimize(tasks, [], windows, crews={"ENGINEERING": 1}, time_limit=4)
    assert len(result["blocks"]) == 3
    spans = sorted((b["start_time"], b["end_time"]) for b in result["blocks"])
    assert spans == [("10:00", "11:00"), ("11:00", "12:00"), ("12:00", "13:00")]
    assert validate_schedule(result, [], crews={"ENGINEERING": 1})["valid"] is True

def test_validation_flags_crew_and_section_violations():
    blocks = [
        {"block_id": f"B{i}", "corridor_id": f"C{i}", "date": "D1", "start_time": "10:00", "end_time": "11:00",
         "duration_minutes": 60, "departments": ["ENGINEERING"],
         "tasks": [{"task_id": f"T{i}", "duration_minutes": 60, "location_km": 1.0}]}
        for i in range(3)
    ]
    blocks[0]["tasks"].append({"task_id": "TX", "duration_minutes": 0, "location_km": 9.0})
    val = validate_schedule({"blocks": blocks}, [], crews={"ENGINEERING": 2})
    assert val["checks"]["crew_violations"] == 1
    assert val["checks"]["section_violations"] == 1

def test_fixed_block_kept_and_its_time_taken():
    # An approved block sits 10:00-11:00 in a 10:00-14:00 window
    fixed = {
        "block_id": "BLK-OLD", "corridor_id": "C1", "date": "2026-09-07",
        "start_time": "10:00", "end_time": "11:00", "duration_minutes": 60,
        "departments": ["ENGINEERING"], "status": "approved",
        "tasks": [dict(_task("F1"), bundled=False)],
    }
    tasks = [_task("F1"), _task("T2")]
    result = optimize(tasks, [], [_window("W1")], fixed_blocks=[fixed], time_limit=2)

    assert "F1" in result["scheduled_tasks"] and "T2" in result["scheduled_tasks"]
    by_id = {b["block_id"]: b for b in result["blocks"]}
    assert by_id["BLK-OLD"]["status"] == "approved"
    new = [b for b in result["blocks"] if b["block_id"] != "BLK-OLD"][0]
    assert new["start_time"] >= "11:00"          # placed after the fixed block
    assert [t["task_id"] for t in new["tasks"]] == ["T2"]
    assert result["stats"]["fixed_blocks"] == 1
    assert validate_schedule(result, [])["valid"] is True

def test_fixed_block_uses_crew():
    # One crew, approved block on corridor A 10:00-11:00 → corridor B block must not overlap
    fixed = {
        "block_id": "BLK-A", "corridor_id": "A", "date": "2026-09-07",
        "start_time": "10:00", "end_time": "11:00", "duration_minutes": 60,
        "departments": ["ENGINEERING"], "status": "approved",
        "tasks": [dict(_task("FA", corridor="A"), bundled=False)],
    }
    tasks = [_task("FA", corridor="A"), _task("TB", corridor="B")]
    result = optimize(tasks, [], [_window("WA", corridor="A"), _window("WB", start="10:00", end="12:00", corridor="B")],
                      crews={"ENGINEERING": 1}, fixed_blocks=[fixed], time_limit=2)
    b = [b for b in result["blocks"] if b["corridor_id"] == "B"][0]
    assert b["start_time"] == "11:00"

def test_replanning_keeps_tasks_in_their_old_window():
    # Two identical windows; the previous plan used the later one, so the task stays there
    windows = [_window("W1", start="10:00", end="12:00"), _window("W2", start="13:00", end="15:00")]
    previous = [{"block_id": "BLK-W2", "corridor_id": "C1", "date": "2026-09-07",
                 "start_time": "13:00", "end_time": "14:00", "tasks": [{"task_id": "T1"}]}]
    result = optimize([_task("T1")], [], windows, previous_blocks=previous, time_limit=2)
    assert result["blocks"][0]["start_time"] == "13:00"
    assert result["stats"]["tasks_moved"] == 0
