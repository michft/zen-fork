#!/usr/bin/env python3
"""Package existing local public build dependencies without contacting upstream."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile


ROOT = Path(__file__).resolve().parent.parent
DIRECTORIES = (".build/SourcePackages", "firefox-ios/build/nimbus", ".tools/swiftlint")


def package(output):
    if output.exists():
        raise ValueError("Output already exists; refusing overwrite")
    for directory in DIRECTORIES:
        if not (ROOT / directory).is_dir():
            raise ValueError(f"Missing local dependency cache: {directory}")
    inputs = sorted({*ROOT.glob("**/Package.swift"), *ROOT.glob("**/Package.resolved")})
    inputs = [path for path in inputs
              if path.is_file() and not any(part.startswith(".") for part in path.relative_to(ROOT).parts)]
    manifest = {"format": 1, "original_root": str(ROOT), "inputs": {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs
    }}
    data = json.dumps(manifest, indent=2).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "w:gz", compresslevel=3) as archive:
        entry = tarfile.TarInfo("ci-dependencies.json")
        entry.size = len(data)
        archive.addfile(entry, io.BytesIO(data))
        for directory in DIRECTORIES:
            archive.add(ROOT / directory, arcname=directory)
    print(hashlib.file_digest(output.open("rb"), "sha256").hexdigest())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package(args.output.resolve())
