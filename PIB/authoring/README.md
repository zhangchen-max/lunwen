# Authoring Workflow

`authoring/cases_template.csv` is the stable offline authoring contract for expanding the benchmark.
`authoring/pilot_casebank_v11.csv` is the deterministic generated seed dataset currently used to build `data/cases.jsonl` and `data/rubrics.jsonl` at 110-case scale.

## Row Model

- One row equals one case.
- JSON-valued columns keep nested structures editable without introducing extra dependencies.
- `scripts/build_cases.py` compiles the CSV into `cases.jsonl` and `rubrics.jsonl`, then immediately re-validates the outputs through the shared schema loaders.

## Required Columns

- `case_id`, `dsm_module`, `label`
- `minimal_cc`, `self_report`, `chart_full`
- `slot_truth_json`
- `gold_ddx_top5_json`
- `required_svcl_domains_json`
- `patient_script_json`
- `must_ask_slots_json`

## Scale Guidance

- The template is intended to scale to 50+ cases by appending rows rather than editing JSONL by hand.
- For spreadsheet workflows, keep JSON cells valid and export UTF-8 CSV before running `build_cases.py`.
- Leave `max_turns` blank to inherit the global cap from `pib_config.yaml`; any explicit value must still be `<= 15`.
