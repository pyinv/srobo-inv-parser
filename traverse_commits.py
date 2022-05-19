#!/usr/bin/env python
"""Traverse commits, but manual."""
from pydantic import BaseModel, ValidationError
from pathlib import Path
from datetime import datetime
from typing import Optional
from git import Repo
from read_inv import Asset, load_inventory_safe

END_COMMIT = "master"
# END_COMMIT = "8bb7e30f8"

class AssetSchema(BaseModel):

    asset_code: str
    asset_type: str
    description: str
    value: Optional[float]
    condition: Optional[str]

class AddAssetEvent(BaseModel):

    timestamp: datetime
    user: str
    asset: AssetSchema
    location: str
    comment: str

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
            live_codes.add(code)
            disposed_codes.remove(code)

        elif isinstance(code, str):
            # EVENT: CREATED
            added_count += 1
            live_codes.add(code)

    # Disposed
    for code in removed:
        if isinstance(code, str):
            # EVENT DISPOSED
            removed_count += 1
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
            else:
                # EVENT: CHANGED
                changed_count += 1

    print(f"{dt} A{added_count} D{removed_count} C{changed_count} M{moved_count} R{restored_count} :: {commit.summary}")

    event_count += added_count + removed_count + changed_count + moved_count + restored_count

    previous = current

repo.git.checkout(END_COMMIT)

print(f"COUNT: {event_count}")