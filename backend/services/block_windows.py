"""
HYDRA - Block Window Generator
Finds available maintenance windows by analyzing gaps between confirmed train movements.

A valid maintenance window:
  - Does not overlap any confirmed train movement
  - Is at least MIN_WINDOW_MINUTES long
  - Falls within the maintenance operating hours (06:00 – 22:00)
"""

MIN_WINDOW_MINUTES = 30
DAY_START = "06:00"
DAY_END = "22:00"


def _time_to_minutes(time_str):
    """Convert HH:MM string to minutes since midnight."""
    parts = time_str.strip().split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _minutes_to_time(minutes):
    """Convert minutes since midnight to HH:MM string."""
    h, m = divmod(int(minutes), 60)
    return f"{h:02d}:{m:02d}"


def find_windows_for_corridor_date(corridor_id, date_str, trains):
    """Find maintenance windows for a specific corridor on a specific date.

    Args:
        corridor_id: Corridor identifier
        date_str: Date string (YYYY-MM-DD)
        trains: List of all train movement dicts

    Returns:
        List of window dicts with: corridor_id, date, start_time, end_time, duration_minutes
    """
    # Filter confirmed trains for this corridor and date
    relevant = [
        t for t in trains
        if t["corridor_id"] == corridor_id
        and t["date"] == date_str
        and t.get("is_confirmed", True)
    ]

    # Sort by start time
    relevant.sort(key=lambda t: _time_to_minutes(t["start_time"]))

    day_start = _time_to_minutes(DAY_START)
    day_end = _time_to_minutes(DAY_END)

    # Collect occupied intervals
    occupied = []
    for t in relevant:
        s = _time_to_minutes(t["start_time"])
        e = _time_to_minutes(t["end_time"])
        occupied.append((s, e))

    # Find gaps
    windows = []
    current = day_start

    for occ_start, occ_end in occupied:
        if occ_start > current:
            gap = occ_start - current
            if gap >= MIN_WINDOW_MINUTES:
                windows.append({
                    "corridor_id": corridor_id,
                    "date": date_str,
                    "start_time": _minutes_to_time(current),
                    "end_time": _minutes_to_time(occ_start),
                    "duration_minutes": gap,
                })
        current = max(current, occ_end)

    # Gap after last train until end of day
    if day_end > current:
        gap = day_end - current
        if gap >= MIN_WINDOW_MINUTES:
            windows.append({
                "corridor_id": corridor_id,
                "date": date_str,
                "start_time": _minutes_to_time(current),
                "end_time": _minutes_to_time(day_end),
                "duration_minutes": gap,
            })

    return windows


def find_all_windows(trains, corridors=None, dates=None):
    """Find maintenance windows across all corridors and dates.

    Args:
        trains: List of all train movement dicts
        corridors: List of corridor IDs (auto-detected if None)
        dates: List of date strings (auto-detected if None)

    Returns:
        List of window dicts, each with a unique window_id
    """
    if corridors is None:
        corridors = sorted(set(t["corridor_id"] for t in trains))
    if dates is None:
        dates = sorted(set(t["date"] for t in trains))

    all_windows = []
    win_counter = 1

    for cid in corridors:
        for d in dates:
            day_windows = find_windows_for_corridor_date(cid, d, trains)
            for w in day_windows:
                w["window_id"] = f"W-{win_counter:03d}"
                all_windows.append(w)
                win_counter += 1

    return all_windows


def check_conflict(block_start, block_end, trains, corridor_id, date_str):
    """Check if a proposed block conflicts with any confirmed train.

    Args:
        block_start: Start time string (HH:MM)
        block_end: End time string (HH:MM)
        trains: List of train movement dicts
        corridor_id: Corridor
        date_str: Date

    Returns:
        List of conflicting train dicts (empty if no conflict)
    """
    bs = _time_to_minutes(block_start)
    be = _time_to_minutes(block_end)

    conflicts = []
    for t in trains:
        if t["corridor_id"] != corridor_id or t["date"] != date_str:
            continue
        if not t.get("is_confirmed", True):
            continue
        ts = _time_to_minutes(t["start_time"])
        te = _time_to_minutes(t["end_time"])
        # Overlaps if not (block ends before train starts OR block starts after train ends)
        if not (be <= ts or bs >= te):
            conflicts.append(t)

    return conflicts
