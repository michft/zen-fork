import importlib.util
import io
from datetime import datetime, timedelta, timezone
import plistlib
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("deploy-device.py")


def load_deployer():
    spec = importlib.util.spec_from_file_location("deploy_device", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeployDeviceTests(unittest.TestCase):
    def setUp(self):
        output = redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)
        self.deployer = load_deployer()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "node_modules").mkdir()
        self.app = self.root / ".build/DeviceDerivedData/Build/Products/Debug-iphoneos/Client.app"
        self.app.mkdir(parents=True)
        (self.app / "Info.plist").write_bytes(plistlib.dumps({
            "CFBundleIdentifier": "net.mich431.ffoxfork.dev",
        }))
        (self.app / "embedded.mobileprovision").touch()
        self.profile = {
            "ExpirationDate": datetime.now(timezone.utc) + timedelta(days=1),
            "Entitlements": {"application-identifier": "PP97C35JA7.net.mich431.ffoxfork.dev"},
            "ProvisionedDevices": list(self.deployer.DEVICES.values()),
        }

    def tearDown(self):
        self.temp.cleanup()

    def run_deploy(self, args, failure=None, profile=None):
        self.calls = []

        def run(command, **kwargs):
            self.calls.append(command)
            if failure == "build" and command[0] == "xcodebuild":
                raise subprocess.CalledProcessError(1, command)
            if failure == "signature" and command[:2] == ["codesign", "--verify"]:
                raise subprocess.CalledProcessError(1, command)
            if command[:3] == ["security", "cms", "-D"]:
                return subprocess.CompletedProcess(command, 0, plistlib.dumps(profile or self.profile))
            return subprocess.CompletedProcess(command, 0, b"")

        with patch.object(self.deployer, "ROOT", self.root), \
             patch.object(self.deployer.subprocess, "run", side_effect=run), \
             patch.object(self.deployer.shutil, "which", return_value="/tool"):
            self.deployer.deploy(args)
        return self.calls

    def test_dry_run_prints_plan_without_tool_calls_or_writes(self):
        empty_root = self.root / "untouched"
        with patch.object(self.deployer, "ROOT", empty_root), \
             patch.object(self.deployer.subprocess, "run") as run:
            self.assertEqual(self.deployer.main(["both", "--dry-run"]), 0)
        run.assert_not_called()
        self.assertFalse(empty_root.exists())

    def test_both_routes_build_install_and_launch_to_both_devices(self):
        calls = self.run_deploy(self.deployer.arguments(["both"]))
        destinations = [command[command.index("-destination") + 1]
                        for command in calls if command[0] == "xcodebuild"]
        self.assertEqual(destinations, [f"id={udid}" for udid in self.deployer.DEVICES.values()])
        installed = [command[command.index("--device") + 1]
                     for command in calls if "install" in command]
        self.assertEqual(installed, list(self.deployer.DEVICES.values()))
        launches = [command[command.index("--device") + 1]
                    for command in calls if "launch" in command]
        self.assertEqual(launches, list(self.deployer.DEVICES.values()))

    def test_build_and_signature_failures_prevent_install(self):
        for failure in ("build", "signature"):
            with self.subTest(failure=failure):
                args = self.deployer.arguments(["deadbeef7"])
                with self.assertRaises(subprocess.CalledProcessError):
                    self.run_deploy(args, failure=failure)
                self.assertFalse(any("install" in command for command in self.calls))

    def test_paid_wildcard_profiles_cover_both_devices(self):
        for app_id in ("PP97C35JA7.*", "PP97C35JA7.net.mich431.*"):
            with self.subTest(app_id=app_id):
                profile = {**self.profile, "Entitlements": {"application-identifier": app_id}}
                calls = self.run_deploy(self.deployer.arguments(["both"]), profile=profile)
                installed = [command[command.index("--device") + 1]
                             for command in calls if "install" in command]
                self.assertEqual(installed, list(self.deployer.DEVICES.values()))

    def test_unrelated_and_invalid_wildcards_prevent_install(self):
        for app_id in ("OTHERTEAM1.*", "PP97C35JA7.net.other.*", "PP97C35JA7.net.mich43.*",
                       "*", "PP97C35JA7.net.*.dev", "PP97C35JA7.net.mich431*"):
            with self.subTest(app_id=app_id):
                profile = {**self.profile, "Entitlements": {"application-identifier": app_id}}
                with self.assertRaises(RuntimeError):
                    self.run_deploy(self.deployer.arguments(["deadbeef7"]), profile=profile)
                self.assertFalse(any("install" in command for command in self.calls))

    def test_invalid_expired_and_wrong_device_profiles_prevent_install(self):
        for case in ("invalid", "expired", "wrong-device"):
            with self.subTest(case=case):
                profile = dict(self.profile)
                profile["Entitlements"] = dict(self.profile["Entitlements"])
                if case == "invalid":
                    profile["Entitlements"]["application-identifier"] = "wrong.app"
                elif case == "expired":
                    profile["ExpirationDate"] = datetime.now(timezone.utc) - timedelta(days=1)
                else:
                    profile["ProvisionedDevices"] = [self.deployer.DEVICES["deadbeef6"]]
                args = self.deployer.arguments(["deadbeef7"])
                with self.assertRaises(RuntimeError):
                    self.run_deploy(args, profile=profile)
                self.assertFalse(any("install" in command for command in self.calls))

    def test_lock_conflict_fails_before_deploy(self):
        (self.root / ".build").mkdir(exist_ok=True)
        with patch.object(self.deployer, "ROOT", self.root), \
             patch.object(self.deployer.fcntl, "flock", side_effect=BlockingIOError), \
             patch.object(self.deployer, "deploy") as deploy, \
             redirect_stderr(io.StringIO()):
            self.assertEqual(self.deployer.main(["deadbeef7"]), 1)
        deploy.assert_not_called()

    def test_launch_failure_reports_installed_and_fails(self):
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            if command[:4] == ["xcrun", "devicectl", "device", "process"]:
                raise subprocess.CalledProcessError(1, command)
            if command[:3] == ["security", "cms", "-D"]:
                return subprocess.CompletedProcess(command, 0, plistlib.dumps(self.profile))
            return subprocess.CompletedProcess(command, 0, b"")

        with patch.object(self.deployer, "ROOT", self.root), \
             patch.object(self.deployer.subprocess, "run", side_effect=run), \
             patch.object(self.deployer.shutil, "which", return_value="/tool"), \
             redirect_stderr(io.StringIO()) as output:
            self.assertEqual(self.deployer.main(["deadbeef7"]), 1)
        self.assertTrue(any("install" in command for command in calls))
        self.assertIn("Installed on deadbeef7, but launch failed.", output.getvalue())


if __name__ == "__main__":
    unittest.main()
