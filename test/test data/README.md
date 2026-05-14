# AnchorWorks Test Containment

This directory contains AnchorWorks test code, harnesses, and test-only data.

Run the active suite from `D:\AnchorWorks_Clean_Runtime\Anchorworks` with:

```powershell
$env:PYTHONPATH="D:\AnchorWorks_Clean_Runtime\Anchorworks\src"
python -m unittest discover -s "..\test\test data\tests"
```

Application code should stay under `Anchorworks/src`. Test-only files should stay here.

Containment layout:

- `tests/`: active unittest suite.
- `experiments/`: proof runners and their isolated runtime output.
- `harnesses/`: probe and benchmark scripts.
- `reports/`: test/probe/benchmark reports.
