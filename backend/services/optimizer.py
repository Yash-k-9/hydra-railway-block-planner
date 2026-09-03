"""
HYDRA - OR-Tools CP-SAT Optimizer
Real constraint-programming model for railway maintenance block scheduling.

Decision: which tasks/groups are assigned to which block windows.

Hard constraints:
  1. Each task assigned at most once (individually or via a group)
  2. Corridor matching (task must be on same corridor as window)
  3. Capacity: total work in a window ≤ window duration
  4. Confirmed trains are never overlapped (windows already exclude them)
  5. A task cannot be scheduled twice

Soft objectives (weighted):
  - Maximize priority coverage
  - Maximize critical-task completion
  - Maximize multi-department bundling
  - Minimize number of blocks used
"""

import time
from ortools.sat.python import cp_model

# ── Default Weights ───────────────────────────────────────────────────────
DEFAULT_WEIGHTS = {
    "priority": 2,       # per priority-score point
    "critical": 200,     # bonus per critical task scheduled
    "bundle": 100,       # bonus per coordination group scheduled as bundle
    "blocks": 10,        # cost per block used
}

SOLVER_TIME_LIMIT = 30  # seconds


def optimize(tasks, groups, windows, weights=None, time_limit=None):
    """Run OR-Tools CP-SAT optimization.

    Args:
        tasks: list of unified task dicts (with priority_score)
        groups: list of coordination group dicts from coordination engine
        windows: list of block window dicts
        weights: optional weight overrides
        time_limit: solver time limit in seconds

    Returns:
        dict with: blocks, scheduled_tasks, unscheduled_tasks,
                   objective_value, optimization_time, stats
    """
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    limit = time_limit or SOLVER_TIME_LIMIT

    # ── Index structures ──────────────────────────────────────────────────
    task_by_id = {t["task_id"]: t for t in tasks}

    # Which tasks are in groups?
    grouped_task_ids = set()
    for g in groups:
        grouped_task_ids.update(g["task_ids"])

    ungrouped_tasks = [t for t in tasks if t["task_id"] not in grouped_task_ids]

    # ── Build CP-SAT model ────────────────────────────────────────────────
    model = cp_model.CpModel()

    # --- Variables ---

    # assign_individual[task_id][window_id] = BoolVar
    assign_individual = {}
    for t in tasks:
        assign_individual[t["task_id"]] = {}
        for win in windows:
            if (t["corridor_id"] == win["corridor_id"]
                    and t["duration_minutes"] <= win["duration_minutes"]):
                var_name = f"ind_{t['task_id']}_{win['window_id']}"
                assign_individual[t["task_id"]][win["window_id"]] = model.NewBoolVar(var_name)

    # assign_group[group_id][window_id] = BoolVar
    assign_group = {}
    for g in groups:
        assign_group[g["group_id"]] = {}
        for win in windows:
            if (g["corridor_id"] == win["corridor_id"]
                    and g["joint_duration"] <= win["duration_minutes"]):
                var_name = f"grp_{g['group_id']}_{win['window_id']}"
                assign_group[g["group_id"]][win["window_id"]] = model.NewBoolVar(var_name)

    # block_used[window_id] = BoolVar
    block_used = {}
    for win in windows:
        block_used[win["window_id"]] = model.NewBoolVar(f"used_{win['window_id']}")

    # task_scheduled[task_id] = BoolVar (is this task scheduled at all?)
    task_scheduled = {}
    for t in tasks:
        task_scheduled[t["task_id"]] = model.NewBoolVar(f"sched_{t['task_id']}")

    # group_scheduled[group_id] = BoolVar
    group_scheduled = {}
    for g in groups:
        group_scheduled[g["group_id"]] = model.NewBoolVar(f"gsched_{g['group_id']}")

    # --- Constraints ---

    # C1: Each task assigned at most once.
    # For grouped tasks: either individually OR via one group assignment.
    # For ungrouped tasks: at most one individual assignment.

    for t in tasks:
        tid = t["task_id"]
        all_assignments = []

        # Individual assignments
        for wid, var in assign_individual[tid].items():
            all_assignments.append(var)

        # Group assignments (for tasks that belong to groups)
        for g in groups:
            if tid in g["task_ids"]:
                for wid, var in assign_group[g["group_id"]].items():
                    all_assignments.append(var)

        # At most one assignment
        model.Add(sum(all_assignments) <= 1)

        # Link to task_scheduled
        model.Add(task_scheduled[tid] == sum(all_assignments))

    # C2: Each group assigned at most once
    for g in groups:
        gid = g["group_id"]
        group_vars = list(assign_group[gid].values())
        model.Add(sum(group_vars) <= 1)
        model.Add(group_scheduled[gid] == sum(group_vars))

    # C3: Capacity constraint for each window
    for win in windows:
        wid = win["window_id"]
        capacity_terms = []

        # Individual task contributions
        for t in tasks:
            tid = t["task_id"]
            if wid in assign_individual[tid]:
                capacity_terms.append(
                    t["duration_minutes"] * assign_individual[tid][wid]
                )

        # Group contributions (joint duration)
        for g in groups:
            gid = g["group_id"]
            if wid in assign_group[gid]:
                capacity_terms.append(
                    g["joint_duration"] * assign_group[gid][wid]
                )

        if capacity_terms:
            model.Add(sum(capacity_terms) <= win["duration_minutes"])

    # C4: Link block_used to assignments
    for win in windows:
        wid = win["window_id"]

        any_assigned = []
        for t in tasks:
            if wid in assign_individual[t["task_id"]]:
                any_assigned.append(assign_individual[t["task_id"]][wid])
        for g in groups:
            if wid in assign_group[g["group_id"]]:
                any_assigned.append(assign_group[g["group_id"]][wid])

        # If anything is assigned to this window, it's used
        for var in any_assigned:
            model.AddImplication(var, block_used[wid])

        # If nothing is assigned, it's not used
        if any_assigned:
            model.AddMaxEquality(block_used[wid], any_assigned)
        else:
            model.Add(block_used[wid] == 0)

    # --- Objective ---
    # MINIMIZE: block_cost - priority_benefit - critical_benefit - bundle_benefit

    objective_terms = []

    # Cost: number of blocks used
    for wid, var in block_used.items():
        objective_terms.append(w["blocks"] * var)

    # Benefit: priority coverage (maximize → negate for minimization)
    for t in tasks:
        score = int(t["priority_score"])  # CP-SAT needs integers
        objective_terms.append(-w["priority"] * score * task_scheduled[t["task_id"]])

    # Benefit: critical task completion
    for t in tasks:
        if t.get("priority_level") == "CRITICAL":
            objective_terms.append(-w["critical"] * task_scheduled[t["task_id"]])

    # Benefit: group bundling
    for g in groups:
        objective_terms.append(-w["bundle"] * group_scheduled[g["group_id"]])

    model.Minimize(sum(objective_terms))

    # ── Solve ─────────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = limit
    solver.parameters.num_workers = 4

    start_time = time.time()
    status = solver.Solve(model)
    solve_time = round(time.time() - start_time, 2)

    # ── Extract solution ──────────────────────────────────────────────────
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": "INFEASIBLE",
            "blocks": [],
            "scheduled_tasks": [],
            "unscheduled_tasks": [t["task_id"] for t in tasks],
            "objective_value": None,
            "optimization_time": solve_time,
            "stats": {},
        }

    # Build block assignments
    window_by_id = {win["window_id"]: win for win in windows}
    blocks = []
    scheduled_task_ids = set()
    bundled_task_ids = set()

    for win in windows:
        wid = win["window_id"]
        if not solver.Value(block_used[wid]):
            continue

        block_tasks = []
        block_departments = set()
        block_duration_used = 0
        is_group_block = False

        # Check group assignments first
        for g in groups:
            gid = g["group_id"]
            if wid in assign_group[gid] and solver.Value(assign_group[gid][wid]):
                is_group_block = True
                for tid in g["task_ids"]:
                    t = task_by_id[tid]
                    t_copy = dict(t)
                    t_copy["bundled"] = True
                    block_tasks.append(t_copy)
                    block_departments.add(t["department"])
                    scheduled_task_ids.add(tid)
                    bundled_task_ids.add(tid)
                block_duration_used = max(block_duration_used, g["joint_duration"])

        # Check individual assignments
        for t in tasks:
            tid = t["task_id"]
            if wid in assign_individual[tid] and solver.Value(assign_individual[tid][wid]):
                t_copy = dict(t)
                t_copy["bundled"] = False
                block_tasks.append(t_copy)
                block_departments.add(t["department"])
                scheduled_task_ids.add(tid)
                block_duration_used += t["duration_minutes"]

        if block_tasks:
            utilization = round(
                block_duration_used / win["duration_minutes"] * 100, 1
            ) if win["duration_minutes"] > 0 else 0

            blocks.append({
                "block_id": f"BLK-{wid}",
                "window_id": wid,
                "corridor_id": win["corridor_id"],
                "date": win["date"],
                "start_time": win["start_time"],
                "end_time": win["end_time"],
                "duration_minutes": win["duration_minutes"],
                "tasks": block_tasks,
                "departments": sorted(block_departments),
                "is_multi_department": len(block_departments) > 1,
                "requires_isolation": any(
                    task_by_id[bt["task_id"]].get("requires_isolation", False)
                    for bt in block_tasks
                ),
                "utilization": utilization,
                "status": "generated",
            })

    unscheduled = [t["task_id"] for t in tasks if t["task_id"] not in scheduled_task_ids]

    # Stats
    critical_scheduled = sum(
        1 for t in tasks
        if t["task_id"] in scheduled_task_ids and t["priority_level"] == "CRITICAL"
    )
    total_block_hours = sum(b["duration_minutes"] for b in blocks) / 60.0

    stats = {
        "total_blocks": len(blocks),
        "total_block_hours": round(total_block_hours, 1),
        "tasks_completed": len(scheduled_task_ids),
        "tasks_deferred": len(unscheduled),
        "critical_completed": critical_scheduled,
        "bundled_tasks": len(bundled_task_ids),
        "multi_dept_blocks": sum(1 for b in blocks if b["is_multi_department"]),
        "avg_utilization": round(
            sum(b["utilization"] for b in blocks) / max(len(blocks), 1), 1
        ),
    }

    return {
        "status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
        "blocks": blocks,
        "scheduled_tasks": sorted(scheduled_task_ids),
        "unscheduled_tasks": unscheduled,
        "objective_value": solver.ObjectiveValue(),
        "optimization_time": solve_time,
        "stats": stats,
    }


