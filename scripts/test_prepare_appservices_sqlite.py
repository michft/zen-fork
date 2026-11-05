import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parent.parent


def load_helper():
    spec = importlib.util.spec_from_file_location("prepare_appservices_sqlite",
                                                  ROOT / "scripts/prepare-appservices-sqlite.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper


CACHE = ROOT / load_helper().XCFRAMEWORK


class AppServicesSQLitePreparationTests(unittest.TestCase):
    def setUp(self):
        self.helper = load_helper()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.binaries = {}
        slices = {}
        for name, (sdk, targets, _) in self.helper.SLICES.items():
            binary = self.root / self.helper.XCFRAMEWORK / name / "MozillaRustComponents.framework/MozillaRustComponents"
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"library " + self.helper.OLD_SOURCE_ID + name.encode())
            self.binaries[name] = binary
            slices[name] = (sdk, targets, hashlib.sha256(binary.read_bytes()).hexdigest())
        self.helper.SLICES = slices

    def contents(self):
        return {name: binary.read_bytes() for name, binary in self.binaries.items()}

    def test_patched_libraries_are_verified_without_tools(self):
        for binary in self.binaries.values():
            binary.write_bytes(b"library " + self.helper.NEW_SOURCE_ID)
        with patch.object(self.helper, "tool", side_effect=AssertionError("unexpected tool use")):
            self.assertFalse(self.helper.apply(self.root))

    def test_changed_app_services_library_is_rejected_without_edits(self):
        self.binaries["ios-arm64"].write_bytes(b"different App Services release")
        before = self.contents()
        with self.assertRaisesRegex(ValueError, "review the SQLite replacement"):
            self.helper.apply(self.root)
        self.assertEqual(self.contents(), before)

    def test_unreviewed_sqlite_source_is_rejected_without_edits(self):
        source = self.root / "sqlite.zip"
        with zipfile.ZipFile(source, "w") as archive:
            archive.writestr(f"{self.helper.SOURCE_DIRECTORY}/sqlite3.c", "int tampered;")
            archive.writestr(f"{self.helper.SOURCE_DIRECTORY}/sqlite3.h", self.helper.NEW_SOURCE_ID.decode())
        self.helper.SOURCE = source
        before = self.contents()
        with patch.object(self.helper.shutil, "which", return_value="/usr/bin/xcrun"), \
                self.assertRaisesRegex(ValueError, "reviewed sqlite.org release"):
            self.helper.apply(self.root)
        self.assertEqual(self.contents(), before)

    def test_missing_cache_is_an_actionable_error(self):
        shutil.rmtree(self.root / ".build")
        with self.assertRaisesRegex(ValueError, "restore the pinned dependency cache"):
            self.helper.apply(self.root)

    def test_library_symlink_is_rejected(self):
        binary = self.binaries["ios-arm64"]
        outside = self.root / "outside"
        outside.write_bytes(binary.read_bytes())
        binary.unlink()
        binary.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "Unexpected App Services library path"):
            self.helper.apply(self.root)

    def test_tracked_source_matches_reviewed_release(self):
        data = self.helper.SOURCE.read_bytes()
        self.assertEqual(hashlib.sha3_256(data).hexdigest(), self.helper.SOURCE_SHA3_256)
        with zipfile.ZipFile(self.helper.SOURCE) as archive:
            header = archive.read(f"{self.helper.SOURCE_DIRECTORY}/sqlite3.h")
        self.assertIn(b'#define SQLITE_VERSION        "3.54.1"', header)
        self.assertIn(self.helper.NEW_SOURCE_ID, header)

    def test_compile_options_parse_adjacent_strings(self):
        data = b"\x00ENABLE_FTS5\x00MAX_SCHEMA=10000000\x00THREADSAFE=1\x00COMPILER=clang\x00"
        self.assertEqual(self.helper.options(data), {"ENABLE_FTS5", "MAX_SCHEMA=10000000", "THREADSAFE=1"})

    def test_device_and_ci_preparation_apply_both_security_patches(self):
        for script in ("prepare-personal-device.py", "prepare-ci-dependencies.py"):
            spec = importlib.util.spec_from_file_location(script[:-3].replace("-", "_"), ROOT / "scripts" / script)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            names, roots = [], []

            def spec_for(name, path):
                names.append(Path(path).name)
                return SimpleNamespace(loader=SimpleNamespace(
                    exec_module=lambda loaded: setattr(loaded, "apply", roots.append)))

            with patch.object(module.importlib.util, "spec_from_file_location", side_effect=spec_for), \
                    patch.object(module.importlib.util, "module_from_spec", side_effect=lambda _: SimpleNamespace()):
                module.apply_security_patches(self.root)
            self.assertEqual(names, ["prepare-down-security.py", "prepare-appservices-sqlite.py"], script)
            self.assertEqual(roots, [self.root, self.root], script)

