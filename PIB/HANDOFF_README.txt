PIB handoff bundle

Included:
- benchmark core source: ontology/, data/, eval/, models/, agents/, scripts/
- product layer source: webapi/, apps/web/src/ + package files
- tests/, docs/, release/, results/, artifacts/, output/, authoring/, mocks/
- root config/docs: README.md, DATASET_CARD.md, CHANGELOG.md, pyproject.toml, requirements.lock, pib_config.yaml

Excluded on purpose:
- apps/web/node_modules/
- apps/web/dist/
- cache/
- .git/
- .openclaw-workspace/
- .playwright-cli/
- local auth/env files

Suggested bring-up on Lenovo:
1. Install Python 3.11+
2. Install Node.js 20+
3. In repo root: python -m scripts.run_tests
4. Start API: python -m webapi.server --host 127.0.0.1 --port 8780
5. Start web: cd apps/web && npm install && npm run dev

If using Windows, WSL2 is recommended for the Python workflow.
