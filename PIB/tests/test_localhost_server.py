from __future__ import annotations

import unittest
from pathlib import Path

from scripts.serve_localhost import collect_snapshot, safe_repo_path


class LocalhostServerTests(unittest.TestCase):
    def test_collect_snapshot_exposes_manifest_and_latest_runs(self) -> None:
        snapshot = collect_snapshot()
        self.assertEqual(snapshot["manifest"]["benchmark_version"], "1.1.0-rc1")
        self.assertIsNotNone(snapshot["static"]["latest_run_dir"])
        self.assertIsNotNone(snapshot["dynamic"]["latest_run_dir"])
        self.assertTrue(snapshot["release_bundle"]["exists"])

    def test_safe_repo_path_rejects_path_escape(self) -> None:
        with self.assertRaises(ValueError):
            safe_repo_path("../outside.txt")

    def test_safe_repo_path_accepts_in_repo_file(self) -> None:
        path = safe_repo_path("README.md")
        self.assertEqual(path, (Path(__file__).resolve().parents[1] / "README.md").resolve())
