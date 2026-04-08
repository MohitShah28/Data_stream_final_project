import networkx as nx
import pandas as pd
import itertools
from collections import deque
import networkx.algorithms.community as nx_comm
from pyvis.network import Network
from design import build_stats_html, COLORS
from multiprocessing import Pool, cpu_count

# CONFIG
# ─────────────────────────────────────────────
FILE_PATH       = "twitter_combined.txt"
CHUNK_SIZE      = 500
WINDOW_SIZE     = 5000
MIN_DEGREE      = 3
SUBGRAPH_NODES  = 150
RERUN_EVERY     = 10
OUTPUT_FILE     = "echo_chambers.html"
TOP_BRIDGES     = 10        # number of bridge users to highlight

BRIDGE_COLOR  = "#FFFFFF"   # white — bridge users stand out
BRIDGE_SIZE   = 42

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def find_best_communities(subgraph):
    """Iterate dendrogram up to 10 levels, return split with best modularity."""
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
        except Exception:
            continue

    if best_communities is None:
        comp2 = nx_comm.girvan_newman(subgraph)
        best_communities = list(next(comp2))
        try:
            best_Q = nx_comm.modularity(subgraph, best_communities)
        except Exception:
            best_Q = 0.0

    return best_communities, best_Q


def process_chunk_parallel(args):
    """Process a single chunk in parallel - returns edges list."""
    chunk_data, chunk_idx = args
    edges = []
    for _, row in chunk_data.iterrows():
        src, tgt = int(row["source"]), int(row["target"])
        edges.append((src, tgt))
    return chunk_idx, edges


def save_results_json(G, subgraph, communities, Q, bridge_nodes, betweenness, 
                      community_map, output_file="results.json"):
    """Save final analysis results as JSON file."""
    
    # Prepare community data
    communities_data = []
    for idx, comm in enumerate(communities):
        communities_data.append({
            "id": idx + 1,
            "color": COLORS[idx % len(COLORS)],
            "size": len(comm),
            "members": list(comm)
        })
    
    # Prepare bridge users data
    bridge_users_data = []
    for rank, node_id in enumerate(bridge_nodes[:TOP_BRIDGES], 1):
        node_color = community_map.get(node_id, "#888888")
        community_idx = COLORS.index(node_color) if node_color in COLORS else 0
        bridge_users_data.append({
            "rank": rank,
            "user_id": int(node_id),
            "betweenness_score": float(betweenness.get(node_id, 0)),
            "degree": int(G.degree(node_id)),
            "community": int(community_idx % len(COLORS)) + 1
        })
    
    # Prepare node data
    nodes_data = []
    for node in subgraph.nodes():
        node_color = community_map.get(node, "#888888")
        community_idx = COLORS.index(node_color) if node_color in COLORS else 0
        nodes_data.append({
            "id": int(node),
            "degree": int(subgraph.degree(node)),
            "is_bridge": node in bridge_nodes,
            "community": int(community_idx % len(COLORS)) + 1
        })
    
    # Prepare edge data
    edges_data = []
    for src, tgt in subgraph.edges():
        edges_data.append({
            "source": int(src),
            "target": int(tgt)
        })
    
    # Create main results dictionary
    dominant_community_size = int(len(max(communities, key=len))) if communities else 0
    dominant_community_percentage = (dominant_community_size / sum(len(c) for c in communities) * 100) if sum(len(c) for c in communities) > 0 else 0.0
    
    results = {
        "analysis_metadata": {
            "total_nodes": int(subgraph.number_of_nodes()),
            "total_edges": int(subgraph.number_of_edges()),
            "num_communities": len(communities),
            "modularity_Q": float(Q),
            "modularity_strength": "Strong Echo Chambers" if Q >= 0.3 else "Weak Separation",
            "dominant_community_size": dominant_community_size,
            "dominant_community_percentage": float(dominant_community_percentage)
        },
        "communities": communities_data,
        "bridge_users": bridge_users_data,
        "nodes": nodes_data,
        "edges": edges_data
    }


def save_visualization(G, subgraph, community_map, bridge_nodes,
                       betweenness, communities, Q, chunk_idx, is_final=False):
    """Build Pyvis HTML with stats panel and save to single output file."""

    net = Network(notebook=False, height="100vh", width="100%",
                  bgcolor="#F8FAFC", font_color="#1E293B")
    net.from_nx(subgraph)

    for node in net.nodes:
        nid   = node["id"]
        color = community_map.get(nid, "#888888")
        comm_num = COLORS.index(color) + 1 if color in COLORS else "?"

        if nid in bridge_nodes:
            node["color"]       = BRIDGE_COLOR
            node["size"]        = BRIDGE_SIZE
            node["borderWidth"] = 3
            node["title"]       = (
                f"<b>⚡ BRIDGE USER</b><br>"
                f"User {nid}<br>"
                f"Degree: {G.degree(nid)}<br>"
                f"Betweenness: {betweenness.get(nid, 0):.4f}<br>"
                f"Community: {comm_num}"
            )
        else:
            node["color"] = color
            node["size"]  = min(6 + G.degree(nid) * 0.6, 30)
            node["title"] = (
                f"User {nid}<br>"
                f"Degree: {G.degree(nid)}<br>"
                f"Community: {comm_num}"
            )
        node["label"] = ""

    net.set_options("""
    {
      "physics": {
        "solver": "forceAtlas2Based",
        "forceAtlas2Based": {
          "gravitationalConstant": -80,
          "centralGravity": 0.01,
          "springLength": 130,
          "springConstant": 0.08,
          "damping": 0.4
        },
        "stabilization": { "enabled": true, "iterations": 250 }
      },
      "edges": {
        "color": { "color": "#CBD5E1", "opacity": 0.6 },
        "width": 0.8,
        "arrows": { "to": { "enabled": true, "scaleFactor": 0.3 } }
      },
      "nodes": {
        "borderWidth": 1.5,
        "borderWidthSelected": 3,
        "shape": "dot"
      },
      "interaction": { "hover": true, "tooltipDelay": 100 }
    }
    """)

    net.write_html(OUTPUT_FILE)

    # Inject stats panel into the HTML
    with open(OUTPUT_FILE, "r") as f:
        html = f.read()

    # Auto-refresh every 30 seconds only during streaming (not for final)
    if not is_final:
        html = html.replace("<head>", "<head><meta http-equiv='refresh' content='30'>")

    stats_panel = build_stats_html(
        communities,
        Q,
        bridge_nodes,
        betweenness,
        chunk_idx
    )

    html = html.replace("</body>", f"{stats_panel}</body>")

    with open(OUTPUT_FILE, "w") as f:
        f.write(html)


