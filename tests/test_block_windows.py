import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from backend.services.block_windows import find_windows_for_corridor_date, check_conflict

def test_window_generation():
    trains = [
        {"train_id": "A", "corridor_id": "C1", "date": "D1", "start_time": "10:00", "end_time": "10:20", "is_confirmed": True},
        {"train_id": "B", "corridor_id": "C1", "date": "D1", "start_time": "12:00", "end_time": "12:15", "is_confirmed": True},
    ]
    
    windows = find_windows_for_corridor_date("C1", "D1", trains)
    
    # Expected gaps: 06:00-10:00, 10:20-12:00, 12:15-22:00
    assert len(windows) == 3
    assert windows[1]["start_time"] == "10:20"
    assert windows[1]["end_time"] == "12:00"

def test_edge_case_no_gap():
    trains = [
        {"train_id": "A", "corridor_id": "C1", "date": "D1", "start_time": "10:00", "end_time": "10:20", "is_confirmed": True},
        {"train_id": "B", "corridor_id": "C1", "date": "D1", "start_time": "10:30", "end_time": "10:45", "is_confirmed": True},
    ]
    # Gap is 10 mins (10:20 to 10:30) which is < 30 mins
    windows = find_windows_for_corridor_date("C1", "D1", trains)
    
    # We should have gaps before A and after B, but NOT between A and B
    for w in windows:
        assert not (w["start_time"] == "10:20" and w["end_time"] == "10:30")

def test_different_corridors():
    trains = [
        {"train_id": "A", "corridor_id": "C1", "date": "D1", "start_time": "10:00", "end_time": "20:00", "is_confirmed": True},
        {"train_id": "B", "corridor_id": "C2", "date": "D1", "start_time": "10:00", "end_time": "11:00", "is_confirmed": True},
    ]
    windows_c2 = find_windows_for_corridor_date("C2", "D1", trains)
    # Train A on C1 should not block C2
    assert any(w["start_time"] == "11:00" for w in windows_c2)

def test_conflict_check():
    trains = [{"train_id": "A", "corridor_id": "C1", "date": "D1", "start_time": "10:00", "end_time": "10:20", "is_confirmed": True}]
    # Overlaps
    assert len(check_conflict("10:00", "10:30", trains, "C1", "D1")) == 1
    assert len(check_conflict("09:50", "10:10", trains, "C1", "D1")) == 1
    # Does not overlap
    assert len(check_conflict("10:20", "11:00", trains, "C1", "D1")) == 0
