"""Service boundaries checked by import-linter (.importlinter, R-20)."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.req("FR-003")
def test_import_contracts_are_kept():
    lint = Path(sys.executable).with_name("lint-imports")
    proc = subprocess.run([str(lint)], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "0 broken" in proc.stdout
