#!/usr/bin/env python3
"""Student Robotics Inventory History Parser."""
import argparse
import json
import subprocess
from pathlib import Path
from typing import Generator, List, TypedDict, Tuple
from dictdiffer import diff

from read_inv import PART_REGEX

from git import Repo

class CommitDict(TypedDict):

    commit: str
    message: str
    author: Tuple[str, str]
    timestamp: int
    files: List[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("traverse_commits.py")
    parser.add_argument("inventory_path", type=Path)
    parser.add_argument("--clear-cache", action='store_true')
    return parser.parse_args()

def validate_path(inv_path: Path) -> None:
    assert inv_path.exists()
    assert inv_path.is_dir()
    assert inv_path.joinpath(".git").exists()

def get_raw_trees(repo: Repo, path: Path, *, skip_initial_commits: int = 0) -> Generator[CommitDict, None, None]:
    commits = reversed(list(repo.iter_commits()))

    # Skip any corrupted commits at the start.
    for _ in range(skip_initial_commits):
        next(commits)

    for i, commit in enumerate(commits):
        print(i, commit.message)
        result = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", str(commit)],cwd=path)
        files = result.decode().splitlines()
        yield {
            "commit": commit, 
            "files": files,
        }


def main() -> None:
    args = parse_args()
    path = args.inventory_path
    validate_path(path)
    repo = Repo(path)

    previous_assets = {}
    for data in get_raw_trees(repo, path, skip_initial_commits=4):
        assets = {}
        changeset = []

        for path in data["files"]:
            parts = path.split("/")
            if parts[0] in [".github", ".meta", ".gitattributes", ".mailmap", ".git", "README.md"]:
                continue
            
            last = parts[-1]
            if ma := PART_REGEX.match(last):
                _, code = ma.groups()
                assets[code] = tuple(parts[:-1])

        if changes := diff(previous_assets, assets):
            for change_type, a, b in changes:
                if change_type == "add":
                    for code, location in b:
                        changeset.append({
                            "type": "added",
                            "asset_code": code,
                            "location": location,
                        })
                        # print(f"Added {code} at {location}")
                elif change_type == "change":
                    old, new = b
                    if old[0] == "unknown-location":
                        changeset.append({
                            "type": "move",
                            "asset_code": code,
                            "old": None,
                            "new": new,
                        })
                        # print(f"Found {a} after it was lost")
                    elif new[0] == "unknown-location":
                        changeset.append({
                            "type": "move",
                            "asset_code": code,
                            "old": old,
                            "new": None,
                        })
                        # print(f"Marked {b} lost")
                    else:
                        changeset.append({
                            "type": "move",
                            "asset_code": code,
                            "old": old,
                            "new": new,
                        })
                        # print(f"Moved {a} from {old} to {new}")
                elif change_type == "remove":
                    for code, _ in b:
                        changeset.append({
                            "type": "delete",
                            "asset_code": code,
                        })
                        # print(f"Deleted {a} last seen in {location}")
        commit = data["commit"]
        if changeset:
            with Path(f"changesets/{commit.authored_date}-{commit.hexsha}.json").open("w") as fh:
                json.dump({"changes": changeset, "hash": commit.hexsha, "message": commit.message, "author_name": commit.author.name, "author_email": commit.author.email, "dt": commit.authored_date}, fh)

        previous_assets = assets

if __name__ == "__main__":
    main()