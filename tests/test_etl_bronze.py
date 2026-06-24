import json
from pathlib import Path

import pytest

from etl.bronze import copy_to_bronze


@pytest.fixture
def sample_json(tmp_path: Path) -> Path:
    p = tmp_path / "81344455.json"
    p.write_text(json.dumps({"id": "test"}), encoding="utf-8")
    return p


def test_copy_to_bronze_creates_file(sample_json: Path, tmp_path: Path) -> None:
    catalog_dir = tmp_path / "unity-catalog"
    result = copy_to_bronze(sample_json, catalog_dir)
    assert result.exists()
    assert result.name == "bronze_81344455.json"


def test_copy_to_bronze_creates_catalog_dir(sample_json: Path, tmp_path: Path) -> None:
    catalog_dir = tmp_path / "new-catalog"
    copy_to_bronze(sample_json, catalog_dir)
    assert catalog_dir.exists()


def test_copy_to_bronze_preserves_content(sample_json: Path, tmp_path: Path) -> None:
    catalog_dir = tmp_path / "unity-catalog"
    result = copy_to_bronze(sample_json, catalog_dir)
    assert result.read_text(encoding="utf-8") == sample_json.read_text(encoding="utf-8")
