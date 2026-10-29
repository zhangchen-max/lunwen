from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.freeze_release import build_manifest


class ReleaseManifestTests(unittest.TestCase):
    def test_release_manifest_matches_current_repository_state(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        manifest_path = repo_root / "release" / "benchmark_manifest.json"
        expected = build_manifest(repo_root)
        actual = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)

    def test_release_manifest_contains_frozen_file_hashes(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        manifest_path = repo_root / "release" / "benchmark_manifest.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertIn("cases_sha256", payload)
        self.assertIn("rubrics_sha256", payload)
        self.assertIn("splits_sha256", payload)
        self.assertIn("dataset_file_hashes", payload)
        self.assertIn("data/cases.jsonl", payload["dataset_file_hashes"])
        self.assertIn("data/rubrics.jsonl", payload["dataset_file_hashes"])
