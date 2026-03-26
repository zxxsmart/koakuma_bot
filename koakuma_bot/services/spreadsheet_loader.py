from __future__ import annotations

import csv
import zipfile
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET


XML_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def _column_letters_to_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha()).upper()
    value = 0
    for ch in letters:
        value = value * 26 + (ord(ch) - ord("A") + 1)
    return max(value - 1, 0)


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []

    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.findall("main:si", XML_NS):
        texts = [node.text or "" for node in item.findall(".//main:t", XML_NS)]
        values.append("".join(texts))
    return values


def _read_first_sheet_path(archive: zipfile.ZipFile) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rel_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_map = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rel_root.findall("pkg:Relationship", XML_NS)
    }

    first_sheet = workbook.find("main:sheets/main:sheet", XML_NS)
    if first_sheet is None:
        raise RuntimeError("xlsx workbook has no sheet")

    rel_id = first_sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    if not rel_id or rel_id not in rel_map:
        raise RuntimeError("failed to resolve first worksheet")

    target = rel_map[rel_id].lstrip("/")
    return f"xl/{target}" if not target.startswith("xl/") else target


def _read_xlsx_rows(path: Path) -> list[list[str]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings = _read_shared_strings(archive)
        sheet_path = _read_first_sheet_path(archive)
        sheet_root = ET.fromstring(archive.read(sheet_path))

    rows: list[list[str]] = []
    for row_node in sheet_root.findall(".//main:sheetData/main:row", XML_NS):
        values: list[str] = []
        for cell in row_node.findall("main:c", XML_NS):
            cell_index = _column_letters_to_index(cell.attrib.get("r", "A1"))
            while len(values) <= cell_index:
                values.append("")

            cell_type = cell.attrib.get("t", "")
            if cell_type == "s":
                value_node = cell.find("main:v", XML_NS)
                shared_index = int(value_node.text) if value_node is not None and value_node.text else 0
                values[cell_index] = shared_strings[shared_index] if shared_index < len(shared_strings) else ""
                continue

            if cell_type == "inlineStr":
                texts = [node.text or "" for node in cell.findall(".//main:t", XML_NS)]
                values[cell_index] = "".join(texts)
                continue

            value_node = cell.find("main:v", XML_NS)
            values[cell_index] = value_node.text if value_node is not None and value_node.text else ""

        rows.append(values)
    return rows


def _read_csv_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [row for row in csv.reader(file)]


@lru_cache(maxsize=32)
def load_sheet_rows(preferred_csv: Path, fallback_xlsx: Path) -> list[list[str]]:
    if preferred_csv.exists():
        return _read_csv_rows(preferred_csv)
    if fallback_xlsx.exists():
        return _read_xlsx_rows(fallback_xlsx)
    raise FileNotFoundError(f"missing both data files: {preferred_csv} and {fallback_xlsx}")
