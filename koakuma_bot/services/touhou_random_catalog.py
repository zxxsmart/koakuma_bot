from __future__ import annotations

import csv
import random
from pathlib import Path

from koakuma_bot.services.project_paths import project_data_path


CHARACTER_CSV = project_data_path("TH_character.csv")
PLAY_CSV = project_data_path("THplay.csv")
SOUND_CSV = project_data_path("TH_sound.csv")
SPELLCARD_CSV = project_data_path("TH_spellcard.csv")

RANDOM_PLAY_ALL_KEYWORDS = {"随机", "随意", "全部", "全作"}


def _clean_cell(cell: str) -> str:
    cleaned = cell.replace("System.Xml.XmlElement", " ").strip()
    return " ".join(cleaned.split())


def _load_csv_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [[_clean_cell(cell) for cell in row] for row in csv.reader(file)]


def random_character(mode: str = "") -> str:
    rows = [row for row in _load_csv_rows(CHARACTER_CSV) if any(row)]
    row = random.choice(rows)

    name = row[0] if len(row) > 0 else ""
    profile = row[1] if len(row) > 1 else ""
    race = row[2] if len(row) > 2 else ""
    ability = row[3] if len(row) > 3 else ""
    title = row[4] if len(row) > 4 else ""

    if "完整" in mode:
        result = name
        if profile:
            result += f"\n相关资料：\n{profile}"
        return result

    result = name
    if race:
        result += f"\n种族：{race}"
    if ability:
        result += f"\n能力：{ability}"
    if title:
        result += f"\n称号：{title}"
    return result


def random_play(title: str = "") -> str:
    rows = [row for row in _load_csv_rows(PLAY_CSV) if any(row)]
    if not rows:
        raise RuntimeError("THplay data is empty")

    keyword = title.strip()
    if not keyword or keyword in RANDOM_PLAY_ALL_KEYWORDS:
        row = random.choice(rows)
    else:
        row = next((item for item in rows if item and item[0] == keyword), None)
        if row is None:
            raise RuntimeError(f"未找到作品：{keyword}")

    prefix = row[0]
    choices = [cell for cell in row[1:] if cell]
    if not choices:
        return prefix
    return prefix + random.choice(choices)


def random_sound() -> str:
    rows = [row for row in _load_csv_rows(SOUND_CSV) if any(row)]
    row = random.choice(rows)
    cd_name = row[0]
    choices = [cell for cell in row[1:] if cell]
    if not choices:
        return cd_name
    return f"{random.choice(choices)}\n出自：{cd_name}"


def random_spellcard() -> str:
    rows = [row for row in _load_csv_rows(SPELLCARD_CSV) if any(row)]
    row = random.choice(rows)
    user = row[0]
    choices = [cell for cell in row[1:] if cell]
    if not choices:
        return user
    return f"{random.choice(choices)}\n使用者：{user}"
