import csv, re, json, sys, argparse

ap = argparse.ArgumentParser(description="Build the Forte gear collision graph page(s).")
ap.add_argument("targets", nargs="*",
                help="beta→graph.html, stable→index.html (reduced), promote→beta HTML to index.html, all→beta+promote. Default: beta stable.")
args = ap.parse_args()
TARGETS = set(args.targets) or {"beta", "stable"}
_valid = {"beta", "stable", "promote", "all"}
_bad = TARGETS - _valid
if _bad: sys.exit(f"error: unknown target(s): {sorted(_bad)}; choose from {sorted(_valid)}")
if "all" in TARGETS: TARGETS = {"beta", "promote"}
if "stable" in TARGETS and "promote" in TARGETS:
    sys.exit("error: 'stable' and 'promote' both write index.html — pick one.")
from collections import defaultdict
from itertools import combinations

CSV = "Forte -TBC- Gear_Alts Tracker - Phase 1.csv"
T4_GROUP = {
    "Warrior":"WDP","Druid":"WDP","Priest":"WDP",
    "Hunter":"HMW","Mage":"HMW","Warlock":"HMW",
    "Paladin":"PRS","Rogue":"PRS","Shaman":"PRS",
}
ITEM_ALIASES = {
    "t4 helm":"T4 Head",
    "t4 gloves":"T4 Hands",
    "voidheart crown t4 head":"T4 Head",
    "bladespire warbrands":"Bladespire Warbands",
    "brute cloak of the ogri-magi":"Brute Cloak of the Ogre-Magi",
    "eredar wand of oblieration":"Eredar Wand of Obliteration",
    "magtheridons head":"Magtheridon's Head",
    "vambraces of courage":"Vambracers of Courage",
    "skullker's greaves":"Skulker's Greaves",
    "ring of a thousand marks":"Ring of Thousand Marks",
    "garona's signet ring":"Garona's Signet Ring",
    "sunfury bow of the phoenix":"Sunfury Bow of the Phoenix",
    "kings defender":"King's Defender",
    "whirlwind bracers":"Whirlwind Bracers",
    # Druid T4 set pieces (Malorne)
    "stag-helm of malorne":"T4 Head",
    "mantle of malorne":"T4 Shoulders",
    "breastplate of malorne":"T4 Chest",
    "gauntlets of malorne":"T4 Hands",
    "greaves of malorne":"T4 Legs",
    # Priest T4 set pieces (Incarnate)
    "light-collar of the incarnate":"T4 Head",
}
CLASS_COLOR = {
    "Warrior":"#C79C6E","Druid":"#FF7D0A","Priest":"#FFFFFF",
    "Hunter":"#ABD473","Mage":"#69CCF0","Warlock":"#9482C9",
    "Paladin":"#F58CBA","Rogue":"#FFF569","Shaman":"#0070DE",
}

# "... of the Fallen Champion/Defender/Hero" rows are T4 slot tokens:
# map the noun to its T4 slot, then normal T4 class-group suffixing applies.
FALLEN_SLOT = {
    "helm":      "Head",
    "chestguard":"Chest",
    "pauldrons": "Shoulders",
    "mantle":    "Shoulders",
    "gauntlets": "Hands",
    "gloves":    "Hands",
    "handguards":"Hands",
    "greaves":   "Legs",
    "leggings":  "Legs",
    "trousers":  "Legs",
}

def norm_item(raw):
    s = re.sub(r"\s+", " ", raw.strip())
    key = s.lower()
    if key in ITEM_ALIASES:
        return ITEM_ALIASES[key]
    m = re.match(r"^(\w+)\s+of\s+the\s+fallen\s+(champion|defender|hero)$", s, flags=re.IGNORECASE)
    if m:
        slot = FALLEN_SLOT.get(m.group(1).lower())
        if slot:
            return f"T4 {slot}"
    m = re.match(r"^(t4)\s+(\w+)(.*)$", s, flags=re.IGNORECASE)
    if m:
        return f"T4 {m.group(2).capitalize()}{m.group(3)}"
    return s

rows = []
player_class = {}
with open(CSV, newline="", encoding="utf-8") as f:
    last = None
    for r in csv.DictReader(f):
        p = r["Player Name"].strip() or last
        if not p: continue
        last = p
        cls = r["Class"].strip()
        if cls: player_class.setdefault(p, cls)
        if r.get("Status", "").strip().lower() == "owned":
            continue
        rows.append((p, r["Item Name"].strip(), r["Raid Name"].strip()))

need = defaultdict(set)
for p, raw, raid in rows:
    if not raw: continue
    item = norm_item(raw)
    if item.startswith("T4 "):
        item = f"{item} [{T4_GROUP.get(player_class.get(p,''),'?')}]"
    need[item].add((p, raid))

nodes = []
for p, c in player_class.items():
    color = CLASS_COLOR.get(c, "#888")
    nodes.append({
        "id": p, "label": p, "title": f"{p} ({c})",
        "shape": "box",
        "color": {"background": "#333", "border": color,
                  "highlight": {"background": "#444", "border": color}},
        "borderWidth": 6, "borderWidthSelected": 8,
        "margin": 14,
        "font": {"size": 28, "color": "#fff", "face": "sans-serif", "bold": True},
        "class": c,
    })

