from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import ci_component_matrix  # noqa: E402


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.decode("utf-8", errors="strict").strip()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


class MatrixRepo:
    def __init__(self, root: Path):
        self.root = root
        run_git(root, "init", "-b", "main")
        run_git(root, "config", "user.name", "Matrix Test")
        run_git(root, "config", "user.email", "matrix-test@example.invalid")

        write_json(
            root / "components" / "registry.json",
            {
                "components": [
                    {"id": "qupath-core", "type": "QUPATH_CORE"},
                    {"id": "instanseg", "type": "QUPATH_EXTENSION"},
                    {"id": "cellpose", "type": "QUPATH_EXTENSION"},
                ]
            },
        )
        for component_id in ("instanseg", "cellpose"):
            write_json(
                root / "components" / component_id / "component.json",
                {"component_id": component_id, "marker": "base"},
            )

        write_json(
            root / "versions" / "0.7.0" / "components.lock.json",
            {
                "components": [
                    {"component_id": "qupath-core", "marker": 1},
                    {"component_id": "instanseg", "marker": 1},
                    {"component_id": "cellpose", "marker": 1},
                ]
            },
        )
        write_json(
            root / "versions" / "0.7.0" / "localizations.lock.json",
            {
                "localizations": [
                    {
                        "component_id": "qupath-core",
                        "locale": "es",
                        "marker": 1,
                    },
                    {
                        "component_id": "instanseg",
                        "locale": "es",
                        "marker": 1,
                    },
                    {
                        "component_id": "cellpose",
                        "locale": "es",
                        "marker": 1,
                    },
                ]
            },
        )
        workflow = root / ".github" / "workflows" / "ci.yml"
        workflow.parent.mkdir(parents=True, exist_ok=True)
        workflow.write_text("name: CI\n", encoding="utf-8", newline="\n")
        docs = root / "docs" / "README.md"
        docs.parent.mkdir(parents=True, exist_ok=True)
        docs.write_text("base\n", encoding="utf-8", newline="\n")

        self.base = self.commit("base")

    def commit(self, message: str) -> str:
        run_git(self.root, "add", "-A")
        run_git(self.root, "commit", "-m", message)
        return run_git(self.root, "rev-parse", "HEAD")


class ComponentMatrixTests(unittest.TestCase):
    def make_repo(self, tmp: str) -> MatrixRepo:
        root = Path(tmp) / "repo"
        root.mkdir()
        return MatrixRepo(root)

    def test_direct_component_path_selects_only_that_component(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(tmp)
            write_json(
                repo.root / "components" / "cellpose" / "component.json",
                {"component_id": "cellpose", "marker": "changed"},
            )
            head = repo.commit("cellpose")

            result = ci_component_matrix.detect_components(
                repo.root,
                repo.base,
                head,
            )
            self.assertEqual(result["components"], ["cellpose"])

    def test_components_lock_diff_selects_only_changed_extension_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(tmp)
            path = repo.root / "versions" / "0.7.0" / "components.lock.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            for entry in data["components"]:
                if entry["component_id"] == "instanseg":
                    entry["marker"] = 2
            write_json(path, data)
            head = repo.commit("lock")

            result = ci_component_matrix.detect_components(
                repo.root,
                repo.base,
                head,
            )
            self.assertEqual(result["components"], ["instanseg"])

    def test_localization_lock_diff_selects_only_changed_component(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(tmp)
            path = (
                repo.root
                / "versions"
                / "0.7.0"
                / "localizations.lock.json"
            )
            data = json.loads(path.read_text(encoding="utf-8"))
            for entry in data["localizations"]:
                if entry["component_id"] == "cellpose":
                    entry["marker"] = 2
            write_json(path, data)
            head = repo.commit("localization lock")

            result = ci_component_matrix.detect_components(
                repo.root,
                repo.base,
                head,
            )
            self.assertEqual(result["components"], ["cellpose"])

    def test_registry_diff_selects_changed_extension_in_registry_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(tmp)
            path = repo.root / "components" / "registry.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            for entry in data["components"]:
                if entry["id"] == "instanseg":
                    entry["owner"] = "qupath"
            write_json(path, data)
            head = repo.commit("registry")

            result = ci_component_matrix.detect_components(
                repo.root,
                repo.base,
                head,
            )
            self.assertEqual(result["components"], ["instanseg"])

    def test_shared_component_contract_selects_every_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(tmp)
            path = repo.root / ".github" / "workflows" / "ci.yml"
            path.write_text(
                "name: CI\n# changed\n",
                encoding="utf-8",
                newline="\n",
            )
            head = repo.commit("ci")

            result = ci_component_matrix.detect_components(
                repo.root,
                repo.base,
                head,
            )
            self.assertEqual(result["components"], ["instanseg", "cellpose"])

    def test_unrelated_documentation_change_selects_no_component(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(tmp)
            path = repo.root / "docs" / "README.md"
            path.write_text("changed\n", encoding="utf-8", newline="\n")
            head = repo.commit("docs")

            result = ci_component_matrix.detect_components(
                repo.root,
                repo.base,
                head,
            )
            self.assertEqual(result["components"], [])

    def test_unknown_component_directory_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(tmp)
            path = repo.root / "components" / "rogue" / "component.json"
            write_json(path, {"component_id": "rogue"})
            head = repo.commit("rogue")

            with self.assertRaises(ci_component_matrix.ComponentMatrixError):
                ci_component_matrix.detect_components(
                    repo.root,
                    repo.base,
                    head,
                )

    def test_qupath_core_component_directory_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(tmp)
            path = repo.root / "components" / "qupath-core" / "forbidden.json"
            write_json(path, {"forbidden": True})
            head = repo.commit("core dir")

            with self.assertRaises(ci_component_matrix.ComponentMatrixError):
                ci_component_matrix.detect_components(
                    repo.root,
                    repo.base,
                    head,
                )

    def test_all_components_preserves_registry_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(tmp)
            result = ci_component_matrix.all_components(
                repo.root,
                repo.base,
            )
            self.assertEqual(result["components"], ["instanseg", "cellpose"])

    def test_github_output_is_compact_and_explicit_when_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "output.txt"
            ci_component_matrix.write_github_output(output, [])
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "components=[]\nhas_components=false\n",
            )

    def test_invalid_base_ref_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(tmp)
            with self.assertRaises(ci_component_matrix.ComponentMatrixError):
                ci_component_matrix.detect_components(
                    repo.root,
                    "does-not-exist",
                    repo.base,
                )


if __name__ == "__main__":
    unittest.main()
