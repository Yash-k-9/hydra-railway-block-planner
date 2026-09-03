import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from backend.generate_data import generate_all
from backend.services.normalizer import normalize_all
from backend.services.priority import calculate_all_priorities
from backend.services.block_windows import find_all_windows
from backend.services.coordination import find_coordination_groups
from backend.services.baseline import schedule_baseline
from backend.services.optimizer import optimize, validate_schedule

def test_full_pipeline():
    # 1. Generate
    raw = generate_all()
    
    # 2. Normalize
    tasks, _ = normalize_all(raw["tms"], raw["smms"], raw["tdms"])
    assert len(tasks) == 90
    
    trains = raw["coa"]
    
    # 3. Priority
    tasks, summary = calculate_all_priorities(tasks, trains)
    assert all("priority_score" in t for t in tasks)
    
    # 4. Windows
    windows = find_all_windows(trains)
    assert len(windows) > 0
    
    # 5. Coordination
    groups = find_coordination_groups(tasks)
    
    # 6. Baseline
    baseline = schedule_baseline(tasks, windows)
    assert len(baseline["blocks"]) > 0
    
    # 7. Optimizer
    optimized = optimize(tasks, groups, windows)
    assert optimized["status"] in ("OPTIMAL", "FEASIBLE")
    
    # 8. Validation
    val = validate_schedule(optimized, trains)
    assert val["valid"] is True, f"Validation failed: {val['violations']}"
