"""
HYDRA - OR-Tools CP-SAT Optimizer
Real constraint-programming model for railway maintenance block scheduling.

Decisions:
  - which tasks/groups go into which train-free window (gap between trains)
  - when the block starts inside that window; a block lasts only as long as
    the work assigned to it, not the whole gap

Hard constraints:
  1. Each task assigned at most once (individually or via a group)
  2. Corridor matching (task must be on same corridor as window)
  3. Block = work assigned to it, and must fit inside its window
  4. Confirmed trains are never overlapped (block stays inside a train-free gap)
  5. All work in one block lies within one block section (BLOCK_SECTION_KM)
  6. Crew limit: per department and day, at most N blocks needing that
     department may run at the same time

Fixed blocks (e.g. already approved) are kept exactly as they are: their tasks
are not rescheduled, their time is taken out of the windows, and their crews
count towards the crew limits.

Goals, solved in strict order (each stage keeps the best value of the previous):
  1. Schedule as many CRITICAL tasks as possible
  2. Maximize priority value; each day a task runs past its due date
     (or past the planning start, if already overdue) loses LATE_DAY_PENALTY_PCT
  3. (re-planning only) Keep as many tasks as possible in the window they had
     in the previous plan, so a disruption doesn't reshuffle the whole week
  4. Minimize track closure: block minutes + BLOCK_SETUP_MINUTES per block
  5. Start blocks as early in their window as possible (tidy, stable times)
"""

import os
import time
from datetime import datetime

from ortools.sat.python import cp_model

from .priority import PLANNING_START

# ── Model Parameters ──────────────────────────────────────────────────────
# Crews per department; mirrors database.insert_default_resources
DEFAULT_CREWS = {"ENGINEERING": 2, "SIGNALLING": 2, "TRACTION": 2}

BLOCK_SECTION_KM = 5.0       # max span of work inside one block
BLOCK_SETUP_MINUTES = 30     # closure cost of opening a block (possession setup/clearance)
LATE_DAY_PENALTY_PCT = 10    # value lost per day late, % of the task's priority value
MIN_VALUE_PCT = 10           # a late task always keeps at least this share of its value

START_STEP_MINUTES = 15     # blocks start on a 15-minute grid from the window start

SOLVER_TIME_LIMIT = 30  # seconds, shared across the stages
MIN_STAGE_SECONDS = 5   # loading a full week's model alone can take ~1–3 s
# Relative share of the time limit per stage; value and closure are where
# crew limits make it hard
STAGE_TIME_WEIGHT = {
    "critical_tasks": 1,
    "priority_value": 4,
    "kept_in_place": 1.5,
    "closure_minutes": 4,
    "start_offset_minutes": 1,
}

KM_SCALE = 10  # CP-SAT needs integers: locations in 0.1 km


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _time_to_minutes(time_str):
    h, m = time_str.strip().split(":")
    return int(h) * 60 + int(m)


def _minutes_to_time(minutes):
    h, m = divmod(int(minutes), 60)
    return f"{h:02d}:{m:02d}"


def days_late(window_date, due_date):
    """Days a task runs late if done on window_date.

    Already-overdue tasks count from the planning start, so earlier is still better.
    Unknown dates count as on time.
    """
    win = _parse_date(window_date)
    due = _parse_date(due_date)
    if not win or not due:
        return 0
    return max(0, (win - max(due, PLANNING_START)).days)


def _task_value(task, window_date):
    """Integer priority value of doing a task on window_date (late days reduce it)."""
    score = int(round(task.get("priority_score", 0) * 10))
    pct = max(MIN_VALUE_PCT, 100 - LATE_DAY_PENALTY_PCT * days_late(window_date, task.get("due_date")))
    return score * pct // 100


