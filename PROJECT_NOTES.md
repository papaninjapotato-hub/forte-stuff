# Forte Gear Collision Graph — Project Notes

## Purpose
Visualize loot contention in a TBC Classic raid roster. Input is `Forte -TBC- Gear_Alts Tracker - Phase 1.csv`. Output is a self-contained HTML page showing players as nodes and shared-item needs as edges, with filters, a max-cut team splitter, and raid setup import.

## Files
- `build_graph.py` — builds the HTML page(s) from the CSV. Targets: `beta` → `graph.html` (full feature set incl. raid import), `stable` → `index.html` (reduced, no raid import), `promote` → writes beta HTML to `index.html`, `all` → `beta` + `promote`. Default (no args): `beta stable`. Runs `audit_csv.py` first unless `--no-audit` is passed.
- `gear_data.py` — shared module: normalization tables (`ITEM_ALIASES`, `FALLEN_SLOT`, `T4_GROUP`, `CLASS_COLOR`), `norm_item()`, and `load_rows()` CSV loader. **Single source of truth** — don't duplicate these in other scripts; import from here.
- `audit_csv.py` — CSV sanity check. Reuses `gear_data`. Flags singletons, raw-text variants, near-duplicate items, raid-name typos, unknown classes. Advisory only (exit code always 0). Run manually with `python3 audit_csv.py` or let it fire automatically during a build.
- `Forte -TBC- Gear_Alts Tracker - Phase 1.csv` — source roster. Updated periodically. Renamed from the original `Forte -TBC- Gear Tracker - Phase 1.csv`.
- `index.html` — production page served by GitHub Pages. Currently the **promoted beta** (has raid import). Rebuild as stable or beta depending on what you want to deploy.
- `graph.html` — beta page. Has a "← Stable" link back to `index.html`.
- `Sat.json` / `Sun.json` — raid composition JSONs (from Discord comp tool). Used with the Import Raid Setup feature.

## Build & deploy
```bash
# Rebuild beta only (graph.html):
python3 build_graph.py beta

# Rebuild stable only (index.html, reduced):
python3 build_graph.py stable

# Promote beta → index.html (so main page == beta):
python3 build_graph.py promote

# Default: beta + stable (graph.html + reduced index.html):
python3 build_graph.py

# Everything current (beta + promoted index.html):
python3 build_graph.py all

# Deploy whatever you built:
git add index.html graph.html && git commit -m "Update" && git push
```
Note: `stable` and `promote` both target `index.html`; the script refuses to run them together. The script's built-in default (no args) is `beta stable`, but during an assistant session the default action is `beta` only — see "Working preferences".
Hosted on GitHub Pages at user `papaninjapotato-hub`, repo `forte-stuff`. Pages is set to deploy from `main` / root.

