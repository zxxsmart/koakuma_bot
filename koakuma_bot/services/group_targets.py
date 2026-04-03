from __future__ import annotations

from pathlib import Path

from koakuma_bot.services.project_paths import project_data_path


GROUP_TARGETS_DIR = project_data_path("group_targets")
GROUP_TARGETS_TEMPLATE = "# One group ID per line.\n# Lines starting with # are ignored.\n"


def ensure_group_targets_dir() -> Path:
    GROUP_TARGETS_DIR.mkdir(parents=True, exist_ok=True)
    return GROUP_TARGETS_DIR


def group_target_file(name: str) -> Path:
    ensure_group_targets_dir()
    return GROUP_TARGETS_DIR / f"{name}.txt"


def ensure_group_target_file(name: str) -> Path:
    path = group_target_file(name)
    if path.exists():
        return path

    path.write_text(GROUP_TARGETS_TEMPLATE, encoding="utf-8")
    return path


def load_group_targets(name: str) -> list[int]:
    path = ensure_group_target_file(name)
    groups: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text.isdigit():
            groups.append(int(text))
    return groups
