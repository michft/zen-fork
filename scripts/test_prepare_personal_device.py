import importlib.util
import plistlib
import shutil
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("prepare-personal-device.py")


def load_generator(path: Path):
    spec = importlib.util.spec_from_file_location("prepare_personal_device", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PreparePersonalDeviceTests(unittest.TestCase):
    def test_prepare_removes_all_extensions_and_rewrites_app_only_project(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scripts = root / "scripts"
            scripts.mkdir()
            shutil.copy2(SCRIPT, scripts / SCRIPT.name)
            app_root = root / "firefox-ios"
            source = app_root / "Client.xcodeproj"
            scheme_dir = source / "xcshareddata" / "xcschemes"
            scheme_dir.mkdir(parents=True)
            (app_root / "Client").mkdir()

            extension_types = [
                "com.apple.product-type.app-extension",
                "com.apple.product-type.app-extension.messages-sticker-pack",
                "com.apple.product-type.app-extension.messages",
            ]
            objects = {
                "PROJECT": {
                    "isa": "PBXProject",
                    "rootObject": "PROJECT",
                    "projectDirPath": "original",
                },
                "CLIENT": {
                    "isa": "PBXNativeTarget",
                    "name": "Client",
                    "buildConfigurationList": "CONFIGS",
                    "dependencies": ["DEP_EXT", "DEP_STICKER", "DEP_MESSAGES"],
                    "buildPhases": ["APP_PHASE", "EXT_PHASE"],
                },
                "EXT": {"isa": "PBXNativeTarget", "name": "Extension", "productType": extension_types[0]},
                "STICKER": {"isa": "PBXNativeTarget", "name": "Sticker", "productType": extension_types[1]},
                "MESSAGES": {"isa": "PBXNativeTarget", "name": "Messages", "productType": extension_types[2]},
                "DEP_EXT": {"isa": "PBXTargetDependency", "target": "EXT"},
                "DEP_STICKER": {"isa": "PBXTargetDependency", "target": "STICKER"},
                "DEP_MESSAGES": {"isa": "PBXTargetDependency", "target": "MESSAGES"},
                "APP_PHASE": {"isa": "PBXResourcesBuildPhase", "name": "Resources"},
                "EXT_PHASE": {"isa": "PBXCopyFilesBuildPhase", "name": "Embed App Extensions"},
                "CONFIGS": {"isa": "XCConfigurationList", "buildConfigurations": ["DEBUG", "RELEASE"]},
                "DEBUG": {"isa": "XCBuildConfiguration", "name": "Debug", "buildSettings": {}},
                "RELEASE": {"isa": "XCBuildConfiguration", "name": "Release", "buildSettings": {}},
            }
            (source / "project.pbxproj").write_bytes(
                plistlib.dumps({"objects": objects, "rootObject": "PROJECT"})
            )
            (app_root / "Client" / "Info.plist").write_bytes(
                plistlib.dumps({"CFBundleIdentifier": "org.mozilla.ios.Fennec"})
            )
            scheme = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Scheme><BuildableReference ReferencedContainer=\"container:Client.xcodeproj\"/><BuildableReference ReferencedContainer=\"container:../BrowserKit.xcodeproj\"/></Scheme>
"""
            (scheme_dir / "Fennec.xcscheme").write_text(scheme)
            original_project = (source / "project.pbxproj").read_bytes()

            generator = load_generator(scripts / SCRIPT.name)
            project = generator.prepare("ABCDE12345", "com.example.ffox.dev")

            self.assertEqual(original_project, (source / "project.pbxproj").read_bytes())
            generated = plistlib.loads((project / "project.pbxproj").read_bytes())
            objects = generated["objects"]
            client = next(obj for obj in objects.values() if obj.get("name") == "Client")
            self.assertEqual(client["dependencies"], [])
            self.assertEqual(client["buildPhases"], ["APP_PHASE"])
            self.assertEqual(objects["DEBUG"]["buildSettings"]["MOZ_BUNDLE_DISPLAY_NAME"], "FFox fork dev")
            self.assertEqual(objects["DEBUG"]["buildSettings"]["PRODUCT_BUNDLE_IDENTIFIER"], "com.example.ffox.dev")
            self.assertEqual(plistlib.loads((project.parent / "Info.plist").read_bytes())["ZenPersonalTeam"], True)
            self.assertTrue((project.parent / "PersonalTeam.entitlements").exists())
            rewritten_scheme = (project / "xcshareddata" / "xcschemes" / "Fennec.xcscheme").read_text()
            self.assertIn(f"container:{project}", rewritten_scheme)
            self.assertIn(f"container:{(root / 'BrowserKit.xcodeproj').resolve()}", rewritten_scheme)


if __name__ == "__main__":
    unittest.main()
