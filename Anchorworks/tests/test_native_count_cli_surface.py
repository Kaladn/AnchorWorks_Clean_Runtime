from __future__ import annotations

import subprocess
import sys


def test_python_cli_does_not_expose_count_producing_ingest_commands() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "AnchorWorks", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "symbolic-batch-intake" not in result.stdout
    assert "ingest-openstax-chunked" not in result.stdout

