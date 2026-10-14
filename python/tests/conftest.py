"""Shared fixtures: the real spec and the trimmed harness outputs in tests/fixtures/."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from performance_engineering_lab.spec import Spec, default_spec_path, load_spec

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def spec() -> Spec:
    """The repository's spec/experiments.json."""
    return load_spec()


@pytest.fixture
def raw_spec() -> dict[str, Any]:
    """A fresh decoded copy of the spec for mutation tests."""
    data: dict[str, Any] = json.loads(default_spec_path().read_text(encoding="utf-8"))
    return copy.deepcopy(data)


@pytest.fixture(scope="session")
def fixtures() -> Path:
    """Folder of trimmed real JMH, pyperf and mitata outputs (smoke profile, local paths removed)."""
    return FIXTURES
