#!/usr/bin/env python3
"""Restore a pinned dependency bundle without contacting dependency services."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import subprocess
import sys
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parent.parent
CONTENTS = (".build/SourcePackages", "firefox-ios/build/nimbus", ".tools/swiftlint")
REQUIRED_INPUTS = (
    "Package.swift", "Package.resolved", "BrowserKit/Package.swift", "BrowserKit/Package.resolved",
    "MozillaRustComponents/Package.swift", "MozillaRustComponents/Package.resolved",
    "focus-ios/BlockzillaPackage/Package.swift",
    "focus-ios/Blockzilla.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved",
    "SampleComponentLibraryApp/SampleComponentLibraryApp.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved",
    "firefox-ios/Client.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved",
)


def safe_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or not path.parts:
        raise ValueError(f"Unsafe archive path: {name}")
    return path


def archive_members(archive):
    members = archive.getmembers()
    names = set()
    parents = {str(parent) for content in CONTENTS for parent in PurePosixPath(content).parents if str(parent) != "."}
    for member in members:
        name = str(safe_path(member.name))
        if name in names:
            raise ValueError(f"Duplicate archive path: {name}")
        names.add(name)
        allowed = name == "ci-dependencies.json" or any(name == content or name.startswith(content + "/") for content in CONTENTS)
        if not allowed and not (member.isdir() and name in parents):
            raise ValueError(f"Unexpected bundle content: {name}")
        if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
            raise ValueError(f"Unsupported archive member: {name}")
        if member.issym():
            if PurePosixPath(member.linkname).is_absolute() or "\\" in member.linkname:
                raise ValueError(f"Unsafe symbolic link: {name}")
            target = posixpath.normpath(str(PurePosixPath(name).parent / member.linkname))
            if not any(target == content or target.startswith(content + "/") for content in CONTENTS):
                raise ValueError(f"Symbolic link leaves dependency directories: {name}")
        if member.islnk():
            target = str(safe_path(member.linkname))
            if not any(target.startswith(content + "/") for content in CONTENTS):
                raise ValueError(f"Hard link leaves dependency directories: {name}")
    manifest = archive.getmember("ci-dependencies.json")
    if not manifest.isfile():
        raise ValueError("Dependency manifest must be a regular file")
    return members


def validate_inputs(manifest, root):
    if manifest.get("format") != 1 or not isinstance(manifest.get("inputs"), dict):
        raise ValueError("Unsupported dependency manifest")
    original = manifest.get("original_root", "")
    if not isinstance(original, str) or not Path(original).is_absolute() or original == "/":
        raise ValueError("Dependency manifest lacks a valid original root")
    if not set(REQUIRED_INPUTS).issubset(manifest["inputs"]):
        raise ValueError("Dependency manifest must pin all local Swift manifests and lock files")
    for relative, expected in manifest["inputs"].items():
        path = root / str(safe_path(relative))
        if not path.resolve().is_relative_to(root) or not re.fullmatch(r"[a-f0-9]{64}", expected):
            raise ValueError(f"Invalid dependency input: {relative}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Cached dependency inputs changed: {relative}; refresh the bundle")


def relocate(source, original, destination):
    packages = source / ".build/SourcePackages"
    state = packages / "workspace-state.json"
    paths = [state]
    paths.extend(packages.glob("checkouts/**/.git/objects/info/alternates"))
    paths.extend(packages.glob("repositories/**/objects/info/alternates"))
    paths.extend(packages.glob("checkouts/**/.git/config"))
    paths.extend(packages.glob("repositories/*/config"))
    for path in paths:
        text = path.read_text()
        updated = text.replace(original.rstrip("/") + "/", str(destination) + "/")
        if updated != text:
            path.write_text(updated)
    return json.loads(state.read_text())["object"]


def verify_packages(root, state, pins):
    packages = root / ".build/SourcePackages"
    dependencies = {dependency["packageRef"]["identity"]: dependency for dependency in state["dependencies"]}
    for pin in pins:
        dependency = dependencies.get(pin["identity"])
        revision = pin["state"]["revision"]
        if not dependency or dependency["state"].get("checkoutState", {}).get("revision") != revision:
            raise ValueError(f"Cached checkout does not match locked revision: {pin['identity']}")
        checkout = packages / "checkouts" / str(safe_path(dependency["subpath"]))
        if not checkout.is_dir() or not checkout.resolve().is_relative_to(packages):
            raise ValueError(f"Missing cached checkout: {pin['identity']}")
        env = {**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/usr/bin/false"}
        command = ["git", "-c", "protocol.allow=never", "-C", str(checkout)]
        head = subprocess.check_output([*command, "rev-parse", "HEAD"], env=env, text=True).strip()
        if head != revision:
            raise ValueError(f"Cached Git checkout has the wrong revision: {pin['identity']}")
        subprocess.run([*command, "cat-file", "-e", revision + "^{commit}"], env=env, check=True)
    for entry in [*state.get("artifacts", []), *state.get("prebuilts", [])]:
        path = Path(entry["path"])
        if not path.resolve().is_relative_to(packages.resolve()) or not path.exists():
            raise ValueError(f"Missing cached binary artifact: {entry.get('targetName', entry.get('identity', 'unknown'))}")
    for alternate in packages.glob("**/objects/info/alternates"):
        for value in alternate.read_text().splitlines():
            path = Path(value)
            if not path.is_absolute():
                path = alternate.parent.parent / path
            if not path.resolve().is_relative_to(packages) or not path.is_dir():
                raise ValueError(f"Missing or external Git object cache: {alternate.relative_to(packages)}")


def restore(archive_path):
    root = ROOT.resolve()
    for content in CONTENTS:
        target = root / content
        for path in (target, *target.parents):
            if path == root:
                break
            if path.is_symlink():
                raise ValueError(f"Refusing dependency destination through a symbolic link: {content}")
        if target.exists() and (not target.is_dir() or any(target.iterdir())):
            raise ValueError(f"Dependency destination must be empty: {content}")
    if not hasattr(tarfile, "data_filter"):
        raise RuntimeError("Offline dependency restore requires Python 3.12 or newer")
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive_members(archive)
        manifest = json.load(archive.extractfile("ci-dependencies.json"))
        validate_inputs(manifest, root)
        (root / ".build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ci-dependencies-", dir=root / ".build") as directory:
            stage = Path(directory)
            archive.extractall(stage, members=members, filter="data")
            for content in CONTENTS:
                if (stage / content).is_symlink() or not (stage / content).is_dir():
                    raise ValueError(f"Dependency bundle is missing: {content}")
            state = relocate(stage, manifest["original_root"], stage)
            pins = json.loads((root / REQUIRED_INPUTS[-1]).read_text())["pins"]
            verify_packages(stage, state, pins)
            relocate(stage, str(stage), root)
            for content in CONTENTS:
                target = root / content
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    target.rmdir()
                (stage / content).rename(target)
    print("Offline dependencies restored; Swift checkout revisions and binary artifacts verified.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        restore(args.archive)
    except (OSError, ValueError, KeyError, RuntimeError, tarfile.TarError, subprocess.CalledProcessError) as error:
        print(f"Dependency restore failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
