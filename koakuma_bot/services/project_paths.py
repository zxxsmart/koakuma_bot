from __future__ import annotations

from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = PACKAGE_DIR.parent

PROJECT_DATA_DIR = PROJECT_DIR / "data"


def ensure_project_data_dir() -> Path:
    PROJECT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return PROJECT_DATA_DIR


def project_data_path(*parts: str) -> Path:
    ensure_project_data_dir()
    return PROJECT_DATA_DIR.joinpath(*parts)
