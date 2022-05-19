"""Traverse commits, but manual."""
from pathlib import Path
from read_inv import load_inventory_safe
from yaml import safe_load

keys = set()

current = load_inventory_safe(Path("."))

for fa in current.values():
    try:
        data = safe_load(fa.data)
        if not isinstance(data, dict):
            print(data)
            continue
        for key in data.keys():
            if key not in keys:
                keys.add(key)
                print(f"{key} {fa.asset_code} {fa.location}")
    except AttributeError:
        # not an asset
        pass

print("---")
for key in keys:
    print(key)
