from __future__ import annotations

import importlib.util
from pathlib import Path

_TEST_PATH = Path(__file__).resolve().parent / 'product' / 'test_p0_happy_path_smoke.py'
_SPEC = importlib.util.spec_from_file_location('pib_test_product_p0_happy_path_smoke', _TEST_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f'Unable to load test module from {_TEST_PATH}')
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

P0HappyPathSmokeTests = _MODULE.P0HappyPathSmokeTests