pair_items = defaultdict(list)
for item, prs in need.items():
    players = sorted({p for p, _ in prs})
    raid_by_player = {p: r for p, r in prs}
    for a, b in combinations(players, 2):
        raid = raid_by_player[a] or raid_by_player[b]
        pair_items[(a, b)].append({"item": item, "raid": raid})

edges = [{"from": a, "to": b, "items": items} for (a, b), items in pair_items.items()]

raids = sorted({i["raid"] for its in pair_items.values() for i in its if i["raid"]})
# every contested item (appears on at least one edge), sorted by # of players needing it (desc)
item_player_counts = {item: len({p for p, _ in prs}) for item, prs in need.items()}
items_all = sorted(
    {i["item"] for its in pair_items.values() for i in its},
    key=lambda it: (-item_player_counts[it], it)
)

# map each contested item to the set of raids it drops from
item_raids = {}
for item in items_all:
    item_raids[item] = sorted({r for _, r in need[item] if r})

html = """<!doctype html>
<html><head><meta charset="utf-8"><title>Gear Collision Graph</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
  html,body{margin:0;height:100vh;overflow:hidden;background:#222;color:#eee;font-family:sans-serif;font-size:16px}
  #wrap{display:flex;height:100vh;width:100vw}
  #side{width:360px;padding:20px;border-right:1px solid #444;box-sizing:border-box;overflow-y:auto;flex-shrink:0}
  #side h3{margin:22px 0 8px 0;font-size:18px;text-transform:uppercase;color:#aaa;letter-spacing:1px}
  #side h3:first-child{margin-top:0}
  #net{flex:1;height:100vh;background:#222;position:relative}
  div.vis-network div.vis-navigation div.vis-button{background-color:rgba(50,50,50,.7);border-radius:4px;margin:2px}
  div.vis-network div.vis-navigation div.vis-button:hover{background-color:rgba(80,80,80,.9)}
  div.vis-tooltip{position:absolute;background:#333;color:#eee;border:1px solid #666;border-radius:4px;padding:8px 12px;font-size:14px;pointer-events:none;z-index:100;max-width:400px;line-height:1.5}
  label{display:block;margin:8px 0;cursor:pointer;font-size:17px;line-height:1.3}
  input[type=checkbox]{width:18px;height:18px;vertical-align:middle;margin-right:6px}
  .muted{color:#888;font-size:14px;margin-top:18px}
  .btns{margin:8px 0 12px 0}
  .btns button{background:#333;color:#ddd;border:1px solid #555;padding:6px 12px;font-size:14px;cursor:pointer;margin-right:6px;border-radius:3px}
  .btns button:hover{background:#444}
  #modal-overlay{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.6);z-index:999;align-items:center;justify-content:center}
  #modal-overlay.show{display:flex}
  #modal{background:#2a2a2a;border:1px solid #555;border-radius:8px;padding:24px;width:520px;max-width:90vw}
  #modal h3{margin:0 0 12px 0;color:#ddd}
  #modal textarea{width:100%;height:200px;background:#1a1a1a;color:#eee;border:1px solid #555;border-radius:4px;padding:8px;font-size:14px;resize:vertical;box-sizing:border-box}
  #modal .btns{margin-top:12px;text-align:right}
</style></head>
<body><div id="wrap">
  <div id="side">
    <div style="text-align:right;margin-bottom:8px"><a href="index.html" style="color:#aaa;font-size:13px;text-decoration:none">&larr; Stable</a> <span style="color:#6af;font-size:13px;border:1px solid #6af;padding:3px 10px;border-radius:3px">&#129514; Beta</span></div>
    <h3>Split into 2 teams</h3>
    <div class="btns">
      <button onclick="computeSplit()">Minimize shared items</button>
      <button onclick="clearSplit()">Clear</button>
    </div>
    <div id="splitInfo" class="muted"></div>
    <h3>Raid Setup</h3>
    <div class="btns">
      <button onclick="showImportModal()">Import Raid Setup</button>
      <button onclick="revertRaidLayout()">Revert Swaps</button>
      <button onclick="clearRaidLayout()">Clear Layout</button>
    </div>
    <div id="raidInfo" class="muted"></div>
    <h3>Loot Sources</h3>
    __RAID_CHECKBOXES__
    <h3>Items</h3>
    <div class="btns">
      <button onclick="toggleAll('i_',true)">All</button>
      <button onclick="toggleAll('i_',false)">None</button>
      <button id="itemToggleBtn" onclick="toggleItemList()">Show all</button>
    </div>
    <div id="itemList" class="collapsed">
    __ITEM_CHECKBOXES__
    </div>
    <div class="muted">Edges appear only for items in both filters.</div>
  </div>
  <div id="net"></div>
</div>
<div id="modal-overlay" onclick="if(event.target===this)hideModal()">
  <div id="modal">
    <h3>Paste Raid Setup JSON</h3>
    <textarea id="raidJson" placeholder="Paste the raid composition JSON here..."></textarea>
    <div class="btns">
      <button onclick="hideModal()">Cancel</button>
      <button onclick="applyRaidImport()">Apply</button>
    </div>
  </div>
</div>
<script>
const NODES = __NODES__;
const EDGES = __EDGES__;
const RAIDS = __RAIDS__;
const ITEMS = __ITEMS__;
const ITEM_RAIDS = __ITEM_RAIDS__;

const nodes = new vis.DataSet(NODES);
const edges = new vis.DataSet();
let currentEdges = [];  // mirror of edges DataSet for split computation
let activeSplit = null; // {assign: Uint8Array, teamA, teamB} when a split is shown

let raidLayoutActive = false;
let addedNodeIds = [];
let activePlayerRaid = {}; // player -> raid name when layout is active
let raidOrder = []; // raid names in layout order
let raidRuns = null; // raid name -> [{name, className, color}]
let originalRunsJson = null; // snapshot of raw JSON text from last import
let raidDrawHandler = null;
let selectedPlayer = null;

function cbId(prefix, key){ return prefix + btoa(unescape(encodeURIComponent(key))).replace(/=/g,''); }
function toggleAll(prefix, val){
  if (prefix === 'i_') {
    const activeRaids = new Set(RAIDS.filter(r => document.getElementById(cbId('r_',r)).checked));
    for (const item of ITEMS) {
      const raids = ITEM_RAIDS[item] || [];
      if (raids.some(r => activeRaids.has(r))) document.getElementById(cbId('i_',item)).checked = val;
    }
  } else {
    document.querySelectorAll('input[id^="'+prefix+'"]').forEach(c => { c.checked = val; });
  }
  rebuildEdges();
}

function filterItemCheckboxes() {
  const activeRaids = new Set(RAIDS.filter(r => document.getElementById(cbId('r_',r)).checked));
  const collapsed = document.getElementById('itemList').classList.contains('collapsed');
  let shown = 0;
  for (const item of ITEMS) {
    const raids = ITEM_RAIDS[item] || [];
    const raidVisible = raids.some(r => activeRaids.has(r));
    const lbl = document.getElementById(cbId('i_',item)).closest('label');
    if (!raidVisible) { lbl.style.display = 'none'; continue; }
    if (collapsed && shown >= 5) { lbl.style.display = 'none'; continue; }
    lbl.style.display = '';
    shown++;
  }
}
function toggleItemList() {
  const list = document.getElementById('itemList');
  const btn = document.getElementById('itemToggleBtn');
  list.classList.toggle('collapsed');
  btn.textContent = list.classList.contains('collapsed') ? 'Show all' : 'Show top 5';
  filterItemCheckboxes();
}

function rebuildEdges() {
  filterItemCheckboxes();
  const activeRaids = new Set(RAIDS.filter(r => document.getElementById(cbId('r_',r)).checked));
  const activeItems = new Set(ITEMS.filter(i => document.getElementById(cbId('i_',i)).checked));
  const next = [];
  for (const e of EDGES) {
    if (raidLayoutActive) {
      if (!activePlayerRaid[e.from] || !activePlayerRaid[e.to]) continue;
      if (activePlayerRaid[e.from] !== activePlayerRaid[e.to]) continue;
    }
    const matched = e.items.filter(i => activeRaids.has(i.raid) && activeItems.has(i.item));
    if (matched.length === 0) continue;
    next.push({
      from: e.from, to: e.to,
      value: matched.length,
      weight: matched.length,
      title: matched.length + ' shared:\\n\\u2022 ' + matched.map(i => i.item+' ('+i.raid+')').join('\\n\\u2022 ')
    });
  }
  currentEdges = next;
  edges.clear(); edges.add(next);
  if (activeSplit) updateSplitStats();
  if (raidLayoutActive) {
    const el = document.getElementById('raidInfo').querySelector('b:last-of-type');
    if (el) el.textContent = next.length;
  }
}

// --- Max-Cut via randomized local search ---
function computeSplit() {
  if (raidLayoutActive) { alert('Clear the raid layout first.'); return; }
  const playerIds = NODES.map(n => n.id);
  const idx = new Map(playerIds.map((p,i)=>[p,i]));
  const n = playerIds.length;
  // adjacency weights
  const W = Array.from({length:n}, ()=>new Float64Array(n));
  for (const e of currentEdges) {
    const a = idx.get(e.from), b = idx.get(e.to);
    W[a][b] += e.weight; W[b][a] += e.weight;
  }
  function cutValue(assign) {
    let s = 0;
    for (let i=0;i<n;i++) for (let j=i+1;j<n;j++)
      if (assign[i] !== assign[j]) s += W[i][j];
    return s;
  }
  function localOpt(assign) {
    let improved = true;
    while (improved) {
      improved = false;
      for (let i=0;i<n;i++) {
        let delta = 0;
        for (let j=0;j<n;j++) if (j!==i) {
          delta += (assign[i]===assign[j] ? W[i][j] : -W[i][j]);
        }
        if (delta > 0) { assign[i] ^= 1; improved = true; }
      }
    }
    return assign;
  }
  let best = null, bestVal = -1;
  for (let trial=0; trial<200; trial++) {
    const a = new Uint8Array(n);
    for (let i=0;i<n;i++) a[i] = Math.random()<0.5 ? 0 : 1;
    localOpt(a);
    const v = cutValue(a);
    if (v > bestVal) { bestVal = v; best = a; }
  }
  // color nodes + push left/right
  const teamA = [], teamB = [];
  for (let i=0;i<n;i++) (best[i]===0 ? teamA : teamB).push(playerIds[i]);
  teamA.sort(); teamB.sort();
  activeSplit = {assign: best, teamA, teamB, idx};

  // size arcs so neighbors are ~NODE_STEP apart along the arc
  const NODE_STEP = 100;
  const maxTeam = Math.max(teamA.length, teamB.length);
  // arc spans PI radians, so arcLength = PI * R; need R >= NODE_STEP * (n-1) / PI
  const RADIUS = Math.max(280, NODE_STEP * Math.max(1, maxTeam - 1) / Math.PI);
  const GAP = Math.max(450, RADIUS * 1.2);
  const updates = [];
  for (let i=0;i<n;i++) {
    const team = best[i];
    const arr = team===0 ? teamA : teamB;
    const count = arr.length;
    const pos = arr.indexOf(playerIds[i]);
    // distribute across full PI so endpoints are at top/bottom, not overlapping
    const theta = count === 1 ? Math.PI/2 : Math.PI * pos / (count - 1);
    const cx = team===0 ? -GAP/2 : GAP/2;
    const dir = team===0 ? -1 : 1;
    const x = cx + dir * RADIUS * Math.sin(theta);
    const y = -RADIUS * Math.cos(theta);
    updates.push({id: playerIds[i],
      x, y, fixed: true,
      color: {background: team===0 ? '#1e3a5f' : '#5f1e1e', border: NODES[i].color.border}});
  }
  // no physics: arc is final
  network.setOptions({physics: false});
  nodes.update(updates);
  // unfix so user can still drag after
  setTimeout(() => {
    nodes.update(playerIds.map(id => ({id, fixed: false})));
    network.fit({animation: {duration: 500}});
  }, 50);
  updateSplitStats();
}

function updateSplitStats() {
  if (!activeSplit) return;
  const {assign, teamA, teamB, idx} = activeSplit;
  let cross = 0, intra = 0;
  for (const e of currentEdges) {
    if (assign[idx.get(e.from)] !== assign[idx.get(e.to)]) cross += e.weight;
    else intra += e.weight;
  }
  document.getElementById('splitInfo').innerHTML =
    '<b style="color:#6aa0e0">Team Blue:</b> ' + teamA.join(', ') +
    '<br><br><b style="color:#e06a6a">Team Red:</b> ' + teamB.join(', ') +
    '<br><br>Cross-team shared items: <b>' + cross + '</b>' +
    '<br>Within-team conflicts: <b>' + intra + '</b>';
}

function clearSplit() {
  activeSplit = null;
  nodes.update(NODES.map(n => ({id: n.id, color: n.color, fixed: false})));
  network.setOptions({
    physics: {enabled: true, solver: 'forceAtlas2Based',
      forceAtlas2Based: {gravitationalConstant:-80, springLength:180, springConstant:0.02, damping:0.9},
      stabilization: {enabled: true, iterations: 1000, fit: true}, timestep: 0.3}
  });
  network.stabilize(1000);
  network.once('stabilized', () => {
    network.setOptions({physics: false});
    network.fit({animation: {duration: 500}});
  });
  document.getElementById('splitInfo').innerHTML = '';
}

const network = new vis.Network(document.getElementById('net'), {nodes, edges}, {
  layout: {randomSeed: 42, improvedLayout: true},
  physics: {
    enabled: true, solver: 'forceAtlas2Based',
    forceAtlas2Based: {gravitationalConstant:-80, springLength:180, springConstant:0.02, damping:0.9},
    stabilization: {enabled: true, iterations: 1000, fit: true},
    timestep: 0.3
  },
  edges: {smooth: false, width: 2, hoverWidth: 4},
  interaction: {dragNodes: true, hover: true, zoomView: true, zoomSpeed: 0.3, tooltipDelay: 100, navigationButtons: true}
});
network.once('stabilizationIterationsDone', () => network.setOptions({physics: false}));

document.querySelectorAll('#side input[type=checkbox]').forEach(c => c.addEventListener('change', rebuildEdges));
rebuildEdges();

// --- Swap players between raid boxes ---
function setSelection(id) {
  if (selectedPlayer && selectedPlayer !== id) {
    const n = nodes.get(selectedPlayer);
    if (n && n._origColor) nodes.update({id: selectedPlayer, color: n._origColor, _origColor: null});
  }
  selectedPlayer = id;
  if (id) {
    const n = nodes.get(id);
    const orig = n._origColor || n.color;
    const border = orig.border;
    const hi = {background: '#2d7a8a', border,
                highlight: {background: '#2d7a8a', border}};
    nodes.update({id, _origColor: orig, color: hi});
  }
}
function restoreNodeColor(id) {
  const n = nodes.get(id);
  if (n && n._origColor) nodes.update({id, color: n._origColor, _origColor: null});
}
function swapPlayers(aId, bId) {
  const raidA = activePlayerRaid[aId], raidB = activePlayerRaid[bId];
  if (!raidA || !raidB || raidA === raidB) return;
  // swap positions
  const pos = network.getPositions([aId, bId]);
  nodes.update([
    {id: aId, x: pos[bId].x, y: pos[bId].y},
    {id: bId, x: pos[aId].x, y: pos[aId].y}
  ]);
  restoreNodeColor(aId); restoreNodeColor(bId);
  // swap raid membership
  activePlayerRaid[aId] = raidB; activePlayerRaid[bId] = raidA;
  const ia = raidRuns[raidA].findIndex(m => m.name === aId);
  const ib = raidRuns[raidB].findIndex(m => m.name === bId);
  if (ia >= 0 && ib >= 0) {
    const ma = raidRuns[raidA][ia], mb = raidRuns[raidB][ib];
    raidRuns[raidA][ia] = mb;
    raidRuns[raidB][ib] = ma;
  }
  selectedPlayer = null;
  rebuildEdges();
  network.redraw();
}
network.on('click', params => {
  if (!raidLayoutActive) return;
  const id = params.nodes[0];
  if (!id || !activePlayerRaid[id]) { setSelection(null); return; }
  if (!selectedPlayer) { setSelection(id); return; }
  if (selectedPlayer === id) { setSelection(null); return; }
  if (activePlayerRaid[selectedPlayer] === activePlayerRaid[id]) { setSelection(id); return; }
  swapPlayers(selectedPlayer, id);
});

// --- Raid Setup Import ---

function showImportModal() {
  document.getElementById('modal-overlay').classList.add('show');
  document.getElementById('raidJson').value = '';
  document.getElementById('raidJson').focus();
}
function hideModal() {
  document.getElementById('modal-overlay').classList.remove('show');
}

function parseRaidJson(txt) {
  const data = JSON.parse(txt);
  // build emote -> class name lookups
  const emoteToClass = {};
  const specToClass = {};
  const classColor = {};
  for (const c of data.classes) {
    emoteToClass[c.emoteId] = c.name;
    classColor[c.name] = c.specs[0] ? c.specs[0].color : '#888';
    for (const sp of c.specs) specToClass[sp.emoteId] = c.name;
  }

  const dividers = {};
  for (const d of data.dividers) dividers[d.position] = d.name;
  const divPositions = Object.keys(dividers).map(Number).sort((a,b)=>a-b);
  const gnumToKara = {};
  for (let i = 0; i < data.groups.length; i++) {
    const gpos = data.groups[i].position;
    let kara = 'Unknown';
    for (let j = divPositions.length - 1; j >= 0; j--) {
      if (gpos >= divPositions[j]) { kara = dividers[divPositions[j]]; break; }
    }
    gnumToKara[i + 1] = kara;
  }
  const knownIds = new Set(NODES.map(n => n.id));
  const runs = {};  // raidName -> [{name, className, color}]
  for (const s of data.slots) {
    const kara = gnumToKara[s.groupNumber] || 'Unknown';
    if (!runs[kara]) runs[kara] = [];
    // resolve actual class: use className unless it's Tank/Bench, then look up emotes
    let cls = s.className;
    let color = s.color;
    if (cls === 'Tank' || cls === 'Bench') {
      cls = emoteToClass[s.classEmoteId] || specToClass[s.specEmoteId] || cls;
      color = classColor[cls] || color;
    }
    // resolve name: strip parentheticals, then for "A/B" prefer whichever is in NODES
    let raw = s.name.replace(/\\s*\\(.*?\\)\\s*/g, '').trim();
    let name = raw;
    if (raw.includes('/')) {
      const parts = raw.split('/').map(p => p.trim());
      const found = parts.find(p => knownIds.has(p));
      name = found || parts[0];
    }
    runs[kara].push({name, className: cls, color});
  }
  return runs;
}

function applyRaidImport() {
  let runs;
  try {
    runs = parseRaidJson(document.getElementById('raidJson').value);
  } catch(e) {
    alert('Invalid JSON: ' + e.message);
    return;
  }
  originalRunsJson = document.getElementById('raidJson').value;
  hideModal();
  raidLayoutActive = true;

  // clean up previous import if any
  for (const id of addedNodeIds) { if (nodes.get(id)) nodes.remove(id); }
  addedNodeIds = [];
  nodes.update(NODES.map(n => ({id: n.id, hidden: false, fixed: false})));

  const knownIds = new Set(NODES.map(n => n.id));

  // add nodes for unknown players using JSON class color, dashed border
  for (const members of Object.values(runs)) {
    for (const p of members) {
      if (!knownIds.has(p.name) && !nodes.get(p.name)) {
        const bc = p.color || '#888';
        nodes.add({
          id: p.name, label: p.name, title: p.name + ' (' + p.className + ', not in spreadsheet)',
          shape: 'box',
          color: {background: '#333', border: bc, highlight: {background: '#444', border: bc}},
          borderWidth: 6, borderWidthSelected: 8, margin: 14,
          shapeProperties: {borderDashes: [8, 4]},
          font: {size: 28, color: '#fff', face: 'sans-serif', bold: true}
        });
        addedNodeIds.push(p.name);
      }
    }
  }

  // seed initial positions: circle per raid, raids laid out left-to-right
  raidOrder = Object.keys(runs).sort();
  const NODE_STEP = 140;   // target arc spacing between neighbours
  const MIN_R = 140;
  const RAID_GAP = 260;
  let offsetX = 0;
  const updates = [];
  for (const raidName of raidOrder) {
    const members = runs[raidName];
    const n = members.length;
    // circumference = n * NODE_STEP → R = n * NODE_STEP / (2π)
    const R = Math.max(MIN_R, n * NODE_STEP / (2 * Math.PI));
    const cx = offsetX + R;
    for (let i = 0; i < n; i++) {
      const theta = 2 * Math.PI * i / n - Math.PI / 2;
      updates.push({
        id: members[i].name,
        x: cx + R * Math.cos(theta),
        y: R * Math.sin(theta)
      });
    }
    offsetX += 2 * R + RAID_GAP;
  }

  // player -> raid mapping (drives edge filtering + raid boxes)
  activePlayerRaid = {};
  for (const [raidName, members] of Object.entries(runs)) {
    for (const m of members) activePlayerRaid[m.name] = raidName;
  }

  // hide players not in any raid
  const allRaidPlayers = new Set(Object.values(runs).flat().map(p => p.name));
  for (const n of NODES) {
    if (!allRaidPlayers.has(n.id)) updates.push({id: n.id, hidden: true});
  }

  nodes.update(updates);
  raidRuns = runs;

  // physics off: nodes stay where placed, still draggable
  network.setOptions({physics: false});

  // install per-raid bounding-box renderer (drawn under nodes)
  if (raidDrawHandler) network.off('beforeDrawing', raidDrawHandler);
  raidDrawHandler = (ctx) => {
    const positions = network.getPositions();
    for (const raidName of raidOrder) {
      const members = (raidRuns[raidName] || []).map(m => m.name).filter(id => positions[id]);
      if (members.length === 0) continue;
      let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
      for (const id of members) {
        const p = positions[id];
        if (p.x < minX) minX = p.x; if (p.x > maxX) maxX = p.x;
        if (p.y < minY) minY = p.y; if (p.y > maxY) maxY = p.y;
      }
      const PAD = 80;
      minX -= PAD; maxX += PAD; minY -= PAD + 30; maxY += PAD;
      ctx.save();
      ctx.fillStyle = 'rgba(255,255,255,0.03)';
      ctx.strokeStyle = '#666';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.rect(minX, minY, maxX - minX, maxY - minY);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = '#aaa';
      ctx.font = 'bold 22px sans-serif';
      ctx.textBaseline = 'top';
      ctx.fillText(raidName, minX + 10, minY + 6);
      ctx.restore();
    }
  };
  network.on('beforeDrawing', raidDrawHandler);

  rebuildEdges();
  setTimeout(() => network.fit({animation: {duration: 500}}), 50);

  // info
  function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
  let info = '';
  for (const rn of raidOrder) {
    info += '<b>' + esc(rn) + '</b>: ' + runs[rn].map(p => esc(p.name)).join(', ') + '<br>';
  }
  info += '<br>Within-raid conflicts: <b>' + currentEdges.length + '</b>';
  document.getElementById('raidInfo').innerHTML = info;
}

function revertRaidLayout() {
  if (!originalRunsJson) return;
  document.getElementById('raidJson').value = originalRunsJson;
  applyRaidImport();
}

function clearRaidLayout() {
  if (!raidLayoutActive) return;
  raidLayoutActive = false;
  activePlayerRaid = {};
  raidOrder = [];
  raidRuns = null;
  originalRunsJson = null;
  selectedPlayer = null;

  if (raidDrawHandler) { network.off('beforeDrawing', raidDrawHandler); raidDrawHandler = null; }

  for (const id of addedNodeIds) { if (nodes.get(id)) nodes.remove(id); }
  addedNodeIds = [];

  nodes.update(NODES.map(n => ({id: n.id, hidden: false, fixed: false, color: n.color})));

  network.setOptions({
    physics: {enabled: true, solver: 'forceAtlas2Based',
      forceAtlas2Based: {gravitationalConstant:-80, springLength:180, springConstant:0.02, damping:0.9},
      stabilization: {enabled: true, iterations: 1000, fit: true}, timestep: 0.3}
  });
  network.stabilize(1000);
  network.once('stabilized', () => {
    network.setOptions({physics: false});
    network.fit({animation: {duration: 500}});
  });

  rebuildEdges();
  document.getElementById('raidInfo').innerHTML = '';
}
</script></body></html>"""

