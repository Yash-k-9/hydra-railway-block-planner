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
