#!/usr/bin/env python3
"""Build local FFox code, update signing as needed, install, and launch."""

import argparse
from datetime import datetime, timezone
import fcntl
import os
from pathlib import Path
import plistlib
import re
import shlex
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
DEVICES = {
    "deadbeef7": "00008150-00112CC60EF2401C",
    "deadbeef6": "00008122-000928CC2E11001C",
}


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("device", nargs="?", default="deadbeef7",
                        choices=[*DEVICES, "both"])
    parser.add_argument("--team", default="PP97C35JA7")
    parser.add_argument("--bundle-id", default="net.mich431.ffoxfork.dev")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print commands without building or changing anything")
    parser.add_argument("--skip-macro-validation", action="store_true",
                        help="Only use after reviewing and trusting the pinned Swift macros")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Z0-9]{10}", args.team):
        parser.error("--team must be a 10-character Apple development team ID")
    if not re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", args.bundle_id):
        parser.error("--bundle-id must be a reverse-domain bundle identifier")
    return args


def deploy(args):
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/usr/bin/false"}

    def run(command, capture=False):
        command = [str(part) for part in command]
        print("+ " + shlex.join(command), flush=True)
        if args.dry_run:
            return None
        return subprocess.run(command, cwd=ROOT, env=env, check=True,
                              stdout=subprocess.PIPE if capture else None).stdout

    if not args.dry_run:
        for tool in ("pnpm", "xcodebuild", "xcrun", "codesign", "security"):
            if not shutil.which(tool):
                raise RuntimeError(f"Missing {tool}. See docs/command-line-deploy.md.")
        if not (ROOT / "node_modules").is_dir():
            raise RuntimeError("Install JS dependencies first: pnpm install --lockfile=false")

    run(["pnpm", "run", "build"])
    run([sys.executable, ROOT / "scripts/prepare-personal-device.py",
         "--team", args.team, "--bundle-id", args.bundle_id])
    app = ROOT / ".build/DeviceDerivedData/Build/Products/Debug-iphoneos/Client.app"
    targets = list(DEVICES) if args.device == "both" else [args.device]
    for name in targets:
        udid = DEVICES[name]
        print(f"\nBuilding and deploying to {name} ({udid})", flush=True)
        build = [
            "xcodebuild", "-project", ROOT / ".build/personal-device/Client.xcodeproj",
            "-scheme", "Fennec", "-configuration", "Debug", "-destination", f"id={udid}",
            "-derivedDataPath", ROOT / ".build/DeviceDerivedData",
            "-clonedSourcePackagesDirPath", ROOT / ".build/SourcePackages",
            "-scmProvider", "system", "-packageAuthorizationProvider", "netrc",
            "-skipPackageUpdates", "-allowProvisioningUpdates",
            "-allowProvisioningDeviceRegistration",
            f"DEVELOPMENT_TEAM={args.team}", "CODE_SIGN_STYLE=Automatic",
        ]
        if args.skip_macro_validation:
            build.append("-skipMacroValidation")
        run([*build, "build"])
        run(["codesign", "--verify", "--deep", "--strict", app])
        profile_data = run(["security", "cms", "-D", "-i", app / "embedded.mobileprovision"],
                           capture=True)
        if not args.dry_run:
            info = plistlib.loads((app / "Info.plist").read_bytes())
            profile = plistlib.loads(profile_data)
            expiry = profile["ExpirationDate"].replace(tzinfo=timezone.utc)
            if info["CFBundleIdentifier"] != args.bundle_id:
                raise RuntimeError("Built app has an unexpected bundle ID; refusing installation.")
            profile_app_id = profile["Entitlements"]["application-identifier"]
            expected_app_id = f"{args.team}.{args.bundle_id}"
            if profile_app_id != expected_app_id and not (
                profile_app_id.endswith(".*") and expected_app_id.startswith(profile_app_id[:-1])
            ):
                raise RuntimeError("Signing profile has an unexpected app ID; refusing installation.")
            if udid not in profile.get("ProvisionedDevices", []):
                raise RuntimeError(f"Signing profile does not cover {name}; refusing installation.")
            if expiry <= datetime.now(timezone.utc):
                raise RuntimeError("Signing profile expired. Check Apple account in Xcode Settings.")
            print(f"Signing expires: {expiry.astimezone().isoformat(timespec='seconds')}", flush=True)
        run(["xcrun", "devicectl", "device", "install", "app", "--device", udid, app])
        try:
            run(["xcrun", "devicectl", "device", "process", "launch", "--device", udid,
                 "--terminate-existing", args.bundle_id])
        except subprocess.CalledProcessError:
            print(f"Installed on {name}, but launch failed. Unlock device and check Developer Mode.\n"
                  "For an untrusted-developer popup: Settings > General > VPN & Device Management\n"
                  "> Developer App > Trust/Verify while connected to the internet.", file=sys.stderr)
            raise
        if not args.dry_run:
            print(f"Installed and launched FFox fork dev on {name}.", flush=True)


def main(argv=None):
    args = arguments(argv)
    try:
        if args.dry_run:
            deploy(args)
        else:
            (ROOT / ".build").mkdir(exist_ok=True)
            with (ROOT / ".build/deploy-device.lock").open("a") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise RuntimeError("Another deployment is running; wait for it to finish.") from None
                deploy(args)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Deployment failed: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Deployment interrupted.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
