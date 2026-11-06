# Copyright (c) Microsoft. All rights reserved.
"""Report source dashboard changes and their portal synchronization targets.

The existing UPSTREAM.json remains authoritative for voice_demo. SOURCE_SYNC.json
adds the independently owned template_view mappings. This tool is read-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any

PORTAL_ROOT = Path(__file__).resolve().parents[1]
DESTINATION_ROOTS = {
    "portal": PORTAL_ROOT,
    "voice_agent": PORTAL_ROOT.parent,
}
UPSTREAM_MANIFEST = PORTAL_ROOT / "UPSTREAM.json"
SYNC_MANIFEST = PORTAL_ROOT / "SOURCE_SYNC.json"
WORKTREE = "WORKTREE"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_relative(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise ValueError(f"Unsafe relative path: {relative}")
    result = root.joinpath(*path.parts).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes root: {relative}")
    return result


def git(source: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(source), *arguments],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def source_bytes(source: Path, ref: str, relative: str) -> bytes:
    if ref == WORKTREE:
        return safe_relative(source, relative).read_bytes()
    return git(source, "show", f"{ref}:{relative}")


def porcelain_paths(raw: bytes) -> set[str]:
    entries = [value for value in raw.split(b"\0") if value]
    paths: set[str] = set()
    index = 0
    while index < len(entries):
        record = entries[index].decode("utf-8")
        if len(record) < 4:
            raise ValueError(f"Invalid porcelain record: {record!r}")
        status = record[:2]
        paths.add(record[3:])
        index += 1
        if "R" in status or "C" in status:
            if index >= len(entries):
                raise ValueError("Rename/copy porcelain record has no source path")
            paths.add(entries[index].decode("utf-8"))
            index += 1
    return paths


def load_manifests() -> tuple[dict[str, Any], dict[str, Any]]:
    upstream = json.loads(UPSTREAM_MANIFEST.read_text(encoding="utf-8"))
    sync = json.loads(SYNC_MANIFEST.read_text(encoding="utf-8"))
    if upstream.get("schema_version") != 1:
        raise ValueError("Unsupported UPSTREAM.json schema")
    if sync.get("schema_version") != 1:
        raise ValueError("Unsupported SOURCE_SYNC.json schema")
    return upstream, sync


def mappings(
    upstream: dict[str, Any],
    sync: dict[str, Any],
) -> list[dict[str, str]]:
    roots = sync["source"]["roots"]
    runtime_root = roots["voice_demo"].rstrip("/")
    result = [
        {
            "source": f"{runtime_root}/{item['path']}",
            "destination": item["path"],
            "destination_root": "portal",
            "action": item["action"],
            "owner": "voice_demo",
        }
        for item in upstream["files"]
    ]
    for item in sync.get("additional_runtime_mappings", []):
        result.append(
            {
                "source": (
                    PurePosixPath(runtime_root) / PurePosixPath(item["source"])
                ).as_posix(),
                "destination": item.get("destination", ""),
                "destination_root": "portal",
                "action": item["action"],
                "owner": "voice_demo",
            }
        )
    for item in sync["template_mappings"]:
        source_root = roots[item["root"]].rstrip("/")
        source_path = (
            PurePosixPath(source_root) / PurePosixPath(item["source"])
        ).as_posix()
        result.append(
            {
                "source": source_path,
                "destination": item.get("destination", ""),
                "destination_root": item.get("destination_root", "portal"),
                "action": item["action"],
                "owner": "template_view",
            }
        )
    for item in sync.get("sample_mappings", []):
        source_root = roots[item["root"]].rstrip("/")
        result.append(
            {
                "source": (
                    PurePosixPath(source_root)
                    / PurePosixPath(item["source"])
                ).as_posix(),
                "destination": item.get("destination", ""),
                "destination_root": item.get(
                    "destination_root",
                    "portal",
                ),
                "action": item["action"],
                "owner": "template_samples",
            }
        )
    return result


def changed_paths(
    source: Path,
    *,
    base: str,
    ref: str,
    roots: list[str],
) -> tuple[str, set[str]]:
    target = (
        git(
            source,
            "rev-parse",
            "--verify",
            "--end-of-options",
            "HEAD^{commit}",
        ).decode().strip()
        if ref == WORKTREE
        else git(
            source,
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{ref}^{{commit}}",
        ).decode().strip()
    )
    committed = git(
        source,
        "diff",
        "--name-only",
        "-z",
        f"{base}..{target}",
        "--",
        *roots,
    )
    paths = {
        value.decode("utf-8")
        for value in committed.split(b"\0")
        if value
    }
    if ref == WORKTREE:
        local = git(
            source,
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            "--",
            *roots,
        )
        paths.update(porcelain_paths(local))
    return target, paths


def exact_drift(
    source: Path,
    ref: str,
    mapping: dict[str, str],
) -> tuple[str, str] | None:
    if mapping["action"] not in {"copied", "exact"}:
        return None
    destination = mapping["destination"]
    if not destination:
        return ("", "destination is missing")
    destination_root = DESTINATION_ROOTS[mapping.get("destination_root", "portal")]
    destination_path = safe_relative(destination_root, destination)
    if not destination_path.is_file():
        return ("", "destination file is missing")
    try:
        left = source_bytes(source, ref, mapping["source"])
    except (OSError, subprocess.CalledProcessError):
        return ("", "source file is missing")
    right = destination_path.read_bytes()
    if left == right:
        return None
    return (sha256(left), sha256(right))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--mcp-source",
        type=Path,
        help=(
            "Workspace checkout containing docs/voice_agent/11_mcp_server. "
            "Defaults to the parent of --source."
        ),
    )
    parser.add_argument(
        "--ref",
        default=WORKTREE,
        help="Git ref to inspect, or WORKTREE (default) for current source edits.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 when source changes need review or exact files drift.",
    )
    parser.add_argument(
        "--mcp-ref",
        default=WORKTREE,
        help="MCP source Git ref, or WORKTREE (default).",
    )
    args = parser.parse_args(argv)
    try:
        upstream, sync = load_manifests()
        all_mappings = mappings(upstream, sync)
        by_source = {item["source"]: item for item in all_mappings}
        roots = [
            *sync["source"]["roots"].values(),
        ]
        target, changed = changed_paths(
            args.source,
            base=sync["source"]["base_commit"],
            ref=args.ref,
            roots=roots,
        )
        print(f"Accepted source baseline: {sync['source']['base_commit']}")
        print(f"Source target: {args.ref} -> {target}")
        print(f"Source changes: {len(changed)}")
        pending = False
        for path in sorted(changed):
            item = by_source.get(path)
            if item is None:
                pending = True
                print(f"  unmapped {path}")
                continue
            target_path = item["destination"] or "(intentionally omitted)"
            if item["destination"] and item.get("destination_root") == "voice_agent":
                target_path = f"VoiceAgent/{target_path}"
            print(
                f"  {item['action']:9} {path} -> {target_path}"
            )
            if item["action"] not in {"omitted"}:
                pending = True

        drifted = []
        for item in all_mappings:
            drift = exact_drift(args.source, args.ref, item)
            if drift is not None:
                drifted.append((item, drift))
        print(f"Exact mapping drift: {len(drifted)}")
        for item, (source_hash, destination_hash) in drifted:
            pending = True
            detail = (
                f"{source_hash} != {destination_hash}"
                if source_hash and destination_hash
                else destination_hash
            )
            print(
                f"  {item['source']} -> {item['destination']}: {detail}"
            )

        mcp = sync["mcp_source"]
        mcp_source = args.mcp_source or args.source.resolve().parent
        mcp_target, mcp_changes = changed_paths(
            mcp_source,
            base=mcp["base_commit"],
            ref=args.mcp_ref,
            roots=[mcp["root"]],
        )
        print(f"MCP source baseline: {mcp['base_commit']}")
        print(f"MCP source target: {args.mcp_ref} -> {mcp_target}")
        print(f"MCP source changes: {len(mcp_changes)}")
        if mcp_changes:
            pending = True
            targets = ", ".join(mcp["review_targets"])
            for path in sorted(mcp_changes):
                print(f"  review    {path} -> {targets}")
            print(f"  reason    {mcp['reason']}")
        return 1 if args.check and pending else 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Error: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
