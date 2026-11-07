from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def legacy_data_dir(repo_root: Path) -> Path:
    """Game data shipped with the original application: the input both implementations read."""
    return repo_root / "legacy" / "Run" / "Data"
