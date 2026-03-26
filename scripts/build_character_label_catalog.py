from __future__ import annotations

import csv
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from koakuma_bot.services.wdv3_character_tagger import ensure_character_labels_catalog


def main() -> None:
    catalog_path = ensure_character_labels_catalog()
    with open(catalog_path, "r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    filled = sum(1 for row in rows if row.get("display_name_zh", "").strip())
    print(f"catalog: {catalog_path}")
    print(f"character tags: {len(rows)}")
    print(f"filled chinese names: {filled}")


if __name__ == "__main__":
    main()
