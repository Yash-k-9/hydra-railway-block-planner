from typing import Dict, List, Any, Set
from collections import deque

def enrich_block_stations(
    block: Dict[str, Any],
    network: Dict[str, Any],
    stations: List[Dict[str, Any]],
    segments: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Enrich a block with affected_stations and boundary_stations based on the network topology.
    """
    # 1. Build adjacency list for the entire network graph
    graph: Dict[str, Set[str]] = {}
    edge_id_to_nodes: Dict[str, tuple] = {}
    
    for feature in network.get("features", []):
        if feature.get("geometry", {}).get("type") == "LineString":
            props = feature.get("properties", {})
            u = props.get("u")
            v = props.get("v")
            edge_id = props.get("edge_id")
            
            if u and v:
                if u not in graph:
                    graph[u] = set()
                if v not in graph:
                    graph[v] = set()
                graph[u].add(v)
                graph[v].add(u)
                
                if edge_id:
                    edge_id_to_nodes[edge_id] = (u, v)

    # 2. Build station lookup by network node id
    station_lookup: Dict[str, Dict[str, Any]] = {}
    for station in stations:
        g_node = station.get("graph_node")
        if g_node:
            try:
                # Normalizing "95" to "GN-0095"
                node_id = f"GN-{str(g_node).zfill(4)}"
                station_lookup[node_id] = station
            except Exception:
                pass

    # 3. Identify edges belonging to the block
    block_edge_ids = set()
    for t in block.get("tasks", []):
        seg_id = t.get("segment_id")
        if seg_id and seg_id in segments:
            block_edge_ids.add(segments[seg_id]["edge_id"])

    # 4. Identify block nodes
    block_nodes = set()
    for edge_id in block_edge_ids:
        if edge_id in edge_id_to_nodes:
            u, v = edge_id_to_nodes[edge_id]
            block_nodes.add(u)
            block_nodes.add(v)

    # 5. Find directly affected stations
    affected_stations = []
    affected_station_ids = set()
    for node in block_nodes:
        if node in station_lookup:
            station = station_lookup[node]
            s_id = station.get("node_id")
            if s_id not in affected_station_ids:
                affected_stations.append(station)
                affected_station_ids.add(s_id)

    # 6. Identify "outer" block nodes and queue for BFS
    # An outer node is a block node that has at least one neighbor in the graph NOT in block_nodes
    queue = deque()
    visited = set(block_nodes)
    
    for node in block_nodes:
        if node in graph:
            for neighbor in graph[node]:
                if neighbor not in block_nodes:
                    # 'node' is an outer block node, 'neighbor' is the first step outward
                    visited.add(neighbor)
                    queue.append(neighbor)

    # 7. Traverse outward for boundary stations
    boundary_stations = []
    boundary_station_ids = set()
    
    while queue:
        curr_node = queue.popleft()
        
        if curr_node in station_lookup:
            # We hit a station!
            station = station_lookup[curr_node]
            s_id = station.get("node_id")
            if s_id not in boundary_station_ids and s_id not in affected_station_ids:
                boundary_stations.append(station)
                boundary_station_ids.add(s_id)
            # DO NOT enqueue neighbors, traversal stops at this station on this branch
        else:
            # Not a station, keep traversing outward
            if curr_node in graph:
                for neighbor in graph[curr_node]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

    return {
        "affected_stations": affected_stations,
        "boundary_stations": boundary_stations
    }
