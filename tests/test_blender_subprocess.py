"""Optional end-to-end run via Blender binary (skipped when `blender` is not on PATH)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
E2E_SCRIPT = REPO_ROOT / "tests" / "blender_e2e.py"
BLENDER = shutil.which("blender")


@pytest.mark.skipif(BLENDER is None, reason="Blender executable not found on PATH")
def test_blender_headless_add_remove_describe():
    result = subprocess.run(
        [BLENDER, "--background", "--python", str(E2E_SCRIPT)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
