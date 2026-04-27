"""Shared normalization + CSV loading for the Forte gear graph.

Used by build_graph.py (for graph construction) and audit_csv.py (for sanity checks).
"""
import csv, re
from collections import defaultdict

CSV_PATH = "Forte -TBC- Gear_Alts Tracker - Phase 1.csv"

T4_GROUP = {
    "Warrior":"WDP","Druid":"WDP","Priest":"WDP",
    "Hunter":"HMW","Mage":"HMW","Warlock":"HMW",
    "Paladin":"PRS","Rogue":"PRS","Shaman":"PRS",
}
CLASS_COLOR = {
    "Warrior":"#C79C6E","Druid":"#FF7D0A","Priest":"#FFFFFF",
    "Hunter":"#ABD473","Mage":"#69CCF0","Warlock":"#9482C9",
    "Paladin":"#F58CBA","Rogue":"#FFF569","Shaman":"#0070DE",
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
# "... of the Fallen Champion/Defender/Hero" rows: map noun → T4 slot.
FALLEN_SLOT = {
    "helm":"Head","chestguard":"Chest","pauldrons":"Shoulders","mantle":"Shoulders",
    "gauntlets":"Hands","gloves":"Hands","handguards":"Hands",
    "greaves":"Legs","leggings":"Legs","trousers":"Legs",
}

def _canon_key(s):
    s = s.lower().replace("'", "").replace("’", "")
    s = re.sub(r"[\-_/]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

_canon_seen = {}  # canon_key -> display form (prettier wins)

def _prettier(a, b):
    score = lambda x: (sum(c.isupper() for c in x), x.count("'")+x.count("-"), len(x))
    return a if score(a) >= score(b) else b

def norm_item(raw):
    s = re.sub(r"\s+", " ", raw.strip())
    key = s.lower()
    if key in ITEM_ALIASES:
        return ITEM_ALIASES[key]
    m = re.match(r"^(\w+)\s+of\s+the\s+fallen\s+(champion|defender|hero)$", s, flags=re.I)
    if m:
        slot = FALLEN_SLOT.get(m.group(1).lower())
        if slot:
            return f"T4 {slot}"
    m = re.match(r"^(t4)\s+(\w+)(.*)$", s, flags=re.I)
    if m:
        return f"T4 {m.group(2).capitalize()}{m.group(3)}"
    ck = _canon_key(s)
    prev = _canon_seen.get(ck)
    _canon_seen[ck] = _prettier(prev, s) if prev else s
    return _canon_seen[ck]

def load_rows(path=CSV_PATH):
    """Return (rows, player_class, skipped_no_raid).

    rows: list of (player, raw_item, raid), filtered to skip Owned and blank-raid rows.
    player_class: {player: first-seen non-blank class}.
    Also runs a prepass so norm_item returns the prettiest display form regardless of row order.
    """
    rows = []
    player_class = {}
    skipped_no_raid = 0
    with open(path, newline="", encoding="utf-8") as f:
        last = None
        for r in csv.DictReader(f):
            p = r["Player Name"].strip() or last
            if not p: continue
            last = p
            cls = r["Class"].strip()
            if cls: player_class.setdefault(p, cls)
            if r.get("Status", "").strip().lower() == "owned":
                continue
            raw = r["Item Name"].strip()
            if not raw: continue
            raid = r["Raid Name"].strip()
            if not raid:
                skipped_no_raid += 1
                continue
            rows.append((p, raw, raid))
    # Prepass: prime canonical display map so first call order doesn't matter.
    for _, raw, _ in rows: norm_item(raw)
    return rows, player_class, skipped_no_raid
