"""
Echo Chambers Design Module
This file contains all HTML/CSS design for the stats panel visualization.
"""

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
