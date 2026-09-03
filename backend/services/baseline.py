"""
HYDRA - Baseline Scheduler
Simulates decentralized/manual planning where each department schedules independently.
No cross-department bundling. Used as comparison against optimized plan.
"""


def schedule_baseline(tasks, windows):
    """Run baseline (decentralized) scheduling.

    Each department independently assigns its tasks to the earliest
    feasible window on the correct corridor. No bundling.

    Args:
        tasks: list of unified task dicts (with priority_score)
        windows: list of block window dicts

    Returns:
        dict with: blocks, stats (same structure as optimizer output for comparison)
    """
    departments = ["ENGINEERING", "SIGNALLING", "TRACTION"]

    # Track remaining capacity per window
    window_capacity = {w["window_id"]: w["duration_minutes"] for w in windows}
    window_by_id = {w["window_id"]: dict(w) for w in windows}

    blocks = {}         # window_id → block dict
    scheduled = set()

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
                if (w["corridor_id"] == task["corridor_id"]
                    and window_capacity[w["window_id"]] >= task["duration_minutes"])
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

    # Finalize blocks
    block_list = []
    for wid, blk in blocks.items():
        blk["departments"] = sorted(blk["departments"])
        total_work = sum(bt["duration_minutes"] for bt in blk["tasks"])
        blk["utilization"] = round(
            total_work / blk["duration_minutes"] * 100, 1
        ) if blk["duration_minutes"] > 0 else 0
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
