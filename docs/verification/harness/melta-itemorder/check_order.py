"""Print where the melta item sorts, straight out of a Factorio --dump-data dump.

The crafting menu / item lists order entries by three keys, outermost first:
item-group `order`, item-subgroup `order`, then the item's own `order`. Within an
order string Factorio ignores the text in square brackets (it is there for humans)
and compares numbers numerically, so `b[turret]-c[flamethrower-turret]-a[melta-turret]`
is the key `b-c-a`.

This script prints the whole turret subgroup in sorted order and marks the melta, and
repeats the sort with plain string comparison so a key that only works under one
reading of the rule cannot pass silently.

Usage: python check_order.py <dump.json> [item]
"""
import json
import re
import sys

dump_path = sys.argv[1]
item_name = sys.argv[2] if len(sys.argv) > 2 else "melta-turret"

data = json.load(open(dump_path, encoding="utf-8"))
items = data["item"]
subgroups = data["item-subgroup"]
groups = data["item-group"]

if item_name not in items:
    sys.exit("FAIL: no item prototype named %r in the dump" % item_name)

item = items[item_name]
subgroup = subgroups.get(item.get("subgroup"))
group = groups.get(subgroup["group"]) if subgroup else None

print("item       : %s" % item_name)
print("subgroup   : %s (group %s, group order %s, subgroup order %s)" % (
    item.get("subgroup"),
    subgroup and subgroup.get("group"),
    group and group.get("order"),
    subgroup and subgroup.get("order")))
print("order      : %s" % item.get("order"))
print("place_result: %s" % item.get("place_result"))

# duplicates: two item prototypes pointing at the same entity is the classic cause of a
# list entry appearing twice, or once in a place nobody expects
same_entity = sorted(name for name, proto in items.items()
                     if proto.get("place_result") == item.get("place_result"))
print("items with place_result=%s: %s" % (item.get("place_result"), same_entity))
if len(same_entity) > 1:
    print("FAIL: %d item prototypes point at the same entity" % len(same_entity))

if not subgroup:
    sys.exit("FAIL: subgroup %r is not defined -- the item would be dropped from the lists"
             % item.get("subgroup"))

siblings = [(name, proto) for name, proto in items.items()
            if proto.get("subgroup") == item["subgroup"]]


def strip_brackets(order):
    return re.sub(r"\[[^\]]*\]", "", order or "")


def plain(order):
    return order or ""


verdicts = []
for label, key in (("documented (bracket text ignored)", strip_brackets),
                   ("plain string compare", plain)):
    rows = sorted((key(proto.get("order")), name, proto.get("order")) for name, proto in siblings)
    names = [row[1] for row in rows]
    index = names.index(item_name)
    print("\n-- %s: subgroup %r, %d item(s) --" % (label, item["subgroup"], len(rows)))
    for position in range(max(0, index - 2), min(len(rows), index + 3)):
        marker = ">>" if rows[position][1] == item_name else "  "
        print("  %s %-22s key=%-12s order=%s" % (
            marker, rows[position][1], rows[position][0], rows[position][2]))
    before = names[index - 1] if index > 0 else None
    after = names[index + 1] if index + 1 < len(names) else None
    print("  neighbours: %s <- %s -> %s" % (before, item_name, after))
    verdicts.append((label, before, after))

print("\n== summary ==")
ok = True
for label, before, after in verdicts:
    turret_before = before is not None and "turret" in before
    turret_after = after is not None and "turret" in after
    close_to_radar = item["subgroup"] == "defensive-structure"
    status = "PASS" if (turret_before or turret_after) and not close_to_radar else "FAIL"
    if status == "FAIL":
        ok = False
    print("%-32s %s (before=%s after=%s, subgroup=%s)" % (
        label, status, before, after, item["subgroup"]))

sys.exit(0 if ok else 2)
