# PIB v1.1 Gap Checklist

## Scope

This checklist compares the v1.1 technical manual against the current repository state before the next patch sequence.

## Status Snapshot

- Hard constraints are partially wired: `slot_count=120`, `dynamic.max_turns<=15`, `OS_OCRD` subtype enum, `unittest` runner.
- Current blockers for v1.1 paper-grade reproducibility are structural, not infrastructural.
- Highest-risk gap is ontology quality: the repository still uses placeholder `aux_slot_*` entries instead of a real frozen 120-slot ontology.

## File-by-File Gaps

| File | Priority | Current Gap | Patch Plan |
| --- | --- | --- | --- |
| `ontology/slots.yaml` | P0 | Contains placeholder `aux_slot_*` entries, so the 120-slot contract is numerically correct but semantically weak. | Replace placeholder slots with a real 120-slot ontology grouped into common + module-specific slots. |
| `ontology/svcl_map.yaml` | P0 | Only partial mapping exists; new slots are not mapped into SVCL coverage. | Expand mapping to cover the full 120-slot ontology. |
| `eval/load.py` | P0 | Hard constraints exist, but ontology validation does not yet enforce slot id shape or fully document v1.1 invariants. | Keep `120/15/3` hard checks, add slot id regex validation, keep config/ontology agreement strict. |
| `eval/schema.py` | P0 | Core constraints exist, but v1.1 regression surface needs to stay explicit. | Keep subtype + turn-cap validation explicit and aligned with constants. |
| `tests/test_schema.py` | P0 | Covers `120/15/3`, but does not protect against placeholder slot regressions. | Extend schema coverage around the real ontology and preserve current `120/15/3` checks. |
| `scripts/check_all.py` | P0 | Missing. | Add one-shot acceptance script for `validate_all`, `sanity_check`, and `run_tests`. |
| `models/adapters/base.py` | P1 | No cache layer; adapters are not reproducibility-friendly. | Add filesystem cache keyed by model name, prompt hash, and temperature. |
| `models/parsing.py` | P1 | Retry exists, but no structured attempt metadata or dedicated tests. | Keep retry path deterministic and add tests for wrapped JSON + retry behavior. |
| `models/adapters/openai_chat.py` | P1 | Stub only; not wired to shared cache behavior. | Rebase on cached adapter base class without adding dependencies. |
| `models/adapters/anthropic.py` | P1 | Stub only; not wired to shared cache behavior. | Rebase on cached adapter base class without adding dependencies. |
| `models/adapters/local_llama.py` | P1 | Stub only; not wired to shared cache behavior. | Rebase on cached adapter base class without adding dependencies. |
| `scripts/build_cases.py` | P1 | Can compile one wide CSV, but the authoring story is still thin for 50+ cases. | Harden CSV parsing, keep schema validation in-loop, and document scalable authoring usage. |
| `authoring/cases_template.csv` | P1 | Exists, but needs to be treated as the stable authoring contract for case expansion. | Keep template valid and align column semantics with `build_cases.py`. |
| `tests/` | P1 | No coverage yet for adapter cache or parsing retry. | Add offline `unittest` coverage for cache hit reuse and retry parsing. |
| `README.md` | P2 | Missing `check_all.py` and cache workflow guidance. | Update usage section after M2/M3. |
| `DATASET_CARD.md` | P2 | Hard parameters are stated, but authoring/build and reproducibility notes are thin. | Add v1.1 reproducibility notes after M4. |

## Milestone Mapping

- `M1`: replace placeholder ontology and keep `120/15/3` hard constraints fully enforced.
- `M2`: add `scripts/check_all.py` and document one-shot acceptance.
- `M3`: add adapter cache + parsing retry tests, keep dependency-free.
- `M4`: harden authoring pipeline for case expansion and validate compiled artifacts.
