import os
import sys
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from backend.main import app

client = TestClient(app)

def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_generate_and_load():
    res1 = client.post("/api/data/generate")
    assert res1.status_code == 200
    
    res2 = client.post("/api/data/load")
    assert res2.status_code == 200
    assert "total_tasks" in res2.json()
    assert res2.json()["total_tasks"] == 90

def test_priority():
    client.post("/api/data/generate")
    client.post("/api/data/load")
    res = client.post("/api/priority/calculate")
    assert res.status_code == 200
    assert "CRITICAL" in res.json()["priority_summary"]

def test_tasks():
    res = client.get("/api/tasks")
    assert res.status_code == 200
    assert isinstance(res.json()["tasks"], list)

def test_analytics_availability_uses_all_corridors():
    client.post("/api/data/generate")
    client.post("/api/data/load")
    client.post("/api/priority/calculate")
    client.post("/api/optimize")
    kpi = client.get("/api/analytics").json()["kpi"]

    import backend.main as m
    days = len({t["date"] for t in m.state["trains"]})
    corridors = len({t["corridor_id"] for t in m.state["trains"]})
    expected = round((1 - kpi["block_hours"] * 60 / (days * 16 * 60 * corridors)) * 100, 1)
    assert kpi["estimated_availability"] == expected
    assert 0 < kpi["estimated_availability"] < 100

def test_generate_is_repeatable():
    client.post("/api/data/generate")
    with open(os.path.join(BACKEND_DIR, "data", "tms.csv")) as f:
        first = f.read()
    client.post("/api/data/generate")
    with open(os.path.join(BACKEND_DIR, "data", "tms.csv")) as f:
        assert f.read() == first

def test_switching_dataset_then_optimize():
    for dataset in ["default", "hyderabad", "default"]:
        assert client.post(f"/api/data/load?dataset={dataset}").status_code == 200
        client.post("/api/priority/calculate")
        res = client.post("/api/optimize")
        assert res.status_code == 200
        assert res.json()["validation"]["valid"] is True

def _fast_solver(monkeypatch):
    import services.optimizer as opt
    monkeypatch.setattr(opt, "SOLVER_TIME_LIMIT", 6)

def test_approved_blocks_survive_replanning(monkeypatch):
    _fast_solver(monkeypatch)
    client.post("/api/data/generate")
    client.post("/api/data/load")
    client.post("/api/priority/calculate")
    blocks = client.post("/api/optimize").json()["blocks"]
    approved = blocks[0]
    assert client.post("/api/blocks/approve", json={"block_id": approved["block_id"], "action": "approve"}).status_code == 200

    # A new defect forces a re-plan; the approved block must come back unchanged
    client.post("/api/simulation/inject?scenario=new_defect")
    res = client.post("/api/simulation/reoptimize").json()
    assert approved["block_id"] in res["kept_approved_blocks"]
    same = [b for b in res["new_blocks"] if b["block_id"] == approved["block_id"]][0]
    assert (same["start_time"], same["end_time"], same["status"]) == (approved["start_time"], approved["end_time"], "approved")
    assert res["validation"]["valid"] is True

    # Re-running the main optimizer keeps it too
    again = client.post("/api/optimize").json()["blocks"]
    assert any(b["block_id"] == approved["block_id"] and b["status"] == "approved" for b in again)

def test_broken_approved_block_is_released(monkeypatch):
    import backend.main as m
    monkeypatch.setitem(m.state, "optimized", {"blocks": [{
        "block_id": "BLK-X", "corridor_id": "C1", "date": "2026-09-07",
        "start_time": "10:00", "end_time": "11:00", "status": "approved", "tasks": [],
    }]})
    # A delayed train now runs 10:30-10:50, so the only window ends at 10:30
    windows = [{"window_id": "W1", "corridor_id": "C1", "date": "2026-09-07",
                "start_time": "09:00", "end_time": "10:30", "duration_minutes": 90}]
    kept, released = m._approved_blocks(windows)
    assert kept == [] and [b["block_id"] for b in released] == ["BLK-X"]

def test_plan_survives_restart(monkeypatch):
    _fast_solver(monkeypatch)
    import backend.main as m
    client.post("/api/data/load")
    client.post("/api/priority/calculate")
    plan = client.post("/api/optimize").json()

    # Simulate a restart: wipe memory, restore from SQLite
    for key in ("tasks", "trains", "optimized", "validation"):
        m.state[key] = [] if key in ("tasks", "trains") else None
    m._restore_state()
    assert [b["block_id"] for b in m.state["optimized"]["blocks"]] == [b["block_id"] for b in plan["blocks"]]
    assert client.get("/api/plans/weekly").status_code == 200

    # The plan is also stored as rows in the blocks table
    import database
    conn = database.get_connection()
    rows = conn.execute("SELECT COUNT(*) FROM blocks WHERE plan_type='optimized'").fetchone()[0]
    conn.close()
    assert rows == len(plan["blocks"])

def test_train_delay_repairs_only_broken_blocks(monkeypatch):
    _fast_solver(monkeypatch)
    client.post("/api/data/load")
    client.post("/api/priority/calculate")
    before = client.post("/api/optimize").json()
    client.post("/api/simulation/reset")
    client.post("/api/simulation/inject?scenario=train_delay&train_id=EXP-101&delay_minutes=45")
    res = client.post("/api/simulation/reoptimize").json()

    assert res["mode"] == "repair"
    assert res["validation"]["valid"] is True
    # Only tasks from blocks the delay broke are moved
    broken = {b["block_id"] for b in before["blocks"]} & set(res["broken_blocks"])
    moved_tasks = sum(len(b["tasks"]) for b in before["blocks"] if b["block_id"] in broken)
    assert res["after"]["tasks_moved"] == moved_tasks
    untouched = [b for b in before["blocks"] if b["block_id"] not in broken]
    new_by_id = {b["block_id"]: b for b in res["new_blocks"]}
    for b in untouched:
        assert (new_by_id[b["block_id"]]["start_time"], new_by_id[b["block_id"]]["end_time"]) == (b["start_time"], b["end_time"])
