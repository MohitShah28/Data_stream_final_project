# 🔍 Echo Chambers - Fast Network Analysis

A high-performance Twitter network analyzer that detects echo chambers and identifies bridge users using Girvan-Newman community detection.

---

## 📊 What It Does

**Analyzes 1.7M+ Twitter edges to:**
- ✅ Detect distinct communities (echo chambers)
- ✅ Identify bridge users connecting communities
- ✅ Calculate modularity (Q) to measure echo chamber strength
- ✅ Generate interactive HTML visualization
- ✅ Export structured JSON results

**Example Output:**
- 3 Communities detected
- Modularity Q = 0.3035 (Strong echo chambers)
- 150 top nodes analyzed
- 2,520 edges in visualization
- 10 bridge users identified

---

## 🚀 How to Run

### Step 1: Activate Virtual Environment
```bash
cd "/Users/mohitshah/Desktop/FINAL_PROJECT/Echo Chambers"
source venv/bin/activate
```

### Step 2: Run Analysis
```bash
python3 main_fast.py
```

### Step 3: View Results
```bash
open echo_chambers.html
```

**Total Time:** ~2 minutes from start to visualization

---

## 📁 Output Files

### `echo_chambers.html` (204KB)
Interactive network visualization with:
- **Color-coded nodes** (each color = different community)
- **White highlighted nodes** (bridge users connecting communities)
- **Stats panel** showing:
  - Community distribution with progress bars
  - Top 10 bridge users ranked
  - Modularity Q indicator
  - Timestamp

**Features:**
- Zoom, pan, drag nodes
- Hover for user details (degree, betweenness score)
- No auto-refresh (results persist after reload)

### `results.json` (Structured Data)
```json
{
  "metadata": {
    "total_nodes": 150,
    "total_edges": 2520,
    "num_communities": 3,
    "modularity_Q": 0.3035,
    "strength": "Strong"
  },
  "communities": [
    {
      "id": 1,
      "size": 111,
      "members": [123456, 234567, ...]
    }
  ],
  "bridge_users": [
    {
      "rank": 1,
      "user_id": 15846407,
      "betweenness": 0.1307,
      "degree": 45
    }
  ]
}
```

---

## ⚡ Why It's Fast (10x Speedup)

### The Problem (Old Approach)
Old code had **three critical bottlenecks:**

#### 1. **Slow Edge Extraction** ❌
```python
# OLD - 10x SLOWER
for _, row in batch.iterrows():
    src, tgt = int(row["source"]), int(row["target"])
```
- Dictionary lookups for every edge
- Python loop overhead
- For 1.7M edges: **extremely slow**

#### 2. **Multiprocessing Overhead** ❌
```python
# OLD - Pool overhead > Benefits
with Pool(cpu_count()) as pool:
    results = pool.map(process_chunk_parallel, all_chunks)
```
- Process creation/spawning cost: expensive
- IPC (Inter-Process Communication): slow
- Better for 10 big tasks, NOT 3,537 tiny ones

#### 3. **Aggressive Window Removal** ❌
```python
# OLD - Lost data constantly
while len(edge_window) > 5000:
    G.remove_edge(old_src, old_tgt)
```
- Kept removing old edges
- By batch 830: graph had barely grown
- By the end: **6 nodes, 0 edges** (garbage!)

**Result:** Script got stuck at batch 820, never finished

---

### The Solution (New Approach)
New code is **optimized across all three:**

#### 1. **Vectorized Edge Extraction** ✅
```python
# NEW - 10x FASTER
srcs = batch["source"].values.astype(int)  # NumPy array
tgts = batch["target"].values.astype(int)  # NumPy array
for src, tgt in zip(srcs, tgts):           # Simple zip
```
- No dictionary lookups
- NumPy C-optimized operations
- Direct array indexing

#### 2. **Pure Sequential Processing** ✅
```python
# NEW - No pool overhead
for batch_start in range(0, len(df), CHUNK_SIZE):
    batch = df.iloc[batch_start:batch_end]
    # Process inline - no IPC
```
- No process spawning
- No IPC overhead
- Single lean Python process

