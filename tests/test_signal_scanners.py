from __future__ import annotations

import importlib.util
import types
import unittest
from pathlib import Path


def _load_module_from_path(module_name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_tests(loader: unittest.TestLoader, tests: unittest.TestSuite, pattern: str) -> unittest.TestSuite:
    suite = unittest.TestSuite()
    scanner_dir = Path(__file__).resolve().parent / "signal" / "scanners"
    for path in sorted(scanner_dir.glob("test_*.py")):
        module = _load_module_from_path(f"_scanner_test_{path.stem}", path)
        suite.addTests(loader.loadTestsFromModule(module))
    return suite
