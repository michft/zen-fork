#!/usr/bin/env python3
"""Archive universal FFox releases without Apple account or provisioning updates."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
MACRO_REVISION = "d020bf8c6432d0c6aa8428b5ca1c3225a0545b3b"


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--build-number", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--team", default="PP97C35JA7")
    parser.add_argument("--bundle-id", default="net.mich431.ffoxfork.dev")
    signing = parser.add_mutually_exclusive_group(required=True)
    signing.add_argument("--unsigned", action="store_true")
    signing.add_argument("--profile", type=Path)
    parser.add_argument("--identity", help="Installed signing certificate SHA-1")
    parser.add_argument("--method", choices=("debugging", "release-testing", "app-store-connect"), default="debugging")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", args.version):
        parser.error("--version must be X.Y.Z without leading zeroes")
    if args.method == "app-store-connect" and not re.fullmatch(r"[1-9][0-9]{0,3}(?:\.(?:0|[1-9][0-9]?)){0,2}", args.build_number):
        parser.error("App Store --build-number must have 1-3 numeric parts: first 1-9999, others 0-99")
    if args.method != "app-store-connect" and not re.fullmatch(r"[1-9][0-9]*", args.build_number):
        parser.error("--build-number must be a positive integer")
    if not re.fullmatch(r"[A-Z0-9]{10}", args.team):
        parser.error("--team must be a 10-character Apple team ID")
    if not re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", args.bundle_id):
        parser.error("--bundle-id must be a reverse-domain bundle identifier")
    if args.profile and not re.fullmatch(r"[A-Fa-f0-9]{40}", args.identity or ""):
        parser.error("--profile requires --identity with a certificate SHA-1")
    if args.unsigned and args.identity:
        parser.error("--identity cannot be used with --unsigned")
    if args.unsigned and args.method == "app-store-connect":
        parser.error("--method app-store-connect requires a signed provisioning profile")
    return args


def run(command, capture=False):
    command = [str(part) for part in command]
    print("+ " + shlex.join(command), flush=True)
    return subprocess.run(command, cwd=ROOT, check=True,
                          env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/usr/bin/false"},
                          stdout=subprocess.PIPE if capture else None).stdout


def validate_profile(profile, args):
    if args.team not in profile.get("TeamIdentifier", []):
        raise ValueError("Provisioning profile belongs to another team")
    entitlements = profile.get("Entitlements", {})
    if entitlements.get("com.apple.developer.team-identifier") != args.team:
        raise ValueError("Provisioning profile has an unexpected entitlement team")
    app_id = entitlements.get("application-identifier", "")
    prefixes = profile.get("ApplicationIdentifierPrefix", [])
    expected_ids = [f"{prefix}.{args.bundle_id}" for prefix in prefixes]
    if not any(app_id == expected or (app_id.endswith(".*") and "*" not in app_id[:-1]
                                     and expected.startswith(app_id[:-1])) for expected in expected_ids):
        raise ValueError("Provisioning profile does not cover this bundle identifier")
    expiry = profile.get("ExpirationDate")
    if not isinstance(expiry, datetime):
        raise ValueError("Provisioning profile has expired or lacks an expiration date")
    expiry = expiry.replace(tzinfo=timezone.utc) if expiry.tzinfo is None else expiry.astimezone(timezone.utc)
    if expiry <= datetime.now(timezone.utc):
        raise ValueError("Provisioning profile has expired or lacks an expiration date")
    if args.method == "app-store-connect":
        if app_id not in expected_ids or "*" in app_id:
            raise ValueError("App Store provisioning requires an explicit App ID")
        if "ProvisionedDevices" in profile or "ProvisionsAllDevices" in profile:
            raise ValueError("App Store provisioning must not contain device lists or enterprise provisioning")
        if entitlements.get("beta-reports-active") is not True:
            raise ValueError("TestFlight provisioning requires beta-reports-active")
    elif not profile.get("ProvisionedDevices") or profile.get("ProvisionsAllDevices"):
        raise ValueError("Expected a registered-device development or ad hoc profile")
    if entitlements.get("get-task-allow") is not (args.method == "debugging"):
        raise ValueError("Provisioning profile does not match the requested export method")
    certificates = profile.get("DeveloperCertificates", [])
    if not all(isinstance(cert, bytes) for cert in certificates) or args.identity.lower() not in [hashlib.sha1(cert).hexdigest() for cert in certificates]:
        raise ValueError("Signing certificate is not included in the provisioning profile")
    if not re.fullmatch(r"[A-Fa-f0-9]{8}(?:-[A-Fa-f0-9]{4}){3}-[A-Fa-f0-9]{12}", profile.get("UUID", "")):
        raise ValueError("Provisioning profile has an invalid UUID")
    return expiry


def decode_profile(path):
    return plistlib.loads(run(["security", "cms", "-D", "-i", path], capture=True))


def verify_app(app, args, profile=None):
    info = plistlib.loads((app / "Info.plist").read_bytes())
    expected = {"CFBundleIdentifier": args.bundle_id, "CFBundleShortVersionString": args.version,
                "CFBundleVersion": args.build_number}
    if any(info.get(key) != value for key, value in expected.items()):
        raise ValueError("Built app has an unexpected identifier or version")
    if sorted(info.get("UIDeviceFamily", [])) != [1, 2]:
        raise ValueError("Built app must support both iPhone and iPad")
    if args.unsigned and (app / "embedded.mobileprovision").exists():
        raise ValueError("Unsigned app unexpectedly contains a private provisioning profile")
    if profile:
        run(["codesign", "--verify", "--deep", "--strict", app])
        embedded = decode_profile(app / "embedded.mobileprovision")
        validate_profile(embedded, args)
        if embedded["UUID"] != profile["UUID"]:
            raise ValueError("Built app uses an unexpected provisioning profile")


def release(args):
    tools = ("xcodebuild", "pnpm", "ditto") + (() if args.unsigned else ("security", "codesign"))
    for tool in tools:
        if not shutil.which(tool):
            raise RuntimeError(f"Missing required tool: {tool}")
    output = args.output.resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Release output must be an empty directory")
    lock = ROOT / "firefox-ios/Client.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved"
    pins = json.loads(lock.read_text())["pins"]
    macro = next((pin for pin in pins if pin["identity"] == "modifiedcopymacro"), None)
    if not macro or macro["state"].get("revision") != MACRO_REVISION:
        raise ValueError("Swift macro pin changed; review it before permitting macro execution")
    profile = None
    expiry = None
    if not args.unsigned:
        profile = decode_profile(args.profile.resolve())
        expiry = validate_profile(profile, args)

    spec = importlib.util.spec_from_file_location("prepare_personal_device", ROOT / "scripts/prepare-personal-device.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    project = module.prepare(args.team, args.bundle_id, configuration="Release")
    if profile:
        project_path = project / "project.pbxproj"
        data = plistlib.loads(project_path.read_bytes())
        objects = data["objects"]
        client = next(obj for obj in objects.values()
                      if obj["isa"] == "PBXNativeTarget" and obj["name"] == "Client")
        configuration = next(objects[key] for key in objects[client["buildConfigurationList"]]["buildConfigurations"]
                             if objects[key]["name"] == "Release")
        configuration["buildSettings"].update({
            "CODE_SIGN_STYLE": "Manual", "CODE_SIGN_IDENTITY": args.identity,
            "PROVISIONING_PROFILE_SPECIFIER": profile["UUID"],
        })
        if args.method == "app-store-connect":
            configuration["buildSettings"]["DEBUG_INFORMATION_FORMAT"] = "dwarf-with-dsym"
        project_path.write_bytes(plistlib.dumps(data, sort_keys=False))
    info_path = project.parent / "Info.plist"
    info = plistlib.loads(info_path.read_bytes())
    info.update({"CFBundleShortVersionString": args.version, "CFBundleVersion": args.build_number})
    info_path.write_bytes(plistlib.dumps(info))
    run(["pnpm", "run", "build"])
    output.mkdir(parents=True, exist_ok=True)
    (ROOT / ".build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="release-ios-", dir=ROOT / ".build") as directory:
        work = Path(directory)
        archive = work / "FFox.xcarchive"
        command = ["xcodebuild", "-project", project, "-scheme", "Fennec", "-configuration", "Release",
                   "-destination", "generic/platform=iOS", "-archivePath", archive,
                   "-derivedDataPath", work / "DerivedData", "-clonedSourcePackagesDirPath", ROOT / ".build/SourcePackages",
                   "-scmProvider", "system", "-skipPackageUpdates", "-onlyUsePackageVersionsFromResolvedFile",
                   "-disableAutomaticPackageResolution", "-skipMacroValidation", "TARGETED_DEVICE_FAMILY=1,2",
                   f"APP_VERSION={args.version}", f"MARKETING_VERSION={args.version}",
                   f"CURRENT_PROJECT_VERSION={args.build_number}", f"DEVELOPMENT_TEAM={args.team}"]
        if args.unsigned:
            command.extend(["CODE_SIGNING_ALLOWED=NO", "CODE_SIGNING_REQUIRED=NO"])
        run([*command, "archive"])
        apps = list((archive / "Products/Applications").glob("*.app"))
        if len(apps) != 1:
            raise ValueError("Archive must contain exactly one app")
        verify_app(apps[0], args, profile)
        artifacts = []
        if args.unsigned:
            artifact = output / f"FFox-{args.version}-unsigned-ios-ipados.zip"
            run(["ditto", "-c", "-k", "--keepParent", apps[0], artifact])
        else:
            export_options = work / "ExportOptions.plist"
            options = {
                "method": args.method, "signingStyle": "manual", "teamID": args.team,
                "signingCertificate": args.identity, "provisioningProfiles": {args.bundle_id: profile["UUID"]},
                "manageAppVersionAndBuildNumber": False,
            }
            if args.method == "app-store-connect":
                options.update({"destination": "export", "uploadSymbols": True})
            else:
                options["thinning"] = "<none>"
            export_options.write_bytes(plistlib.dumps(options))
            exported = work / "Export"
            run(["xcodebuild", "-exportArchive", "-archivePath", archive,
                 "-exportPath", exported, "-exportOptionsPlist", export_options])
            ipas = list(exported.glob("*.ipa"))
            if len(ipas) != 1:
                raise ValueError("Export must contain exactly one IPA")
            unpacked = work / "VerifiedIPA"
            run(["ditto", "-x", "-k", ipas[0], unpacked])
            exported_apps = list((unpacked / "Payload").glob("*.app"))
            if len(exported_apps) != 1:
                raise ValueError("IPA must contain exactly one app")
            verify_app(exported_apps[0], args, profile)
            artifact = output / f"FFox-{args.version}-ios-ipados.ipa"
            shutil.copyfile(ipas[0], artifact)
            if args.method == "app-store-connect":
                symbols = archive / "dSYMs"
                if not symbols.is_dir() or not any(symbols.glob("*.dSYM")):
                    raise ValueError("App Store archive is missing debug symbols")
                symbol_archive = output / f"FFox-{args.version}-ios-ipados-dSYMs.zip"
                run(["ditto", "-c", "-k", "--keepParent", symbols, symbol_archive])
                artifacts.append(symbol_archive)
        metadata = {"version": args.version, "buildNumber": args.build_number,
                    "bundleIdentifier": args.bundle_id, "platforms": ["iOS", "iPadOS"],
                    "signing": "unsigned" if args.unsigned else args.method,
                    "installation": "requires-resigning" if args.unsigned else
                    "app-store-connect" if args.method == "app-store-connect" else "profile-registered-devices-only"}
        if expiry:
            metadata["signingExpires"] = expiry.isoformat()
        commit = os.environ.get("GITHUB_SHA", "")
        if re.fullmatch(r"[a-fA-F0-9]{40,64}", commit):
            metadata["sourceCommit"] = commit
        build_info = output / "build-info.json"
        build_info.write_text(json.dumps(metadata, indent=2) + "\n")
        sums = []
        for path in (artifact, build_info, *artifacts):
            with path.open("rb") as stream:
                digest = hashlib.sha256()
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            sums.append(f"{digest.hexdigest()}  {path.name}\n")
        (output / "SHA256SUMS").write_text("".join(sums))
    print(f"Release artifacts: {output}")


def main(argv=None):
    args = arguments(argv)
    try:
        release(args)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Release failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
