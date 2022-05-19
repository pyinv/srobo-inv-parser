import re
from pathlib import Path
from typing import NamedTuple, Dict, NewType
import yaml

AssetCode = NewType("AssetCode", str)

PART_REGEX = re.compile(r"(.+)-(sr[^ -]+)$")

class Location(NamedTuple):
    
    path: str
    location: str

class Asset(NamedTuple):

    asset_code: AssetCode
    type: str
    location: str
    data: dict

def find_highest_common_parent(path: Path):
    if path == Path("."):
        return path
    for p in path.parents:
        if len([l for l in p.iterdir()]) == 1:
            continue
        return p
    raise RuntimeError("No common parent found?")

def load_inventory(root_dir: Path) -> Dict[AssetCode, Asset]:

    assets = {}

    for item in root_dir.iterdir():

        if item.name in [".github", ".meta", ".gitattributes", ".mailmap", ".git"]:
            continue
        
        if item.is_dir():
            assets = {**load_inventory(item), **assets}
        else:
            if item.name == "info":
                name = item.parent.name
                location = item.parent.parent
                try:
                    data = yaml.safe_load(item.read_bytes())
                except Exception:
                    data = {}
            else:
                name = item.name
                location = item.parent
                try:
                    data = yaml.safe_load(item.read_bytes())
                except Exception:
                    data = {}
            
            match = PART_REGEX.match(name)
            if not match:
                # Ignore
                continue

            type, code = match.groups()

            location_match = PART_REGEX.match(location.name)
            if location_match:
                # Parent is an asset
                _, parent_code = location_match.groups()
                location_ref = parent_code
            else:
                # Parent is a folder
                location_ref = location
                if location not in assets:
                    assets[location] = Location(location, find_highest_common_parent(location))
            
            if code in assets:
                print("Duplicate asset code!")
            else:
                assets[code] = Asset(code, type, location_ref, data)
    
    # Create the parents of the locations if necessary
    looking = True
    while looking:
        looking = False
        for asset in list(assets.values()):  # Needs list() to copy so we can append during iteration
            if isinstance(asset, Location)and asset.location not in assets and asset.location != Path("."):
                assets[asset.location] = Location(asset.location, find_highest_common_parent(asset.location))
                looking = True

    return assets

def load_inventory_safe(root: Path):
    assets = load_inventory(root)

    # Super quickly check that everything has a location
    for key, asset in list(assets.items()):
        if not (asset.location in assets or asset.location == Path(".")):
            print(f"Deleting invalid: {asset}")
            del assets[key]
    return assets
