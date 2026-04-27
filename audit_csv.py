#!/usr/bin/env python3
"""Sanity-check the gear tracker CSV. Run standalone or invoked by build_graph.py.

Flags typo-prone anomalies:
  1. Singletons — normalized items wanted by exactly one player (advisory)
  2. Normalized items whose raw CSV text varies across rows (candidates for a new alias
     if the canonical dedup didn't catch them)
  3. Near-duplicate normalized items (fuzzy similarity)
  4. Same item listed under multiple raid names
  5. Unexpected raid-name values
  6. Unknown classes

Exit code is always 0 — this is advisory, not a gate.
"""
from collections import defaultdict, Counter
from difflib import SequenceMatcher

from gear_data import norm_item, load_rows

KNOWN_CLASSES = {"Warrior","Druid","Priest","Hunter","Mage","Warlock","Paladin","Rogue","Shaman"}
KNOWN_RAIDS   = {"Kara","Gruul Lair","Maggy"}

def main():
    rows, player_class, skipped_no_raid = load_rows()

    norm_raws    = defaultdict(Counter)
    norm_players = defaultdict(set)
    norm_raids   = defaultdict(set)
    for p, raw, raid in rows:
        n = norm_item(raw)
        norm_raws[n][raw] += 1
        norm_players[n].add(p)
        norm_raids[n].add(raid)

    print(f"=== CSV audit: {len(rows)} needs, {len(norm_raws)} distinct items, {len(player_class)} players"
          + (f"; skipped {skipped_no_raid} rows with blank raid" if skipped_no_raid else "") + " ===\n")
    issues = 0

    singletons = sorted((n, next(iter(norm_players[n])), next(iter(v))) for n,v in norm_raws.items() if len(norm_players[n])==1)
    print(f"[1] Singletons ({len(singletons)}) — only 1 player, check for typos:")
    for n, p, raw in singletons:
        raids = "/".join(sorted(norm_raids[n]))
        raw_disp = f'   raw="{raw}"' if raw != n else ""
        print(f"    {n:45s} {p:14s} {raids}{raw_disp}")
    print()

    print("[2] Items with varying raw text (consider adding to ITEM_ALIASES):")
    found = False
    for n, counter in sorted(norm_raws.items()):
        raws = set(counter.keys())
        if len(raws) > 1 or (len(raws) == 1 and next(iter(raws)) != n):
            variants = ", ".join(f'"{r}"×{c}' for r,c in counter.most_common())
            print(f"    {n}  <-  {variants}")
            found = True; issues += 1
    if not found: print("    (none)")
    print()

    print("[3] Near-duplicate normalized items (similarity ≥ 0.85):")
    items = sorted(norm_raws.keys()); found = False
    for i,a in enumerate(items):
        for b in items[i+1:]:
            # Same T4 slot in different class groups → not a dup (build adds [group] suffix).
            if a.startswith("T4 ") and b.startswith("T4 ") and a.split()[:2]==b.split()[:2]: continue
            if SequenceMatcher(None, a.lower(), b.lower()).ratio() >= 0.85:
                print(f"    {a!r}  ~  {b!r}")
                found = True; issues += 1
    if not found: print("    (none)")
    print()

    print("[4] Items appearing under multiple raid names:")
    found = False
    for n, raids in sorted(norm_raids.items()):
        if len(raids) > 1:
            print(f"    {n}: {sorted(raids)}")
            found = True; issues += 1
    if not found: print("    (none)")
    print()

    raid_counts = Counter(raid for _,_,raid in rows)
    unknown_raids = [r for r in raid_counts if r not in KNOWN_RAIDS]
    print("[5] Raid names:")
    for k,v in raid_counts.most_common():
        mark = "  ← unknown" if k not in KNOWN_RAIDS else ""
        print(f"    {v:3d}  {k!r}{mark}")
    if unknown_raids: issues += len(unknown_raids)
    print()

    unknown_cls = {p:c for p,c in player_class.items() if c not in KNOWN_CLASSES}
    print("[6] Unknown classes:")
    if unknown_cls:
        for p,c in sorted(unknown_cls.items()): print(f"    {p}: {c!r}")
        issues += len(unknown_cls)
    else:
        print("    (none)")
    print()

    print(f"=== Audit finished. Definite issues (cats 2/3/4/5/6): {issues}. Category 1 is advisory. ===")

if __name__ == "__main__":
    main()
