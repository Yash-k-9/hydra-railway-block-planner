import csv
import os
import json
import random
from typing import List, Dict, Any

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "hyderabad")

def get_hyderabad_paths():
    return {
        "assets": os.path.join(DATA_DIR, "assets", "synthetic_assets.csv"),
        "segments": os.path.join(DATA_DIR, "corridors", "hydra_segments.csv"),
        "network": os.path.join(DATA_DIR, "network", "network_graph.geojson"),
        "stations": os.path.join(DATA_DIR, "network", "stations_mapped.csv"),
    }

def load_hyderabad_segments() -> Dict[str, Any]:
    """Loads segments mapping segment_id -> {edge_id, start_km, end_km}"""
    paths = get_hyderabad_paths()
    segments = {}
    if not os.path.exists(paths["segments"]):
        return segments
    
    with open(paths["segments"], "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            segments[row["segment_id"]] = {
                "corridor_id": row["corridor_id"],
                "edge_id": row["edge_id"],
                "start_km": float(row.get("cumulative_start_km", 0.0)),
                "end_km": float(row.get("cumulative_end_km", 0.0)),
                "length_km": float(row.get("length_km", 0.0))
            }
    return segments

def load_hyderabad_tasks() -> List[Dict[str, Any]]:
    """Converts synthetic assets to HYDRA tasks"""
    paths = get_hyderabad_paths()
    tasks = []
    
    if not os.path.exists(paths["assets"]):
        return tasks

    segments = load_hyderabad_segments()

    skipped_count = 0
    with open(paths["assets"], "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            seg_id = row.get("segment_id", "")
            if not seg_id or seg_id not in segments:
                skipped_count += 1
                continue
                
            seg_info = segments[seg_id]
            
            asset_type = row.get("asset_type", "TRACK").upper()
            dept = "ENGINEERING"
            if asset_type == "OHE":
                dept = "TRACTION"
            elif asset_type in ["SIGNAL", "SIGNALS"]:
                dept = "SIGNALLING"
                
            base_km = seg_info.get("start_km", 0.0)
            loc_km = base_km + float(row.get("position_km_on_segment", 0.0))
            
            condition = int(row.get("condition_score", 100))
            severity = 5 if condition < 50 else (3 if condition < 80 else 1)

            tasks.append({
                "task_id": f"HYD-TSK-{idx:04d}",
                "source_system": "HYDERABAD",
                "asset_id": row.get("asset_id", ""),
                "segment_id": seg_id,
                "corridor_id": seg_info.get("corridor_id", row.get("corridor_id", "")),
                "location_km": loc_km,
                "defect_type": f"Maintenance for {asset_type}",
                "severity": severity,
                "duration_minutes": 120, # Fixed for simulation
                "overdue_days": 5 if condition < 60 else 0,
                "asset_criticality": 3,
                "safety_impact": 3,
                "due_date": "2026-09-10",
                "department": dept
            })
            
    print(f"Hyderabad tasks loaded: {len(tasks)}, Skipped assets: {skipped_count}")
    return tasks

def load_hyderabad_trains() -> List[Dict[str, Any]]:
    """Generate some synthetic trains for Hyderabad corridors so the optimizer has conflicts to resolve."""
    # We will just generate a few regular trains on HYD-C01, HYD-C02, HYD-C03
    trains = []
    corridors = ["HYD-C01", "HYD-C02", "HYD-C03"]
    dates = [f"2026-09-{d:02d}" for d in range(7, 14)] # 2026-09-07 to 2026-09-13
    times = [("06:00", "08:00"), ("10:00", "12:00"), ("14:00", "16:00"), ("18:00", "20:00")]
    idx = 1
    for date_str in dates:
        for c in corridors:
            for st, et in times:
                trains.append({
                    "train_id": f"HYD-EXP-{idx:03d}",
                    "train_type": "EXPRESS",
                    "corridor_id": c,
                    "date": date_str,
                    "start_time": st,
                    "end_time": et,
                    "is_confirmed": True
                })
                idx += 1
    return trains

def get_hyderabad_map_data() -> Dict[str, Any]:
    """Returns the GeoJSON components for the frontend map."""
    paths = get_hyderabad_paths()
    
    # Load network graph
    network = {"type": "FeatureCollection", "features": []}
    if os.path.exists(paths["network"]):
        with open(paths["network"], "r", encoding="utf-8") as f:
            network = json.load(f)
            
    segments_mapping = load_hyderabad_segments()
    
    stations = []
    if os.path.exists(paths["stations"]):
        with open(paths["stations"], "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            stations = list(reader)
            
    return {
        "network": network,
        "segments": segments_mapping,
        "stations": stations
    }
