import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("prepare-ci-dependencies.py")


class PrepareCIDependenciesTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("prepare_ci_dependencies", SCRIPT)
        self.helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.helper)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = (self.base / "repo").resolve()
        self.root.mkdir()
        self.helper.ROOT = self.root
        self.source = self.base / "bundle"
        self.source.mkdir()
        self.original = "/old/repo"
        self.revision = "a" * 40
        inputs = {}
        for relative in self.helper.REQUIRED_INPUTS:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("pinned manifest\n")
            if relative == self.helper.REQUIRED_INPUTS[-1]:
                path.write_text(json.dumps({"pins": [{"identity": "test-package", "state": {"revision": self.revision}}]}))
            inputs[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        (self.source / "ci-dependencies.json").write_text(json.dumps({
            "format": 1, "original_root": self.original, "inputs": inputs,
        }))
        packages = self.source / ".build/SourcePackages"
        checkout = packages / "checkouts/test-package"
        (checkout / ".git/objects/info").mkdir(parents=True)
        (checkout / ".git/objects/info/alternates").write_text(
            self.original + "/.build/SourcePackages/repositories/test-package-123/objects\n")
        (checkout / ".git/config").write_text(
            '[remote "origin"]\n\turl = ' + self.original + '/.build/SourcePackages/repositories/test-package-123\n')
        (checkout / "binary").write_bytes(b"\x00/old/repo/unchanged\xff")
        (packages / "repositories/test-package-123/objects").mkdir(parents=True)
        artifact = packages / "artifacts/test-package/test.xcframework"
        artifact.mkdir(parents=True)
        (artifact / "binary").write_bytes(b"framework")
        (packages / "workspace-state.json").write_text(json.dumps({"object": {
            "dependencies": [{"packageRef": {"identity": "test-package"}, "subpath": "test-package",
                              "state": {"checkoutState": {"revision": self.revision}}}],
            "artifacts": [{"path": self.original + "/.build/SourcePackages/artifacts/test-package/test.xcframework", "targetName": "test"}],
            "prebuilts": [],
        }}))
        (self.source / "firefox-ios/build/nimbus").mkdir(parents=True)
        (self.source / "firefox-ios/build/nimbus/nimbus-fml").write_bytes(b"compiler")
        (self.source / ".tools/swiftlint").mkdir(parents=True)
        tool = self.source / ".tools/swiftlint/swiftlint"
        tool.write_bytes(b"lint")
        tool.chmod(0o755)
        self.archive = self.base / "dependencies.tar.gz"

    def bundle(self, extra=None):
        with tarfile.open(self.archive, "w:gz") as archive:
            archive.add(self.source / "ci-dependencies.json", arcname="ci-dependencies.json")
            for content in self.helper.CONTENTS:
                archive.add(self.source / content, arcname=content)
            if extra:
                info, content = extra
                archive.addfile(info, io.BytesIO(content) if content else None)

    def restore(self, revision=None):
        with patch.object(self.helper.subprocess, "check_output", return_value=(revision or self.revision) + "\n") as git_head, \
             patch.object(self.helper.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as git_object, \
             redirect_stdout(io.StringIO()):
            self.helper.restore(self.archive)
        return git_head, git_object

    def test_restore_relocates_paths_preserves_binaries_and_verifies_local_commits(self):
        self.bundle()
        head, objects = self.restore()
        packages = self.root / ".build/SourcePackages"
        self.assertNotIn(self.original, (packages / "workspace-state.json").read_text())
        alternate = packages / "checkouts/test-package/.git/objects/info/alternates"
        self.assertEqual(alternate.read_text(), str(packages / "repositories/test-package-123/objects") + "\n")
        self.assertIn(str(self.root), (packages / "checkouts/test-package/.git/config").read_text())
        self.assertEqual((packages / "checkouts/test-package/binary").read_bytes(), b"\x00/old/repo/unchanged\xff")
        self.assertEqual((self.root / ".tools/swiftlint/swiftlint").stat().st_mode & 0o777, 0o755)
        self.assertIn("protocol.allow=never", head.call_args.args[0])
        self.assertEqual(objects.call_args.kwargs["env"]["GIT_NO_LAZY_FETCH"], "1")

    def test_stale_manifest_hash_rejected_before_extraction(self):
        self.bundle()
        (self.root / "MozillaRustComponents/Package.swift").write_text("new binary version")
        with self.assertRaisesRegex(ValueError, "inputs changed"):
            self.restore()
        self.assertFalse((self.root / ".build/SourcePackages").exists())

    def test_wrong_checkout_revision_rejected_before_installing_bundle(self):
        self.bundle()
        with self.assertRaisesRegex(ValueError, "wrong revision"):
            self.restore(revision="b" * 40)
        self.assertFalse((self.root / ".build/SourcePackages").exists())

    def test_missing_binary_artifact_rejected(self):
        state = self.source / ".build/SourcePackages/workspace-state.json"
        data = json.loads(state.read_text())
        data["object"]["artifacts"][0]["path"] += "/absent"
        state.write_text(json.dumps(data))
        self.bundle()
        with self.assertRaisesRegex(ValueError, "Missing cached binary"):
            self.restore()
        self.assertFalse((self.root / ".build/SourcePackages").exists())

    def test_traversal_absolute_paths_and_unrelated_files_rejected(self):
        for name in ("../escape", "/tmp/escape", ".build/SourcePackages/../../../escape", "scripts/replace.py"):
            with self.subTest(name=name):
                info = tarfile.TarInfo(name)
                info.size = 4
                self.bundle(extra=(info, b"evil"))
                with self.assertRaises(ValueError):
                    self.restore()
                self.assertFalse((self.root / ".build/SourcePackages").exists())

    def test_symbolic_and_hard_links_cannot_escape_dependency_directories(self):
        for linktype, target in ((tarfile.SYMTYPE, "/tmp/escape"), (tarfile.SYMTYPE, "../../../../escape"),
                                 (tarfile.LNKTYPE, "scripts/private.py")):
            with self.subTest(target=target):
                info = tarfile.TarInfo(".build/SourcePackages/link")
                info.type = linktype
                info.linkname = target
                self.bundle(extra=(info, None))
                with self.assertRaises(ValueError):
                    self.restore()
                self.assertFalse((self.root / ".build/SourcePackages").exists())

    def test_internal_framework_symlink_allowed(self):
        info = tarfile.TarInfo(".build/SourcePackages/artifacts/current")
        info.type = tarfile.SYMTYPE
        info.linkname = "test-package/test.xcframework"
        self.bundle(extra=(info, None))
        self.restore()
        self.assertTrue((self.root / ".build/SourcePackages/artifacts/current/binary").is_file())

    def test_external_git_alternates_rejected(self):
        alternate = self.source / ".build/SourcePackages/checkouts/test-package/.git/objects/info/alternates"
        alternate.write_text("/external/git/objects\n")
        self.bundle()
        with self.assertRaisesRegex(ValueError, "external Git object"):
            self.restore()
        self.assertFalse((self.root / ".build/SourcePackages").exists())

    def test_existing_cache_never_overwritten(self):
        self.bundle()
        cache = self.root / ".build/SourcePackages"
        cache.mkdir(parents=True)
        (cache / "keep").write_text("user cache")
        with self.assertRaisesRegex(ValueError, "must be empty"):
            self.restore()
        self.assertEqual((cache / "keep").read_text(), "user cache")


if __name__ == "__main__":
    unittest.main()
