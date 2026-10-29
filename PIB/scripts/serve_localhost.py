from __future__ import annotations

import argparse
import csv
import html
import json
import mimetypes
import subprocess
import sys
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import parse_qs, quote, urlparse

from eval.constants import BENCHMARK_VERSION, SCORING_POLICY_VERSION


REPO_ROOT = Path(__file__).resolve().parents[1]
LAST_ACTION_RESULT: Dict[str, Any] | None = None


def repo_relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def safe_repo_path(raw_path: str) -> Path:
    candidate = (REPO_ROOT / raw_path.lstrip("/")).resolve()
    if candidate != REPO_ROOT and REPO_ROOT not in candidate.parents:
        raise ValueError(f"Path escapes repository root: {raw_path}")
    return candidate


def latest_run_dir(output_jsonl: Path) -> Path | None:
    run_root = output_jsonl.with_suffix("")
    runs = sorted(run_root.glob("run_*"))
    return runs[-1] if runs else None


def read_json(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def manifest_snapshot() -> Dict[str, Any]:
    manifest_path = REPO_ROOT / "release" / "benchmark_manifest.json"
    manifest = read_json(manifest_path) or {}
    return {
        "path": repo_relative(manifest_path),
        "benchmark_version": manifest.get("benchmark_version", BENCHMARK_VERSION),
        "scoring_policy_version": manifest.get("scoring_policy_version", SCORING_POLICY_VERSION),
        "dataset_hash_sha256": manifest.get("dataset_hash_sha256"),
        "scoring_hash_sha256": manifest.get("scoring_hash_sha256"),
        "cases_sha256": manifest.get("cases_sha256"),
        "rubrics_sha256": manifest.get("rubrics_sha256"),
        "splits_sha256": manifest.get("splits_sha256"),
        "case_counts": manifest.get("case_counts", {}),
    }


def run_snapshot(task: str) -> Dict[str, Any]:
    output_jsonl = REPO_ROOT / "results" / task / f"test_{task}.jsonl"
    latest = latest_run_dir(output_jsonl)
    metrics = read_json(latest / "metrics.json") if latest else None
    return {
        "task": task,
        "output_jsonl": repo_relative(output_jsonl) if output_jsonl.exists() else repo_relative(output_jsonl),
        "latest_run_dir": repo_relative(latest) if latest else None,
        "metrics": metrics,
    }


def release_bundle_snapshot() -> Dict[str, Any]:
    bundle = REPO_ROOT / "release" / "PIB-Benchmark-v1.1.0-rc1"
    return {
        "path": repo_relative(bundle),
        "exists": bundle.exists(),
        "files": [
            "benchmark_manifest.json",
            "README.md",
            "DATASET_CARD.md",
            "CHANGELOG.md",
            "requirements.lock",
            "REPRODUCE.md",
            "RELEASE_NOTES.md",
        ],
    }


def audits_snapshot() -> Dict[str, Any]:
    no_oracle_path = REPO_ROOT / "results" / "audit" / "no_oracle_baselines.json"
    text_scan_path = REPO_ROOT / "results" / "audit" / "text_contamination_scan.json"
    no_oracle = read_json(no_oracle_path) or {}
    text_scan = read_json(text_scan_path) or {}
    return {
        "no_oracle": {
            "path": repo_relative(no_oracle_path),
            "allowed_slots_audit": no_oracle.get("allowed_slots_audit"),
        },
        "text_contamination": {
            "path": repo_relative(text_scan_path),
            "contaminated_case_count": text_scan.get("contaminated_case_count"),
            "hit_count": text_scan.get("hit_count"),
        },
    }


def baseline_snapshot() -> Dict[str, Any]:
    pure_path = REPO_ROOT / "results" / "reports" / "pure_baselines.csv"
    guided_path = REPO_ROOT / "results" / "reports" / "guided_llm_baselines.csv"
    deprecated_path = REPO_ROOT / "results" / "reports" / "deprecated_results.json"
    deprecated = read_json(deprecated_path) or {}
    return {
        "pure_path": repo_relative(pure_path),
        "guided_path": repo_relative(guided_path),
        "deprecated_path": repo_relative(deprecated_path),
        "pure_rows": read_csv_rows(pure_path),
        "guided_rows": read_csv_rows(guided_path),
        "deprecated_results": deprecated.get("deprecated_results", []),
    }


def collect_snapshot() -> Dict[str, Any]:
    return {
        "manifest": manifest_snapshot(),
        "static": run_snapshot("static"),
        "dynamic": run_snapshot("dynamic"),
        "audits": audits_snapshot(),
        "baselines": baseline_snapshot(),
        "release_bundle": release_bundle_snapshot(),
        "last_action": LAST_ACTION_RESULT,
    }


def action_sequence(action: str) -> List[List[str]]:
    python = sys.executable
    if action == "validate":
        return [
            [
                python,
                "-m",
                "scripts.validate_all",
                "--cases",
                "data/cases.jsonl",
                "--rubrics",
                "data/rubrics.jsonl",
                "--ontology",
                "ontology",
                "--config",
                "pib_config.yaml",
            ]
        ]
    if action == "acceptance":
        return [
            [
                python,
                "-m",
                "scripts.check_all",
                "--cases",
                "data/cases.jsonl",
                "--rubrics",
                "data/rubrics.jsonl",
                "--ontology",
                "ontology",
                "--config",
                "pib_config.yaml",
            ]
        ]
    if action == "static":
        return [
            [
                python,
                "-m",
                "eval.run_static",
                "--mode",
                "heuristic",
                "--split",
                "test",
                "--output",
                "results/static/test_static.jsonl",
            ]
        ]
    if action == "dynamic":
        return [
            [
                python,
                "-m",
                "eval.run_dynamic",
                "--doctor",
                "dummy",
                "--split",
                "test",
                "--output",
                "results/dynamic/test_dynamic.jsonl",
            ]
        ]
    if action == "audits":
        return [
            [python, "-m", "scripts.no_oracle_baseline_audit"],
            [python, "-m", "scripts.text_contamination_scan"],
            [python, "-m", "scripts.freeze_release_reports"],
            [python, "-m", "scripts.freeze_release", "--check"],
        ]
    if action == "refresh":
        return action_sequence("static") + action_sequence("dynamic") + action_sequence("audits")
    raise KeyError(action)


def run_action(action: str) -> Dict[str, Any]:
    started = time.time()
    steps = []
    ok = True
    for cmd in action_sequence(action):
        proc = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        step = {
            "cmd": cmd,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
        steps.append(step)
        if proc.returncode != 0:
            ok = False
            break
    return {
        "action": action,
        "ok": ok,
        "started_at": started,
        "duration_sec": round(time.time() - started, 3),
        "steps": steps,
    }


def render_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "<p class='muted'>No rows.</p>"
    headers = list(rows[0].keys())
    head_html = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    body_parts = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(row.get(h, '')))}</td>" for h in headers)
        body_parts.append(f"<tr>{cells}</tr>")
    return (
        "<div class='table-wrap'><table><thead><tr>"
        + head_html
        + "</tr></thead><tbody>"
        + "".join(body_parts)
        + "</tbody></table></div>"
    )


