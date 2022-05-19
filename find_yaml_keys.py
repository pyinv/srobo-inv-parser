"""Traverse commits, but manual."""
from pathlib import Path
from read_inv import load_inventory_safe

keys = set()

current = load_inventory_safe(Path("."))

for fa in current.values():
    try:
        data = fa.data
        if not isinstance(data, dict):
            print(data)
            continue
        for key, val in data.items():
            if key not in keys:
                keys.add(key)
                print(f"{key} {fa.type} {fa.asset_code} {fa.location}: {val}")
    except AttributeError:
        # not an asset
        pass

print("---")
for key in keys:
    print(key)
