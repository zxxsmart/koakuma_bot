from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pysilk
from nonebot import get_driver


SILK_SAMPLE_RATE = 24000
SILK_BIT_RATE = 24000


def _resolve_binary(binary_name: str) -> str:
    ffmpeg_bin = ""
    try:
        ffmpeg_bin = str(getattr(get_driver().config, "ffmpeg_bin", "") or "").strip()
    except ValueError:
        ffmpeg_bin = os.environ.get("FFMPEG_BIN", "").strip()

    if ffmpeg_bin:
        candidate = Path(ffmpeg_bin) / f"{binary_name}.exe"
        if candidate.exists():
            return str(candidate)
        candidate = Path(ffmpeg_bin) / binary_name
        if candidate.exists():
            return str(candidate)
    return binary_name


def probe_audio_duration_ms(file_path: Path) -> int:
    command = [
        _resolve_binary("ffprobe"),
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        str(file_path),
    ]
    result = subprocess.run(command, capture_output=True, check=True)
    stdout_text = result.stdout.decode("utf-8", errors="replace")
    payload = json.loads(stdout_text)
    duration_seconds = float(payload["format"]["duration"])
    return int(duration_seconds * 1000)


def export_audio_fragment(source_path: Path, output_path: Path, start_ms: int, clip_ms: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    start_seconds = max(start_ms, 0) / 1000
    clip_seconds = max(clip_ms, 1) / 1000
    pcm_path = output_path.with_suffix(".pcm")

    command = [
        _resolve_binary("ffmpeg"),
        "-y",
        "-ss",
        f"{start_seconds:.3f}",
        "-t",
        f"{clip_seconds:.3f}",
        "-i",
        str(source_path),
        "-vn",
        "-ar",
        str(SILK_SAMPLE_RATE),
        "-ac",
        "1",
        "-f",
        "s16le",
        str(pcm_path),
    ]
    try:
        subprocess.run(command, capture_output=True, check=True)
        with pcm_path.open("rb") as pcm_file, output_path.open("wb") as silk_file:
            pysilk.encode(pcm_file, silk_file, SILK_SAMPLE_RATE, SILK_BIT_RATE, tencent=True)
    finally:
        pcm_path.unlink(missing_ok=True)
