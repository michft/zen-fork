import difflib
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".build/SourcePackages/checkouts/Down"


def load_helper():
    spec = importlib.util.spec_from_file_location("prepare_down_security", ROOT / "scripts/prepare-down-security.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper


class DownSecurityPreparationTests(unittest.TestCase):
    def setUp(self):
        self.helper = load_helper()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.checkout = self.root / ".build/SourcePackages/checkouts/Down"
        self.original = {name: f"original {name}\n" for name in self.helper.HASHES}
        final = {name: content.replace("original", "patched") for name, content in self.original.items()}
        self.helper.HASHES = {name: (hashlib.sha256(content.encode()).hexdigest(),
                                     hashlib.sha256(final[name].encode()).hexdigest())
                              for name, content in self.original.items()}
        for name, content in self.original.items():
            path = self.checkout / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        patch_dir = self.root / "patches/down"
        patch_dir.mkdir(parents=True)
        self.helper.PATCH_DIRECTORY = patch_dir
        changes = "".join("".join(difflib.unified_diff(content.splitlines(keepends=True),
                                                     final[name].splitlines(keepends=True),
                                                     fromfile="a/" + name, tofile="b/" + name))
                          for name, content in self.original.items())
        self.helper.PATCHES = ("fixture.patch",)
        (patch_dir / "fixture.patch").write_text(changes)
        revision = patch.object(self.helper.subprocess, "check_output", return_value=self.helper.REVISION + "\n")
        self.git = revision.start()
        self.addCleanup(revision.stop)

    def test_apply_is_idempotent_and_git_cannot_fetch(self):
        self.assertTrue(self.helper.apply(self.root))
        self.assertFalse(self.helper.apply(self.root))
        for name, hashes in self.helper.HASHES.items():
            self.assertEqual(self.helper.digest(self.checkout / name), hashes[1])
        self.assertIn("protocol.allow=never", self.git.call_args.args[0])
        self.assertEqual(self.git.call_args.kwargs["env"]["GIT_NO_LAZY_FETCH"], "1")

    def test_unknown_revision_and_changed_source_are_rejected_without_edits(self):
        self.git.return_value = "a" * 40
        with self.assertRaisesRegex(ValueError, "revision changed"):
            self.helper.apply(self.root)
        self.git.return_value = self.helper.REVISION
        first = next(iter(self.original))
        (self.checkout / first).write_text("user modification\n")
        with self.assertRaisesRegex(ValueError, "source hashes changed"):
            self.helper.apply(self.root)
        for name, content in self.original.items():
            if name != first:
                self.assertEqual((self.checkout / name).read_text(), content)

    def test_unreviewed_patch_output_is_rejected_before_changing_checkout(self):
        self.helper.HASHES = {name: (hashes[0], "0" * 64) for name, hashes in self.helper.HASHES.items()}
        with self.assertRaisesRegex(ValueError, "output hashes"):
            self.helper.apply(self.root)
        for name, content in self.original.items():
            self.assertEqual((self.checkout / name).read_text(), content)

    def test_missing_cache_is_an_actionable_error(self):
        shutil.rmtree(self.checkout)
        with self.assertRaisesRegex(ValueError, "restore the pinned dependency cache"):
            self.helper.apply(self.root)

    def test_separate_restore_stage_uses_tracked_patch_directory(self):
        stage = self.root / "stage"
        destination = stage / ".build/SourcePackages/checkouts/Down"
        destination.parent.mkdir(parents=True)
        self.checkout.rename(destination)

        self.assertTrue(self.helper.apply(stage))
        self.assertFalse((stage / "patches/down").exists())

    def test_source_symlink_is_rejected(self):
        name = next(iter(self.original))
        path = self.checkout / name
        path.unlink()
        path.symlink_to(self.root / "outside")
        with self.assertRaisesRegex(ValueError, "Unexpected Down source path"):
            self.helper.apply(self.root)

    def test_incomplete_backport_state_is_rejected(self):
        self.helper.apply(self.root)
        name = next(iter(self.original))
        (self.checkout / name).write_text(self.original[name])
        with self.assertRaisesRegex(ValueError, "backports are incomplete"):
            self.helper.apply(self.root)


@unittest.skipUnless(os.environ.get("DOWN_CMARK_INTEGRATION") == "1" and CACHE.is_dir() and shutil.which("cc"),
                     "set DOWN_CMARK_INTEGRATION=1 with a restored Down cache and a C compiler")
class DownCmarkRegressionTests(unittest.TestCase):
    def test_real_cmark_backports_keep_markdown_output_and_bound_regression_inputs(self):
        helper = load_helper()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout = root / ".build/SourcePackages/checkouts/Down"
            source = checkout / "Sources/cmark"
            shutil.copytree(CACHE / "Sources/cmark", source, copy_function=shutil.copyfile)
            git = ["git", "-c", "protocol.allow=never", "-C", str(CACHE)]
            env = {**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"}
            for name in helper.HASHES:
                original = subprocess.check_output([*git, "show", f"{helper.REVISION}:{name}"], env=env)
                (checkout / name).write_bytes(original)
            main = root / "main.c"
            main.write_text('''#include <stdio.h>
#include <stdlib.h>
#include "cmark.h"
int main(void) {
  char buffer[4096];
  size_t size;
  cmark_parser *parser = cmark_parser_new(CMARK_OPT_DEFAULT);
  while ((size = fread(buffer, 1, sizeof(buffer), stdin)) != 0) {
    cmark_parser_feed(parser, buffer, size);
  }
  cmark_node *document = cmark_parser_finish(parser);
  char *html = cmark_render_html(document, CMARK_OPT_DEFAULT);
  fputs(html, stdout);
  free(html);
  cmark_node_free(document);
  cmark_parser_free(parser);
  return 0;
}
''')
            ordinary = [
                "# Heading\n\nA **bold** and *em* [link](https://example.com).\n",
                "![alt [text](https://example.com)](image.png) [another](https://example.org)\n",
                "[outer [inner](url)](url)\n",
                "- one\n  - nested\n\n- two\n\n",
                "> - one\n>\n>\n> - two\n",
                "- item\n\n      code\n\n\n      more code\n",
                "- item\n\n  <div>\n\n\n  content\n  </div>\n",
                "> *nested **bold** and emphasis*\n\n`code`\n",
                "## [Down](https://github.com/johnxnnguyen/Down)",
            ]
            for fixture in (CACHE / "README.md", CACHE / "Down-Example/Shared/README-sample.md"):
                if fixture.is_file():
                    ordinary.append(fixture.read_text())
            binary = root / "cmark"
            command = [shutil.which("cc"), "-O2", "-I", str(source), str(main),
                       *map(str, sorted(source.glob("*.c"))), "-o", str(binary)]
            def compile_parser():
                result = subprocess.run(command, capture_output=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr.decode())

            compile_parser()
            expected = [subprocess.check_output([binary], input=text.encode(), timeout=3) for text in ordinary]
            with patch.object(helper.subprocess, "check_output", return_value=helper.REVISION):
                self.assertTrue(helper.apply(root))
                self.assertFalse(helper.apply(root))
            compile_parser()
            for text, output in zip(ordinary, expected):
                self.assertEqual(subprocess.check_output([binary], input=text.encode(), timeout=3), output)
            snapshot = CACHE / "Tests/DownTests/__Snapshots__/BindingTests/testHTMLBindingsWork.1.txt"
            if snapshot.is_file():
                self.assertEqual(expected[8].rstrip(b"\n"), snapshot.read_bytes().rstrip(b"\n"))
            repetitions = 20000
            regressions = ["![[]()" * repetitions,
                           " -" * repetitions + "x" + "\n" * repetitions,
                           ">" * repetitions + "a*" * repetitions]
            for name, markdown in zip(("brackets", "blank lists", "blockquote emphasis"), regressions):
                with self.subTest(regression=name):
                    started = time.perf_counter()
                    result = subprocess.run([binary], input=markdown.encode(), stdout=subprocess.DEVNULL,
                                            stderr=subprocess.PIPE, timeout=3, check=True)
                    self.assertEqual(result.returncode, 0)
                    print(f"Down cmark {name}: {time.perf_counter() - started:.3f}s", flush=True)


if __name__ == "__main__":
    unittest.main()
