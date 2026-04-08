#!/usr/bin/env python3
"""Fast Echo Chamber Analysis - Sequential, no intermediate saves"""
import networkx as nx
import pandas as pd
import itertools
from collections import deque
import networkx.algorithms.community as nx_comm
from pyvis.network import Network
from design import build_stats_html, COLORS
import json
import sys

FILE_PATH = "twitter_combined.txt"
CHUNK_SIZE = 500
WINDOW_SIZE = 5000
MIN_DEGREE = 3
SUBGRAPH_NODES = 150
OUTPUT_FILE = "echo_chambers.html"
TOP_BRIDGES = 10

BRIDGE_COLOR = "#FFFFFF"
BRIDGE_SIZE = 42

print("📥 Loading data...", flush=True)
df = pd.read_csv(FILE_PATH, sep=r'\s+', names=["source", "target"])
df = df.drop_duplicates()
print(f"✓ {len(df):,} edges loaded\n", flush=True)

def find_best_communities(subgraph):
    """Girvan-Newman community detection."""
    comp = nx_comm.girvan_newman(subgraph)
    best_communities = None
    best_Q = -1
    for communities in itertools.islice(comp, 10):
        communities = list(communities)
        if len(communities) < 3:
            continue
        try:
            Q = nx_comm.modularity(subgraph, communities)
            if Q > best_Q:
                best_Q = Q
                best_communities = communities
        except:
            continue
    if best_communities is None:
        comp2 = nx_comm.girvan_newman(subgraph)
        best_communities = list(next(comp2))
        try:
            best_Q = nx_comm.modularity(subgraph, best_communities)
        except:
            best_Q = 0.0
    return best_communities, best_Q

def save_json(G, subgraph, communities, Q, bridge_nodes, betweenness, community_map):
    """Save results to JSON."""
    communities_data = []
    for idx, comm in enumerate(communities):
        communities_data.append({
            "id": idx + 1,
            "color": COLORS[idx % len(COLORS)],
            "size": len(comm),
            "members": list(comm)
        })
    
    bridge_users_data = []
    for rank, node_id in enumerate(bridge_nodes[:TOP_BRIDGES], 1):
        bridge_users_data.append({
            "rank": rank,
            "user_id": int(node_id),
            "betweenness": float(betweenness.get(node_id, 0)),
            "degree": int(G.degree(node_id))
        })
    
    results = {
        "metadata": {
            "total_nodes": int(subgraph.number_of_nodes()),
            "total_edges": int(subgraph.number_of_edges()),
            "num_communities": len(communities),
            "modularity_Q": float(Q),
            "strength": "Strong" if Q >= 0.3 else "Weak"
        },
        "communities": communities_data,
        "bridge_users": bridge_users_data
    }
    
    with open("results.json", "w") as f:
        json.dump(results, f, indent=2)

def save_html(G, subgraph, community_map, bridge_nodes, betweenness, communities, Q):
    """Save visualization to HTML."""
    net = Network(notebook=False, height="100vh", width="100%", bgcolor="#F8FAFC", font_color="#1E293B")
    net.from_nx(subgraph)

    for node in net.nodes:
        nid = int(node["id"])  # Ensure int type
        color = community_map.get(nid, "#888888")
        if nid in bridge_nodes:
            node["color"] = BRIDGE_COLOR
            node["size"] = BRIDGE_SIZE
            node["borderWidth"] = 3
            node["title"] = f"⚡ BRIDGE {nid}\nDegree: {G.degree(nid)}\nBetweenness: {betweenness.get(nid, 0):.4f}"
        else:
            node["color"] = color
            node["size"] = min(6 + G.degree(nid) * 0.6, 30)
            node["title"] = f"User {nid}\nDegree: {G.degree(nid)}"
        node["label"] = ""

    net.set_options("""{
      "physics": {"solver": "forceAtlas2Based", "forceAtlas2Based": {"gravitationalConstant": -80, "damping": 0.4}, "stabilization": {"enabled": true, "iterations": 250}},
      "edges": {"color": {"color": "#CBD5E1", "opacity": 0.6}, "width": 0.8, "arrows": {"to": {"enabled": true, "scaleFactor": 0.3}}},
      "nodes": {"borderWidth": 1.5, "shape": "dot"},
      "interaction": {"hover": true, "tooltipDelay": 100}
    }""")

    net.write_html(OUTPUT_FILE)

    with open(OUTPUT_FILE, "r") as f:
        html = f.read()

    stats = build_stats_html(communities, Q, bridge_nodes, betweenness, "FINAL")
    html = html.replace("</body>", f"{stats}</body>")

    with open(OUTPUT_FILE, "w") as f:
        f.write(html)