@unittest.skipUnless(os.environ.get("APPSERVICES_SQLITE_INTEGRATION") == "1" and shutil.which("xcrun"),
                     "set APPSERVICES_SQLITE_INTEGRATION=1 with Xcode installed")
class AppServicesSQLiteIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.helper = load_helper()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def sqlite(self, source_directory, program, sanitize=True):
        executable = self.root / "sqlite-test"
        flags = [f"-D{define}" for define in self.helper.DEFINES]
        if sanitize:
            flags.append("-fsanitize=address")
        subprocess.run(["xcrun", "clang", "-g", "-O1", "-w", *flags, "-I", str(source_directory),
                        str(program), str(source_directory / "sqlite3.c"), "-o", str(executable)], check=True)
        return subprocess.run([str(executable)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_fts5_regressions_and_app_services_tables(self):
        source = self.root / "source"
        source.mkdir()
        self.helper.unpack_source(source)
        program = self.root / "fts5.c"
        program.write_text(r"""
#include <stdio.h>
#include "sqlite3.h"
static int row(void *p, int n, char **v, char **c) { printf("%s\n", v[0] ? v[0] : "NULL"); return 0; }
int main(void) {
  sqlite3 *db;
  char *error = 0;
  sqlite3_open(":memory:", &db);
  int rc = sqlite3_exec(db,
    "CREATE VIRTUAL TABLE t1 USING fts5(x, detail=none);"
    "WITH RECURSIVE c(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM c WHERE x<55)"
    " INSERT INTO t1(rowid, x) SELECT x, 'ab' FROM c;"
    "INSERT INTO t1(rowid, x) VALUES(-9223372036854775808, 'abc');"
    "SELECT count(*) FROM t1('a*');"
    "CREATE VIRTUAL TABLE amp_fts USING fts5(full_keywords, title, content='', contentless_delete=1,"
    " tokenize=\"porter unicode61 remove_diacritics 2 tokenchars '''-'\");"
    "INSERT INTO amp_fts(rowid, full_keywords, title) VALUES(1, 'running shoes', 'Shoe Shop'),"
    " (2, 'caf\xC3\xA9 menu', 'Caf\xC3\xA9'), (3, 'run-club', 'Clubs');"
    "DELETE FROM amp_fts WHERE rowid = 1;"
    "SELECT group_concat(rowid) FROM (SELECT rowid FROM amp_fts WHERE amp_fts MATCH 'run* OR cafe' ORDER BY rowid);"
    "SELECT sqlite_version();", row, 0, &error);
  if (rc != SQLITE_OK) { fprintf(stderr, "%s\n", error); return 1; }
  return 0;
}
""")
        result = self.sqlite(source, program)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["56", "2,3", "3.54.1"])
        self.assertNotIn("AddressSanitizer", result.stderr)

    @unittest.skipUnless(CACHE.is_dir(), "restore the App Services dependency cache")
    def test_real_libraries_are_rebuilt_once_and_keep_architectures(self):
        members = {}
        original = True
        for name, (_, _, digest) in self.helper.SLICES.items():
            relative = self.helper.XCFRAMEWORK / name / "MozillaRustComponents.framework/MozillaRustComponents"
            target = self.root / relative
            target.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / relative, target)
            original = original and self.helper.state(target, digest) == "original"
            members[name] = subprocess.run(["xcrun", "lipo", "-archs", str(target)], check=True,
                                           stdout=subprocess.PIPE, text=True).stdout.split()
        self.assertEqual(self.helper.apply(self.root), original)
        self.assertFalse(self.helper.apply(self.root))
        for name, architectures in members.items():
            target = self.root / self.helper.XCFRAMEWORK / name / "MozillaRustComponents.framework/MozillaRustComponents"
            data = target.read_bytes()
            self.assertNotIn(self.helper.OLD_SOURCE_ID, data)
            self.assertIn(self.helper.NEW_SOURCE_ID, data)
            self.assertEqual(subprocess.run(["xcrun", "lipo", "-archs", str(target)], check=True,
                                            stdout=subprocess.PIPE, text=True).stdout.split(), architectures)


if __name__ == "__main__":
    unittest.main()
