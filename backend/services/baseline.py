"""
HYDRA - Baseline Scheduler
Simulates decentralized/manual planning where each department schedules independently.
No cross-department bundling. Used as comparison against optimized plan.

For a fair comparison it follows the same hard rules as the optimizer:
work fits the window, one block section per block, and crew limits.
"""

from .optimizer import DEFAULT_CREWS, BLOCK_SECTION_KM


def _to_minutes(time_str):
    h, m = time_str.split(":")
    return int(h) * 60 + int(m)


def _max_overlap(spans):
    """Most intervals running at the same moment (an end and a start at the same minute don't overlap)."""
    events = sorted([(s, 1) for s, _ in spans] + [(e, -1) for _, e in spans])
    busy = peak = 0
    for _, delta in events:
        busy += delta
        peak = max(peak, busy)
    return peak


def schedule_baseline(tasks, windows, crews=None):
    """Run baseline (decentralized) scheduling.

    Each department independently assigns its tasks to the earliest
    feasible window on the correct corridor. No bundling.

    Args:
        tasks: list of unified task dicts (with priority_score)
        windows: list of block window dicts
        crews: crews per department (default DEFAULT_CREWS)

    Returns:
        dict with: blocks, stats (same structure as optimizer output for comparison)
    """
    departments = ["ENGINEERING", "SIGNALLING", "TRACTION"]
    crews = DEFAULT_CREWS if crews is None else crews

    # Track remaining capacity per window
    window_capacity = {w["window_id"]: w["duration_minutes"] for w in windows}
    window_by_id = {w["window_id"]: dict(w) for w in windows}

    blocks = {}         # window_id → block dict
    scheduled = set()

    def fits(win, task):
        """Can this task be appended to the block in this window?"""
        wid = win["window_id"]
        if window_capacity[wid] < task["duration_minutes"]:
            return False
        blk = blocks.get(wid)
        kms = [bt["location_km"] for bt in blk["tasks"]] if blk else []
        kms.append(task["location_km"])
        if max(kms) - min(kms) > BLOCK_SECTION_KM + 1e-9:
            return False

        # Tasks run one after another from the window start
        start = _to_minutes(win["start_time"])
        used = win["duration_minutes"] - window_capacity[wid]
        span = (start, start + used + task["duration_minutes"])
        block_depts = (blk["departments"] if blk else set()) | {task["department"]}
        for dept in block_depts & set(crews):
            spans = [span]
            for other_wid, other in blocks.items():
                if other_wid != wid and other["date"] == win["date"] and dept in other["departments"]:
                    o_start = _to_minutes(other["start_time"])
                    o_used = window_by_id[other_wid]["duration_minutes"] - window_capacity[other_wid]
                    spans.append((o_start, o_start + o_used))
            if _max_overlap(spans) > crews[dept]:
                return False
        return True

    for dept in departments:
        # Get tasks for this department, sorted by priority (highest first)
        dept_tasks = sorted(
            [t for t in tasks if t["department"] == dept],
            key=lambda t: t["priority_score"],
            reverse=True,
        )

        for task in dept_tasks:
            if task["task_id"] in scheduled:
                continue

            # Find earliest feasible window on the task's corridor
            # Sort windows by date then start_time
            compatible = [
                w for w in windows
                if w["corridor_id"] == task["corridor_id"] and fits(w, task)
            ]
            compatible.sort(key=lambda w: (w["date"], w["start_time"]))

            if not compatible:
                continue  # task cannot be scheduled

            win = compatible[0]
            wid = win["window_id"]

            # Allocate the task
            window_capacity[wid] -= task["duration_minutes"]
            scheduled.add(task["task_id"])

            if wid not in blocks:
                blocks[wid] = {
                    "block_id": f"BASE-{wid}",
                    "window_id": wid,
                    "corridor_id": win["corridor_id"],
                    "date": win["date"],
                    "start_time": win["start_time"],
                    "end_time": win["end_time"],
                    "duration_minutes": win["duration_minutes"],
                    "tasks": [],
                    "departments": set(),
                    "status": "baseline",
                }

            blocks[wid]["tasks"].append({
                "task_id": task["task_id"],
                "department": task["department"],
                "location_km": task["location_km"],
                "duration_minutes": task["duration_minutes"],
                "priority_score": task["priority_score"],
                "priority_level": task["priority_level"],
            })
            blocks[wid]["departments"].add(task["department"])

    # Finalize blocks: like the optimizer, a block lasts only as long as its
    # work (run one after another from the window start), not the whole gap
    block_list = []
    for wid, blk in blocks.items():
        blk["departments"] = sorted(blk["departments"])
        total_work = sum(bt["duration_minutes"] for bt in blk["tasks"])
        window_minutes = blk["duration_minutes"]
        h, m = map(int, blk["start_time"].split(":"))
        end = h * 60 + m + total_work
        blk["window_start"] = blk["start_time"]
        blk["window_end"] = blk["end_time"]
        blk["window_minutes"] = window_minutes
        blk["end_time"] = f"{end // 60:02d}:{end % 60:02d}"
        blk["duration_minutes"] = total_work
        blk["utilization"] = round(
            total_work / window_minutes * 100, 1
        ) if window_minutes > 0 else 0
        block_list.append(blk)

    # Note: in baseline, departments work SEQUENTIALLY (no bundling)
    # so a window with Engineering (120) + Signal (60) uses 180 min of capacity.

    unscheduled = [t["task_id"] for t in tasks if t["task_id"] not in scheduled]
    critical_done = sum(
        1 for t in tasks
        if t["task_id"] in scheduled and t["priority_level"] == "CRITICAL"
    )
    total_block_hours = sum(b["duration_minutes"] for b in block_list) / 60.0

    stats = {
        "total_blocks": len(block_list),
        "total_block_hours": round(total_block_hours, 1),
        "tasks_completed": len(scheduled),
        "tasks_deferred": len(unscheduled),
        "critical_completed": critical_done,
        "bundled_tasks": 0,  # baseline never bundles
        "multi_dept_blocks": sum(
            1 for b in block_list if len(b["departments"]) > 1
        ),
        "avg_utilization": round(
            sum(b["utilization"] for b in block_list) / max(len(block_list), 1), 1
        ),
    }

    return {
        "status": "BASELINE",
        "blocks": block_list,
        "scheduled_tasks": sorted(scheduled),
        "unscheduled_tasks": unscheduled,
        "stats": stats,
    }
