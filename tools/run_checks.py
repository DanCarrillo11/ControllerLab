"""Run the real suite and record machine-readable release evidence."""
from pathlib import Path
import json
import sys
import unittest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
suite = unittest.defaultTestLoader.discover(str(root / "tests"))
result = unittest.TextTestRunner(verbosity=2).run(suite)
output = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "outputs" / "test-summary.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps({"tests": result.testsRun, "failures": len(result.failures),
                             "errors": len(result.errors), "passed": result.wasSuccessful()}, indent=2), encoding="utf-8")
raise SystemExit(0 if result.wasSuccessful() else 1)
