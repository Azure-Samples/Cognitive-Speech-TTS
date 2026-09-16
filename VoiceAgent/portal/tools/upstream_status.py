# Copyright (c) Microsoft. All rights reserved.
"""Read-only port comparison; --record-local explicitly refreshes local hashes.

No fetch, checkout, pull, reset, copy, or automatic merge is performed.
Uses only Python's standard library and an optional existing Git checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "UPSTREAM.json"
IGNORE_DIRS = {
    ".git", ".venv", "__pycache__", ".pytest_cache", ".run",
    "node_modules", "test-results", "playwright-report", "session-logs",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_path(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative:
        raise ValueError(f"Unsafe manifest path: {relative}")
    result = root.joinpath(*path.parts).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError(f"Manifest path escapes the portal: {relative}")
    return result


def local_files(root: Path) -> dict[str, str]:
    found = {}
    for directory, dirs, files in os.walk(root):
        dirs[:] = sorted(name for name in dirs if name not in IGNORE_DIRS)
        for name in sorted(files):
            if (
                name == MANIFEST or name.endswith((".pyc", ".map", ".log"))
                or (name.startswith(".env") and name != ".env.example")
            ):
                continue
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            found[relative] = sha256(safe_path(root, relative).read_bytes())
    return dict(sorted(found.items()))


def compare(before: dict[str, str], after: dict[str, str]) -> dict[str, list[str]]:
    return {
        "added": sorted(after.keys() - before.keys()),
        "removed": sorted(before.keys() - after.keys()),
        "changed": sorted(path for path in before.keys() & after.keys() if before[path] != after[path]),
    }


def expected_local(manifest: dict) -> dict[str, str]:
    result = dict(manifest.get("local_files", {}))
    for item in manifest["files"]:
        if item["action"] != "omitted":
            result[item["path"]] = item["ported_sha256"]
    return result


def record_local(root: Path, manifest: dict) -> dict:
    actual = local_files(root)
    imported = set()
    for item in manifest["files"]:
        relative = item["path"]
        imported.add(relative)
        if item["action"] == "omitted":
            if relative in actual:
                raise ValueError(f"Omitted upstream file has reappeared: {relative}. Review it explicitly before importing.")
            continue
        if relative not in actual:
            raise ValueError(f"Imported file missing: {relative}. Record intentional removals with an omission reason.")
        item["ported_sha256"] = actual[relative]
        if item["action"] != "generated":
            item["action"] = "copied" if item["ported_sha256"] == item["upstream_sha256"] else "modified"
    manifest["local_files"] = {path: digest for path, digest in actual.items() if path not in imported}
    return manifest


def git(source: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(source), *arguments],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return result.stdout


def upstream_files(source: Path, commit: str, prefix: str) -> dict[str, str]:
    prefix = prefix.rstrip("/") + "/"
    raw = git(source, "ls-tree", "-rz", "--name-only", commit, "--", prefix)
    paths = [value.decode("utf-8") for value in raw.split(b"\0") if value]
    return {
        path[len(prefix):]: sha256(git(source, "show", f"{commit}:{path}"))
        for path in paths
    }


def report(label: str, changes: dict[str, list[str]]) -> bool:
    print(f"{label}: " + ", ".join(f"{len(paths)} {kind}" for kind, paths in changes.items()))
    for kind, paths in changes.items():
        for path in paths:
            print(f"  {kind:7} {path}")
    return any(changes.values())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Existing upstream Git checkout; private access is optional.")
    parser.add_argument("--ref", default="origin/main", help="Source Git ref to compare; default origin/main.")
    parser.add_argument("--check", action="store_true", help="Exit 1 for local drift or an upstream revision change.")
    parser.add_argument("--record-local", action="store_true",
                        help="After editing CHANGELOG.md, explicitly record local file hashes. Never changes the source pin.")
    args = parser.parse_args(argv)
    try:
        manifest = json.loads((ROOT / MANIFEST).read_text(encoding="utf-8"))
        if manifest.get("schema_version") != 1:
            raise ValueError("Unsupported manifest schema.")
        # Validate paths even when they are omitted from this port.
        for item in manifest["files"]:
            safe_path(ROOT, item["path"])
        print(f"Upstream pin: {manifest['upstream']['commit']}")
        if args.record_local:
            record_local(ROOT, manifest)
            (ROOT / MANIFEST).write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
            print("Recorded local hashes. Upstream pin unchanged; include the reviewed CHANGELOG.md in the same change.")
        dirty = report("Local files", compare(expected_local(manifest), local_files(ROOT)))
        if args.source:
            pin = manifest["upstream"]["commit"]
            prefix = manifest["upstream"]["path"]
            expected = {item["path"]: item["upstream_sha256"] for item in manifest["files"]}
            pinned = upstream_files(args.source, pin, prefix)
            if compare(expected, pinned) != {"added": [], "removed": [], "changed": []}:
                raise ValueError("The pinned source tree does not match the manifest's upstream hashes.")
            print("Pinned upstream file hashes: verified")
            target = git(args.source, "rev-parse", "--verify", "--end-of-options", f"{args.ref}^{{commit}}").decode().strip()
            print(f"Compared ref: {args.ref} -> {target}")
            dirty |= report("Upstream portal files (including omissions)", compare(pinned, upstream_files(args.source, target, prefix)))
            if target != pin:
                print("Upstream repository revision advanced; review it even if the portal files are unchanged.")
                dirty = True
            worktree = git(args.source, "status", "--porcelain", "--", prefix).decode().strip()
            if worktree:
                print("Note: source worktree has local changes; comparison used committed Git blobs only.")
        else:
            print("Upstream comparison skipped (optional --source PATH). No network access was attempted.")
        return 1 if args.check and dirty else 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"Error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