def file_link(rel_path: str | None) -> str:
    if not rel_path:
        return "<span class='muted'>missing</span>"
    href = "/files/" + quote(rel_path)
    return f"<a href='{href}'>{html.escape(rel_path)}</a>"


def render_page(snapshot: Dict[str, Any]) -> str:
    manifest = snapshot["manifest"]
    static = snapshot["static"]
    dynamic = snapshot["dynamic"]
    audits = snapshot["audits"]
    baselines = snapshot["baselines"]
    bundle = snapshot["release_bundle"]
    last_action = snapshot["last_action"]
    static_overall = ((static.get("metrics") or {}).get("summary") or {}).get("overall", {})
    dynamic_overall = ((dynamic.get("metrics") or {}).get("summary") or {}).get("overall", {})

    action_html = ""
    if last_action:
        step_blocks = []
        for step in last_action["steps"]:
            cmd = " ".join(step["cmd"])
            merged = (step.get("stdout") or "") + ("\n" + step.get("stderr") if step.get("stderr") else "")
            step_blocks.append(
                "<div class='log-card'>"
                f"<div class='log-title'>{html.escape(cmd)}</div>"
                f"<pre>{html.escape(merged.strip() or '[no output]')}</pre>"
                "</div>"
            )
        action_html = (
            "<section class='panel accent'>"
            f"<h2>Last Action: {html.escape(last_action['action'])}</h2>"
            f"<p>Status: {'PASS' if last_action['ok'] else 'FAIL'} | Duration: {last_action['duration_sec']}s</p>"
            + "".join(step_blocks)
            + "</section>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PIB Localhost Console</title>
  <style>
    :root {{
      --bg: #f4efe7;
      --ink: #1e2430;
      --muted: #677180;
      --panel: rgba(255,255,255,0.88);
      --line: #d8cfbf;
      --accent: #b9532f;
      --accent-2: #265f73;
      --shadow: 0 18px 50px rgba(30,36,48,0.10);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(185,83,47,0.12), transparent 32%),
        radial-gradient(circle at top right, rgba(38,95,115,0.10), transparent 28%),
        linear-gradient(180deg, #f8f3eb 0%, var(--bg) 100%);
    }}
    .shell {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 28px 20px 56px;
    }}
    .hero {{
      background: linear-gradient(135deg, rgba(30,36,48,0.95), rgba(38,95,115,0.92));
      color: #fff7ee;
      border-radius: 22px;
      padding: 28px;
      box-shadow: var(--shadow);
      overflow: hidden;
      position: relative;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      inset: auto -10% -50% auto;
      width: 320px;
      height: 320px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(255,255,255,0.15), transparent 65%);
    }}
    h1, h2, h3 {{
      font-family: Georgia, "Times New Roman", serif;
      margin: 0 0 12px;
    }}
    .hero p {{ margin: 6px 0; color: rgba(255,247,238,0.86); max-width: 80ch; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 18px;
      margin-top: 20px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid rgba(216,207,191,0.9);
      border-radius: 18px;
      padding: 18px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(8px);
    }}
    .panel.accent {{
      border-color: rgba(185,83,47,0.35);
    }}
    .muted {{ color: var(--muted); }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 10px;
      margin-top: 14px;
    }}
    .stat {{
      background: rgba(255,255,255,0.72);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
    }}
    .stat strong {{ display: block; font-size: 1.1rem; }}
    .actions {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 12px;
    }}
    form {{ margin: 0; }}
    button {{
      border: 0;
      border-radius: 999px;
      padding: 10px 16px;
      cursor: pointer;
      color: white;
      background: linear-gradient(135deg, var(--accent), #d47d42);
      font-weight: 600;
    }}
    button.secondary {{
      background: linear-gradient(135deg, var(--accent-2), #4688a1);
    }}
    .table-wrap {{ overflow-x: auto; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.94rem;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      text-align: left;
      padding: 10px 8px;
      vertical-align: top;
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      background: #191d26;
      color: #f7f1e7;
      border-radius: 14px;
      padding: 14px;
      font-family: "SFMono-Regular", Menlo, monospace;
      font-size: 0.86rem;
      overflow-x: auto;
    }}
    .log-card {{ margin-top: 12px; }}
    .log-title {{ font-weight: 700; margin-bottom: 8px; }}
    a {{ color: var(--accent-2); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .api-list code {{
      display: inline-block;
      background: rgba(38,95,115,0.08);
      border: 1px solid rgba(38,95,115,0.18);
      padding: 4px 8px;
      border-radius: 999px;
      margin: 4px 6px 0 0;
    }}
    @media (max-width: 640px) {{
      .hero, .panel {{ border-radius: 16px; }}
      .shell {{ padding: 16px 12px 36px; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <h1>PIB Localhost Console</h1>
      <p>本地离线控制台。用于在这台 Mac 上直接查看冻结版本、运行 benchmark 验证、刷新 static/dynamic baseline 产物，并通过 localhost API 与文件路由做本机核验。</p>
      <div class="stats">
        <div class="stat"><span class="muted">Benchmark</span><strong>{html.escape(str(manifest.get('benchmark_version')))}</strong></div>
        <div class="stat"><span class="muted">Scoring</span><strong>{html.escape(str(manifest.get('scoring_policy_version')))}</strong></div>
        <div class="stat"><span class="muted">Cases</span><strong>{html.escape(str((manifest.get('case_counts') or {}).get('cases')))}</strong></div>
        <div class="stat"><span class="muted">Bundle</span><strong>{'Ready' if bundle.get('exists') else 'Missing'}</strong></div>
      </div>
      <div class="actions">
        <form method="post" action="/action"><input type="hidden" name="action" value="validate"><button type="submit">Validate</button></form>
        <form method="post" action="/action"><input type="hidden" name="action" value="acceptance"><button type="submit" class="secondary">Acceptance</button></form>
        <form method="post" action="/action"><input type="hidden" name="action" value="static"><button type="submit">Run Static</button></form>
        <form method="post" action="/action"><input type="hidden" name="action" value="dynamic"><button type="submit">Run Dynamic</button></form>
        <form method="post" action="/action"><input type="hidden" name="action" value="audits"><button type="submit" class="secondary">Refresh Audits</button></form>
        <form method="post" action="/action"><input type="hidden" name="action" value="refresh"><button type="submit">Refresh All</button></form>
      </div>
    </section>

    {action_html}

    <div class="grid">
      <section class="panel">
        <h2>Frozen Manifest</h2>
        <p>{file_link(manifest.get('path'))}</p>
        <p><strong>dataset_hash</strong><br>{html.escape(str(manifest.get('dataset_hash_sha256')))}</p>
        <p><strong>scoring_hash</strong><br>{html.escape(str(manifest.get('scoring_hash_sha256')))}</p>
        <p><strong>cases_sha256</strong><br>{html.escape(str(manifest.get('cases_sha256')))}</p>
        <p><strong>rubrics_sha256</strong><br>{html.escape(str(manifest.get('rubrics_sha256')))}</p>
        <p><strong>splits_sha256</strong><br>{html.escape(str(manifest.get('splits_sha256')))}</p>
      </section>

      <section class="panel">
        <h2>Static Test Baseline</h2>
        <p>Run: {file_link(static.get('latest_run_dir'))}</p>
        <p>Metrics: {file_link((static.get('latest_run_dir') + '/metrics.json') if static.get('latest_run_dir') else None)}</p>
        <div class="stats">
          <div class="stat"><span class="muted">top1</span><strong>{html.escape(str(static_overall.get('top1_acc')))}</strong></div>
          <div class="stat"><span class="muted">top5</span><strong>{html.escape(str(static_overall.get('top5_cov')))}</strong></div>
          <div class="stat"><span class="muted">n</span><strong>{html.escape(str(static_overall.get('n')))}</strong></div>
        </div>
      </section>

      <section class="panel">
        <h2>Dynamic Test Baseline</h2>
        <p>Run: {file_link(dynamic.get('latest_run_dir'))}</p>
        <p>Metrics: {file_link((dynamic.get('latest_run_dir') + '/metrics.json') if dynamic.get('latest_run_dir') else None)}</p>
        <div class="stats">
          <div class="stat"><span class="muted">must_ask</span><strong>{html.escape(str(dynamic_overall.get('must_ask_hit_rate')))}</strong></div>
          <div class="stat"><span class="muted">turns</span><strong>{html.escape(str(dynamic_overall.get('turns')))}</strong></div>
          <div class="stat"><span class="muted">harm_flags</span><strong>{html.escape(str(dynamic_overall.get('harm_flags_count')))}</strong></div>
        </div>
      </section>

      <section class="panel">
        <h2>Audits</h2>
        <p>No-oracle: {file_link(audits['no_oracle']['path'])}</p>
        <p>allowed_slots matches ontology: <strong>{html.escape(str((audits['no_oracle']['allowed_slots_audit'] or {}).get('matches_global_ontology_for_all_contexts')))}</strong></p>
        <p>Text scan: {file_link(audits['text_contamination']['path'])}</p>
        <p>contaminated_case_count: <strong>{html.escape(str(audits['text_contamination'].get('contaminated_case_count')))}</strong></p>
      </section>
    </div>

    <section class="panel">
      <h2>Baseline Tables</h2>
      <p>Pure baselines: {file_link(baselines.get('pure_path'))}</p>
      {render_table(baselines.get('pure_rows', []))}
      <p style="margin-top:16px;">Guided LLM baselines: {file_link(baselines.get('guided_path'))}</p>
      {render_table(baselines.get('guided_rows', []))}
    </section>

    <section class="panel">
      <h2>Release Bundle</h2>
      <p>Bundle root: {file_link(bundle.get('path'))}</p>
      <div class="api-list">{"".join(f"<code>{html.escape(name)}</code>" for name in bundle.get('files', []))}</div>
    </section>

    <section class="panel">
      <h2>JSON API</h2>
      <p class="muted">适合 curl / 浏览器直接验证。</p>
      <div class="api-list">
        <code>/api/status</code>
        <code>/api/manifest</code>
        <code>/api/static</code>
        <code>/api/dynamic</code>
        <code>/api/audits</code>
        <code>/api/baselines</code>
      </div>
    </section>
  </div>
</body>
</html>"""


class PIBLocalhostHandler(BaseHTTPRequestHandler):
    server_version = "PIBLocalhost/1.0"

    def _send_head_only(self, content_type: str, content_length: int, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(content_length))
        self.end_headers()

    def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, content: str, status: int = 200) -> None:
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, rel_path: str) -> None:
        try:
            file_path = safe_repo_path(rel_path)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
            return
        if not file_path.exists() or not file_path.is_file():
            self._send_json({"error": f"File not found: {rel_path}"}, status=404)
            return
        content = file_path.read_bytes()
        mime_type, _ = mimetypes.guess_type(file_path.name)
        self.send_response(200)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(render_page(collect_snapshot()))
            return
        if parsed.path == "/api/status":
            self._send_json(collect_snapshot())
            return
        if parsed.path == "/api/manifest":
            self._send_json(manifest_snapshot())
            return
        if parsed.path == "/api/static":
            self._send_json(run_snapshot("static"))
            return
        if parsed.path == "/api/dynamic":
            self._send_json(run_snapshot("dynamic"))
            return
        if parsed.path == "/api/audits":
            self._send_json(audits_snapshot())
            return
        if parsed.path == "/api/baselines":
            self._send_json(baseline_snapshot())
            return
        if parsed.path.startswith("/files/"):
            rel = parsed.path.removeprefix("/files/")
            self._send_file(rel)
            return
        self._send_json({"error": "Not found"}, status=404)

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = render_page(collect_snapshot()).encode("utf-8")
            self._send_head_only("text/html; charset=utf-8", len(body), status=200)
            return
        if parsed.path == "/api/status":
            body = json.dumps(collect_snapshot(), ensure_ascii=False, indent=2).encode("utf-8")
            self._send_head_only("application/json; charset=utf-8", len(body), status=200)
            return
        if parsed.path == "/api/manifest":
            body = json.dumps(manifest_snapshot(), ensure_ascii=False, indent=2).encode("utf-8")
            self._send_head_only("application/json; charset=utf-8", len(body), status=200)
            return
        self._send_head_only("application/json; charset=utf-8", len(b'{"error":"Not found"}'), status=404)

    def do_POST(self) -> None:
        global LAST_ACTION_RESULT
        parsed = urlparse(self.path)
        if parsed.path != "/action":
            self._send_json({"error": "Not found"}, status=404)
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length).decode("utf-8")
        form = parse_qs(body)
        action = form.get("action", [""])[0]
        try:
            LAST_ACTION_RESULT = run_action(action)
        except KeyError:
            self._send_json({"error": f"Unknown action: {action}"}, status=400)
            return
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stdout.write(f"[localhost] {self.address_string()} - {fmt % args}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve PIB localhost console")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    httpd = ThreadingHTTPServer((args.host, args.port), PIBLocalhostHandler)
    print(f"PIB localhost console serving on http://{args.host}:{args.port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
