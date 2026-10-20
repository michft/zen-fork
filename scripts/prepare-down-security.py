#!/usr/bin/env python3
"""Apply reviewed cmark security backports to the pinned Down checkout, offline."""

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
PATCH_DIRECTORY = ROOT / "patches/down"
REVISION = "f34b166be1f1db4aa8f573067e901d72f2a6be57"
PATCHES = ("CVE-2023-22486.patch", "CVE-2023-24824.patch")
HASHES = {
    "Sources/cmark/inlines.c": (
        "600d08cad3af1a6f9f313b8176a03261d0a53a23d407fec8b82195b2f597ae5a",
        "9fe65a309b4e2319ad93dec464d3406f82430eb594bdb64cf3cc2c8bf81b0034",
    ),
    "Sources/cmark/blocks.c": (
        "0bf3964bd74b4ff1e61184348b3ea472615742a774e5e3b1b35af20ff19e4bdf",
        "80042936cf0aa6e84f757d4c45db8881363df9dddaac563bd2c1c242e1c07871",
    ),
    "Sources/cmark/node.h": (
        "ade6e6c0cb3bd89cf536180c0fc9772f65410bcb68885f09eaf4acf76971f9ab",
        "f64a90e64a4efad39daf5b4b6677da92c577797f8211a305c34d106e48316fdd",
    ),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply(root=ROOT):
    root = Path(root).resolve()
    checkout = root / ".build/SourcePackages/checkouts/Down"
    if not checkout.is_dir() or not checkout.resolve().is_relative_to(root):
        raise ValueError("Missing local Down checkout; restore the pinned dependency cache first")
    env = {**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/usr/bin/false"}
    revision = subprocess.check_output(
        ["git", "-c", "protocol.allow=never", "-c", "core.fsmonitor=false", "-C", str(checkout), "rev-parse", "HEAD"],
        env=env, text=True,
    ).strip()
    if revision != REVISION:
        raise ValueError("Down revision changed; review the cmark security backports before building")
    for relative in HASHES:
        path = checkout / relative
        if path.is_symlink() or not path.resolve().is_relative_to(checkout.resolve()):
            raise ValueError(f"Unexpected Down source path: {relative}")
    current = {relative: digest(checkout / relative) for relative in HASHES}
    if all(current[relative] == hashes[1] for relative, hashes in HASHES.items()):
        return False
    if not all(current[relative] == hashes[0] for relative, hashes in HASHES.items()):
        raise ValueError("Down source hashes changed or backports are incomplete; restore a reviewed dependency cache")
    if not shutil.which("patch"):
        raise RuntimeError("Missing required tool: patch")
    with tempfile.TemporaryDirectory(prefix="down-security-") as directory:
        stage = Path(directory)
        for relative in HASHES:
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(checkout / relative, target)
        for name in PATCHES:
            subprocess.run(
                ["patch", "--batch", "--forward", "-p1", "-i", str(PATCH_DIRECTORY / name)],
                cwd=stage, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        if not all(digest(stage / relative) == hashes[1] for relative, hashes in HASHES.items()):
            raise ValueError("Down security patch output hashes do not match the reviewed source")
        for relative in HASHES:
            target = checkout / relative
            with tempfile.NamedTemporaryFile(prefix=".down-security-", dir=target.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write((stage / relative).read_bytes())
            try:
                temporary.chmod(stat.S_IMODE(target.stat().st_mode))
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        changed = apply(args.root)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Down security preparation failed: {error}", file=sys.stderr)
        return 1
    print("Down cmark security backports applied." if changed else "Down cmark security backports already verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