def cb_id(prefix, key):
    import base64
    return prefix + base64.b64encode(key.encode()).decode().replace("=", "")

raid_cbs = "\n".join(
    f'<label><input type="checkbox" id="{cb_id("r_", r)}" checked> {r}</label>' for r in raids
)
item_cbs = "\n".join(
    f'<label data-raids="{",".join(item_raids[i])}"><input type="checkbox" id="{cb_id("i_", i)}" checked> {i} <span style="color:#888">({item_player_counts[i]})</span></label>'
    for i in items_all
)

html = (html
    .replace("__RAID_CHECKBOXES__", raid_cbs)
    .replace("__ITEM_CHECKBOXES__", item_cbs)
    .replace("__NODES__", json.dumps(nodes))
    .replace("__EDGES__", json.dumps(edges))
    .replace("__RAIDS__", json.dumps(raids))
    .replace("__ITEMS__", json.dumps(items_all))
    .replace("__ITEM_RAIDS__", json.dumps(item_raids)))

if "beta" in TARGETS:
    with open("graph.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote graph.html  ({len(nodes)} nodes, {len(edges)} edges, {len(raids)} raids, {len(items_all)} items)")

if "promote" in TARGETS:
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote index.html  (promoted beta)")

# --- Stable page (index.html) — same data, no raid import ---
stable_html = """<!doctype html>
<html><head><meta charset="utf-8"><title>Gear Collision Graph</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
  html,body{margin:0;height:100vh;overflow:hidden;background:#222;color:#eee;font-family:sans-serif;font-size:16px}
  #wrap{display:flex;height:100vh;width:100vw}
  #side{width:360px;padding:20px;border-right:1px solid #444;box-sizing:border-box;overflow-y:auto;flex-shrink:0}
  #side h3{margin:22px 0 8px 0;font-size:18px;text-transform:uppercase;color:#aaa;letter-spacing:1px}
  #side h3:first-child{margin-top:0}
  #net{flex:1;height:100vh;background:#222}
  label{display:block;margin:8px 0;cursor:pointer;font-size:17px;line-height:1.3}
  input[type=checkbox]{width:18px;height:18px;vertical-align:middle;margin-right:6px}
  .muted{color:#888;font-size:14px;margin-top:18px}
  .btns{margin:8px 0 12px 0}
  .btns button{background:#333;color:#ddd;border:1px solid #555;padding:6px 12px;font-size:14px;cursor:pointer;margin-right:6px;border-radius:3px}
  .btns button:hover{background:#444}
</style></head>
<body><div id="wrap">
  <div id="side">
    <div style="text-align:right;margin-bottom:8px"><a href="graph.html" style="color:#6af;font-size:13px;text-decoration:none;border:1px solid #6af;padding:3px 10px;border-radius:3px">&#129514; Beta</a></div>
    <h3>Split into 2 teams</h3>
    <div class="btns">
      <button onclick="computeSplit()">Minimize shared items</button>
      <button onclick="clearSplit()">Clear</button>
    </div>
    <div id="splitInfo" class="muted"></div>
    <h3>Loot Sources</h3>
    __RAID_CHECKBOXES__
    <h3>Items</h3>
    <div class="btns">
      <button onclick="toggleAll('i_',true)">All</button>
      <button onclick="toggleAll('i_',false)">None</button>
      <button id="itemToggleBtn" onclick="toggleItemList()">Show all</button>
    </div>
    <div id="itemList" class="collapsed">
    __ITEM_CHECKBOXES__
    </div>
    <div class="muted">Edges appear only for items in both filters.</div>
  </div>
  <div id="net"></div>
</div>
<script>
const NODES = __NODES__;
const EDGES = __EDGES__;
const RAIDS = __RAIDS__;
const ITEMS = __ITEMS__;
const ITEM_RAIDS = __ITEM_RAIDS__;
const nodes = new vis.DataSet(NODES);
const edges = new vis.DataSet();
let currentEdges = [];
let activeSplit = null;
function cbId(prefix, key){ return prefix + btoa(unescape(encodeURIComponent(key))).replace(/=/g,''); }
function toggleAll(prefix, val){
  if (prefix === 'i_') {
    const activeRaids = new Set(RAIDS.filter(r => document.getElementById(cbId('r_',r)).checked));
    for (const item of ITEMS) {
      const raids = ITEM_RAIDS[item] || [];
      if (raids.some(r => activeRaids.has(r))) document.getElementById(cbId('i_',item)).checked = val;
    }
  } else {
    document.querySelectorAll('input[id^="'+prefix+'"]').forEach(c => { c.checked = val; });
  }
  rebuildEdges();
}
function filterItemCheckboxes() {
  const activeRaids = new Set(RAIDS.filter(r => document.getElementById(cbId('r_',r)).checked));
  const collapsed = document.getElementById('itemList').classList.contains('collapsed');
  let shown = 0;
  for (const item of ITEMS) {
    const raids = ITEM_RAIDS[item] || [];
    const raidVisible = raids.some(r => activeRaids.has(r));
    const lbl = document.getElementById(cbId('i_',item)).closest('label');
    if (!raidVisible) { lbl.style.display = 'none'; continue; }
    if (collapsed && shown >= 5) { lbl.style.display = 'none'; continue; }
    lbl.style.display = ''; shown++;
  }
}
function toggleItemList(){const l=document.getElementById('itemList'),b=document.getElementById('itemToggleBtn');l.classList.toggle('collapsed');b.textContent=l.classList.contains('collapsed')?'Show all':'Show top 5';filterItemCheckboxes();}
function rebuildEdges() {
  filterItemCheckboxes();
  const activeRaids = new Set(RAIDS.filter(r => document.getElementById(cbId('r_',r)).checked));
  const activeItems = new Set(ITEMS.filter(i => document.getElementById(cbId('i_',i)).checked));
  const next = [];
  for (const e of EDGES) {
    const matched = e.items.filter(i => activeRaids.has(i.raid) && activeItems.has(i.item));
    if (matched.length === 0) continue;
    next.push({from:e.from,to:e.to,value:matched.length,weight:matched.length,
      title:matched.length+' shared:\\n\\u2022 '+matched.map(i=>i.item+' ('+i.raid+')').join('\\n\\u2022 ')});
  }
  currentEdges = next; edges.clear(); edges.add(next);
  if (activeSplit) updateSplitStats();
}
function computeSplit() {
  const playerIds = NODES.map(n=>n.id);
  const idx = new Map(playerIds.map((p,i)=>[p,i]));
  const n = playerIds.length;
  const W = Array.from({length:n},()=>new Float64Array(n));
  for (const e of currentEdges){const a=idx.get(e.from),b=idx.get(e.to);W[a][b]+=e.weight;W[b][a]+=e.weight;}
  function cutValue(assign){let s=0;for(let i=0;i<n;i++)for(let j=i+1;j<n;j++)if(assign[i]!==assign[j])s+=W[i][j];return s;}
  function localOpt(assign){let improved=true;while(improved){improved=false;for(let i=0;i<n;i++){let delta=0;for(let j=0;j<n;j++)if(j!==i)delta+=(assign[i]===assign[j]?W[i][j]:-W[i][j]);if(delta>0){assign[i]^=1;improved=true;}}}return assign;}
  let best=null,bestVal=-1;
  for(let trial=0;trial<200;trial++){const a=new Uint8Array(n);for(let i=0;i<n;i++)a[i]=Math.random()<0.5?0:1;localOpt(a);const v=cutValue(a);if(v>bestVal){bestVal=v;best=a;}}
  const teamA=[],teamB=[];for(let i=0;i<n;i++)(best[i]===0?teamA:teamB).push(playerIds[i]);teamA.sort();teamB.sort();
  activeSplit={assign:best,teamA,teamB,idx};
  const NODE_STEP=100,maxTeam=Math.max(teamA.length,teamB.length);
  const RADIUS=Math.max(280,NODE_STEP*Math.max(1,maxTeam-1)/Math.PI),GAP=Math.max(450,RADIUS*1.2);
  const updates=[];
  for(let i=0;i<n;i++){const team=best[i],arr=team===0?teamA:teamB,count=arr.length,pos=arr.indexOf(playerIds[i]);
    const theta=count===1?Math.PI/2:Math.PI*pos/(count-1),cx=team===0?-GAP/2:GAP/2,dir=team===0?-1:1;
    updates.push({id:playerIds[i],x:cx+dir*RADIUS*Math.sin(theta),y:-RADIUS*Math.cos(theta),fixed:true,
      color:{background:team===0?'#1e3a5f':'#5f1e1e',border:NODES[i].color.border}});}
  network.setOptions({physics:false});nodes.update(updates);
  setTimeout(()=>{nodes.update(playerIds.map(id=>({id,fixed:false})));network.fit({animation:{duration:500}});},50);
  updateSplitStats();
}
function updateSplitStats(){if(!activeSplit)return;const{assign,teamA,teamB,idx}=activeSplit;let cross=0,intra=0;
  for(const e of currentEdges){if(assign[idx.get(e.from)]!==assign[idx.get(e.to)])cross+=e.weight;else intra+=e.weight;}
  document.getElementById('splitInfo').innerHTML='<b style="color:#6aa0e0">Team Blue:</b> '+teamA.join(', ')+'<br><br><b style="color:#e06a6a">Team Red:</b> '+teamB.join(', ')+'<br><br>Cross-team shared items: <b>'+cross+'</b><br>Within-team conflicts: <b>'+intra+'</b>';}
function clearSplit(){activeSplit=null;nodes.update(NODES.map(n=>({id:n.id,color:n.color,fixed:false})));
  network.setOptions({physics:{enabled:true,solver:'forceAtlas2Based',forceAtlas2Based:{gravitationalConstant:-80,springLength:180,springConstant:0.02,damping:0.9},stabilization:{enabled:true,iterations:1000,fit:true},timestep:0.3}});
  network.stabilize(1000);network.once('stabilized',()=>{network.setOptions({physics:false});network.fit({animation:{duration:500}});});
  document.getElementById('splitInfo').innerHTML='';}
const network = new vis.Network(document.getElementById('net'),{nodes,edges},{
  layout:{randomSeed:42,improvedLayout:true},
  physics:{enabled:true,solver:'forceAtlas2Based',forceAtlas2Based:{gravitationalConstant:-80,springLength:180,springConstant:0.02,damping:0.9},stabilization:{enabled:true,iterations:1000,fit:true},timestep:0.3},
  edges:{smooth:false,width:2,hoverWidth:4},
  interaction:{dragNodes:true,hover:true,zoomView:true,zoomSpeed:0.3,tooltipDelay:100,navigationButtons:true}
});
network.once('stabilizationIterationsDone',()=>network.setOptions({physics:false}));
document.querySelectorAll('#side input[type=checkbox]').forEach(c=>c.addEventListener('change',rebuildEdges));
rebuildEdges();
</script></body></html>"""

stable_html = (stable_html
    .replace("__RAID_CHECKBOXES__", raid_cbs)
    .replace("__ITEM_CHECKBOXES__", item_cbs)
    .replace("__NODES__", json.dumps(nodes))
    .replace("__EDGES__", json.dumps(edges))
    .replace("__RAIDS__", json.dumps(raids))
    .replace("__ITEMS__", json.dumps(items_all))
    .replace("__ITEM_RAIDS__", json.dumps(item_raids)))

if "stable" in TARGETS:
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(stable_html)
    print(f"wrote index.html  (stable)")
