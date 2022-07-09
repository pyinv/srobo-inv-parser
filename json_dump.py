#!/usr/bin/env python3
"""Dump the inventory as JSON."""
import json
from pydantic import BaseModel, validator
from pathlib import Path
from typing import Optional
from read_inv import Asset, Location, load_inventory_safe

asset_keys = {
    "mac_address",
    "development",
    "description",
    "revision",
    "physical_condition",
    "bootloader_version",
    "supplier",
    "part_number",
    "labelled",
    "condition",
    "value",
}

asset_key_aliases = {
    "mac": "mac_address",
    "serial": "serial_number",
}

class AssetSchema(BaseModel):

    asset_code: str
    location: str
    asset_type: str
    data: Optional[dict]

    @validator("data", pre=True)
    def trim_data(cls, v: Optional[dict]) -> dict:
        if v is None:
            return {}
        data = {k: v for k, v in v.items() if k in asset_keys}
        for key, new_key in asset_key_aliases.items():
            if key in data:
                data[new_key] = v[key]
        return data

    @classmethod
    def from_tuple(cls, asset: Asset) -> 'AssetSchema':
        return cls(
            asset_code=asset.asset_code,
            location=str(asset.location),
            asset_type=asset.type,
            data=asset.data,
        )

current = load_inventory_safe(Path("."))

class PathJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Path):
            return str(o)
        return super().default(o)

data = {}
for code, asset in current.items():
    if isinstance(asset, Asset):
        data[code] = {"type": "asset", "data": AssetSchema.from_tuple(asset).dict()}
    elif isinstance(asset, Location):
        data[str(code)] = {"type": "location", "data": asset}
    else:
        raise RuntimeError("Unrecognised type")

with Path(f"../inv.json").open("w") as fh:
    fh.write(json.dumps(data, cls=PathJSONEncoder))