def _build_items(tasks, groups):
    """Schedulable units: each coordination group, plus every task on its own.

    A grouped task can still be scheduled alone if that works out better.
    """
    task_by_id = {t["task_id"]: t for t in tasks}
    items = []

    for g in groups:
        members = [task_by_id[tid] for tid in g["task_ids"] if tid in task_by_id]
        if len(members) != len(g["task_ids"]):
            continue
        kms = [t["location_km"] for t in members]
        items.append({
            "kind": "group",
            "id": g["group_id"],
            "tasks": members,
            "corridor_id": g["corridor_id"],
            "duration": g["joint_duration"],
            "km_lo": min(kms),
            "km_hi": max(kms),
            "departments": {t["department"] for t in members},
        })

    for t in tasks:
        items.append({
            "kind": "task",
            "id": t["task_id"],
            "tasks": [t],
            "corridor_id": t["corridor_id"],
            "duration": t["duration_minutes"],
            "km_lo": t["location_km"],
            "km_hi": t["location_km"],
            "departments": {t["department"]},
        })

    return items


def _max_overlap(spans):
    """Most (start, end) spans running at the same moment; touching ends don't overlap."""
    events = sorted([(s, 1) for s, _ in spans] + [(e, -1) for _, e in spans])
    busy = peak = 0
    for _, delta in events:
        busy += delta
        peak = max(peak, busy)
    return peak


def _split_windows(windows, fixed_blocks):
    """Take the time of fixed blocks out of the windows they sit in.

    A window with a fixed block in the middle becomes two pieces (ids W-001a, W-001b).
    """
    pieces = []
    for win in windows:
        ws = _time_to_minutes(win["start_time"])
        we = ws + win["duration_minutes"]
        taken = sorted(
            (_time_to_minutes(b["start_time"]), _time_to_minutes(b["end_time"]))
            for b in fixed_blocks
            if b["corridor_id"] == win["corridor_id"] and b["date"] == win["date"]
        )
        taken = [(max(s, ws), min(e, we)) for s, e in taken if s < we and e > ws]
        if not taken:
            pieces.append(win)
            continue
        free, cursor = [], ws
        for s, e in taken:
            if s > cursor:
                free.append((cursor, s))
            cursor = max(cursor, e)
        if we > cursor:
            free.append((cursor, we))
        for n, (s, e) in enumerate(free):
            pieces.append({
                **win,
                "window_id": f"{win['window_id']}{chr(ord('a') + n)}",
                "start_time": _minutes_to_time(s),
                "end_time": _minutes_to_time(e),
                "duration_minutes": e - s,
            })
    return pieces


def _previous_placement(previous_blocks):
    """task_id → (corridor, date, block start minute) from an earlier plan."""
    placement = {}
    for b in previous_blocks or []:
        for bt in b["tasks"]:
            placement[bt["task_id"]] = (b["corridor_id"], b["date"], _time_to_minutes(b["start_time"]))
    return placement


def _in_window(place, win):
    """Is an earlier placement inside this window (same corridor, day and gap)?"""
    corridor, date_str, minute = place
    ws = _time_to_minutes(win["start_time"])
    return (corridor == win["corridor_id"] and date_str == win["date"]
            and ws <= minute < ws + win["duration_minutes"])


