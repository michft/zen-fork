#!/usr/bin/env python3
"""Rebuild SQLite inside the pinned App Services xcframework from reviewed source, offline."""

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "patches/sqlite/sqlite-amalgamation-3540100.zip"
SOURCE_SHA3_256 = "92281c86e2957f9b9305890f9ac04204caa7b677cc868dc326d942689df28e30"
SOURCE_DIRECTORY = "sqlite-amalgamation-3540100"
OLD_SOURCE_ID = b"2025-06-28 14:00:48 2af157d77fb1304a74176eaee7fbc7c7e932d946bf25325e9c26c91db19e3079"
NEW_SOURCE_ID = b"2026-10-16 14:45:20 555e07ef33f69a0957d24d8e555b702464a131d6f1607f4c3c1e4551e8e6ca76"
XCFRAMEWORK = Path(".build/SourcePackages/artifacts/mozillarustcomponents/MozillaRustComponents/"
                   "MozillaRustComponents.xcframework")
MEMBER = "c877a2978823c39d-sqlite3.o"
# App Services 158.0.20260911050252 slices: (SDK, architecture targets, original SHA-256).
SLICES = {
    "ios-arm64": (
        "iphoneos", {"arm64": "arm64-apple-ios15.0"},
        "f77758625fa9d3821840632722051363649ba8e26e9f46e81c540ce55de1e02a",
    ),
    "ios-arm64_x86_64-simulator": (
        "iphonesimulator",
        {"x86_64": "x86_64-apple-ios15.0-simulator", "arm64": "arm64-apple-ios15.0-simulator"},
        "4befae872422711fd57405b839b31b4fd05fef07efdd00428a6011d4c914be48",
    ),
}
# libsqlite3-sys 0.35.0 bundled build flags plus rusqlite's unlock_notify feature, as App Services uses them.
DEFINES = (
    "SQLITE_CORE", "SQLITE_DEFAULT_FOREIGN_KEYS=1", "SQLITE_ENABLE_API_ARMOR", "SQLITE_ENABLE_COLUMN_METADATA",
    "SQLITE_ENABLE_DBSTAT_VTAB", "SQLITE_ENABLE_FTS3", "SQLITE_ENABLE_FTS3_PARENTHESIS", "SQLITE_ENABLE_FTS5",
    "SQLITE_ENABLE_JSON1", "SQLITE_ENABLE_LOAD_EXTENSION=1", "SQLITE_ENABLE_MEMORY_MANAGEMENT",
    "SQLITE_ENABLE_RTREE", "SQLITE_ENABLE_STAT4", "SQLITE_SOUNDEX", "SQLITE_THREADSAFE=1", "SQLITE_USE_URI",
    "HAVE_USLEEP=1", "HAVE_ISNAN", "_POSIX_THREAD_SAFE_FUNCTIONS", "HAVE_LOCALTIME_R",
    "SQLITE_ENABLE_UNLOCK_NOTIFY",
)
ADDED_OPTIONS = {"MAX_SCHEMA=10000000"}
OPTION = re.compile(rb"(?<=\x00)((?:ATOMIC_|DEFAULT_|DQS|ENABLE_|HAVE_|MALLOC_|MAX_|OMIT_|SOUNDEX|SYSTEM_|TEMP_|"
                    rb"THREADSAFE|USE_)[A-Z0-9_]*(?:=[0-9A-Za-z_.-]+)?)(?=\x00)")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def options(data):
    return {match.decode() for match in OPTION.findall(data)}


def tool(*command, cwd=None):
    return subprocess.run(["xcrun", *command], cwd=cwd, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env={**os.environ, "ZERO_AR_DATE": "1"}).stdout


def exports(path):
    return set(tool("nm", "-gUj", str(path)).decode().split())


def unpack_source(stage):
    data = SOURCE.read_bytes()
    if hashlib.sha3_256(data).hexdigest() != SOURCE_SHA3_256:
        raise ValueError("SQLite source archive does not match the reviewed sqlite.org release")
    with zipfile.ZipFile(SOURCE) as archive:
        for name in ("sqlite3.c", "sqlite3.h"):
            (stage / name).write_bytes(archive.read(f"{SOURCE_DIRECTORY}/{name}"))
    if NEW_SOURCE_ID not in (stage / "sqlite3.h").read_bytes():
        raise ValueError("SQLite source archive has an unexpected version")
    return stage / "sqlite3.c"


