from __future__ import annotations

import ast
import csv
from functools import lru_cache
from pathlib import Path

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from PIL import Image

from koakuma_bot.services.project_paths import project_data_path
from koakuma_bot.services.touhou_character_labels import SUPPLEMENTAL_TOUHOU_LABELS


MODEL_REPO = "SmilingWolf/wd-vit-tagger-v3"
MODEL_FILENAME = "model.onnx"
LABEL_FILENAME = "selected_tags.csv"
LEGACY_LABELS_PATH = project_data_path("labels_legacy.txt")
CHARACTER_LABELS_CSV_PATH = project_data_path("character_labels_full.csv")

KAOMOJIS = {
    "0_0",
    "(o)_(o)",
    "+_+",
    "+_-",
    "._.",
    "_",
    "<|>_<|>",
    "=_=",
    ">_<",
    "3_3",
    "6_9",
    ">_o",
    "@_@",
    "^_^",
    "o_o",
    "u_u",
    "x_x",
    "|_|",
    "||_||",
}

RATING_LABELS = {
    "general": "全年龄",
    "sensitive": "轻度敏感",
    "questionable": "较敏感",
    "explicit": "成人",
}


@lru_cache(maxsize=1)
def _load_legacy_character_names() -> dict[str, str]:
    if not LEGACY_LABELS_PATH.exists():
        return dict(SUPPLEMENTAL_TOUHOU_LABELS)

    for encoding in ("utf-8", "gbk", "utf-8-sig"):
        try:
            raw_text = LEGACY_LABELS_PATH.read_text(encoding=encoding)
            mapping = ast.literal_eval(raw_text)
            if isinstance(mapping, dict):
                merged = {str(key): str(value) for key, value in mapping.items()}
                merged.update(SUPPLEMENTAL_TOUHOU_LABELS)
                return merged
        except Exception:
            continue
    return dict(SUPPLEMENTAL_TOUHOU_LABELS)


def _normalize_tag(name: str) -> str:
    return name if name in KAOMOJIS else name.replace("_", " ")


def _display_character_name(raw_name: str) -> str:
    character_names = _load_character_name_map()
    chinese_name = character_names.get(raw_name)
    normalized_name = _normalize_tag(raw_name)
    if chinese_name:
        return f"{chinese_name} ({normalized_name})"
    return normalized_name


@lru_cache(maxsize=1)
def _load_character_name_map() -> dict[str, str]:
    _ensure_character_labels_catalog()

    if not CHARACTER_LABELS_CSV_PATH.exists():
        return _load_legacy_character_names()

    mapping: dict[str, str] = {}
    with open(CHARACTER_LABELS_CSV_PATH, "r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            raw_name = row.get("raw_name", "").strip()
            zh_name = row.get("display_name_zh", "").strip()
            if raw_name and zh_name:
                mapping[raw_name] = zh_name
    if not mapping:
        return _load_legacy_character_names()
    return mapping


def _ensure_character_labels_catalog() -> None:
    if CHARACTER_LABELS_CSV_PATH.exists():
        return

    label_rows = _load_label_rows()
    known_names = _load_legacy_character_names()

    CHARACTER_LABELS_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CHARACTER_LABELS_CSV_PATH, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["tag_id", "raw_name", "display_name_en", "display_name_zh", "count"],
        )
        writer.writeheader()
        for row in label_rows:
            if row.get("category") != "4":
                continue
            raw_name = row["name"]
            writer.writerow(
                {
                    "tag_id": row.get("tag_id", ""),
                    "raw_name": raw_name,
                    "display_name_en": _normalize_tag(raw_name),
                    "display_name_zh": known_names.get(raw_name, ""),
                    "count": row.get("count", ""),
                }
            )


def ensure_character_labels_catalog() -> Path:
    _ensure_character_labels_catalog()
    return CHARACTER_LABELS_CSV_PATH


@lru_cache(maxsize=1)
def _load_label_rows() -> list[dict[str, str]]:
    csv_path = hf_hub_download(repo_id=MODEL_REPO, filename=LABEL_FILENAME)
    with open(csv_path, "r", encoding="utf-8") as file:
        return list(csv.DictReader(file))


@lru_cache(maxsize=1)
def _load_session() -> ort.InferenceSession:
    model_path = hf_hub_download(repo_id=MODEL_REPO, filename=MODEL_FILENAME)
    return ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])


def _prepare_image(image_path: Path, target_size: int) -> np.ndarray:
    image = Image.open(image_path)
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    canvas = Image.new("RGBA", image.size, (255, 255, 255, 255))
    canvas.alpha_composite(image)
    image = canvas.convert("RGB")

    width, height = image.size
    side = max(width, height)
    padded = Image.new("RGB", (side, side), (255, 255, 255))
    padded.paste(image, ((side - width) // 2, (side - height) // 2))
    if side != target_size:
        padded = padded.resize((target_size, target_size), Image.BICUBIC)

    arr = np.asarray(padded, dtype=np.float32)
    arr = arr[:, :, ::-1]
    arr = np.expand_dims(arr, axis=0)
    return arr


def _run_inference(image_path: Path) -> tuple[list[dict[str, str]], np.ndarray]:
    session = _load_session()
    labels = _load_label_rows()

    input_info = session.get_inputs()[0]
    output_info = session.get_outputs()[0]
    _, height, width, _ = input_info.shape
    if height != width:
        raise RuntimeError(f"unexpected model input shape: {input_info.shape}")

    image_arr = _prepare_image(image_path, int(height))
    preds = session.run([output_info.name], {input_info.name: image_arr})[0][0].astype(float)
    return labels, preds


def classify_character_tags(
    image_path: Path,
    character_threshold: float = 0.85,
    top_n: int = 8,
) -> list[tuple[str, float]]:
    labels, preds = _run_inference(image_path)

    character_results: list[tuple[str, float]] = []
    for index, row in enumerate(labels):
        if row.get("category") != "4":
            continue
        score = float(preds[index])
        if score < character_threshold:
            continue
        character_results.append((_display_character_name(row["name"]), score))

    character_results.sort(key=lambda item: item[1], reverse=True)
    return character_results[:top_n]


def classify_image(
    image_path: Path,
    character_threshold: float = 0.85,
    top_n: int = 8,
) -> dict[str, object]:
    labels, preds = _run_inference(image_path)

    ratings: list[tuple[str, float]] = []
    characters: list[tuple[str, float]] = []

    for index, row in enumerate(labels):
        category = row.get("category")
        raw_name = row["name"]
        score = float(preds[index])
        if category == "9":
            ratings.append((raw_name, score))
            continue
        if category == "4" and score >= character_threshold:
            characters.append((_display_character_name(raw_name), score))

    ratings.sort(key=lambda item: item[1], reverse=True)
    characters.sort(key=lambda item: item[1], reverse=True)

    top_rating_name, top_rating_score = ratings[0] if ratings else ("unknown", 0.0)

    return {
        "rating_key": top_rating_name,
        "rating_name": RATING_LABELS.get(top_rating_name, top_rating_name),
        "rating_score": top_rating_score,
        "characters": characters[:top_n],
    }