def _hint_previous_plan(model, previous_blocks, fixed_task_ids, items, windows,
                        x, used, start, steps, work):
    """Give the solver the previous plan as its starting point (a hint for every
    placement variable). Parts that no longer fit are repaired by the solver."""
    item_index = {(item["kind"], item["id"]): i for i, item in enumerate(items)}
    group_members = {item["id"]: {t["task_id"] for t in item["tasks"]}
                     for item in items if item["kind"] == "group"}
    chosen = set()     # (item_index, window_id)
    block_start = {}   # window_id → previous start minute

    for b in previous_blocks:
        if any(bt["task_id"] in fixed_task_ids for bt in b["tasks"]):
            continue
        place = (b["corridor_id"], b["date"], _time_to_minutes(b["start_time"]))
        win = next((w for w in windows if _in_window(place, w)), None)
        if not win:
            continue
        wid = win["window_id"]
        block_start[wid] = place[2]
        for bt in b["tasks"]:
            gid = bt.get("group_id")
            if bt.get("bundled") and gid in group_members:
                key = ("group", gid)
            else:
                key = ("task", bt["task_id"])
            if key in item_index and (item_index[key], wid) in x:
                chosen.add((item_index[key], wid))

    for key, var in x.items():
        model.AddHint(var, 1 if key in chosen else 0)
    for win in windows:
        wid = win["window_id"]
        ws = _time_to_minutes(win["start_time"])
        minutes = sum(items[i]["duration"] for (i, w) in chosen if w == wid)
        n_steps = 0
        if wid in block_start and minutes:
            room = (win["duration_minutes"] - minutes) // START_STEP_MINUTES
            n_steps = max(0, min(room, (block_start[wid] - ws) // START_STEP_MINUTES))
        model.AddHint(used[wid], 1 if minutes else 0)
        model.AddHint(work[wid], min(minutes, win["duration_minutes"]))
        model.AddHint(steps[wid], n_steps)
        model.AddHint(start[wid], ws + START_STEP_MINUTES * n_steps)


def _empty_result(tasks, status, solve_time):
    return {
        "status": status,
        "blocks": [],
        "scheduled_tasks": [],
        "unscheduled_tasks": [t["task_id"] for t in tasks],
        "objective_value": None,
        "objectives": {},
        "optimality_gaps": {},
        "optimization_time": solve_time,
        "stats": {},
    }


def optimize(tasks, groups, windows, crews=None, time_limit=None,
             fixed_blocks=None, previous_blocks=None):
    """Run OR-Tools CP-SAT optimization.

    Args:
        tasks: list of unified task dicts (with priority_score)
        groups: list of coordination group dicts from coordination engine
        windows: list of block window dicts
        crews: crews per department (default DEFAULT_CREWS); departments not
               listed are not crew-limited
        time_limit: total solver time limit in seconds
        fixed_blocks: blocks to keep exactly as they are (e.g. approved ones);
                      each must sit inside a train-free window
        previous_blocks: blocks of the plan being revised; tasks are kept in
                         their old window where possible

    Returns:
        dict with: status, blocks, scheduled_tasks, unscheduled_tasks,
                   objective_value, objectives, optimization_time, stats
    """
    crews = DEFAULT_CREWS if crews is None else crews
    limit = time_limit or SOLVER_TIME_LIMIT
    fixed_blocks = fixed_blocks or []
    fixed_task_ids = {bt["task_id"] for b in fixed_blocks for bt in b["tasks"]}
    all_tasks = tasks
    tasks = [t for t in tasks if t["task_id"] not in fixed_task_ids]
    windows = _split_windows(windows, fixed_blocks)
    # Groups with a member in a fixed block drop out here (member missing)
    items = _build_items(tasks, groups)
    previous = {
        tid: place for tid, place in _previous_placement(previous_blocks).items()
        if tid not in fixed_task_ids
    }

    model = cp_model.CpModel()

    # ── Variables ─────────────────────────────────────────────────────────
    # x[(item_index, window_id)] = item scheduled in that window
    x = {}
    for i, item in enumerate(items):
        for win in windows:
            if (item["corridor_id"] == win["corridor_id"]
                    and item["duration"] <= win["duration_minutes"]):
                x[(i, win["window_id"])] = model.NewBoolVar(f"x_{item['id']}_{win['window_id']}")

    items_in_window = {win["window_id"]: [] for win in windows}
    for (i, wid) in x:
        items_in_window[wid].append(i)

    used, start, steps, work = {}, {}, {}, {}
    for win in windows:
        wid = win["window_id"]
        ws = _time_to_minutes(win["start_time"])
        we = ws + win["duration_minutes"]
        used[wid] = model.NewBoolVar(f"used_{wid}")
        # start = window start + a whole number of START_STEP_MINUTES steps
        steps[wid] = model.NewIntVar(0, win["duration_minutes"] // START_STEP_MINUTES, f"steps_{wid}")
        start[wid] = model.NewIntVar(ws, we, f"start_{wid}")
        model.Add(start[wid] == ws + START_STEP_MINUTES * steps[wid])
        work[wid] = model.NewIntVar(0, win["duration_minutes"], f"work_{wid}")

    # ── Constraints ───────────────────────────────────────────────────────

    # C1: each task at most once, alone or inside one group
    task_vars = {t["task_id"]: [] for t in tasks}
    for (i, wid), var in x.items():
        for t in items[i]["tasks"]:
            task_vars[t["task_id"]].append(var)
    for vars_ in task_vars.values():
        if vars_:
            model.AddAtMostOne(vars_)

    for win in windows:
        wid = win["window_id"]
        ws = _time_to_minutes(win["start_time"])
        we = ws + win["duration_minutes"]
        in_win = [x[(i, wid)] for i in items_in_window[wid]]

        # C3: block length = work assigned (items run one after another),
        # and the block stays inside the train-free window
        model.Add(work[wid] == sum(items[i]["duration"] * x[(i, wid)] for i in items_in_window[wid]))
        model.Add(start[wid] + work[wid] <= we)

        # A window is used exactly when something is assigned to it
        if in_win:
            model.AddMaxEquality(used[wid], in_win)
        else:
            model.Add(used[wid] == 0)
        # Unused windows sit at their start, so they don't affect stage 4
        model.Add(start[wid] == ws).OnlyEnforceIf(used[wid].Not())

        # C5: all work in the block within one block section — two items too far
        # apart never share a window (pairwise form propagates far better than min/max bounds)
        section = int(round(BLOCK_SECTION_KM * KM_SCALE))
        idx = sorted(items_in_window[wid], key=lambda i: items[i]["km_lo"])
        for a_pos, a in enumerate(idx):
            a_lo = int(round(items[a]["km_lo"] * KM_SCALE))
            for b in idx[a_pos + 1:]:
                b_hi = int(round(items[b]["km_hi"] * KM_SCALE))
                a_hi = int(round(items[a]["km_hi"] * KM_SCALE))
                if max(a_hi, b_hi) - min(a_lo, int(round(items[b]["km_lo"] * KM_SCALE))) > section:
                    model.AddBoolOr([x[(a, wid)].Not(), x[(b, wid)].Not()])

    # C6: crew limits. A department's crew is busy for the whole block it works in.
    crew_intervals = {}  # (department, date) → list of optional intervals
    for win in windows:
        wid = win["window_id"]
        for dept in crews:
            dept_vars = [x[(i, wid)] for i in items_in_window[wid] if dept in items[i]["departments"]]
            if not dept_vars:
                continue
            needs = model.NewBoolVar(f"needs_{dept}_{wid}")
            model.AddMaxEquality(needs, dept_vars)
            end = model.NewIntVar(0, 24 * 60, f"end_{dept}_{wid}")
            interval = model.NewOptionalIntervalVar(start[wid], work[wid], end, needs, f"crew_{dept}_{wid}")
            crew_intervals.setdefault((dept, win["date"]), []).append(interval)
    fixed_spans = {}  # (department, date) → spans of fixed blocks
    for b in fixed_blocks:
        s, e = _time_to_minutes(b["start_time"]), _time_to_minutes(b["end_time"])
        for dept in set(b.get("departments", [])) & set(crews):
            crew_intervals.setdefault((dept, b["date"]), []).append(
                model.NewFixedSizeIntervalVar(s, e - s, f"fixed_{dept}_{b['block_id']}")
            )
            fixed_spans.setdefault((dept, b["date"]), []).append((s, e))
    for (dept, date_str), intervals in crew_intervals.items():
        # Fixed blocks alone must never make the model infeasible
        capacity = max(crews[dept], _max_overlap(fixed_spans.get((dept, date_str), [])))
        if len(intervals) > capacity:
            model.AddCumulative(intervals, [1] * len(intervals), capacity)

    # ── Staged objectives ─────────────────────────────────────────────────
    window_by_id = {win["window_id"]: win for win in windows}
    critical_expr = sum(
        sum(1 for t in items[i]["tasks"] if t.get("priority_level") == "CRITICAL") * var
        for (i, wid), var in x.items()
    )
    value_expr = sum(
        sum(_task_value(t, window_by_id[wid]["date"]) for t in items[i]["tasks"]) * var
        for (i, wid), var in x.items()
    )
    closure_expr = sum(work[wid] + BLOCK_SETUP_MINUTES * used[wid] for wid in used)
    offset_expr = sum(
        start[wid] - _time_to_minutes(window_by_id[wid]["start_time"]) for wid in start
    )

    stages = [
        ("critical_tasks", critical_expr, "max"),
        ("priority_value", value_expr, "max"),
    ]
    if previous:
        kept_expr = sum(
            sum(1 for t in items[i]["tasks"]
                if t["task_id"] in previous and _in_window(previous[t["task_id"]], window_by_id[wid])) * var
            for (i, wid), var in x.items()
        )
        stages.append(("kept_in_place", kept_expr, "max"))
    stages += [
        ("closure_minutes", closure_expr, "min"),
        ("start_offset_minutes", offset_expr, "min"),
    ]
    total_weight = sum(STAGE_TIME_WEIGHT[name] for name, _, _ in stages)

    # When re-planning, start the search from the previous plan, so the solver
    # begins with the old plan in hand and changes it only where that pays off
    if previous:
        _hint_previous_plan(model, previous_blocks, fixed_task_ids, items, windows,
                            x, used, start, steps, work)

    solver = cp_model.CpSolver()
    solver.parameters.num_workers = os.cpu_count() or 4
    # A disruption can make parts of the old plan impossible; let the solver repair it
    solver.parameters.repair_hint = bool(previous)

    objectives = {}
    # How far each stage's answer may be from the best possible, in % (0 = proven optimal)
    gaps = {}
    all_optimal = True
    start_time = time.time()

    for name, expr, sense in stages:
        solver.parameters.max_time_in_seconds = max(
            MIN_STAGE_SECONDS, limit * STAGE_TIME_WEIGHT[name] / total_weight
        )
        if sense == "max":
            model.Maximize(expr)
        else:
            model.Minimize(expr)
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            if not objectives:
                # Scheduling nothing is always allowed, so no answer means no time, not no plan
                label = "INFEASIBLE" if status == cp_model.INFEASIBLE else "TIMEOUT"
                return _empty_result(all_tasks, label, round(time.time() - start_time, 2))
            all_optimal = False
            break  # keep the previous stage's solution (still in the hints)
        all_optimal = all_optimal and status == cp_model.OPTIMAL

        best = int(round(solver.ObjectiveValue()))
        bound = solver.BestObjectiveBound()
        objectives[name] = best
        gaps[name] = round(abs(bound - best) / max(abs(bound), abs(best), 1) * 100, 1)
        solution = list(solver.ResponseProto().solution)

        # Lock this goal in, and start the next stage from this solution. The hint
        # covers every variable, so the next stage starts from a complete, valid plan.
        if sense == "max":
            model.Add(expr >= best)
        else:
            model.Add(expr <= best)
        model.ClearHints()
        hint_proto = model.Proto().solution_hint
        hint_proto.vars.extend(range(len(solution)))
        hint_proto.values.extend(solution)

    solve_time = round(time.time() - start_time, 2)

    # The last successful solution lives in the hints; read values from there
    hint = dict(zip(model.Proto().solution_hint.vars, model.Proto().solution_hint.values))
    val = lambda var: hint[var.Index()]

    # ── Extract solution ──────────────────────────────────────────────────
    blocks = []
    scheduled_task_ids = set()
    bundled_task_ids = set()
    late_tasks = 0
    total_days_late = 0

    for win in windows:
        wid = win["window_id"]
        if not val(used[wid]):
            continue

        # Groups first, then single tasks; each runs after the previous one
        chosen = sorted(
            (i for i in items_in_window[wid] if val(x[(i, wid)])),
            key=lambda i: (items[i]["kind"] != "group", items[i]["id"]),
        )
        block_start = val(start[wid])
        cursor = block_start
        block_tasks = []
        for i in chosen:
            item = items[i]
            for t in item["tasks"]:
                t_copy = dict(t)
                t_copy["bundled"] = item["kind"] == "group"
                if t_copy["bundled"]:
                    t_copy["group_id"] = item["id"]
                    bundled_task_ids.add(t["task_id"])
                t_copy["work_start"] = _minutes_to_time(cursor)
                t_copy["work_end"] = _minutes_to_time(cursor + t["duration_minutes"])
                t_copy["days_late"] = days_late(win["date"], t.get("due_date"))
                if t_copy["days_late"]:
                    late_tasks += 1
                    total_days_late += t_copy["days_late"]
                block_tasks.append(t_copy)
                scheduled_task_ids.add(t["task_id"])
            cursor += item["duration"]

        block_minutes = cursor - block_start
        kms = [t["location_km"] for t in block_tasks]
        departments = sorted({t["department"] for t in block_tasks})

        blocks.append({
            "block_id": f"BLK-{wid}",
            "window_id": wid,
            "corridor_id": win["corridor_id"],
            "date": win["date"],
            "start_time": _minutes_to_time(block_start),
            "end_time": _minutes_to_time(cursor),
            "duration_minutes": block_minutes,
            "window_start": win["start_time"],
            "window_end": win["end_time"],
            "window_minutes": win["duration_minutes"],
            "section_km": [min(kms), max(kms)],
            "tasks": block_tasks,
            "departments": departments,
            "is_multi_department": len(departments) > 1,
            "requires_isolation": any(t.get("requires_isolation", False) for t in block_tasks),
            # Share of the train-free window this block takes up
            "utilization": round(block_minutes / win["duration_minutes"] * 100, 1)
                           if win["duration_minutes"] > 0 else 0,
            "status": "generated",
        })

    # Fixed blocks go into the plan unchanged
    for b in fixed_blocks:
        blocks.append(b)
        for bt in b["tasks"]:
            scheduled_task_ids.add(bt["task_id"])
            if bt.get("bundled"):
                bundled_task_ids.add(bt["task_id"])
            if bt.get("days_late"):
                late_tasks += 1
                total_days_late += bt["days_late"]

    # Tasks from the previous plan that left their old window (or were dropped)
    new_place = {bt["task_id"]: b for b in blocks for bt in b["tasks"]}
    tasks_moved = sum(
        1 for tid, place in previous.items()
        if tid not in new_place or not _in_window(place, {
            "corridor_id": new_place[tid]["corridor_id"],
            "date": new_place[tid]["date"],
            "start_time": new_place[tid].get("window_start", new_place[tid]["start_time"]),
            "duration_minutes": new_place[tid].get("window_minutes", new_place[tid]["duration_minutes"]),
        })
    )

    unscheduled = [t["task_id"] for t in all_tasks if t["task_id"] not in scheduled_task_ids]
    critical_scheduled = sum(
        1 for t in all_tasks
        if t["task_id"] in scheduled_task_ids and t.get("priority_level") == "CRITICAL"
    )

    stats = {
        "total_blocks": len(blocks),
        "total_block_hours": round(sum(b["duration_minutes"] for b in blocks) / 60.0, 1),
        "tasks_completed": len(scheduled_task_ids),
        "tasks_deferred": len(unscheduled),
        "critical_completed": critical_scheduled,
        "bundled_tasks": len(bundled_task_ids),
        "multi_dept_blocks": sum(1 for b in blocks if len(b.get("departments", [])) > 1),
        "avg_utilization": round(
            sum(b.get("utilization", 0) for b in blocks) / max(len(blocks), 1), 1
        ),
        "late_tasks": late_tasks,
        "total_days_late": total_days_late,
        "priority_gap_pct": gaps.get("priority_value", 0.0),
        "fixed_blocks": len(fixed_blocks),
        "tasks_moved": tasks_moved,
    }

    return {
        "status": "OPTIMAL" if all_optimal else "FEASIBLE",
        "blocks": blocks,
        "scheduled_tasks": sorted(scheduled_task_ids),
        "unscheduled_tasks": unscheduled,
        "objective_value": objectives.get("priority_value"),
        "objectives": objectives,
        "optimality_gaps": gaps,
        "optimization_time": solve_time,
        "stats": stats,
    }


def validate_schedule(result, trains, crews=None):
    """Validate the optimized schedule against hard constraints.

    Returns:
        dict with: valid (bool), violations (list of strings), checks (counts)
    """
    from .block_windows import check_conflict

    crews = DEFAULT_CREWS if crews is None else crews
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

    # Check 3: Tasks fit within their blocks, and blocks within their windows
    capacity_violations = 0
    for block in result["blocks"]:
        # For bundled tasks: each group's joint duration = max of its tasks,
        # and groups sharing a block run one after another
        group_durations = {}
        individual = []
        for bt in block["tasks"]:
            if bt.get("bundled"):
                gid = bt.get("group_id")
                group_durations[gid] = max(group_durations.get(gid, 0), bt["duration_minutes"])
            else:
                individual.append(bt)

        total_needed = sum(group_durations.values())
        total_needed += sum(bt["duration_minutes"] for bt in individual)

        if total_needed > block["duration_minutes"]:
            capacity_violations += 1
            violations.append(
                f"Block {block['block_id']}: work ({total_needed} min) exceeds "
                f"block ({block['duration_minutes']} min)"
            )
        if "window_start" in block and (
            _time_to_minutes(block["start_time"]) < _time_to_minutes(block["window_start"])
            or _time_to_minutes(block["end_time"]) > _time_to_minutes(block["window_end"])
        ):
            capacity_violations += 1
            violations.append(
                f"Block {block['block_id']} ({block['start_time']}-{block['end_time']}) exceeds "
                f"its window ({block['window_start']}-{block['window_end']})"
            )

    # Check 4: All work in a block within one block section
    section_violations = 0
    for block in result["blocks"]:
        kms = [bt["location_km"] for bt in block["tasks"] if "location_km" in bt]
        if kms and max(kms) - min(kms) > BLOCK_SECTION_KM + 1e-9:
            section_violations += 1
            violations.append(
                f"Block {block['block_id']} spans {max(kms) - min(kms):.1f} km "
                f"(max {BLOCK_SECTION_KM} km)"
            )

    # Check 5: Crew limits — overlapping blocks per department and day
    crew_violations = 0
    for dept, limit in crews.items():
        by_date = {}
        for block in result["blocks"]:
            if dept in block.get("departments", []):
                by_date.setdefault(block["date"], []).append(
                    (_time_to_minutes(block["start_time"]), _time_to_minutes(block["end_time"]))
                )
        for date_str, spans in by_date.items():
            events = sorted([(s, 1) for s, _ in spans] + [(e, -1) for _, e in spans])
            busy = 0
            for _, delta in events:  # ends sort before starts at the same minute
                busy += delta
                if busy > limit:
                    crew_violations += 1
                    violations.append(
                        f"{dept} on {date_str}: more than {limit} blocks at the same time"
                    )
                    break

    checks = {
        "duplicate_tasks": len(set(duplicates)) if duplicates else 0,
        "train_conflicts": train_conflicts,
        "capacity_violations": capacity_violations,
        "section_violations": section_violations,
        "crew_violations": crew_violations,
    }

    return {
        "valid": len(violations) == 0,
        "violations": violations,
        "checks": checks,
    }
