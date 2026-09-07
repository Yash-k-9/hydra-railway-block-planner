"""
HYDRA - FastAPI Backend
Railway Maintenance Block Planning API
"""

import sys
import os
import copy
import json
from datetime import datetime

# Ensure backend/ is on the import path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

import database
from generate_data import generate_all
from services.data_loader import load_tms, load_smms, load_tdms, load_coa
from services.normalizer import normalize_all
from services.priority import calculate_all_priorities
from services.block_windows import find_all_windows
from services.coordination import find_coordination_groups, summarize_groups, get_ungrouped_tasks
from services.optimizer import optimize, validate_schedule
from services.baseline import schedule_baseline
from services.simulation import (
    inject_train_delay, inject_new_defect, find_affected_blocks,
    create_simulation_snapshot,
)
from services.hyderabad_adapter import load_hyderabad_tasks, load_hyderabad_trains, get_hyderabad_map_data, load_hyderabad_segments
from services.station_enrichment import enrich_block_stations


DATA_DIR = os.path.join(PROJECT_DIR, "data")

app = FastAPI(title="HYDRA", description="Intelligent Railway Maintenance Block Planner")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory state ───────────────────────────────────────────────────────
# For a prototype, we hold the current pipeline results in memory.
state = {
    "tasks": [],
    "trains": [],
    "windows": [],
    "groups": [],
    "baseline": None,
    "optimized": None,
    "validation": None,
    "priority_summary": {},
    "group_summary": {},
    "simulation_snapshot": None,
    "simulation_result": None,
    "dataset": "default",
}


# ── Pydantic models ──────────────────────────────────────────────────────

class DefectInput(BaseModel):
    department: str = "ENGINEERING"
    corridor_id: str = "C124"
    location_km: float = 124.8
    duration_minutes: int = 90
    severity: int = 5
    criticality: int = 5
    safety_impact: int = 5
    defect_type: str = "Emergency track defect"
    due_date: str = "2026-09-07"
    requires_isolation: bool = False

class TrainDelayInput(BaseModel):
    train_id: str = "EXP-101"
    delay_minutes: int = 30

class BlockApproval(BaseModel):
    block_id: str
    action: str  # "approve" or "reject"


# ── Health ────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "HYDRA", "timestamp": datetime.now().isoformat()}


# ── Data Generation & Loading ─────────────────────────────────────────────

@app.post("/api/data/generate")
def generate_data():
    """Generate synthetic demo data (CSVs)."""
    result = generate_all()
    return {
        "tms": len(result["tms"]),
        "smms": len(result["smms"]),
        "tdms": len(result["tdms"]),
        "coa": len(result["coa"]),
        "message": "Demo data generated",
    }


@app.post("/api/data/load")
def load_data(dataset: str = "default"):
    """Load CSVs, normalize, and store in SQLite. Also loads trains."""
    state["dataset"] = dataset
    if dataset == "hyderabad":
        tasks = load_hyderabad_tasks()
        trains = load_hyderabad_trains()
        state["tasks"] = tasks
        state["trains"] = trains
        counts = {"TMS": len(tasks), "SMMS": 0, "TDMS": 0, "total": len(tasks)}
    else:
        try:
            tms_raw = load_tms(os.path.join(DATA_DIR, "tms.csv"))
            smms_raw = load_smms(os.path.join(DATA_DIR, "smms.csv"))
            tdms_raw = load_tdms(os.path.join(DATA_DIR, "tdms.csv"))
            coa_raw = load_coa(os.path.join(DATA_DIR, "coa.csv"))
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        tasks, counts = normalize_all(tms_raw, smms_raw, tdms_raw)
        trains = coa_raw

    conn = database.reset_db()
    database.insert_tasks(conn, tasks)
    database.insert_trains(conn, trains)
    database.insert_default_resources(conn)
    conn.close()

    state["tasks"] = tasks
    state["trains"] = trains

    return {
        "tms_loaded": counts.get("TMS", 0),
        "smms_loaded": counts.get("SMMS", 0),
        "tdms_loaded": counts.get("TDMS", 0),
        "total_tasks": counts.get("total", 0),
        "train_movements": len(trains),
    }

@app.get("/api/hyderabad/map")
def get_hyderabad_map():
    """Return static geojson layers for the hyderabad map."""
    return get_hyderabad_map_data()



# ── Priority ──────────────────────────────────────────────────────────────