def state(path, original):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() == original:
        return "original"
    if OLD_SOURCE_ID not in data and NEW_SOURCE_ID in data:
        return "patched"
    return "unknown"


def rebuild_archive(archive, source, sdk, target, work):
    members = tool("ar", "t", str(archive)).decode().splitlines()
    if members.count(MEMBER) != 1:
        raise ValueError("App Services archive does not contain exactly one bundled SQLite object")
    old = work / "old"
    old.mkdir()
    tool("ar", "x", str(archive), MEMBER, cwd=old)
    new = work / "new"
    new.mkdir()
    tool("--sdk", sdk, "clang", "-c", "-Os", "-g", "-ffunction-sections", "-fdata-sections", "-fPIC", "-w",
         f"-ffile-prefix-map={source.parent}=sqlite", "-target", target, *(f"-D{define}" for define in DEFINES), str(source), "-o", str(new / MEMBER))
    old_data = (old / MEMBER).read_bytes()
    new_data = (new / MEMBER).read_bytes()
    if OLD_SOURCE_ID not in old_data or NEW_SOURCE_ID not in new_data:
        raise ValueError("Unexpected SQLite source identifiers while rebuilding App Services")
    if options(new_data) != options(old_data) | ADDED_OPTIONS:
        raise ValueError("Rebuilt SQLite compile options differ from App Services")
    if not exports(old / MEMBER) <= exports(new / MEMBER):
        raise ValueError("Rebuilt SQLite does not export every App Services SQLite symbol")
    tool("ar", "-r", str(archive), MEMBER, cwd=new)
    tool("ranlib", str(archive))
    if tool("ar", "t", str(archive)).decode().splitlines() != members:
        raise ValueError("App Services archive members changed while replacing SQLite")
    check = work / "check"
    check.mkdir()
    tool("ar", "x", str(archive), MEMBER, cwd=check)
    if (check / MEMBER).read_bytes() != new_data:
        raise ValueError("App Services archive did not receive the rebuilt SQLite object")


def rebuild(binary, source, sdk, targets, work):
    output = work / "output"
    if len(targets) == 1:
        shutil.copyfile(binary, output)
        rebuild_archive(output, source, sdk, next(iter(targets.values())), work)
        return output
    thin = []
    for architecture, target in targets.items():
        directory = work / architecture
        directory.mkdir()
        archive = directory / "library.a"
        tool("lipo", str(binary), "-thin", architecture, "-output", str(archive))
        rebuild_archive(archive, source, sdk, target, directory)
        thin += ["-arch", architecture, str(archive)]
    tool("lipo", "-create", *thin, "-output", str(output))
    if set(tool("lipo", "-archs", str(output)).decode().split()) != set(targets):
        raise ValueError("Rebuilt App Services library has unexpected architectures")
    return output


def apply(root=ROOT):
    root = Path(root).resolve()
    framework = root / XCFRAMEWORK
    if not framework.is_dir() or not framework.resolve().is_relative_to(root):
        raise ValueError("Missing App Services xcframework; restore the pinned dependency cache first")
    binaries = {}
    for name, (_, _, original) in SLICES.items():
        binary = framework / name / "MozillaRustComponents.framework/MozillaRustComponents"
        if binary.is_symlink() or not binary.is_file() or not binary.resolve().is_relative_to(framework.resolve()):
            raise ValueError(f"Unexpected App Services library path: {name}")
        binaries[name] = (binary, state(binary, original))
    if all(current == "patched" for _, current in binaries.values()):
        return False
    if any(current == "unknown" for _, current in binaries.values()):
        raise ValueError("App Services library changed; review the SQLite replacement before building")
    if not shutil.which("xcrun"):
        raise RuntimeError("Missing required tool: xcrun")
    with tempfile.TemporaryDirectory(prefix="appservices-sqlite-") as directory:
        stage = Path(directory)
        source = unpack_source(stage)
        outputs = {}
        for name, (binary, current) in binaries.items():
            if current == "patched":
                continue
            sdk, targets, _ = SLICES[name]
            work = stage / name
            work.mkdir()
            outputs[name] = rebuild(binary, source, sdk, targets, work)
        for name, output in outputs.items():
            target = binaries[name][0]
            with tempfile.NamedTemporaryFile(prefix=".appservices-sqlite-", dir=target.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(output.read_bytes())
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
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        print(f"App Services SQLite preparation failed: {error}", file=sys.stderr)
        return 1
    print("App Services SQLite 3.54.1 rebuilt." if changed else "App Services SQLite 3.54.1 already verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
