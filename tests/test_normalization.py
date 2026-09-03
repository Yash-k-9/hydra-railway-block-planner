import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from backend.services.normalizer import normalize_tms, normalize_smms, normalize_tdms, normalize_all

def test_normalization_fields():
    tms_raw = [{"task_id": "TMS-001", "corridor_id": "C1", "severity": 4, "location_km": 10.5, "defect_type": "Rail defect"}]
    tms_norm = normalize_tms(tms_raw)
    
    assert len(tms_norm) == 1
    t = tms_norm[0]
    
    assert t["task_id"] == "TMS-001"
    assert t["source_system"] == "TMS"
    assert t["department"] == "ENGINEERING"
    assert t["task_type"] == "Rail defect"
    assert t["severity"] == 4  # Cast to int
    assert t["location_km"] == 10.5  # Cast to float

def test_department_consistency():
    smms_raw = [{"task_id": "SMMS-001", "corridor_id": "C1"}]
    tdms_raw = [{"task_id": "TDMS-001", "corridor_id": "C1", "requires_isolation": True}]
    
    smms_norm = normalize_smms(smms_raw)
    tdms_norm = normalize_tdms(tdms_raw)
    
    assert smms_norm[0]["department"] == "SIGNALLING"
    assert tdms_norm[0]["department"] == "TRACTION"

def test_duplicate_handling():
    tms = [{"task_id": "T1", "corridor_id": "C1"}]
    smms = [{"task_id": "T1", "corridor_id": "C1"}]
    tdms = []
    
    tasks, counts = normalize_all(tms, smms, tdms)
    assert len(tasks) == 1
    assert counts["total"] == 1
