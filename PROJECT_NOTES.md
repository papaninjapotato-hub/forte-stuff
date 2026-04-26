# Forte Gear Collision Graph — Project Notes

## Purpose
Visualize loot contention in a TBC Classic raid roster. Input is `Forte -TBC- Gear_Alts Tracker - Phase 1.csv`. Output is a self-contained HTML page showing players as nodes and shared-item needs as edges, with filters, a max-cut team splitter, and raid setup import.

## Files
- `build_graph.py` — single script that parses the CSV and emits BOTH `graph.html` (beta, full feature set) and `index.html` (stable, no raid-import UI).
- `Forte -TBC- Gear_Alts Tracker - Phase 1.csv` — source roster. Updated periodically. Renamed from the original `Forte -TBC- Gear Tracker - Phase 1.csv`.
- `index.html` — stable/production page, generated. Has a "🧪 Beta" link to `graph.html`.
- `graph.html` — beta page, generated. Has a "← Stable" link back to `index.html`.
- `Sat.json` / `Sun.json` — raid composition JSONs (from Discord comp tool). Used with the Import Raid Setup feature on the beta page.

## Build & deploy
```bash
# Rebuild both pages (stable + beta) from the CSV:
python3 build_graph.py

# Deploy:
git add index.html graph.html && git commit -m "Update" && git push
```
Both HTML files are regenerated every build from the same data; there is no manual promote step.
Hosted on GitHub Pages at user `papaninjapotato-hub`, repo `forte-stuff`. Pages is set to deploy from `main` / root.

## Data model / normalization rules (authoritative)
1. **Player name blank → carry forward from previous row** (spreadsheet quirk).
2. **Ignore alts** — only the `Player Name` column matters; `Alt Name` / `Alt Class` are unused.
3. **Classes** can be blank on some rows; fill from the same player's other rows (first non-blank wins).
4. **Status column** — rows with `Status: Owned` are skipped (player already has the item, no contention).
5. **Item-name normalization** in `norm_item()`:
   - Explicit aliases in `ITEM_ALIASES` (typos, case, apostrophes):
     - Bladespire Warbrands→Warbands, Ogri→Ogre, Magtheridons→Magtheridon's, Vambraces→Vambracers, Eredar Oblieration→Obliteration
     - Skullker's→Skulker's, Ring of a Thousand→Ring of Thousand, Garona's Signet RIng→Ring, sunfury→Sunfury
     - Kings Defender→King's Defender, Whirlwind bracers→Whirlwind Bracers
     - T4 Gloves→T4 Hands
   - **Druid T4 set (Malorne)**: Stag-Helm→T4 Head, Mantle→T4 Shoulders, Breastplate→T4 Chest, Gauntlets→T4 Hands, Greaves→T4 Legs
   - **Priest T4 set (Incarnate)**: Light-Collar of the Incarnate→T4 Shoulders
   - `T4 <slot>` title-cased (handles `T4 chest`, `t4 Shoulders` etc.). `T4 Helm` and `Voidheart Crown T4 Head` → `T4 Head`.
   - `<noun> of the Fallen (Champion|Defender|Hero)` → corresponding `T4 <slot>` via `FALLEN_SLOT` map (Helm→Head, Chestguard→Chest, Mantle/Pauldrons→Shoulders, etc.). The Champion/Defender/Hero label is discarded; the player's class determines the token group.
6. **T4 class groups (USER-AUTHORITATIVE, do not "correct" to wowhead):**
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
- **Loot Sources** checkboxes (Kara / Gruul Lair / Maggy).
- **Items** checkboxes, sorted by contestedness desc with `(N)` suffix. Has All/None buttons.
  - **Items filter by raid**: unchecking a raid hides items that only drop from that raid. Items from multiple raids stay visible if any of their raids is checked. All/None only affects visible items.
- **Split into 2 teams** button: max-cut via randomized local search (200 trials). Blocked during raid layout mode.
- **Raid Setup** section:
  - **Import Raid Setup** — opens modal popup, paste Discord comp tool JSON.
  - **Clear Layout** — reverts to normal physics-based view.

### Raid Setup Import (beta feature)
- Parses the Discord composition tool JSON format (has `slots`, `groups`, `dividers`, `classes` arrays).
- Extracts raid run names from `dividers`, maps groups to runs.
- **Bench players included** (not skipped).
- **Name resolution**: for `A/B` format names (e.g. `Mogryn/Syraah`), prefers whichever name exists in the CSV. Strips `(parentheticals)` from names.
- **Class resolution for Tank/Bench slots**: `className` is "Tank"/"Bench" in the JSON, so actual class is resolved via `specEmoteId` → class lookup from the JSON's `classes` array.
- **New player nodes**: players not in the CSV get nodes with their class color (from JSON) and **dashed borders** to distinguish them from spreadsheet players.
- **Layout**: each raid gets a labeled box, members arranged in a 5-column grid inside.
- **Edges**: only within-raid edges shown. Filter checkboxes still work and update live.
- **Re-import**: safe to import again without clearing first (cleans up previous import's nodes).

### Graph canvas (vis-network)
- Nodes: rounded boxes with `#333` fill, 28px white bold text, 6px class-colored border.
- **Straight edges** (`smooth: false`), base width 2, hover width 4, color changes on hover.
- **Tooltips**: HTML-formatted edge tooltips showing shared items. Styled with `div.vis-tooltip` CSS.
- **Zoom**: mouse wheel zoom enabled (`zoomSpeed: 0.3`), navigation buttons visible.
- Layout: forceAtlas2Based with `randomSeed: 42`. Physics disables after stabilization.
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
