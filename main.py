import networkx as nx
import pandas as pd
import itertools
from collections import deque
import networkx.algorithms.community as nx_comm
from pyvis.network import Network

# ─────────────────────────────────────────────
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

COLORS = [
    "#E76F51",  # orange
    "#048A81",  # teal
    "#9B5DE5",  # purple
    "#F4A261",  # amber
    "#2196F3",  # blue
    "#4CAF50",  # green
    "#F72585",  # pink
    "#FFD166",  # yellow
]

BRIDGE_COLOR  = "#FFFFFF"   # white — bridge users stand out
BRIDGE_SIZE   = 42

# ─────────────────────────────────────────────
# STEP 1: LOAD DATA
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


def build_stats_html(communities, Q, bridge_nodes, betweenness, chunk_idx):
    """Build a responsive and interactive HTML stats panel."""
    import datetime
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")

    # community size rows with progress bars
    comm_rows = ""
    total_nodes = sum(len(c) for c in communities)
    for i, comm in enumerate(communities):
        color = COLORS[i % len(COLORS)]
        percentage = (len(comm) / total_nodes) * 100 if total_nodes > 0 else 0
        comm_rows += (
            f'<div style="margin-bottom:10px;padding:10px;background:#F1F5F9;'
            f'border-radius:8px;border-left:4px solid {color};'
            f'transition:all 0.3s ease;cursor:pointer;" class="comm-item" onmouseover="this.style.background=\'#E0E7FF\';this.style.transform=\'translateX(-4px)\';" onmouseout="this.style.background=\'#F1F5F9\';this.style.transform=\'translateX(0)\';">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">'
            f'<span style="font-weight:600;font-size:12px;">Community {i+1}</span>'
            f'<span style="background:{color};color:white;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">{len(comm)} users</span>'
            f'</div>'
            f'<div style="background:#E2E8F0;height:5px;border-radius:3px;overflow:hidden;">'
            f'<div style="background:{color};height:100%;width:{percentage}%;transition:width 0.5s ease;border-radius:3px;"></div>'
            f'</div>'
            f'</div>'
        )

    # bridge user rows with ranking
    bridge_rows = ""
    for rank, nid in enumerate(bridge_nodes[:5], 1):
        score = betweenness.get(nid, 0)
        bridge_rows += (
            f'<div style="margin-bottom:8px;padding:10px;background:#FEF3C7;'
            f'border-radius:8px;border-left:4px solid #F59E0B;'
            f'display:flex;align-items:center;gap:10px;'
            f'transition:all 0.3s ease;cursor:pointer;" onmouseover="this.style.background=\'#FCDAB7\';this.style.transform=\'translateX(-4px)\';" onmouseout="this.style.background=\'#FEF3C7\';this.style.transform=\'translateX(0)\';">'
            f'<div style="width:32px;height:32px;background:#F59E0B;color:white;'
            f'border-radius:50%;display:flex;align-items:center;justify-content:center;'
            f'font-weight:700;font-size:14px;">{rank}</div>'
            f'<div style="flex:1;">'
            f'<div style="font-weight:600;font-size:12px;color:#1E293B;">User {nid}</div>'
            f'<div style="font-size:11px;color:#64748B;">Score: {score:.4f}</div>'
            f'</div>'
            f'</div>'
        )

    # alert if Q is weak
    q_color  = "#10B981" if Q >= 0.3 else "#F97316"
    q_emoji  = "✅" if Q >= 0.3 else "⚠️"
    q_label  = "Strong Echo Chambers" if Q >= 0.3 else "Weak Separation"
    dom_comm = max(communities, key=len)
    dom_pct  = len(dom_comm) / sum(len(c) for c in communities) * 100
    alert    = ""
    if dom_pct > 70:
        alert = (
            f'<div style="margin-top:12px;padding:12px;background:#FEE2E2;'
            f'border-radius:8px;border-left:4px solid #EF4444;'
            f'color:#7F1D1D;font-size:12px;line-height:1.5;">'
            f'⚠️ <b>Dominant Cluster Alert</b><br>'
            f'One community holds {dom_pct:.0f}% of nodes'
            f'</div>'
        )

    panel = f"""
    <div id="stats-panel" style="
        position: fixed; top: 16px; right: 16px; z-index: 999;
        background: #FFFFFF; border: 2px solid #E2E8F0;
        border-radius: 16px; padding: 20px; width: 320px;
        font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px;
        color: #1E293B; box-shadow: 0 10px 30px rgba(0,0,0,0.15);
        max-height: 85vh; overflow-y: auto;
        transition: all 0.3s ease;">

      <style>
        @keyframes pulse {{
          0%, 100% {{ opacity: 1; }}
          50% {{ opacity: 0.6; }}
        }}
        #stats-panel::-webkit-scrollbar {{
          width: 6px;
        }}
        #stats-panel::-webkit-scrollbar-track {{
          background: #F1F5F9;
          border-radius: 3px;
        }}
        #stats-panel::-webkit-scrollbar-thumb {{
          background: #94A3B8;
          border-radius: 3px;
        }}
        #stats-panel::-webkit-scrollbar-thumb:hover {{
          background: #64748B;
        }}
      </style>

      <div style="font-weight:700;font-size:16px;margin-bottom:12px;
                  border-bottom:3px solid #3B82F6;padding-bottom:12px;
                  display:flex;align-items:center;gap:8px;">
        <span style="font-size:18px;animation:pulse 2s infinite;">📡</span>
        Echo Chamber Monitor
      </div>

      <div style="margin-bottom:12px;padding:8px;background:#EFF6FF;
                  border-radius:8px;border-left:4px solid #3B82F6;
                  color:#1E40AF;font-size:11px;font-family:'Courier New',monospace;">
        🕐 {timestamp} | Chunk #{chunk_idx}
      </div>

      <div style="margin-bottom:10px;font-weight:700;font-size:13px;
                  text-transform:uppercase;letter-spacing:0.5px;color:#64748B;">
        Communities ({len(communities)})
      </div>
      {comm_rows}

      <div style="margin:16px 0 10px;padding:14px;background:#F0F9FF;
                  border-radius:10px;border:2px solid {q_color};
                  text-align:center;transition:all 0.3s ease;">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.5px;
                    color:#64748B;margin-bottom:4px;">Modularity Q</div>
        <div style="font-size:28px;font-weight:700;color:{q_color};
                    font-family:'Courier New',monospace;margin-bottom:4px;">
          {Q:.4f}
        </div>
        <div style="font-size:12px;color:{q_color};font-weight:600;">
          {q_emoji} {q_label}
        </div>
      </div>

      <div style="margin:14px 0 10px;font-weight:700;font-size:13px;
                  text-transform:uppercase;letter-spacing:0.5px;color:#64748B;">
        ⚡ Top Bridge Users
      </div>
      {bridge_rows}

      {alert}

      <div style="margin-top:16px;padding:12px;background:#F8FAFC;
                  border-radius:10px;border:1px solid #CBD5E1;
                  font-size:11px;line-height:1.6;color:#475569;">
        <div style="font-weight:600;margin-bottom:6px;">Legend:</div>
        <div style="margin-bottom:4px;">🔴 Colored nodes = Communities</div>
        <div style="margin-bottom:4px;">⚪ White nodes = Bridge Users</div>
        <div>📏 Node size = Influence (Degree)</div>
      </div>
    </div>
    """
    return panel


def save_visualization(G, subgraph, community_map, bridge_nodes,
                       betweenness, communities, Q, chunk_idx):
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

    # Auto-refresh every 30 seconds
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
# STEP 2: STREAMING LOOP
# ─────────────────────────────────────────────
edge_window   = deque()
G             = nx.DiGraph()
community_map = {}

print("Starting stream simulation...\n")

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

    print(f"Chunk {chunk_idx+1:>4} | Window: {len(edge_window):>5} | "
          f"Nodes: {G.number_of_nodes():>5} | Edges: {G.number_of_edges():>6}")

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
                               betweenness, communities, Q, chunk_idx + 1)

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
                           betweenness, communities, Q, "FINAL")
        print(f"Final saved: {OUTPUT_FILE}")

    except Exception as e:
        print(f"Final failed: {e}")

print("\nDone.")

