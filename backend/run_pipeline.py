"""
HYDRA - CLI Pipeline Runner
Executes the full backend pipeline end-to-end and prints results.

Usage:
    python backend/run_pipeline.py

Runs from the hydra/ project root.
"""

import sys
import os
import io
import time

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Ensure backend/ is on the import path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)

DATA_DIR = os.path.join(PROJECT_DIR, "data")

from generate_data import generate_all
import database
from services.data_loader import load_tms, load_smms, load_tdms, load_coa
from services.normalizer import normalize_all
from services.priority import calculate_all_priorities
from services.block_windows import find_all_windows
from services.coordination import find_coordination_groups, summarize_groups, get_ungrouped_tasks
from services.optimizer import optimize, validate_schedule
from services.baseline import schedule_baseline


def hr(char="─", width=50):
    return char * width


def main():
    print()
    print(hr("═"))
    print("  HYDRA BLOCK PLANNING ENGINE")
    print(hr("═"))
    print()

    # ── Phase 1: Generate data ────────────────────────────────────────────
    print("Generating synthetic data...")
    generate_all()
    print()

    # ── Phase 2-3: Load & Normalize ───────────────────────────────────────
    print(hr())
    print("  DATA")
    print(hr())

    tms_raw = load_tms(os.path.join(DATA_DIR, "tms.csv"))
    smms_raw = load_smms(os.path.join(DATA_DIR, "smms.csv"))
    tdms_raw = load_tdms(os.path.join(DATA_DIR, "tdms.csv"))
    coa_raw = load_coa(os.path.join(DATA_DIR, "coa.csv"))

    tasks, counts = normalize_all(tms_raw, smms_raw, tdms_raw)

    print(f"  TMS tasks       : {counts['TMS']}")
    print(f"  SMMS tasks      : {counts['SMMS']}")
    print(f"  TDMS tasks      : {counts['TDMS']}")
    print(f"  Total tasks     : {counts['total']}")
    print(f"  Train movements : {len(coa_raw)}")
    print()

    # ── Phase 2: Store in SQLite ──────────────────────────────────────────
    conn = database.reset_db()
    database.insert_tasks(conn, tasks)
    database.insert_trains(conn, coa_raw)
    database.insert_default_resources(conn)
    print(f"  Database        : hydra.db (SQLite)")
    print()

    # ── Phase 4: Priority ─────────────────────────────────────────────────
    print(hr())
    print("  PRIORITY")
    print(hr())

    tasks, priority_summary = calculate_all_priorities(tasks, coa_raw)

    print(f"  Critical        : {priority_summary['CRITICAL']}")
    print(f"  High            : {priority_summary['HIGH']}")
    print(f"  Medium          : {priority_summary['MEDIUM']}")
    print(f"  Low             : {priority_summary['LOW']}")

    # Update DB with priority scores
    for t in tasks:
        conn.execute(
            "UPDATE maintenance_tasks SET priority_score=?, priority_level=?, urgency=?, train_impact=? WHERE task_id=?",
            (t["priority_score"], t["priority_level"], t["urgency"], t["train_impact"], t["task_id"])
        )
    conn.commit()
    print()

    # ── Phase 5: Block Windows ────────────────────────────────────────────
    print(hr())
    print("  BLOCK WINDOWS")
    print(hr())

    windows = find_all_windows(coa_raw)
    print(f"  Candidate windows: {len(windows)}")

    # Show windows per corridor
    from collections import Counter
    win_per_corridor = Counter(w["corridor_id"] for w in windows)
    for cid in sorted(win_per_corridor):
        print(f"    {cid}: {win_per_corridor[cid]} windows")
    print()

    # ── Phase 6: Coordination ─────────────────────────────────────────────
    print(hr())
    print("  COORDINATION")
    print(hr())

    groups = find_coordination_groups(tasks)
    group_summary = summarize_groups(groups)

    print(f"  Joint groups    : {group_summary['total_groups']}")
    print(f"  Bundled tasks   : {group_summary['total_bundled_tasks']}")
    print(f"  Multi-dept groups: {group_summary['multi_department_groups']}")
    print(f"  3-dept groups   : {group_summary['three_department_groups']}")
    print(f"  Time saved (min): {group_summary['time_saved_minutes']}")

    for g in groups[:5]:  # Show first 5 groups
        depts = "+".join(g["departments"])
        print(f"    {g['group_id']}: {g['corridor_id']} KM{g['location_range'][0]}-{g['location_range'][1]} "
              f"[{depts}] joint={g['joint_duration']}min (serial={g['serial_duration']}min)")
    if len(groups) > 5:
        print(f"    ... and {len(groups) - 5} more groups")
    print()

    # ── Phase 8: Baseline ─────────────────────────────────────────────────
    print(hr())
    print("  BASELINE (Decentralized)")
    print(hr())

    baseline = schedule_baseline(tasks, windows)
    bs = baseline["stats"]

    print(f"  Blocks          : {bs['total_blocks']}")
    print(f"  Block hours     : {bs['total_block_hours']}")
    print(f"  Tasks completed : {bs['tasks_completed']}")
    print(f"  Critical done   : {bs['critical_completed']}")
    print(f"  Bundled tasks   : {bs['bundled_tasks']}")
    print(f"  Avg utilization : {bs['avg_utilization']}%")
    print()

    # ── Phase 7: OR-Tools ─────────────────────────────────────────────────
    print(hr())
    print("  HYDRA OPTIMIZER (OR-Tools CP-SAT)")
    print(hr())

    print("  Running optimizer...")
    result = optimize(tasks, groups, windows)

    os_ = result["stats"]
    print(f"  Status          : {result['status']}")
    print(f"  Blocks          : {os_['total_blocks']}")
    print(f"  Block hours     : {os_['total_block_hours']}")
    print(f"  Tasks completed : {os_['tasks_completed']}")
    print(f"  Critical done   : {os_['critical_completed']}")
    print(f"  Bundled tasks   : {os_['bundled_tasks']}")
    print(f"  Multi-dept blocks: {os_['multi_dept_blocks']}")
    print(f"  Avg utilization : {os_['avg_utilization']}%")
    print(f"  Optimization time: {result['optimization_time']} sec")
    print()

    # ── Phase 9: Comparison ───────────────────────────────────────────────
    print(hr())
    print("  COMPARISON: BASELINE vs HYDRA")
    print(hr())

    def _pct(baseline_val, opt_val):
        if baseline_val == 0:
            return "N/A"
        change = ((baseline_val - opt_val) / baseline_val) * 100
        return f"{change:+.1f}%"

    print(f"  {'Metric':<22} {'Baseline':>10} {'HYDRA':>10} {'Change':>10}")
    print(f"  {hr(width=54)}")
    print(f"  {'Blocks':<22} {bs['total_blocks']:>10} {os_['total_blocks']:>10} {_pct(bs['total_blocks'], os_['total_blocks']):>10}")
    print(f"  {'Block Hours':<22} {bs['total_block_hours']:>10} {os_['total_block_hours']:>10} {_pct(bs['total_block_hours'], os_['total_block_hours']):>10}")
    print(f"  {'Tasks Completed':<22} {bs['tasks_completed']:>10} {os_['tasks_completed']:>10} {_pct(-bs['tasks_completed'], -os_['tasks_completed']):>10}")
    print(f"  {'Critical Done':<22} {bs['critical_completed']:>10} {os_['critical_completed']:>10} {_pct(-bs['critical_completed'], -os_['critical_completed']):>10}")
    print(f"  {'Bundled Tasks':<22} {bs['bundled_tasks']:>10} {os_['bundled_tasks']:>10} {'':>10}")
    print(f"  {'Avg Utilization':<22} {str(bs['avg_utilization'])+'%':>10} {str(os_['avg_utilization'])+'%':>10} {'':>10}")
    print()

    # ── Validation ────────────────────────────────────────────────────────
    print(hr())
    print("  VALIDATION")
    print(hr())

    validation = validate_schedule(result, coa_raw)

    print(f"  Train conflicts : {validation['checks'].get('train_conflicts', 0)}")
    print(f"  Duplicate tasks : {validation['checks'].get('duplicate_tasks', 0)}")
    print(f"  Capacity issues : {validation['checks'].get('capacity_violations', 0)}")
    print()

    if validation["valid"]:
        print("  ✓ VALID OPTIMIZED SCHEDULE")
    else:
        print("  ✗ SCHEDULE HAS VIOLATIONS:")
        for v in validation["violations"]:
            print(f"    - {v}")

    print()
    print(hr("═"))
    print()

    conn.close()
    return result, baseline, validation


if __name__ == "__main__":
    main()
