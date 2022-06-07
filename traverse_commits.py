#!/usr/bin/env python
"""Traverse commits, but manual."""
from pydantic import BaseModel, Field, validator
from pathlib import Path
from datetime import datetime
from graphlib import TopologicalSorter
from typing import Dict, List, Optional, Union, Literal
from typing_extensions import Annotated
from git import Repo
from read_inv import Asset, load_inventory_safe

END_COMMIT = "master"
END_COMMIT = "8bb7e30f8"
END_COMMIT = "ec1ae9aa8"

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

class AddAssetEvent(BaseModel):

    event: Literal["add"] = "add"
    asset: AssetSchema


class ChangeAssetEvent(BaseModel):

    event: Literal["change"] = "change"
    old: AssetSchema
    new: AssetSchema


class DisposeAssetEvent(BaseModel):

    event: Literal["dispose"] = "dispose"
    asset_code: str

class MoveAssetEvent(BaseModel):

    event: Literal["move"] = "move"
    asset_code: str
    old_location: str
    new_location: str

class RestoreAssetEvent(BaseModel):

    event: Literal["restore"] = "restore"
    asset: AssetSchema

Event = Annotated[
    Union[AddAssetEvent, ChangeAssetEvent, DisposeAssetEvent, MoveAssetEvent, RestoreAssetEvent],
    Field(discriminator="event"),
]

class ChangeSet(BaseModel):

    timestamp: datetime
    user: str
    comment: str
    events: List[Event]


repo = Repo(".")
repo.git.checkout(END_COMMIT)  # Should be master for real thing

commits = repo.iter_commits()

live_codes = set()
disposed_codes = set()

event_count = 0

previous = {}

for commit in sorted(commits, key=lambda x: x.committed_date):
    if len(commit.parents) > 1:
        # Merge commit, ignore
        continue

    repo.git.checkout(commit)

    events: Dict[str, List[Event]] = {}

    dt = datetime.utcfromtimestamp(commit.committed_date)
    current = load_inventory_safe(Path("."))

    # Look at diff
    added = current.keys() - previous.keys()
    removed = previous.keys() - current.keys()
    changed = set()
    for key, new_val in current.items():
        try:
            if previous[key] != new_val:
                changed.add(key)
        except KeyError:
            pass

    if len(added) + len(removed) + len(changed) == 0:
        print(f"{dt} {commit.summary}")
        continue

    added_count = 0
    removed_count = 0
    changed_count = 0
    moved_count = 0
    restored_count = 0

    # Added
    for code in added:
        if code in live_codes:
            raise ValueError(f"{code} already exists ")
        
        if code in disposed_codes:
            # EVENT: RESTORED
            restored_count += 1
            event = RestoreAssetEvent(
                asset=AssetSchema.from_tuple(current[code]),
            )
            if code in events:
                events[code].append(event)
            else:
                events[code] = [event]
            live_codes.add(code)
            disposed_codes.remove(code)

        elif isinstance(code, str):
            # EVENT: CREATED
            added_count += 1
            event = AddAssetEvent(
                asset=AssetSchema.from_tuple(current[code]),
            )
            if code in events:
                events[code].append(event)
            else:
                events[code] = [event]
            live_codes.add(code)

    # Disposed
    for code in removed:
        if isinstance(code, str):
            # EVENT DISPOSED
            removed_count += 1
            event = DisposeAssetEvent(
                asset_code=code,
            )
            if code in events:
                events[code].append(event)
            else:
                events[code] = [event]
            live_codes.remove(code)
            disposed_codes.add(code)

    # Changed
    for code in changed:

        if isinstance(code, str):

            old = previous[code]
            new = current[code]

            if Asset(old.asset_code, old.type, new.location, old.data) == new:
                # EVENT: MOVED
                moved_count += 1
                event = MoveAssetEvent(
                    asset_code=code,
                    old_location=str(old.location),
                    new_location=str(new.location),
                )
                if code in events:
                    events[code].append(event)
                else:
                    events[code] = [event]
            else:
                # EVENT: CHANGED
                changed_count += 1
                event = ChangeAssetEvent(
                    asset_code=code,
                    old=AssetSchema.from_tuple(old),
                    new=AssetSchema.from_tuple(new),
                )
                if code in events:
                    events[code].append(event)
                else:
                    events[code] = [event]

    print(f"{dt} A{added_count} D{removed_count} C{changed_count} M{moved_count} R{restored_count} :: {commit.summary}")

    event_count += added_count + removed_count + changed_count + moved_count + restored_count

    graph = {code: {data.location} if data.location in current else {} for code, data in current.items()}
    graph_filtered = {k: vl for k, vl in graph.items() if all(isinstance(v, str) for v in vl)}
    topo_sorter = TopologicalSorter(graph_filtered)
    topo_sorted_assets = topo_sorter.static_order()

    sorted_events = []
    for asset in reversed([x for x in topo_sorted_assets]):
        if asset in events:
            sorted_events.extend(events[asset])

    cs = ChangeSet(
        timestamp=dt,
        user=commit.author.email,
        comment=commit.hexsha + ": " + commit.summary,
        events=sorted_events,
    )
    
    with Path(f"../changesets/{dt.isoformat()}-{commit.hexsha}.yaml").open("w") as fh:
        fh.write(cs.json())

    previous = current

repo.git.checkout(END_COMMIT)

print(f"COUNT: {event_count}")