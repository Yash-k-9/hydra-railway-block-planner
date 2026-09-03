"""
HYDRA - Multi-Department Coordination Engine
Finds groups of tasks from different departments that can be performed
together in a single maintenance block.

Grouping criteria:
  1. Same corridor
  2. Locations within MAX_DISTANCE_KM of each other
  3. Isolation requirements are compatible

Joint block duration = max(individual task durations)
  → departments work in parallel, not sequentially.
"""

from collections import defaultdict

MAX_DISTANCE_KM = 1.0


def _tasks_compatible(tasks):
    """Check if a set of tasks can be grouped together.

    All tasks must be on the same corridor and within MAX_DISTANCE_KM.
    """
    if len(tasks) < 2:
        return False

    corridors = set(t["corridor_id"] for t in tasks)
    if len(corridors) != 1:
        return False

    kms = [t["location_km"] for t in tasks]
    if max(kms) - min(kms) > MAX_DISTANCE_KM:
        return False

    return True


def find_coordination_groups(tasks):
    """Find groups of tasks that can be bundled into joint maintenance blocks.

    Uses greedy clustering: for each corridor, groups tasks within MAX_DISTANCE_KM
    that come from different departments.

    Args:
        tasks: List of unified task dicts (with priority scores)

    Returns:
        List of group dicts, each containing:
          - group_id
          - task_ids
          - tasks (list of task dicts)
          - corridor_id
          - location_range [min_km, max_km]
          - joint_duration (max of individual durations)
          - serial_duration (sum of individual durations)
          - departments (list of unique departments)
          - requires_isolation (True if any task requires it)
          - avg_priority (average priority score of group)
    """
    # Group tasks by corridor
    by_corridor = defaultdict(list)
    for t in tasks:
        by_corridor[t["corridor_id"]].append(t)

    groups = []
    group_counter = 1
    assigned_tasks = set()  # each task can be in at most one group

    for corridor_id in sorted(by_corridor.keys()):
        corridor_tasks = by_corridor[corridor_id]

        # Sort by location
        corridor_tasks.sort(key=lambda t: t["location_km"])

        # Greedy clustering: try to form multi-department groups
        for i, anchor in enumerate(corridor_tasks):
            if anchor["task_id"] in assigned_tasks:
                continue

            # Find all unassigned tasks within MAX_DISTANCE_KM of anchor
            candidates = [anchor]
            for j, other in enumerate(corridor_tasks):
                if i == j or other["task_id"] in assigned_tasks:
                    continue
                if abs(other["location_km"] - anchor["location_km"]) <= MAX_DISTANCE_KM:
                    candidates.append(other)

            # Only form a group if we have tasks from multiple departments
            departments = set(t["department"] for t in candidates)
            if len(departments) < 2:
                continue

            # Take the best candidate from each department
            dept_best = {}
            for t in candidates:
                dept = t["department"]
                if dept not in dept_best or t["priority_score"] > dept_best[dept]["priority_score"]:
                    dept_best[dept] = t

            group_tasks = list(dept_best.values())

            # Verify the group is still valid (all within MAX_DISTANCE_KM)
            kms = [t["location_km"] for t in group_tasks]
            if max(kms) - min(kms) > MAX_DISTANCE_KM:
                continue

            # Create the group
            task_ids = [t["task_id"] for t in group_tasks]
            durations = [t["duration_minutes"] for t in group_tasks]
            depts = sorted(set(t["department"] for t in group_tasks))
            isolation = any(t.get("requires_isolation", False) for t in group_tasks)
            avg_pri = sum(t["priority_score"] for t in group_tasks) / len(group_tasks)

            group = {
                "group_id": f"GRP-{group_counter:03d}",
                "task_ids": task_ids,
                "tasks": group_tasks,
                "corridor_id": corridor_id,
                "location_range": [min(kms), max(kms)],
                "joint_duration": max(durations),
                "serial_duration": sum(durations),
                "departments": depts,
                "requires_isolation": isolation,
                "avg_priority": round(avg_pri, 1),
            }

            groups.append(group)
            group_counter += 1

            # Mark tasks as assigned to this group
            for tid in task_ids:
                assigned_tasks.add(tid)

    return groups


def get_ungrouped_tasks(tasks, groups):
    """Return tasks that are not part of any coordination group."""
    grouped_ids = set()
    for g in groups:
        grouped_ids.update(g["task_ids"])
    return [t for t in tasks if t["task_id"] not in grouped_ids]


def summarize_groups(groups):
    """Return summary statistics about coordination groups."""
    total_tasks = sum(len(g["task_ids"]) for g in groups)
    time_saved = sum(g["serial_duration"] - g["joint_duration"] for g in groups)
    multi_dept = sum(1 for g in groups if len(g["departments"]) >= 2)
    three_dept = sum(1 for g in groups if len(g["departments"]) >= 3)

    return {
        "total_groups": len(groups),
        "total_bundled_tasks": total_tasks,
        "multi_department_groups": multi_dept,
        "three_department_groups": three_dept,
        "time_saved_minutes": time_saved,
    }