print("⚙️  Processing edges...", flush=True)
G = nx.DiGraph()
total_batches = (len(df) + CHUNK_SIZE - 1) // CHUNK_SIZE

for batch_start in range(0, len(df), CHUNK_SIZE):
    batch_end = min(batch_start + CHUNK_SIZE, len(df))
    batch = df.iloc[batch_start:batch_end]
    batch_num = (batch_start // CHUNK_SIZE) + 1
    
    srcs = batch["source"].values.astype(int)
    tgts = batch["target"].values.astype(int)
    for src, tgt in zip(srcs, tgts):
        G.add_edge(src, tgt)

    # Remove low-degree nodes periodically (keep graph manageable)
    if batch_num % 50 == 0:
        low_degree = [n for n, d in list(G.degree()) if d < MIN_DEGREE]
        G.remove_nodes_from(low_degree)

    if batch_num % 200 == 0:
        print(f"  Batch {batch_num:>4}/{total_batches} | Nodes: {G.number_of_nodes():>5} | Edges: {G.number_of_edges():>6}", flush=True)

print(f"\n🔍 Final analysis...", flush=True)
if G.number_of_nodes() > 0:
    top_nodes = sorted(G.nodes(), key=lambda n: G.degree(n), reverse=True)[:SUBGRAPH_NODES]
    # Convert all nodes to int to avoid numpy type issues
    top_nodes = [int(n) for n in top_nodes]
    final_sub = G.subgraph(top_nodes).to_undirected().copy()
    # Relabel nodes to ensure they're Python ints
    final_sub = nx.relabel_nodes(final_sub, {n: int(n) for n in final_sub.nodes()})
    final_sub.remove_edges_from(nx.selfloop_edges(final_sub))

    if final_sub.number_of_edges() > 0:
        print("🎯 Detecting communities...", flush=True)
        communities, Q = find_best_communities(final_sub)
        print(f"✓ Found {len(communities)} communities (Q={Q:.4f})", flush=True)

        community_map = {}
        for idx, community in enumerate(communities):
            for node in community:
                community_map[node] = COLORS[idx % len(COLORS)]

        print("🌉 Finding bridges...", flush=True)
        betweenness = nx.betweenness_centrality(final_sub)
        bridge_nodes = sorted(betweenness, key=betweenness.get, reverse=True)[:TOP_BRIDGES]

        print("💾 Saving HTML...", flush=True)
        save_html(G, final_sub, community_map, bridge_nodes, betweenness, communities, Q)
        print(f"✓ Saved: {OUTPUT_FILE}", flush=True)

        print("💾 Saving JSON...", flush=True)
        save_json(G, final_sub, communities, Q, bridge_nodes, betweenness, community_map)
        print(f"✓ Saved: results.json", flush=True)

        print(f"\n✅ COMPLETE!")
        print(f"   Communities: {len(communities)}")
        print(f"   Bridge Users: {len(bridge_nodes)}")
        print(f"   Nodes: {final_sub.number_of_nodes()}")
        print(f"   Edges: {final_sub.number_of_edges()}")
        sys.exit(0)

print("❌ No data processed")
sys.exit(1)
