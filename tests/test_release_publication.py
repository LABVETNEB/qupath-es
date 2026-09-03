from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
GUARD = ROOT / "tools" / "release_guard.py"
RELEASING_DOC = ROOT / "docs" / "RELEASING.md"
ADR = ROOT / "docs" / "adr" / "0006-tag-gated-release-publication.md"
ADR_INDEX = ROOT / "docs" / "adr" / "README.md"
SPEC_PATH = "versions/0.7.0/release-es.json"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import build_release  # noqa: E402
import release_guard  # noqa: E402


ATTEST_SHA = "1e69f48acb82d1966a394da916b4c1698aa569d6"
CHECKOUT_SHA = "11d5960a326750d5838078e36cf38b85af677262"
SETUP_PYTHON_SHA = "a26af69be951a213d495a4c3e4e4022e16d87065"


def git_text(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.decode("utf-8", errors="strict").strip()


def run_git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


class ReleasePublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow_text = WORKFLOW.read_text(encoding="utf-8")
        cls.head = git_text(ROOT, "rev-parse", "HEAD")

    def test_new_release_files_are_strict_utf8_without_bom_and_use_lf(self):
        for path in (WORKFLOW, GUARD, RELEASING_DOC, ADR, ADR_INDEX):
            with self.subTest(path=path):
                raw = path.read_bytes()
                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
                raw.decode("utf-8", errors="strict")
                self.assertNotIn(b"\r", raw)
                self.assertTrue(raw.endswith(b"\n"))

    def test_release_workflow_is_manual_only(self):
        text = self.workflow_text
        self.assertIn("workflow_dispatch:", text)
        self.assertNotRegex(text, re.compile(r"(?m)^\s*push\s*:"))
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("schedule:", text)

    def test_release_workflow_has_exact_write_permissions(self):
        text = self.workflow_text
        block = text.split("permissions:\n", 1)[1].split("\n\n", 1)[0]
        permissions = {
            line.strip()
            for line in block.splitlines()
            if line.strip()
        }
        self.assertEqual(
            permissions,
            {
                "contents: write",
                "id-token: write",
                "attestations: write",
                "artifact-metadata: write",
            },
        )

    def test_release_workflow_pins_every_action_to_full_sha(self):
        refs = re.findall(r"uses:\s*([^@\s]+)@([^\s]+)", self.workflow_text)
        self.assertEqual(
            refs,
            [
                ("actions/checkout", CHECKOUT_SHA),
                ("actions/setup-python", SETUP_PYTHON_SHA),
                ("actions/attest", ATTEST_SHA),
            ],
        )
        for _, ref in refs:
            self.assertRegex(ref, r"^[0-9a-f]{40}$")

    def test_checkout_does_not_persist_write_credentials(self):
        text = self.workflow_text
        self.assertIn("fetch-depth: 0", text)
        self.assertIn("persist-credentials: false", text)

    def test_publication_sequence_is_fail_closed(self):
        text = self.workflow_text

        preflight = text.index("tools/release_guard.py preflight")
        tests = text.index("python -m unittest discover")
        build = text.index("tools/build_release.py")
        verify_outputs = text.index("tools/release_guard.py verify-outputs")
        attest = text.index("uses: actions/attest@")
        verify_attestation = text.index('gh attestation verify "$artifact"')
        publish = text.index('gh release create "$GITHUB_REF_NAME"')
        verify_release = text.index('gh release verify "$GITHUB_REF_NAME"')
        verify_asset = text.index('gh release verify-asset "$GITHUB_REF_NAME"')

        self.assertLess(preflight, tests)
        self.assertLess(tests, build)
        self.assertLess(build, verify_outputs)
        self.assertLess(verify_outputs, attest)
        self.assertLess(attest, verify_attestation)
        self.assertLess(verify_attestation, publish)
        self.assertLess(publish, verify_release)
        self.assertLess(verify_release, verify_asset)

    def test_attestation_policy_is_bound_to_tag_commit_and_workflow(self):
        text = self.workflow_text
        self.assertIn("subject-path: release-out/*", text)
        self.assertIn("--signer-workflow \"$signer\"", text)
        self.assertIn("--source-ref \"$GITHUB_REF\"", text)
        self.assertIn("--source-digest \"$GITHUB_SHA\"", text)
        self.assertIn("--deny-self-hosted-runners", text)

    def test_workflow_cannot_create_or_replace_release_identity(self):
        text = self.workflow_text
        self.assertIn("--verify-tag", text)
        self.assertNotIn("--clobber", text)
        self.assertNotIn("gh release delete", text)
        self.assertNotIn("git tag ", text)
        self.assertNotIn("git push ", text)
        self.assertNotIn("git update-ref", text)

    def test_release_source_state_is_publishable_at_current_commit(self):
        state = release_guard.verify_release_state(
            ROOT,
            source_commit=self.head,
            spec_path=SPEC_PATH,
        )
        self.assertEqual(state["qupath_version"], "0.7.0")
        self.assertEqual(state["locale"], "es")
        self.assertEqual(state["supported_status"], "stable")
        self.assertEqual(state["distributed_components"], ["qupath-core"])
        self.assertGreater(state["payload_files"], 0)

    def test_release_output_guard_accepts_builder_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "out"
            build_release.build_release(
                ROOT,
                SPEC_PATH,
                output_dir,
                release_tag="test-release-0.7.0-es",
                source_commit=self.head,
            )
            result = release_guard.verify_output_set(ROOT, output_dir)

            self.assertEqual(
                result["artifact_basename"],
                "qupath-es-0.7.0-es",
            )
            self.assertRegex(result["artifact"]["sha256"], r"^[0-9A-F]{64}$")
            self.assertRegex(result["manifest"]["sha256"], r"^[0-9A-F]{64}$")
            self.assertRegex(result["sbom"]["sha256"], r"^[0-9A-F]{64}$")

    def test_release_output_guard_rejects_extra_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "out"
            build_release.build_release(
                ROOT,
                SPEC_PATH,
                output_dir,
                release_tag="test-release-0.7.0-es",
                source_commit=self.head,
            )
            (output_dir / "unexpected.txt").write_text(
                "unexpected\n",
                encoding="utf-8",
            )

            with self.assertRaises(release_guard.ReleaseGuardError):
                release_guard.verify_output_set(ROOT, output_dir)

    def test_tag_guard_accepts_tag_on_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            run_git(repo, "init", "-b", "main")
            run_git(repo, "config", "user.name", "Release Test")
            run_git(repo, "config", "user.email", "release-test@example.invalid")

            (repo / "file.txt").write_text("one\n", encoding="utf-8")
            run_git(repo, "add", "file.txt")
            run_git(repo, "commit", "-m", "initial")
            commit = git_text(repo, "rev-parse", "HEAD")
            run_git(repo, "tag", "release-good")

            state = release_guard.verify_tag_checkout(
                repo,
                tag_ref="refs/tags/release-good",
                checkout_commit=commit,
                main_ref="refs/heads/main",
            )
            self.assertEqual(state["source_commit"], commit)
            self.assertEqual(state["tag"], "release-good")

    def test_tag_guard_rejects_tag_on_unmerged_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            run_git(repo, "init", "-b", "main")
            run_git(repo, "config", "user.name", "Release Test")
            run_git(repo, "config", "user.email", "release-test@example.invalid")

            (repo / "file.txt").write_text("main\n", encoding="utf-8")
            run_git(repo, "add", "file.txt")
            run_git(repo, "commit", "-m", "main")

            run_git(repo, "switch", "-c", "feature")
            (repo / "file.txt").write_text("feature\n", encoding="utf-8")
            run_git(repo, "add", "file.txt")
            run_git(repo, "commit", "-m", "feature")
            feature_commit = git_text(repo, "rev-parse", "HEAD")
            run_git(repo, "tag", "release-side")

            with self.assertRaises(release_guard.ReleaseGuardError):
                release_guard.verify_tag_checkout(
                    repo,
                    tag_ref="refs/tags/release-side",
                    checkout_commit=feature_commit,
                    main_ref="refs/heads/main",
                )

    def test_tag_guard_rejects_non_tag_ref(self):
        with self.assertRaises(release_guard.ReleaseGuardError):
            release_guard._validate_tag_ref("refs/heads/main")

    def test_adr_index_registers_publication_decision(self):
        text = ADR_INDEX.read_text(encoding="utf-8")
        self.assertIn(
            "[ADR-0006](0006-tag-gated-release-publication.md)",
            text,
        )


if __name__ == "__main__":
    unittest.main()
