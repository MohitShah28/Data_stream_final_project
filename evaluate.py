import networkx as nx
import pandas as pd
import itertools
import csv
import os
from collections import deque
import networkx.algorithms.community as nx_comm

# ─────────────────────────────────────────────
# CONFIG — must match your main script
# ─────────────────────────────────────────────
FILE_PATH      = "twitter_combined.txt"
CHUNK_SIZE     = 500
WINDOW_SIZE    = 5000
MIN_DEGREE     = 3
SUBGRAPH_NODES = 150
RERUN_EVERY    = 10
TOP_BRIDGES    = 10
EVAL_FILE      = "evaluation_log.csv"

# ─────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────
print("Loading data...")
df = pd.read_csv(FILE_PATH, sep=r'\s+', names=["source", "target"])
df = df.drop_duplicates()
df["timestamp"] = range(len(df))
df = df.sort_values("timestamp").reset_index(drop=True)
print(f"Total edges loaded: {len(df)}\n")

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def find_best_communities(subgraph):
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


def compute_metrics(G, subgraph, communities, Q):
    """Compute all evaluation metrics for one snapshot."""

    # Community sizes
    community_sizes = sorted([len(c) for c in communities], reverse=True)
    largest_community_pct = (community_sizes[0] / sum(community_sizes)) * 100

    # Betweenness centrality
    betweenness   = nx.betweenness_centrality(subgraph)
    bridge_nodes  = sorted(betweenness, key=betweenness.get, reverse=True)[:TOP_BRIDGES]
    avg_between   = sum(betweenness.values()) / len(betweenness) if betweenness else 0
    max_between   = max(betweenness.values()) if betweenness else 0

    # Graph density
    density = nx.density(subgraph)

    # Average clustering coefficient
    try:
        avg_clustering = nx.average_clustering(subgraph)
    except Exception:
        avg_clustering = 0.0

    # Average shortest path (on largest connected component only)
    try:
        largest_cc = max(nx.connected_components(subgraph), key=len)
        lcc_sub    = subgraph.subgraph(largest_cc)
        avg_path   = nx.average_shortest_path_length(lcc_sub) if len(lcc_sub) > 1 else 0
    except Exception:
        avg_path = 0.0

    return {
        "num_communities":       len(communities),
        "modularity_Q":          round(Q, 4),
        "community_sizes":       str(community_sizes),
        "largest_comm_pct":      round(largest_community_pct, 2),
        "num_bridge_users":      len(bridge_nodes),
        "top_bridge_user":       bridge_nodes[0] if bridge_nodes else "N/A",
        "max_betweenness":       round(max_between, 4),
        "avg_betweenness":       round(avg_between, 4),
        "graph_density":         round(density, 6),
        "avg_clustering":        round(avg_clustering, 4),
        "avg_shortest_path":     round(avg_path, 4),
        "subgraph_nodes":        subgraph.number_of_nodes(),
        "subgraph_edges":        subgraph.number_of_edges(),
        "full_graph_nodes":      G.number_of_nodes(),
        "full_graph_edges":      G.number_of_edges(),
        "q_strong":              "Yes" if Q >= 0.3 else "No",
        "dominant_cluster_alert":"Yes" if largest_community_pct > 70 else "No",
    }

# ─────────────────────────────────────────────
# STREAMING LOOP WITH EVALUATION
# ─────────────────────────────────────────────
edge_window = deque()
G           = nx.DiGraph()
all_metrics = []

# CSV header
csv_columns = [
    "chunk", "full_graph_nodes", "full_graph_edges",
    "subgraph_nodes", "subgraph_edges",
    "num_communities", "modularity_Q", "q_strong",
    "community_sizes", "largest_comm_pct", "dominant_cluster_alert",
    "num_bridge_users", "top_bridge_user",
    "max_betweenness", "avg_betweenness",
    "graph_density", "avg_clustering", "avg_shortest_path"
]

