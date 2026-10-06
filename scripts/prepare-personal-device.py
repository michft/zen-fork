#!/usr/bin/env python3
"""Prepare an isolated, app-only Xcode project for Personal Team device builds."""

import argparse
import json
import plistlib
import re
import shutil
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET


def prepare(team: str, bundle_id: str) -> Path:
    if not re.fullmatch(r"[A-Z0-9]{10}", team):
        raise ValueError("Expected a 10-character Apple development team ID")
    if not re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", bundle_id):
        raise ValueError("Expected a reverse-domain bundle identifier")

    root = Path(__file__).resolve().parent.parent
    app_root = root / "firefox-ios"
    source = app_root / "Client.xcodeproj"
    output = root / ".build" / "personal-device"
    project = output / "Client.xcodeproj"
    shutil.copytree(source, project, dirs_exist_ok=True, ignore=shutil.ignore_patterns("xcuserdata"))
    data = json.loads(subprocess.check_output([
        "plutil", "-convert", "json", "-o", "-", str(source / "project.pbxproj")
    ]))
    objects = data["objects"]
    objects[data["rootObject"]]["projectDirPath"] = str(app_root)
    client = next(obj for obj in objects.values()
                  if obj["isa"] == "PBXNativeTarget" and obj["name"] == "Client")
    extensions = {key for key, obj in objects.items()
                  if ".app-extension" in obj.get("productType", "")}
    client["dependencies"] = [key for key in client["dependencies"]
                              if objects[key].get("target") not in extensions]
    client["buildPhases"] = [key for key in client["buildPhases"]
                             if objects[key].get("name") != "Embed App Extensions"]

    info = plistlib.loads((app_root / "Client" / "Info.plist").read_bytes())
    info["ZenPersonalTeam"] = True
    info_path = output / "Info.plist"
    info_path.write_bytes(plistlib.dumps(info))
    entitlements = output / "PersonalTeam.entitlements"
    entitlements.write_bytes(plistlib.dumps({
        "keychain-access-groups": ["$(AppIdentifierPrefix)$(PRODUCT_BUNDLE_IDENTIFIER)"]
    }))
    configurations = objects[client["buildConfigurationList"]]["buildConfigurations"]
    for key in configurations:
        if objects[key]["name"] != "Debug":
            continue
        objects[key]["buildSettings"].update({
            "CODE_SIGN_ENTITLEMENTS": str(entitlements),
            "CODE_SIGN_STYLE": "Automatic",
            "DEVELOPMENT_TEAM": team,
            "INFOPLIST_FILE": str(info_path),
            "MOZ_BUNDLE_ID": bundle_id,
            "MOZ_BUNDLE_DISPLAY_NAME": "FFox fork dev",
            "PRODUCT_BUNDLE_IDENTIFIER": bundle_id,
            "PROVISIONING_PROFILE_SPECIFIER": "",
        })
    (project / "project.pbxproj").write_bytes(plistlib.dumps(data, sort_keys=False))

    scheme_path = project / "xcshareddata" / "xcschemes" / "Fennec.xcscheme"
    scheme = ET.parse(scheme_path)
    for reference in scheme.findall(".//BuildableReference"):
        container = reference.get("ReferencedContainer", "")
        if container == "container:Client.xcodeproj":
            reference.set("ReferencedContainer", "container:" + str(project))
        elif container.startswith("container:../"):
            reference.set("ReferencedContainer", "container:" + str((app_root / container[10:]).resolve()))
    scheme.write(scheme_path, encoding="utf-8", xml_declaration=True)
    return project


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team", required=True)
    parser.add_argument("--bundle-id", required=True)
    args = parser.parse_args()
    print(prepare(args.team, args.bundle_id))