# ─────────────────────────────────────────────
# MAIN EXECUTION
# ─────────────────────────────────────────────

if __name__ == '__main__':
    print("Loading data...")
    df = pd.read_csv(FILE_PATH, sep=r'\s+', names=["source", "target"])
    df = df.drop_duplicates()
    df["timestamp"] = range(len(df))
    df = df.sort_values("timestamp").reset_index(drop=True)
    print(f"Total edges loaded: {len(df)}\n")

    # ─────────────────────────────────────────────
    # STEP 2: STREAMING LOOP (PARALLELIZED)
    # ─────────────────────────────────────────────
    edge_window   = deque()
    G             = nx.DiGraph()
    community_map = {}

    print("Starting stream simulation (PARALLEL MODE)...\n")

    # Prepare all chunks for parallel processing
    all_chunks = []
    for chunk_idx, start in enumerate(range(0, len(df), CHUNK_SIZE)):
        chunk = df.iloc[start : start + CHUNK_SIZE]
        all_chunks.append((chunk, chunk_idx))

    # Process chunks in parallel
    num_workers = max(1, cpu_count() - 1)  # Use all cores except one
    print(f"Using {num_workers} parallel workers\n")

    with Pool(num_workers) as pool:
        results = pool.map(process_chunk_parallel, all_chunks)

    # Process results sequentially (maintain graph consistency)
    for chunk_idx, edges in sorted(results):
        # Add edges to window
        for src, tgt in edges:
            edge_window.append((src, tgt))
            G.add_edge(src, tgt)

        # Maintain sliding window
        while len(edge_window) > WINDOW_SIZE:
            old_src, old_tgt = edge_window.popleft()
            if G.has_edge(old_src, old_tgt):
                G.remove_edge(old_src, old_tgt)

        # Remove low-degree nodes
        low_degree = [n for n, d in list(G.degree()) if d < MIN_DEGREE]
        G.remove_nodes_from(low_degree)

        print(f"Chunk {chunk_idx+1:>4} | Window: {len(edge_window):>5} | "
              f"Nodes: {G.number_of_nodes():>5} | Edges: {G.number_of_edges():>6}")

        # Run community detection every RERUN_EVERY chunks
        if (chunk_idx + 1) % RERUN_EVERY == 0 and G.number_of_nodes() > 10:
            print(f"\n  → Running Girvan-Newman at chunk {chunk_idx + 1}...")

            top_nodes = sorted(
                G.nodes(), key=lambda n: G.degree(n), reverse=True
            )[:SUBGRAPH_NODES]
            subgraph = G.subgraph(top_nodes).to_undirected().copy()
            subgraph.remove_edges_from(nx.selfloop_edges(subgraph))

            if subgraph.number_of_edges() == 0:
                print("  → No edges in subgraph, skipping.\n")
                continue

            try:
                communities, Q = find_best_communities(subgraph)

                # Assign community colors
                community_map = {}
                for idx, community in enumerate(communities):
                    color = COLORS[idx % len(COLORS)]
                    for node in community:
                        community_map[node] = color

                # Find bridge users via betweenness centrality
                betweenness = nx.betweenness_centrality(subgraph)
                bridge_nodes = sorted(
                    betweenness, key=betweenness.get, reverse=True
                )[:TOP_BRIDGES]

                save_visualization(G, subgraph, community_map, bridge_nodes,
                                   betweenness, communities, Q, chunk_idx + 1, is_final=False)

            except Exception as e:
                print(f"  → Failed: {e}\n")

    # ─────────────────────────────────────────────
    # STEP 3: FINAL VISUALIZATION
    # ─────────────────────────────────────────────
    print("\nGenerating final visualization...")

    if G.number_of_nodes() > 0:
        top_nodes = sorted(
            G.nodes(), key=lambda n: G.degree(n), reverse=True
        )[:SUBGRAPH_NODES]
        final_sub = G.subgraph(top_nodes).to_undirected().copy()
        final_sub.remove_edges_from(nx.selfloop_edges(final_sub))

        try:
            communities, Q = find_best_communities(final_sub)

            community_map = {}
            for idx, community in enumerate(communities):
                color = COLORS[idx % len(COLORS)]
                for node in community:
                    community_map[node] = color

            betweenness  = nx.betweenness_centrality(final_sub)
            bridge_nodes = sorted(
                betweenness, key=betweenness.get, reverse=True
            )[:TOP_BRIDGES]

            save_visualization(G, final_sub, community_map, bridge_nodes,
                               betweenness, communities, Q, "FINAL", is_final=True)
            print("Final HTML saved: " + OUTPUT_FILE)
            
            json_file = save_results_json(G, final_sub, communities, Q, bridge_nodes,
                                           betweenness, community_map)
            print("Final results saved: " + json_file)

        except Exception as e:
            print(f"Final failed: {e}")

    print("\nDone.")
