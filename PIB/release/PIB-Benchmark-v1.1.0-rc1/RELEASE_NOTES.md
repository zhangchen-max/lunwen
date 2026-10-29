# PIB Benchmark 1.1.0-rc1 Release Notes

## Scope
This release candidate freezes the PIB benchmark for external review and sign-off.

## Included
- Frozen manifest and hashes
- No-oracle pure baselines
- Guided LLM baseline reported separately
- Deprecated pre-no-oracle-fix dynamic dummy results
- No-oracle audit and text contamination audit
- Canonical static/dynamic release artifacts for the test split

## Known Limitations
- Casebank remains synthetic and does not include clinician adjudication records
- `OS_OCRD_OTHER` coverage remains smaller than the other two OS_OCRD subtypes
- psychosis / substance positive cases are present but still limited in count
- guided LLM baselines are separated from the pure baseline table and are not bundled here as scored runs
