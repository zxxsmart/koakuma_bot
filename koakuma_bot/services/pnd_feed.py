from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from koakuma_bot.services.project_paths import project_data_path


RECENT_URL = "https://thscore.pndsng.com/index.php?recent=1"
STATE_PATH = project_data_path("recent_pnd_state.json")


@dataclass
class PndEntry:
    game: str
    score: str
    shot_type: str
    player: str
    date: str
    replay_url: str
    source_key: str

    def format_message(self) -> str:
        lines = [
            "最新PND榜：",
            self.game,
            f"分数：{self.score}",
            f"机体：{self.shot_type}",
            f"机师：{self.player}",
            f"日期：{self.date}",
        ]
        if self.replay_url and self.replay_url != "N/A":
            lines.append(f"Replay：{self.replay_url}")
        return "\n".join(lines)


def _fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": "koakuma-bot/1.0"})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="ignore")


def _normalize_cell_text(cell) -> str:
    return cell.get_text(" ", strip=True) if cell else ""


def _build_replay_url(anchor) -> str:
    if not anchor:
        return "N/A"
    href = anchor.get("href", "").strip()
    if not href:
        return "N/A"
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return "https://thscore.pndsng.com" + href.lstrip(".")


def fetch_recent_entries(limit: int = 20) -> list[PndEntry]:
    html = _fetch_html(RECENT_URL)
    soup = BeautifulSoup(html, "html.parser")

    entries: list[PndEntry] = []
    for row in soup.select("tr"):
        cells = row.find_all("td")
        if len(cells) < 6:
            continue

        game_anchor = cells[0].find("a")
        player_anchor = cells[3].find("a")

        game = _normalize_cell_text(game_anchor or cells[0])
        score = _normalize_cell_text(cells[1])
        shot_type = _normalize_cell_text(cells[2])
        player = _normalize_cell_text(player_anchor or cells[3])
        date = _normalize_cell_text(cells[4])
        replay_url = _build_replay_url(cells[5].find("a"))

        if not all([game, score, shot_type, player, date]):
            continue

        source_key = "||".join([game, score, shot_type, player, date, replay_url])
        entries.append(
            PndEntry(
                game=game,
                score=score,
                shot_type=shot_type,
                player=player,
                date=date,
                replay_url=replay_url,
                source_key=source_key,
            )
        )
        if len(entries) >= limit:
            break

    return entries


def load_seen_keys(max_keep: int = 200) -> list[str]:
    if not STATE_PATH.exists():
        return []

    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

    seen = payload.get("seen_keys", [])
    if not isinstance(seen, list):
        return []
    return [str(item) for item in seen[:max_keep]]


def save_seen_keys(keys: list[str], max_keep: int = 200) -> None:
    unique_keys: list[str] = []
    for key in keys:
        if key in unique_keys:
            continue
        unique_keys.append(key)
    payload = {"seen_keys": unique_keys[:max_keep]}
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def find_new_recent_entries(limit: int = 20) -> list[PndEntry]:
    entries = fetch_recent_entries(limit=limit)
    seen = load_seen_keys()
    seen_set = set(seen)

    new_entries = [entry for entry in entries if entry.source_key not in seen_set]
    if not new_entries:
        return []

    combined_keys = [entry.source_key for entry in entries] + seen
    save_seen_keys(combined_keys)
    return list(reversed(new_entries))


def prime_recent_state(limit: int = 20) -> list[PndEntry]:
    entries = fetch_recent_entries(limit=limit)
    save_seen_keys([entry.source_key for entry in entries])
    return entries
