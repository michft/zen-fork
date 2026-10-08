import importlib.util
import io
import json
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import plistlib
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import Mock, patch


SCRIPT = Path(__file__).with_name("release-ios.py")


class ReleaseIOSTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("release_ios", SCRIPT)
        self.helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.helper)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.helper.ROOT = self.root
        self.output = self.root / "release"
        self.certificate = b"test-certificate"
        self.identity = hashlib.sha1(self.certificate).hexdigest()
        self.profile = {
            "UUID": "12345678-1234-1234-1234-123456789ABC",
            "TeamIdentifier": ["PP97C35JA7"], "ApplicationIdentifierPrefix": ["PP97C35JA7"],
            "ExpirationDate": datetime.now(timezone.utc) + timedelta(days=330),
            "DeveloperCertificates": [self.certificate], "ProvisionedDevices": ["private-device-id"],
            "Entitlements": {"application-identifier": "PP97C35JA7.*", "get-task-allow": True,
                             "com.apple.developer.team-identifier": "PP97C35JA7"},
        }
        self.info = {"CFBundleIdentifier": "net.mich431.ffoxfork.dev", "CFBundleVersion": "42",
                     "CFBundleShortVersionString": "0.1.0", "UIDeviceFamily": [1, 2]}
        lock = self.root / "firefox-ios/Client.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved"
        lock.parent.mkdir(parents=True)
        lock.write_text(json.dumps({"pins": [{"identity": "modifiedcopymacro",
                                              "state": {"revision": self.helper.MACRO_REVISION}}]}))
        self.project = self.root / ".build/personal-device/Client.xcodeproj"
        self.project.mkdir(parents=True)
        (self.project.parent / "Info.plist").write_bytes(plistlib.dumps({"ZenPersonalTeam": True}))
        (self.project / "project.pbxproj").write_bytes(plistlib.dumps({"objects": {
            "client": {"isa": "PBXNativeTarget", "name": "Client", "buildConfigurationList": "client-configurations"},
            "client-configurations": {"isa": "XCConfigurationList", "buildConfigurations": ["client-debug", "client-release"]},
            "client-debug": {"isa": "XCBuildConfiguration", "name": "Debug", "buildSettings": {"CODE_SIGN_STYLE": "Automatic"}},
            "client-release": {"isa": "XCBuildConfiguration", "name": "Release", "buildSettings": {"CODE_SIGN_STYLE": "Automatic"}},
            "framework-release": {"isa": "XCBuildConfiguration", "name": "Release", "buildSettings": {"CODE_SIGNING_ALLOWED": "NO"}},
        }}))
        self.prepare = Mock(return_value=self.project)
        self.calls = []

    def args(self, signed=False, extra=()):
        signing = ["--profile", str(self.root / "profile.mobileprovision"), "--identity", self.identity] if signed else ["--unsigned"]
        return self.helper.arguments(["--version", "0.1.0", "--build-number", "42",
                                      "--output", str(self.output), *signing, *extra])

    def command(self, command, capture=False):
        command = [str(part) for part in command]
        self.calls.append(command)
        if command[:3] == ["security", "cms", "-D"]:
            return plistlib.dumps(self.profile)
        if command[0] == "xcodebuild" and "archive" in command:
            archive = Path(command[command.index("-archivePath") + 1])
            app = archive / "Products/Applications/Client.app"
            app.mkdir(parents=True)
            (app / "Info.plist").write_bytes(plistlib.dumps(self.info))
            symbols = archive / "dSYMs/Client.app.dSYM/Contents/Resources/DWARF"
            symbols.mkdir(parents=True)
            (symbols / "Client").write_bytes(b"debug symbols")
        elif command[:2] == ["xcodebuild", "-exportArchive"]:
            exported = Path(command[command.index("-exportPath") + 1])
            exported.mkdir()
            (exported / "Client.ipa").write_bytes(b"signed IPA")
            self.export_options = plistlib.loads(Path(command[-1]).read_bytes())
        elif command[:4] == ["ditto", "-c", "-k", "--keepParent"]:
            Path(command[-1]).write_bytes(b"unsigned ZIP")
        elif command[:3] == ["ditto", "-x", "-k"]:
            app = Path(command[-1]) / "Payload/Client.app"
            app.mkdir(parents=True)
            (app / "Info.plist").write_bytes(plistlib.dumps(self.info))
        return None

    def release(self, args, command=None):
        preparer = SimpleNamespace(prepare=self.prepare)
        with patch.object(self.helper, "run", side_effect=command or self.command), \
             patch.object(self.helper.shutil, "which", return_value="/tool"), \
             patch.object(self.helper.importlib.util, "spec_from_file_location", return_value=Mock(loader=Mock())), \
             patch.object(self.helper.importlib.util, "module_from_spec", return_value=preparer), \
             redirect_stdout(io.StringIO()):
            self.helper.release(args)

    def test_unsigned_archive_has_no_signing_or_apple_account_operations(self):
        self.release(self.args())
        archive = next(command for command in self.calls if "archive" in command)
        self.assertIn("CODE_SIGNING_ALLOWED=NO", archive)
        self.assertIn("generic/platform=iOS", archive)
        self.assertIn("TARGETED_DEVICE_FAMILY=1,2", archive)
        self.assertIn("-onlyUsePackageVersionsFromResolvedFile", archive)
        self.assertFalse(any(command[0] in ("security", "codesign") for command in self.calls))
        self.assertFalse(any("ProvisioningUpdates" in item or "DeviceRegistration" in item
                             for command in self.calls for item in command))
        self.prepare.assert_called_once_with("PP97C35JA7", "net.mich431.ffoxfork.dev", configuration="Release")
        generated_info = plistlib.loads((self.project.parent / "Info.plist").read_bytes())
        self.assertEqual(generated_info["CFBundleVersion"], "42")
        self.assertTrue(generated_info["ZenPersonalTeam"])
        self.assertEqual(set(path.name for path in self.output.iterdir()),
                         {"FFox-0.1.0-unsigned-ios-ipados.zip", "SHA256SUMS", "build-info.json"})
        self.assertEqual(json.loads((self.output / "build-info.json").read_text())["installation"], "requires-resigning")
        self.check_checksums()

    def check_checksums(self):
        for line in (self.output / "SHA256SUMS").read_text().splitlines():
            expected, name = line.split("  ")
            self.assertEqual(hashlib.sha256((self.output / name).read_bytes()).hexdigest(), expected)

    def test_signed_archive_exports_manual_non_thinned_ipa_without_private_metadata(self):
        self.release(self.args(signed=True))
        self.assertEqual(self.export_options, {
            "method": "debugging", "signingStyle": "manual", "teamID": "PP97C35JA7",
            "signingCertificate": self.identity,
            "provisioningProfiles": {"net.mich431.ffoxfork.dev": self.profile["UUID"]},
            "thinning": "<none>", "manageAppVersionAndBuildNumber": False,
        })
        self.assertEqual(sum(command[:2] == ["codesign", "--verify"] for command in self.calls), 2)
        metadata = (self.output / "build-info.json").read_text()
        for private in ("private-device-id", "test-certificate", self.identity, self.profile["UUID"]):
            self.assertNotIn(private, metadata)
        self.assertIn("signingExpires", metadata)
        self.assertTrue((self.output / "FFox-0.1.0-ios-ipados.ipa").is_file())
        self.check_checksums()

    def test_manual_signing_settings_apply_only_to_client_release(self):
        self.release(self.args(signed=True))
        objects = plistlib.loads((self.project / "project.pbxproj").read_bytes())["objects"]
        self.assertEqual(objects["client-release"]["buildSettings"], {
            "CODE_SIGN_STYLE": "Manual", "CODE_SIGN_IDENTITY": self.identity,
            "PROVISIONING_PROFILE_SPECIFIER": self.profile["UUID"],
        })
        self.assertEqual(objects["client-debug"]["buildSettings"], {"CODE_SIGN_STYLE": "Automatic"})
        self.assertEqual(objects["framework-release"]["buildSettings"], {"CODE_SIGNING_ALLOWED": "NO"})
        archive = next(command for command in self.calls if "archive" in command)
        for setting in ("PROVISIONING_PROFILE_SPECIFIER=", "CODE_SIGN_STYLE=", "CODE_SIGN_IDENTITY="):
            self.assertFalse(any(argument.startswith(setting) for argument in archive))

    def app_store_profile(self):
        profile = {key: value for key, value in self.profile.items() if key != "ProvisionedDevices"}
        profile["Entitlements"] = {**self.profile["Entitlements"],
                                   "application-identifier": "PP97C35JA7.net.mich431.ffoxfork.dev",
                                   "get-task-allow": False, "beta-reports-active": True}
        return profile

    def test_app_store_exports_testflight_ipa_and_symbols_with_correct_metadata(self):
        self.profile = self.app_store_profile()
        self.info["CFBundleVersion"] = "42.1"
        self.release(self.args(signed=True, extra=["--method", "app-store-connect", "--build-number", "42.1"]))
        self.assertEqual(self.export_options["method"], "app-store-connect")
        self.assertEqual(self.export_options["destination"], "export")
        self.assertTrue(self.export_options["uploadSymbols"])
        self.assertNotIn("thinning", self.export_options)
        metadata = json.loads((self.output / "build-info.json").read_text())
        self.assertEqual(metadata["installation"], "app-store-connect")
        self.assertEqual(metadata["signing"], "app-store-connect")
        self.assertEqual(metadata["buildNumber"], "42.1")
        self.assertEqual(sum(command[:2] == ["codesign", "--verify"] for command in self.calls), 2)
        self.assertEqual(set(path.name for path in self.output.iterdir()),
                         {"FFox-0.1.0-ios-ipados.ipa", "FFox-0.1.0-ios-ipados-dSYMs.zip", "SHA256SUMS", "build-info.json"})
        objects = plistlib.loads((self.project / "project.pbxproj").read_bytes())["objects"]
        self.assertEqual(objects["client-release"]["buildSettings"]["DEBUG_INFORMATION_FORMAT"], "dwarf-with-dsym")
        for private in ("private-device-id", self.identity, self.profile["UUID"]):
            self.assertNotIn(private, json.dumps(metadata))
        self.check_checksums()

    def test_app_store_profiles_require_explicit_id_beta_entitlement_and_no_device_fields(self):
        args = self.args(signed=True, extra=["--method", "app-store-connect"])
        profile = self.app_store_profile()
        self.helper.validate_profile(profile, args)
        invalid = []
        for entitlements in ({"application-identifier": "PP97C35JA7.*"},
                             {"application-identifier": "PP97C35JA7.net.mich431.*"},
                             {"beta-reports-active": False}, {"get-task-allow": True}):
            invalid.append({**profile, "Entitlements": {**profile["Entitlements"], **entitlements}})
        without_beta = {**profile["Entitlements"]}
        without_beta.pop("beta-reports-active")
        invalid.extend([{**profile, "ProvisionedDevices": []},
                        {**profile, "ProvisionedDevices": ["private-device-id"]},
                        {**profile, "ProvisionsAllDevices": False},
                        {**profile, "ProvisionsAllDevices": True},
                        {**profile, "Entitlements": without_beta}])
        for candidate in invalid:
            with self.subTest(profile=candidate), self.assertRaises(ValueError):
                self.helper.validate_profile(candidate, args)

    def test_profile_types_cannot_cross_app_store_and_registered_device_methods(self):
        for method in ("debugging", "release-testing"):
            with self.subTest(method=method), self.assertRaises(ValueError):
                self.helper.validate_profile(self.app_store_profile(), self.args(signed=True, extra=["--method", method]))
        args = self.args(signed=True, extra=["--method", "app-store-connect"])
        for get_task_allow in (False, True):
            profile = {**self.profile, "Entitlements": {**self.profile["Entitlements"],
                       "application-identifier": "PP97C35JA7.net.mich431.ffoxfork.dev",
                       "get-task-allow": get_task_allow, "beta-reports-active": True}}
            with self.subTest(get_task_allow=get_task_allow), self.assertRaises(ValueError):
                self.helper.validate_profile(profile, args)

    def test_app_store_build_number_format_and_signed_profile_are_required(self):
        for number in ("0", "10000", "42.100", "42.01", "42.1.1.1", "42.beta"):
            with self.subTest(number=number), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.args(signed=True, extra=["--method", "app-store-connect", "--build-number", number])
        for number in ("1", "9999.99.99", "42.0", "42.1"):
            with self.subTest(number=number):
                self.assertEqual(self.args(signed=True, extra=["--method", "app-store-connect", "--build-number", number]).build_number, number)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.args(extra=["--method", "app-store-connect"])
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.args(signed=True, extra=["--build-number", "42.1"])

    def test_exact_scoped_and_paid_team_wildcard_profiles(self):
        for app_id in ("PP97C35JA7.*", "PP97C35JA7.net.mich431.*", "PP97C35JA7.net.mich431.ffoxfork.dev"):
            with self.subTest(app_id=app_id):
                self.profile["Entitlements"]["application-identifier"] = app_id
                self.helper.validate_profile(self.profile, self.args(signed=True))

    def test_legacy_app_prefix_and_ad_hoc_export_supported(self):
        self.profile["ApplicationIdentifierPrefix"] = ["LEGACYPFX1"]
        self.profile["Entitlements"].update({"application-identifier": "LEGACYPFX1.*", "get-task-allow": False})
        self.helper.validate_profile(self.profile, self.args(signed=True, extra=["--method", "release-testing"]))

    def test_profiles_wrong_team_app_expiry_identity_or_method_rejected(self):
        invalid = []
        for app_id in ("OTHERTEAM1.*", "PP97C35JA7.net.mich43.*", "PP97C35JA7.net.*.dev", "PP97C35JA7.net.mich431*", "*"):
            invalid.append({**self.profile, "Entitlements": {**self.profile["Entitlements"], "application-identifier": app_id}})
        invalid.extend([
            {**self.profile, "TeamIdentifier": ["OTHERTEAM1"]},
            {**self.profile, "ExpirationDate": datetime.now(timezone.utc) - timedelta(days=1)},
            {**self.profile, "DeveloperCertificates": [b"different-certificate"]},
            {**self.profile, "ProvisionedDevices": []},
            {**self.profile, "ProvisionsAllDevices": True},
            {**self.profile, "Entitlements": {**self.profile["Entitlements"], "get-task-allow": False}},
        ])
        for profile in invalid:
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                self.helper.validate_profile(profile, self.args(signed=True))

    def test_invalid_profile_rejected_before_preparing_or_building(self):
        self.profile["ExpirationDate"] = datetime(2000, 1, 1)
        with self.assertRaises(ValueError):
            self.release(self.args(signed=True))
        self.prepare.assert_not_called()
        self.assertFalse(any(command[0] == "xcodebuild" for command in self.calls))
        self.assertFalse(self.output.exists())

    def test_app_version_bundle_and_device_family_must_match(self):
        cases = {"CFBundleIdentifier": "wrong.app", "CFBundleVersion": "1",
                 "CFBundleShortVersionString": "99.0.0", "UIDeviceFamily": [1]}
        for key, value in cases.items():
            with self.subTest(key=key):
                previous = self.info[key]
                self.info[key] = value
                with self.assertRaises(ValueError):
                    self.release(self.args())
                self.info[key] = previous
                self.assertFalse(any(command[0] == "ditto" for command in self.calls))

    def test_macro_pin_change_stops_before_build(self):
        lock = next(self.root.glob("firefox-ios/**/Package.resolved"))
        lock.write_text(json.dumps({"pins": [{"identity": "modifiedcopymacro", "state": {"revision": "changed"}}]}))
        with self.assertRaises(ValueError):
            self.release(self.args())
        self.prepare.assert_not_called()
        self.assertEqual(self.calls, [])

    def test_output_never_overwrites_existing_files(self):
        self.output.mkdir()
        (self.output / "keep").write_text("user work")
        with self.assertRaises(ValueError):
            self.release(self.args())
        self.assertEqual((self.output / "keep").read_text(), "user work")
        self.prepare.assert_not_called()

    def test_archive_failure_publishes_no_release_files(self):
        def command(command, capture=False):
            if command[0] == "xcodebuild":
                raise subprocess.CalledProcessError(65, command)
            return self.command(command, capture)

        with self.assertRaises(subprocess.CalledProcessError):
            self.release(self.args(), command=command)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_unsigned_artifact_refuses_embedded_private_profile(self):
        def command(command, capture=False):
            result = self.command(command, capture)
            if command[0] == "xcodebuild" and "archive" in command:
                archive = Path(command[command.index("-archivePath") + 1])
                (archive / "Products/Applications/Client.app/embedded.mobileprovision").touch()
            return result

        with self.assertRaises(ValueError):
            self.release(self.args(), command=command)
        self.assertFalse(any(command[0] == "ditto" for command in self.calls))
        self.assertEqual(list(self.output.iterdir()), [])

    def test_cli_rejects_ambiguous_signing_and_invalid_release_inputs(self):
        for flags in (["--version", "../bad"], ["--version", "01.2.3"], ["--build-number", "0"],
                      ["--team", "bad"], ["--bundle-id", "bad"], ["--identity", self.identity]):
            with self.subTest(flags=flags), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.args(extra=flags)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.args(signed=True, extra=["--identity", "not-a-certificate"])


if __name__ == "__main__":
    unittest.main()
