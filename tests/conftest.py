from __future__ import annotations

from pathlib import Path

import pytest

from agentgate.application import build_application


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def app(tmp_path):
    return build_application(PROJECT_ROOT, runtime_root=tmp_path / "runtime")