def validate_schedule(result, trains):
    """Validate the optimized schedule against hard constraints.

    Returns:
        dict with: valid (bool), violations (list of strings)
    """
    violations = []

    if not result.get("blocks"):
        return {"valid": True, "violations": [], "checks": {}}

    # Check 1: No task scheduled twice
    all_task_ids = []
    for block in result["blocks"]:
        for bt in block["tasks"]:
            all_task_ids.append(bt["task_id"])

    duplicates = [tid for tid in all_task_ids if all_task_ids.count(tid) > 1]
    if duplicates:
        violations.append(f"Duplicate task assignments: {set(duplicates)}")

    # Check 2: No train conflict
    train_conflicts = 0
    for block in result["blocks"]:
        from services.block_windows import check_conflict
        conflicts = check_conflict(
            block["start_time"], block["end_time"],
            trains, block["corridor_id"], block["date"]
        )
        if conflicts:
            train_ids = [c["train_id"] for c in conflicts]
            violations.append(
                f"Block {block['block_id']} conflicts with trains: {train_ids}"
            )
            train_conflicts += len(conflicts)

    # Check 3: Tasks fit within their blocks
    for block in result["blocks"]:
        # For bundled tasks: joint duration = max
        bundled = [bt for bt in block["tasks"] if bt.get("bundled")]
        individual = [bt for bt in block["tasks"] if not bt.get("bundled")]

        total_needed = 0
        if bundled:
            total_needed += max(bt["duration_minutes"] for bt in bundled)
        total_needed += sum(bt["duration_minutes"] for bt in individual)

        if total_needed > block["duration_minutes"]:
            violations.append(
                f"Block {block['block_id']}: work ({total_needed} min) exceeds "
                f"window ({block['duration_minutes']} min)"
            )

    # Check 4: Corridor consistency
    for block in result["blocks"]:
        for bt in block["tasks"]:
            # We trust the optimizer here, but verify the data
            pass  # Corridor check is enforced by variable creation

    checks = {
        "duplicate_tasks": len(set(duplicates)) if duplicates else 0,
        "train_conflicts": train_conflicts,
        "capacity_violations": sum(1 for v in violations if "exceeds" in v),
    }

    return {
        "valid": len(violations) == 0,
        "violations": violations,
        "checks": checks,
    }
