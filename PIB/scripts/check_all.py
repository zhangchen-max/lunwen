from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> None:
    print(f"[check_all] running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PIB offline acceptance checks")
    parser.add_argument("--cases", type=Path, default=Path("data/cases.jsonl"))
    parser.add_argument("--rubrics", type=Path, default=Path("data/rubrics.jsonl"))
    parser.add_argument("--ontology", type=Path, default=Path("ontology"))
    parser.add_argument("--config", type=Path, default=Path("pib_config.yaml"))
    args = parser.parse_args()

    repo_root = Path.cwd()
    python = sys.executable

    _run(
        [
            python,
            "-m",
            "scripts.validate_all",
            "--cases",
            str(args.cases),
            "--rubrics",
            str(args.rubrics),
            "--ontology",
            str(args.ontology),
            "--config",
            str(args.config),
        ],
        cwd=repo_root,
    )
    _run([python, "-m", "scripts.sanity_check"], cwd=repo_root)
    _run([python, "-m", "scripts.run_tests"], cwd=repo_root)
    print("[check_all] all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