## Data model / normalization rules (authoritative)
1. **Player name blank → carry forward from previous row** (spreadsheet quirk).
2. **Ignore alts** — only the `Player Name` column matters; `Alt Name` / `Alt Class` are unused.
3. **Classes** can be blank on some rows; fill from the same player's other rows (first non-blank wins).
4. **Status column** — rows with `Status: Owned` are skipped (player already has the item, no contention).
5. **Raid column** — rows with a blank `Raid Name` are skipped entirely (non-raid items like world drops, crafted, vendor). They can't collide by raid source, so they'd just noise the graph.
6. **Item-name normalization** in `norm_item()` (see `gear_data.py`):
   - Explicit aliases in `ITEM_ALIASES` (typos, case, apostrophes):
     - Bladespire Warbrands→Warbands, Ogri→Ogre, Magtheridons→Magtheridon's, Vambraces→Vambracers, Eredar Oblieration→Obliteration
     - Skullker's→Skulker's, Ring of a Thousand→Ring of Thousand, Garona's Signet RIng→Ring, sunfury→Sunfury
     - Kings Defender→King's Defender, Whirlwind bracers→Whirlwind Bracers
     - T4 Gloves→T4 Hands
   - **Druid T4 set (Malorne)**: Stag-Helm→T4 Head, Mantle→T4 Shoulders, Breastplate→T4 Chest, Gauntlets→T4 Hands, Greaves→T4 Legs
   - **Priest T4 set (Incarnate)**: Light-Collar of the Incarnate→T4 Head
   - `T4 <slot>` title-cased (handles `T4 chest`, `t4 Shoulders` etc.). `T4 Helm` and `Voidheart Crown T4 Head` → `T4 Head`.
   - `<noun> of the Fallen (Champion|Defender|Hero)` → corresponding `T4 <slot>` via `FALLEN_SLOT` map (Helm→Head, Chestguard→Chest, Mantle/Pauldrons→Shoulders, etc.). The Champion/Defender/Hero label is discarded; the player's class determines the token group.
   - **Canonical dedup (fallback, no alias needed)**: items not caught above are deduplicated by a canonical key that ignores case, apostrophes, and hyphens/underscores/slashes. Example: `Drape of the dark Reavers` and `Drape of the Dark Reavers` merge automatically. Display name picks the "prettiest" raw form seen (most uppercase letters, then most punctuation, then longest). `load_rows()` does a prepass to prime this map, so output is deterministic and independent of CSV row order.
7. **T4 class groups (USER-AUTHORITATIVE, do not "correct" to wowhead):**
   - `WDP` = Warrior, Druid, Priest
   - `HMW` = Hunter, Mage, Warlock
   - `PRS` = Paladin, Rogue, Shaman
   
   Any item that starts with `T4 ` (after normalization) gets suffixed `[<group>]` based on the player's class. Two players collide on T4 only if they share the group.

## Graph construction
- Vertex per player, edge per pair of players who both need at least one normalized item.
- Edge carries list of `{item, raid}` for tooltips + filtering.
- Edge weight = number of items currently passing the filters.
- Isolated players (like Selmy) render with no edges — intentional.

## UI features (beta / graph.html)

### Sidebar (360px wide, scrollable)
Order top → bottom:
1. **Split into 2 teams** — max-cut via randomized local search (200 trials). Blocked during raid layout mode.
2. **Raid Setup**:
   - **Import Raid Setup** — modal popup, paste Discord comp tool JSON.
   - **Revert Swaps** — reapplies the last imported JSON (undoes all manual swaps).
   - **Clear Layout** — exits raid-layout mode, returns to the normal stabilized view.
3. **Loot Sources** checkboxes (Kara / Gruul Lair / Maggy).
4. **Items** checkboxes, sorted by contestedness desc with `(N)` suffix.
   - **Collapsed by default** to the top 5 most-contested. "Show all" button toggles; pure visual, no effect on filter logic.
   - **Items filter by raid**: unchecking a raid hides items that only drop from that raid. Items from multiple raids stay visible if any of their raids is checked.
   - **All / None** operate on every item passing the loot-source filter, regardless of collapse state.

