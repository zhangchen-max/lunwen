# Clean Environment Reproduction

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
pip install -e .

python -m scripts.validate_all --cases data/cases.jsonl --rubrics data/rubrics.jsonl --ontology ontology --config pib_config.yaml
python -m scripts.freeze_release --check
python -m scripts.run_tests

python -m eval.run_static --mode heuristic --split test --output results/static/test_static.jsonl
python -m eval.run_dynamic --doctor dummy --split test --output results/dynamic/test_dynamic.jsonl
python -m scripts.no_oracle_baseline_audit
python -m scripts.freeze_release_reports
python -m scripts.text_contamination_scan
```

Canonical release artifacts expected from this reproduction:
- `results/static/test_static/run_xxx/metrics.json`
- `results/static/test_static/run_xxx/predictions.jsonl`
- `results/dynamic/test_dynamic/run_xxx/metrics.json`
- `results/dynamic/test_dynamic/run_xxx/predictions.jsonl`
- `results/audit/no_oracle_baselines.json`
- `results/audit/text_contamination_scan.json`
- `results/reports/pure_baselines.csv`
- `results/reports/guided_llm_baselines.csv`
- `results/reports/deprecated_results.json`
```