@app.post("/api/priority/calculate")
def calculate_priorities():
    """Calculate priority scores for all loaded tasks."""
    if not state["tasks"]:
        raise HTTPException(status_code=400, detail="No tasks loaded. Call /api/data/load first.")

    tasks, summary = calculate_all_priorities(state["tasks"], state["trains"])
    state["tasks"] = tasks
    state["priority_summary"] = summary

    # Update DB
    conn = database.get_connection()
    for t in tasks:
        conn.execute(
            "UPDATE maintenance_tasks SET priority_score=?, priority_level=?, urgency=?, train_impact=? WHERE task_id=?",
            (t["priority_score"], t["priority_level"], t["urgency"], t["train_impact"], t["task_id"])
        )
    conn.commit()
    conn.close()

    return {"priority_summary": summary, "total_tasks": len(tasks)}


@app.get("/api/tasks")
def get_tasks():
    """Return all maintenance tasks."""
    return {"tasks": state["tasks"], "total": len(state["tasks"])}


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str):
    """Return a single task by ID."""
    for t in state["tasks"]:
        if t["task_id"] == task_id:
            return t
    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")


# ── Coordination ──────────────────────────────────────────────────────────

@app.get("/api/coordination/groups")
def get_coordination_groups():
    """Find and return multi-department coordination groups."""
    if not state["tasks"]:
        raise HTTPException(status_code=400, detail="No tasks loaded.")

    groups = find_coordination_groups(state["tasks"])
    summary = summarize_groups(groups)
    state["groups"] = groups
    state["group_summary"] = summary

    # Serialize groups (remove task objects for JSON, keep IDs)
    serializable = []
    for g in groups:
        sg = dict(g)
        sg["tasks"] = [
            {"task_id": t["task_id"], "department": t["department"],
             "location_km": t["location_km"], "duration_minutes": t["duration_minutes"],
             "priority_score": t["priority_score"]}
            for t in g["tasks"]
        ]
        serializable.append(sg)

    return {"groups": serializable, "summary": summary}


# ── Block Windows ─────────────────────────────────────────────────────────

@app.get("/api/block-windows")
def get_block_windows():
    """Find available maintenance windows."""
    if not state["trains"]:
        raise HTTPException(status_code=400, detail="No train data loaded.")

    windows = find_all_windows(state["trains"])
    state["windows"] = windows
    return {"windows": windows, "total": len(windows)}


# ── Optimization ──────────────────────────────────────────────────────────

@app.post("/api/optimize")
def run_optimization():
    """Run OR-Tools optimization."""
    if not state["tasks"]:
        raise HTTPException(status_code=400, detail="No tasks loaded.")

    # Ensure dependencies are computed
    if not state["windows"]:
        state["windows"] = find_all_windows(state["trains"])
    if not state["groups"]:
        state["groups"] = find_coordination_groups(state["tasks"])

    result = optimize(state["tasks"], state["groups"], state["windows"])
    validation = validate_schedule(result, state["trains"])

    state["optimized"] = result
    state["validation"] = validation

    return {
        "status": result["status"],
        "stats": result["stats"],
        "blocks": result["blocks"],
        "unscheduled_tasks": result["unscheduled_tasks"],
        "objective_value": result["objective_value"],
        "optimization_time": result["optimization_time"],
        "validation": validation,
    }


@app.post("/api/baseline")
def run_baseline():
    """Run baseline (decentralized) scheduler."""
    if not state["tasks"]:
        raise HTTPException(status_code=400, detail="No tasks loaded.")
    if not state["windows"]:
        state["windows"] = find_all_windows(state["trains"])

    result = schedule_baseline(state["tasks"], state["windows"])
    state["baseline"] = result

    return {
        "stats": result["stats"],
        "blocks": result["blocks"],
    }


# ── Weekly Plan ───────────────────────────────────────────────────────────