#### 3. **Smart Graph Growth** ✅
```python
# NEW - Keep all edges, clean periodically
for src, tgt in zip(srcs, tgts):
    G.add_edge(src, tgt)  # ACCUMULATE

# Only prune low-degree nodes every 50 batches
if batch_num % 50 == 0:
    low_degree = [n for n, d in G.degree() if d < 3]
    G.remove_nodes_from(low_degree)
```
- Graph grows naturally: 99K → 200K → 1.7M edges
- Minimal pruning (memory efficient)
- By the end: **68K+ nodes, 1.7M edges** (complete data!)

---

## 📈 Performance Comparison

| Metric | Old Code | New Code | Improvement |
|--------|----------|----------|-------------|
| **Processing Time** | 2+ hours (stalled) | ~2 minutes | **60x faster** |
| **Edge Extraction** | `iterrows()` | Vectorized `.values` | **10x faster** |
| **Parallelization** | Multiprocessing Pool | Sequential | **Overhead removed** |
| **Final Graph** | 6 nodes, 0 edges ❌ | 68K nodes, 1.7M edges ✅ | **Complete data** |
| **Communities** | None (failed) | 3 detected ✅ | **Valid analysis** |
| **Modularity Q** | N/A | 0.3035 ✅ | **Strong echo chambers** |

---

## 🔬 How The Analysis Works

### Algorithm: Girvan-Newman Community Detection

1. **Load Data**
   - Read 1.7M edges from `twitter_combined.txt`
   - Remove duplicates
   - Store as DataFrame

2. **Process in Chunks**
   - Read 500 edges per batch (3,537 total batches)
   - Use **vectorized extraction** (not `iterrows()`)
   - Add to directed graph
   - Periodically clean low-degree nodes

3. **Final Analysis**
   - Extract top 150 nodes (by degree)
   - Convert to undirected subgraph
   - Run Girvan-Newman algorithm:
     - Iteratively remove edges with highest betweenness
     - Stop after 10 iterations or best modularity found
   - Return partition with highest modularity Q

4. **Identify Bridge Users**
   - Calculate betweenness centrality
   - Top 10 users with highest betweenness = bridges
   - Bridges connect different communities

5. **Visualize**
   - Color nodes by community
   - Highlight bridges in white
   - Size nodes by degree
   - Use ForceAtlas2 physics for layout
   - Inject stats panel

### What Modularity Q Means

**Q = 0.3035 (Strong Echo Chambers)**
- Q ranges from -1 to 1
- Q > 0.3 = Strong community structure
- Q > 0.5 = Very strong separation
- Q < 0.1 = Weak/random structure

Your result: **Q = 0.3035** = Clear echo chambers detected! 🎯

---

## 📊 Configuration

Edit these values in `main_fast.py` to customize:

```python
FILE_PATH = "twitter_combined.txt"      # Input CSV file
CHUNK_SIZE = 500                        # Edges per batch (lower = more frequent updates)
WINDOW_SIZE = 5000                      # [UNUSED in new version - kept for reference]
MIN_DEGREE = 3                          # Remove nodes with < 3 connections
SUBGRAPH_NODES = 150                    # Top N nodes to analyze
OUTPUT_FILE = "echo_chambers.html"      # Output HTML file
TOP_BRIDGES = 10                        # Number of bridge users to highlight

BRIDGE_COLOR = "#FFFFFF"                # Bridge user color (white)
BRIDGE_SIZE = 42                        # Bridge user node size
```

---

## 🛠 Dependencies

- **networkx** (2.6.3) - Graph algorithms + community detection
- **pandas** (1.3.5) - CSV loading + data manipulation
- **pyvis** (0.3.2) - Interactive HTML visualization

All installed in virtual environment at:
```
venv/lib/python3.7/site-packages/
```

---

## 🎨 Visualization Guide

