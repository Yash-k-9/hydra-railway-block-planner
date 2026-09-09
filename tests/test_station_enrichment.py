import pytest
from backend.services.station_enrichment import enrich_block_stations

def test_enrich_block_stations_corridor_constrained():
    # Mock data
    network = {
        "features": [
            # Edge touching a station (C1)
            {
                "geometry": {"type": "LineString"},
                "properties": {"edge_id": "E1", "u": "GN-0001", "v": "GN-0002"}
            },
            # Edges between anonymous junctions (C1)
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
            # Edge branching out to a station, but belongs to another corridor (C2)
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
        "SEG1": {"edge_id": "E1", "corridor_id": "C1"},
        "SEG2": {"edge_id": "E2", "corridor_id": "C1"},
        "SEG3": {"edge_id": "E3", "corridor_id": "C1"},
        "SEG4": {"edge_id": "E4", "corridor_id": "C1"},
        "SEG5": {"edge_id": "E5", "corridor_id": "C2"},
    }

    # Scenario 1: Block whose edge directly touches a station.
    # Block nodes: GN-0001, GN-0002. C1.
    block1 = {"tasks": [{"segment_id": "SEG1"}]}
    res1 = enrich_block_stations(block1, network, stations, segments)
    assert len(res1["affected_stations"]) == 1
    assert res1["affected_stations"][0]["node_id"] == "S1"
    
    # BFS outward from GN-0002 to GN-0003, then GN-0004(Station 4).
    # GN-0006 is reached via E5, which is C2. So BFS should NOT reach S6.
    b_ids1 = {s["node_id"] for s in res1["boundary_stations"]}
    assert b_ids1 == {"S4"}

    # Scenario 2 & 3: Block whose edges do not directly touch a station, with multiple segments
    # SEG2 connects GN-0002 and GN-0003. C1.
    block2 = {"tasks": [{"segment_id": "SEG2"}]}
    res2 = enrich_block_stations(block2, network, stations, segments)
    assert len(res2["affected_stations"]) == 0
    # Outer nodes are GN-0002 and GN-0003.
    # GN-0002 neighbors GN-0001 (Station 1) via E1 (C1).
    # GN-0003 neighbors GN-0004 (Station 4) via E3 (C1).
    # GN-0006 via E5 (C2) is ignored.
    b_ids2 = {s["node_id"] for s in res2["boundary_stations"]}
    assert b_ids2 == {"S1", "S4"}

    # Scenario 4 & 5: Duplicate station reached through multiple edges / graph branch
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
    segments_cycle = {**segments, 
        "SEG6": {"edge_id": "E6", "corridor_id": "C1"},
        "SEG7": {"edge_id": "E7", "corridor_id": "C1"}
    }
    block3 = {"tasks": [{"segment_id": "SEG2"}]}
    res3 = enrich_block_stations(block3, network_cycle, stations, segments_cycle)
    # GN-0003 hits S4.
    # GN-0002 hits S1 directly, and hits GN-0007, which hits GN-0004 (S4). S4 should not be duplicated.
    b_ids3 = [s["node_id"] for s in res3["boundary_stations"]]
    assert len(b_ids3) == len(set(b_ids3)) # No duplicates
    assert set(b_ids3) == {"S1", "S4"}


def test_regression_blk_w_001():
    # BLK-W-001 returned 7 stations because GN-0007 branched into another corridor.
    network = {
        "features": [
            # Block edges
            {"geometry": {"type": "LineString"}, "properties": {"edge_id": "E_W1_1", "u": "GN-0096", "v": "GN-0159"}},
            {"geometry": {"type": "LineString"}, "properties": {"edge_id": "E_W1_2", "u": "GN-0159", "v": "GN-0007"}},
            # Path to Secunderabad Junction (C01)
            {"geometry": {"type": "LineString"}, "properties": {"edge_id": "E_W1_3", "u": "GN-0096", "v": "GN-0095"}},
            # Path to Ammuguda (C01)
            {"geometry": {"type": "LineString"}, "properties": {"edge_id": "E_W1_4", "u": "GN-0159", "v": "GN-0092"}},
            # Path from GN-0007 branching to another corridor (C99)
            {"geometry": {"type": "LineString"}, "properties": {"edge_id": "E_W1_X", "u": "GN-0007", "v": "GN-0015"}},
        ]
    }
    stations = [
        {"node_id": "SEC", "graph_node": "95", "name": "Secunderabad Junction"},
        {"node_id": "AMM", "graph_node": "92", "name": "Ammuguda"},
        {"node_id": "CHA", "graph_node": "15", "name": "Charlapalli"},
    ]
    segments = {
        "SEG_W1_1": {"edge_id": "E_W1_1", "corridor_id": "HYD-C01"},
        "SEG_W1_2": {"edge_id": "E_W1_2", "corridor_id": "HYD-C01"},
        "SEG_W1_3": {"edge_id": "E_W1_3", "corridor_id": "HYD-C01"},
        "SEG_W1_4": {"edge_id": "E_W1_4", "corridor_id": "HYD-C01"},
        "SEG_W1_X": {"edge_id": "E_W1_X", "corridor_id": "HYD-C99"},
    }
    block = {"tasks": [{"segment_id": "SEG_W1_1"}, {"segment_id": "SEG_W1_2"}]}
    
    res = enrich_block_stations(block, network, stations, segments)
    
    assert len(res["affected_stations"]) == 0
    b_names = {s["name"] for s in res["boundary_stations"]}
    # Should only return stations on HYD-C01
    assert b_names == {"Secunderabad Junction", "Ammuguda"}
    assert "Charlapalli" not in b_names


def test_regression_blk_w_002():
    # BLK-W-002 returned Bolarum Bazaar through a bypass not on the corridor.
    network = {
        "features": [
            # Block edges
            {"geometry": {"type": "LineString"}, "properties": {"edge_id": "E_W2_1", "u": "GN-0230", "v": "GN-0066"}},
            # Path to Bolarum along C01
            {"geometry": {"type": "LineString"}, "properties": {"edge_id": "E_W2_2", "u": "GN-0066", "v": "GN-0097"}},
            {"geometry": {"type": "LineString"}, "properties": {"edge_id": "E_W2_3", "u": "GN-0097", "v": "GN-0221"}},
            {"geometry": {"type": "LineString"}, "properties": {"edge_id": "E_W2_4", "u": "GN-0221", "v": "GN-0202"}}, # Bolarum
            # Bypass path (C99)
            {"geometry": {"type": "LineString"}, "properties": {"edge_id": "E_W2_5", "u": "GN-0097", "v": "GN-0135"}},
            {"geometry": {"type": "LineString"}, "properties": {"edge_id": "E_W2_6", "u": "GN-0135", "v": "GN-0044"}}, # Bolarum Bazaar
        ]
    }
    stations = [
        {"node_id": "GP", "graph_node": "230", "name": "Gundla Pochampally"},
        {"node_id": "GV", "graph_node": "66", "name": "Gowdavalli"},
        {"node_id": "BOL", "graph_node": "202", "name": "Bolarum"},
        {"node_id": "BB", "graph_node": "44", "name": "Bolarum Bazaar"},
    ]
    segments = {
        "SEG_W2_1": {"edge_id": "E_W2_1", "corridor_id": "HYD-C01"},
        "SEG_W2_2": {"edge_id": "E_W2_2", "corridor_id": "HYD-C01"},
        "SEG_W2_3": {"edge_id": "E_W2_3", "corridor_id": "HYD-C01"},
        "SEG_W2_4": {"edge_id": "E_W2_4", "corridor_id": "HYD-C01"},
        "SEG_W2_5": {"edge_id": "E_W2_5", "corridor_id": "HYD-C99"},
        "SEG_W2_6": {"edge_id": "E_W2_6", "corridor_id": "HYD-C99"},
    }
    block = {"tasks": [{"segment_id": "SEG_W2_1"}]}
    
    res = enrich_block_stations(block, network, stations, segments)
    
    a_names = {s["name"] for s in res["affected_stations"]}
    assert a_names == {"Gundla Pochampally", "Gowdavalli"}
    
    b_names = {s["name"] for s in res["boundary_stations"]}
    assert b_names == {"Bolarum"}
    assert "Bolarum Bazaar" not in b_names