@app.get("/api/plans/weekly")
def get_weekly_plan():
    """Return the optimized plan organized by day of the week."""
    if not state["optimized"]:
        raise HTTPException(status_code=400, detail="No optimized plan. Run /api/optimize first.")

    blocks = copy.deepcopy(state["optimized"]["blocks"])

    if state.get("dataset") == "hyderabad":
        segments = load_hyderabad_segments()
        map_data = get_hyderabad_map_data()
        edges_features = {
            f["properties"].get("edge_id"): f 
            for f in map_data["network"].get("features", []) 
            if f["geometry"]["type"] == "LineString"
        }

        for b in blocks:
            block_edge_ids = set()
            for t in b.get("tasks", []):
                seg_id = t.get("segment_id")
                if seg_id and seg_id in segments:
                    block_edge_ids.add(segments[seg_id]["edge_id"])
            
            coords = []
            for eid in block_edge_ids:
                if eid in edges_features:
                    coords.append(edges_features[eid]["geometry"]["coordinates"])
                    
            if coords:
                b["geometry"] = {
                    "type": "MultiLineString",
                    "coordinates": coords
                }
            
            enrichment_result = enrich_block_stations(b, map_data["network"], map_data.get("stations", []), segments)
            b["affected_stations"] = enrichment_result["affected_stations"]
            b["boundary_stations"] = enrichment_result["boundary_stations"]

    # Organize by date
    by_date = {}
    for b in blocks:
        d = b["date"]
        if d not in by_date:
            by_date[d] = []
        by_date[d].append(b)

    # Sort within each day
    for d in by_date:
        by_date[d].sort(key=lambda b: (b["corridor_id"], b["start_time"]))

    return {"weekly_plan": by_date, "total_blocks": len(blocks)}


# ── Analytics ─────────────────────────────────────────────────────────────

@app.get("/api/analytics")
def get_analytics():
    """Return comparison analytics and KPI data."""
    baseline = state.get("baseline", {})
    optimized = state.get("optimized", {})

    baseline_stats = baseline.get("stats", {}) if baseline else {}
    opt_stats = optimized.get("stats", {}) if optimized else {}

    # Calculate overdue remaining
    scheduled_ids = set(optimized.get("scheduled_tasks", [])) if optimized else set()
    overdue_remaining = sum(
        1 for t in state["tasks"]
        if t["task_id"] not in scheduled_ids and t.get("overdue_days", 0) > 0
    )
    total_overdue = sum(1 for t in state["tasks"] if t.get("overdue_days", 0) > 0)

    # Estimated asset availability
    total_planning_minutes = 7 * 16 * 60  # 7 days * 16h operating window * 5 corridors
    total_block_minutes = opt_stats.get("total_block_hours", 0) * 60
    availability = round((1 - total_block_minutes / max(total_planning_minutes, 1)) * 100, 1) if opt_stats else 0

    return {
        "kpi": {
            "total_tasks": len(state["tasks"]),
            "critical_tasks": state["priority_summary"].get("CRITICAL", 0),
            "high_tasks": state["priority_summary"].get("HIGH", 0),
            "overdue_tasks": total_overdue,
            "overdue_remaining": overdue_remaining,
            "scheduled_blocks": opt_stats.get("total_blocks", 0),
            "block_hours": opt_stats.get("total_block_hours", 0),
            "bundled_tasks": opt_stats.get("bundled_tasks", 0),
            "estimated_availability": availability,
        },
        "comparison": {
            "baseline": baseline_stats,
            "optimized": opt_stats,
        },
        "priority_summary": state["priority_summary"],
    }


# ── Block Details ─────────────────────────────────────────────────────────

@app.get("/api/blocks/{block_id}")
def get_block_detail(block_id: str):
    """Return detailed info about a specific block, including explanation."""
    if not state["optimized"]:
        raise HTTPException(status_code=400, detail="No plan available.")

    for block in state["optimized"]["blocks"]:
        if block["block_id"] == block_id:
            # Build explanation
            reasons = []
            reasons.append(f"Same corridor: {block['corridor_id']}")

            kms = [t["location_km"] for t in block["tasks"]]
            if len(kms) > 1:
                span = max(kms) - min(kms)
                reasons.append(f"Tasks within {span:.1f} km (max 1.0 km for bundling)")

            reasons.append("No confirmed train conflict in this window")

            high_pri = [t for t in block["tasks"] if t["priority_level"] in ("CRITICAL", "HIGH")]
            if high_pri:
                reasons.append(f"{len(high_pri)} high-priority task(s) in this block")

            if block["is_multi_department"]:
                depts = " + ".join(block["departments"])
                reasons.append(f"Multi-department bundling: {depts}")
                reasons.append("Teams can work in parallel → reduced block time")

            if block.get("requires_isolation"):
                reasons.append("OHE isolation block – power disconnection required")

            return {
                "block": block,
                "explanation": reasons,
                "utilization_detail": {
                    "block_duration": block["duration_minutes"],
                    "work_duration": max(t["duration_minutes"] for t in block["tasks"]),
                    "utilization_pct": block["utilization"],
                },
            }

    raise HTTPException(status_code=404, detail=f"Block {block_id} not found")


# ── Block Approval ────────────────────────────────────────────────────────