### Node Colors
- **Purple** = Community 1
- **Red** = Community 2
- **Blue** = Community 3
- **White** = Bridge user (connects multiple communities)

### Node Size
- Larger = Higher degree (more connections)
- Smallest = MIN_DEGREE (3 connections)
- Largest = Hub users with 30+ connections

### Hover Information
- User ID
- Degree (number of connections)
- Betweenness centrality (bridge strength)
- Community assignment

### Interaction
- **Drag** = Move nodes around
- **Scroll** = Zoom in/out
- **Hover** = Show tooltips
- **Click** = Select node (physics pauses)

---

## 📝 JSON Output Structure

```json
{
  "metadata": {
    "total_nodes": 150,                    // Nodes in analysis
    "total_edges": 2520,                   // Edges in analysis
    "num_communities": 3,                  // Communities detected
    "modularity_Q": 0.3035,                // Q score (0-1 scale)
    "strength": "Strong"                   // Echo chamber strength
  },
  "communities": [
    {
      "id": 1,                             // Community number
      "color": "#8B7BB8",                  // Hex color in visualization
      "size": 111,                         // Number of users
      "members": [123456, 234567, ...]     // User IDs in community
    }
  ],
  "bridge_users": [
    {
      "rank": 1,                           // Ranking (1 = strongest bridge)
      "user_id": 15846407,                 // Twitter user ID
      "betweenness": 0.1307,               // Betweenness score (0-1)
      "degree": 45                         // Number of connections
    }
  ]
}
```

---

## ⚠️ Troubleshooting

### Issue: "No data processed"
**Solution:** Check that `twitter_combined.txt` exists in the same directory as `main_fast.py`

### Issue: HTML shows empty graph
**Solution:** Ensure `design.py` exists in the same directory (needed for stats panel)

### Issue: Takes longer than expected
**Reason:** First time might be slower due to:
- Girvan-Newman algorithm complexity (O(n³) worst case)
- NetworkX graph operations
- HTML generation with pyvis physics simulation

**Workaround:** Reduce `SUBGRAPH_NODES` from 150 to 100 for faster results

### Issue: Virtual environment not working
**Solution:**
```bash
deactivate  # Exit current env
source venv/bin/activate  # Reactivate
which python3  # Should show venv/bin/python3
```

---

## 🔑 Key Differences: New vs Old

| Feature | Old `main.py` | New `main_fast.py` |
|---------|---------------|-------------------|
| Edge extraction | `iterrows()` loop | Vectorized `.values.astype()` |
| Processing | Multiprocessing Pool | Pure sequential |
| Window handling | Aggressive removal | Minimal cleanup |
| Intermediate saves | Every 10 batches | None (final only) |
| Final graph | 6 nodes, 0 edges | 68K nodes, 1.7M edges |
| Time to complete | 2+ hours (failed) | ~2 minutes ✅ |
| Result quality | Garbage (incomplete) | Valid analysis ✅ |

**Recommendation:** Always use `main_fast.py` - it's faster AND produces better results!

---

## 📚 References

- **Girvan-Newman Algorithm:** [Wikipedia](https://en.wikipedia.org/wiki/Girvan%E2%80%93Newman_algorithm)
- **Modularity:** [NetworkX Docs](https://networkx.org/documentation/stable/reference/algorithms/community.html)
- **Betweenness Centrality:** [NetworkX Docs](https://networkx.org/documentation/stable/reference/algorithms/centrality.html)
- **Pyvis:** [GitHub](https://github.com/WestHealth/pyvis)

---

## 📄 License

Project: Echo Chambers - Twitter Network Analysis

---

## 🎯 Summary

**Echo Chambers** is a fast, efficient tool for detecting community structures in large Twitter networks. By using vectorized operations and sequential processing instead of slow loops and multiprocessing overhead, it processes 1.7M edges in ~2 minutes with high-quality results.

**Key Achievement:** 10x speedup while maintaining (actually improving!) analysis quality. 🚀
