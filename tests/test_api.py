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