@app.post("/api/blocks/approve")
def approve_block(approval: BlockApproval):
    """Approve or reject a block (prototype workflow)."""
    if not state["optimized"]:
        raise HTTPException(status_code=400, detail="No plan available.")

    for block in state["optimized"]["blocks"]:
        if block["block_id"] == approval.block_id:
            if approval.action == "approve":
                block["status"] = "approved"
            elif approval.action == "reject":
                block["status"] = "rejected"
            else:
                raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")
            return {"block_id": block["block_id"], "status": block["status"]}

    raise HTTPException(status_code=404, detail=f"Block {approval.block_id} not found")


# ── Simulation ────────────────────────────────────────────────────────────

@app.post("/api/simulation/reset")
def reset_simulation():
    """Reset simulation to base state."""
    state["simulation_snapshot"] = None
    state["simulation_result"] = None
    return {"message": "Simulation reset"}


@app.post("/api/simulation/inject")
def inject_simulation_event(
    scenario: str = "train_delay",
    train_id: Optional[str] = None,
    delay_minutes: Optional[int] = None,
    defect: Optional[DefectInput] = None,
):
    """Inject a disruption event for test mode."""
    if not state["optimized"]:
        raise HTTPException(status_code=400, detail="Run optimization first.")

    # Save snapshot of current state
    state["simulation_snapshot"] = create_simulation_snapshot(state["tasks"], state["trains"])

    if scenario == "train_delay":
        tid = train_id or "EXP-101"
        delay = delay_minutes or 30
        sim_trains = copy.deepcopy(state["trains"])
        event = inject_train_delay(sim_trains, tid, delay)

        # Find affected blocks
        affected = find_affected_blocks(
            state["optimized"]["blocks"], sim_trains,
            corridor_id=None
        )

        state["simulation_result"] = {
            "event": event,
            "affected_blocks": [
                {
                    "block_id": a["block"]["block_id"],
                    "corridor_id": a["block"]["corridor_id"],
                    "date": a["block"]["date"],
                    "start_time": a["block"]["start_time"],
                    "end_time": a["block"]["end_time"],
                    "conflicting_trains": [c["train_id"] for c in a["conflicting_trains"]],
                }
                for a in affected
            ],
            "sim_trains": sim_trains,
            "reoptimized": None,
        }

        return {
            "event": event,
            "affected_blocks": len(affected),
            "details": state["simulation_result"]["affected_blocks"],
        }

    elif scenario == "new_defect":
        if not defect:
            defect = DefectInput()

        sim_tasks = copy.deepcopy(state["tasks"])
        new_task = inject_new_defect(sim_tasks, defect.model_dump())

        # Recalculate priority for the new task
        from services.priority import calculate_priority
        calculate_priority(new_task, {})

        state["simulation_result"] = {
            "event": {"event_type": "new_defect", "task": new_task},
            "affected_blocks": [],
            "sim_tasks": sim_tasks,
            "reoptimized": None,
        }

        return {
            "event_type": "new_defect",
            "new_task": new_task,
        }

    raise HTTPException(status_code=400, detail="Unknown scenario. Use 'train_delay' or 'new_defect'.")


@app.post("/api/simulation/reoptimize")
def reoptimize():
    """Re-run optimization after a simulation event."""
    if not state["simulation_result"]:
        raise HTTPException(status_code=400, detail="No simulation event. Inject an event first.")

    sim = state["simulation_result"]

    # Use modified data
    sim_trains = sim.get("sim_trains", state["trains"])
    sim_tasks = sim.get("sim_tasks", state["tasks"])

    # Recalculate windows with modified trains
    new_windows = find_all_windows(sim_trains)

    # Recalculate groups with possibly modified tasks
    new_groups = find_coordination_groups(sim_tasks)

    # Re-optimize
    new_result = optimize(sim_tasks, new_groups, new_windows)
    new_validation = validate_schedule(new_result, sim_trains)

    sim["reoptimized"] = new_result

    # Build comparison
    old_stats = state["optimized"]["stats"]
    new_stats = new_result["stats"]

    return {
        "status": new_result["status"],
        "optimization_time": new_result["optimization_time"],
        "before": old_stats,
        "after": new_stats,
        "new_blocks": new_result["blocks"],
        "validation": new_validation,
        "changes": {
            "blocks_changed": old_stats["total_blocks"] - new_stats["total_blocks"],
            "tasks_rescheduled": abs(old_stats["tasks_completed"] - new_stats["tasks_completed"]),
            "tasks_deferred": new_stats["tasks_deferred"],
        },
    }