### Raid Setup Import
- Parses the Discord composition tool JSON format (has `slots`, `groups`, `dividers`, `classes` arrays).
- Extracts raid run names from `dividers`, maps groups to runs.
- **Bench players included** (not skipped).
- **Name resolution**: for `A/B` format names (e.g. `Mogryn/Syraah`), prefers whichever name exists in the CSV. Strips `(parentheticals)` from names.
- **Class resolution for Tank/Bench slots**: `className` is "Tank"/"Bench" in the JSON; actual class resolved via `classEmoteId` / `specEmoteId` → class lookup from the JSON's `classes` array.
- **New player nodes**: players not in the CSV get nodes with their class color (from JSON) and **dashed borders** to distinguish them from spreadsheet players.
- **Layout**: physics off; each raid's members are placed on a circle whose radius scales with member count; raids laid out left-to-right. Labeled bounding rectangles drawn via `network.on('beforeDrawing')` using live `getPositions()` (so boxes follow drags and swaps).
- **Edges**: only within-raid edges shown. Filter checkboxes still work and update live.
- **Tooltip** on edges uses `\n• ` separators (plain-text; vis-network does not render HTML in `title` by default).
- **Re-import**: safe to import again without clearing first (cleans up previous import's nodes and state).

### Swap players between raids (beta, active only in raid layout)
- Click a player → slowly pulsing teal fill (`#2d7a8a` ↔ `#1a4a55`, 700ms) marks selection.
- Click another player in the **same** raid → selection moves.
- Click a player in a **different** raid → positions swap, raid membership updates in `activePlayerRaid` and `raidRuns`, edges rebuild, selection clears, original colors restored.
- Click empty canvas → deselect.
- **Revert Swaps** button restores the imported roster exactly (stored `originalRunsJson` snapshot → reapplies import).

### Graph canvas (vis-network)
- Nodes: rounded boxes with `#333` fill, 28px white bold text, 6px class-colored border.
- **Straight edges** (`smooth: false`), base width 2, hover width 4. No explicit `color` override (uses vis defaults, matching stable).
- **Tooltips**: edge tooltips show shared items, `\n• ` separated. Styled via `div.vis-tooltip` CSS.
- **Zoom**: mouse wheel zoom (`zoomSpeed: 0.3`), navigation buttons visible.
- **Default (non-raid) layout**: forceAtlas2Based with `randomSeed: 42`; physics disables after stabilization.
- **Raid layout mode**: physics off immediately, positions seeded by the circle layout. Nodes remain draggable.
- Clear split/layout uses `network.stabilize()` + `stabilized` event to avoid visible jelly physics.

## Known audit points
- Last audit (39 players, 160 edges, 28 contested items) confirmed all within-raid edges for Sun.json match expected item overlaps exactly (9 edges across 3 Kara runs).
- Owned items correctly excluded (Synod T4 Chest, Trujil T4 Chest, Selmy Vambracers, Nyxria Greaves, Syraah Band of Crimson Fury).

## Known bugs / open items
- ~~**T4 Shoulders shows when only Kara selected**~~ — Fixed. Light-Collar of the Incarnate was incorrectly mapped to T4 Shoulders instead of T4 Head.
- Inline vis-network JS so the HTML works fully offline (not done yet).
- Swap randomized local search for an exact ILP solver if user wants guaranteed-optimal splits.
- No fuzzy name matching for raid import (e.g. `Varkk` in JSON vs `Varrk` in CSV) — exact match only, creates new node for mismatches.
- `raid_by_player` dict in `build_graph.py` overwrites if a player lists the same item under multiple raids — currently impossible with the data but fragile.

## GitHub auth context
- User logged in via Google OAuth → no password. Pushes use a fine-grained PAT.
- PAT needs **Contents: Read and write** scoped to the target repo.
- Per-host credential storage set up via: `git config --global credential.https://github.com.helper store`

## Working preferences (assistant must follow)
- **Default build command is `python3 build_graph.py beta`** — only rebuild `graph.html` unless the user explicitly says stable, promote, or all. Do **not** touch `index.html` implicitly.
- **Physics is disabled in the raid-layout view by default.** User dislikes physics-driven layouts; prefer deterministic placements with `dragNodes: true` so nodes remain movable without auto-settling.
- **Do not "correct" T4 class groups against wowhead.** The WDP/HMW/PRS groups in the normalization section are authoritative; treat any discrepancy as the spec, not a bug.
- **Keep beta and stable visually consistent** for features present in both (edge color, tooltip format, etc.). Changes that diverge should be intentional beta-only features (raid import, swap, collapse).
- **Tooltips in vis-network `title` are plain text** — use `\n• ` for lists, not `<br>•`. HTML-in-title is not rendered with the current setup.
- **Prefer canvas drawing over invisible node tricks.** The old "background box" nodes with huge `widthConstraint` broke hover/tooltips because they intercepted pointer events with no z-order control. Group rectangles are drawn via `network.on('beforeDrawing')` using live `getPositions()`.
