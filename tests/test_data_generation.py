import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from backend.generate_data import generate_tms, generate_smms, generate_tdms, generate_coa, generate_all

def test_task_count():
    tms = generate_tms()
    smms = generate_smms()
    tdms = generate_tdms()
    
    assert len(tms) == 30, f"Expected 30 TMS tasks, got {len(tms)}"
    assert len(smms) == 30, f"Expected 30 SMMS tasks, got {len(smms)}"
    assert len(tdms) == 30, f"Expected 30 TDMS tasks, got {len(tdms)}"
    assert len(tms) + len(smms) + len(tdms) == 90, "Expected 90 total tasks"

def test_required_fields():
    all_data = generate_all()
    tms = all_data["tms"]
    
    # Check fields in raw TMS
    for t in tms:
        assert "task_id" in t
        assert "asset_id" in t
        assert "location_km" in t
        assert "corridor_id" in t
        assert "defect_type" in t
        assert "severity" in t
        assert "duration_minutes" in t

def test_train_data():
    coa = generate_coa()
    assert len(coa) > 0
    for tr in coa:
        assert "train_id" in tr
        assert "train_type" in tr
        assert "corridor_id" in tr
        assert "date" in tr
        assert "start_time" in tr
        assert "end_time" in tr
        assert "is_confirmed" in tr
