from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def samples_inputs() -> Path:
    return REPO_ROOT / "samples" / "inputs"