print("Starting stream simulation with evaluation...\n")
print(f"{'Chunk':>6} | {'Nodes':>6} | {'Edges':>7} | {'Communities':>12} | {'Q':>7} | {'Dominant %':>11} | {'Status'}")
print("-" * 75)

for chunk_idx, start in enumerate(range(0, len(df), CHUNK_SIZE)):
    chunk = df.iloc[start : start + CHUNK_SIZE]

    for _, row in chunk.iterrows():
        src, tgt = int(row["source"]), int(row["target"])
        edge_window.append((src, tgt))
        G.add_edge(src, tgt)

    while len(edge_window) > WINDOW_SIZE:
        old_src, old_tgt = edge_window.popleft()
        if G.has_edge(old_src, old_tgt):
            G.remove_edge(old_src, old_tgt)

    low_degree = [n for n, d in list(G.degree()) if d < MIN_DEGREE]
    G.remove_nodes_from(low_degree)

    if (chunk_idx + 1) % RERUN_EVERY == 0 and G.number_of_nodes() > 10:

        top_nodes = sorted(
            G.nodes(), key=lambda n: G.degree(n), reverse=True
        )[:SUBGRAPH_NODES]
        subgraph = G.subgraph(top_nodes).to_undirected().copy()
        subgraph.remove_edges_from(nx.selfloop_edges(subgraph))

        if subgraph.number_of_edges() == 0:
            continue

        try:
            communities, Q = find_best_communities(subgraph)
            metrics        = compute_metrics(G, subgraph, communities, Q)
            metrics["chunk"] = chunk_idx + 1
            all_metrics.append(metrics)

            status = "✓ Strong" if Q >= 0.3 else "✗ Weak"
            alert  = " ⚠ DOM"  if metrics["dominant_cluster_alert"] == "Yes" else ""
            print(
                f"{chunk_idx+1:>6} | "
                f"{G.number_of_nodes():>6} | "
                f"{G.number_of_edges():>7} | "
                f"{len(communities):>12} | "
                f"{Q:>7.4f} | "
                f"{metrics['largest_comm_pct']:>10.1f}% | "
                f"{status}{alert}"
            )

        except Exception as e:
            print(f"Chunk {chunk_idx+1}: evaluation failed — {e}")

# ─────────────────────────────────────────────
# SAVE CSV LOG
# ─────────────────────────────────────────────
if all_metrics:
    with open(EVAL_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns)
        writer.writeheader()
        for row in all_metrics:
            writer.writerow({k: row.get(k, "") for k in csv_columns})
    print(f"\nEvaluation log saved: {EVAL_FILE}")
else:
    print("\nNo evaluation data collected.")

# ─────────────────────────────────────────────
# SUMMARY STATISTICS
# ─────────────────────────────────────────────
if all_metrics:
    qs      = [m["modularity_Q"]    for m in all_metrics]
    comms   = [m["num_communities"] for m in all_metrics]
    doms    = [m["largest_comm_pct"]for m in all_metrics]

    print("\n" + "=" * 55)
    print("  EVALUATION SUMMARY")
    print("=" * 55)
    print(f"  Total snapshots evaluated : {len(all_metrics)}")
    print(f"  Avg Modularity Q          : {sum(qs)/len(qs):.4f}")
    print(f"  Max Modularity Q          : {max(qs):.4f}")
    print(f"  Min Modularity Q          : {min(qs):.4f}")
    print(f"  Snapshots with Q >= 0.3   : {sum(1 for q in qs if q >= 0.3)} / {len(qs)}")
    print(f"  Avg communities detected  : {sum(comms)/len(comms):.1f}")
    print(f"  Max communities detected  : {max(comms)}")
    print(f"  Avg dominant cluster %    : {sum(doms)/len(doms):.1f}%")
    print(f"  Dominant cluster alerts   : {sum(1 for m in all_metrics if m['dominant_cluster_alert']=='Yes')}")
    print("=" * 55)
    print(f"\nFull log written to: {EVAL_FILE}")

print("\nDone.")
