import pytest
from backend.services.station_enrichment import enrich_block_stations

def test_enrich_block_stations():
    # Mock data
    network = {
        "features": [
            # Edge touching a station
            {
                "geometry": {"type": "LineString"},
                "properties": {"edge_id": "E1", "u": "GN-0001", "v": "GN-0002"}
            },
            # Edges between anonymous junctions
            {
                "geometry": {"type": "LineString"},
                "properties": {"edge_id": "E2", "u": "GN-0002", "v": "GN-0003"}
            },
            {
                "geometry": {"type": "LineString"},
                "properties": {"edge_id": "E3", "u": "GN-0003", "v": "GN-0004"}
            },
            {
                "geometry": {"type": "LineString"},
                "properties": {"edge_id": "E4", "u": "GN-0004", "v": "GN-0005"}
            },
            # Edge branching out to a station
            {
                "geometry": {"type": "LineString"},
                "properties": {"edge_id": "E5", "u": "GN-0003", "v": "GN-0006"}
            },
        ]
    }

    stations = [
        {"node_id": "S1", "graph_node": "1", "name": "Station 1"},
        {"node_id": "S4", "graph_node": "4", "name": "Station 4"},
        {"node_id": "S6", "graph_node": "6", "name": "Station 6"},
    ]

    segments = {
        "SEG1": {"edge_id": "E1"},
        "SEG2": {"edge_id": "E2"},
        "SEG3": {"edge_id": "E3"},
        "SEG4": {"edge_id": "E4"},
        "SEG5": {"edge_id": "E5"},
    }

    # Scenario 1: Block whose edge directly touches a station.
    # Block nodes: GN-0001, GN-0002
    block1 = {"tasks": [{"segment_id": "SEG1"}]}
    res1 = enrich_block_stations(block1, network, stations, segments)
    assert len(res1["affected_stations"]) == 1
    assert res1["affected_stations"][0]["node_id"] == "S1"
    # BFS outward from GN-0002 to GN-0003, then GN-0004(Station 4) and GN-0006(Station 6)
    # Wait, GN-0001 is already a station, GN-0002 goes to GN-0003. GN-0003 goes to 4 and 6. Both are stations.
    b_ids1 = {s["node_id"] for s in res1["boundary_stations"]}
    assert b_ids1 == {"S4", "S6"}

    # Scenario 2 & 3: Block whose edges do not directly touch a station, with multiple segments
    # SEG2 connects GN-0002 and GN-0003. Neither are stations.
    block2 = {"tasks": [{"segment_id": "SEG2"}]}
    res2 = enrich_block_stations(block2, network, stations, segments)
    assert len(res2["affected_stations"]) == 0
    # Outer nodes are GN-0002 and GN-0003.
    # GN-0002 neighbors GN-0001 (Station 1).
    # GN-0003 neighbors GN-0004 (Station 4) and GN-0006 (Station 6).
    b_ids2 = {s["node_id"] for s in res2["boundary_stations"]}
    assert b_ids2 == {"S1", "S4", "S6"}

    # Scenario 4 & 5: Duplicate station reached through multiple edges / graph branch
    # Let's create a cycle to reach S4 from two paths
    network_cycle = {
        "features": network["features"] + [
            {
                "geometry": {"type": "LineString"},
                "properties": {"edge_id": "E6", "u": "GN-0002", "v": "GN-0007"}
            },
            {
                "geometry": {"type": "LineString"},
                "properties": {"edge_id": "E7", "u": "GN-0007", "v": "GN-0004"}
            }
        ]
    }
    block3 = {"tasks": [{"segment_id": "SEG2"}]}
    res3 = enrich_block_stations(block3, network_cycle, stations, segments)
    # Outer nodes GN-0002 and GN-0003.
    # GN-0003 hits S4 and S6.
    # GN-0002 hits S1 directly, and hits GN-0007, which hits GN-0004 (S4). S4 should not be duplicated.
    b_ids3 = [s["node_id"] for s in res3["boundary_stations"]]
    assert len(b_ids3) == len(set(b_ids3)) # No duplicates
    assert set(b_ids3) == {"S1", "S4", "S6"}

