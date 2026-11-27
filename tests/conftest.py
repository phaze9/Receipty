from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))


import pytest


@pytest.fixture(autouse=True)
def _disable_receipt_log(monkeypatch):
    # Existing tests must never hit the network for log generation.
    monkeypatch.setenv("RECEIPTY_LOG", "0")
