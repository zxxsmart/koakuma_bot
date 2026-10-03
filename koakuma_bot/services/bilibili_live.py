from __future__ import annotations

import json
from dataclasses import dataclass, field
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from nonebot import logger

from koakuma_bot.services.project_paths import project_data_path


ROOMS_PATH = project_data_path("bilibili_live_rooms.txt")
STATE_PATH = project_data_path("bilibili_live_state.json")
ROOM_INFO_URL = "https://api.live.bilibili.com/room/v1/Room/get_info"
ROOMS_TEMPLATE = "# One Bilibili live room ID per line (short or full ID).\n# Lines starting with # are ignored.\n"


@dataclass
class LiveRoom:
    room_id: int
    live_status: int
    title: str
    live_time: str = ""

    def format_message(self) -> str:
        lines = [
            "Bilibili 开播通知：",
            f"直播间：{self.room_id}",
            f"标题：{self.title or '未设置标题'}",
        ]
        if self.live_time:
            lines.append(f"开播时间：{self.live_time}")
        lines.append(f"https://live.bilibili.com/{self.room_id}")
        return "\n".join(lines)


@dataclass
class LiveRoomState:
    live_status: int
    live_time: str = ""
    notified_groups: set[int] = field(default_factory=set)


def ensure_room_file() -> None:
    if not ROOMS_PATH.exists():
        ROOMS_PATH.write_text(ROOMS_TEMPLATE, encoding="utf-8")


def load_room_ids() -> list[int]:
    ensure_room_file()
    rooms: list[int] = []
    for line_number, line in enumerate(ROOMS_PATH.read_text(encoding="utf-8-sig").splitlines(), 1):
        text = line.partition("#")[0].strip()
        if not text:
            continue
        if not text.isascii() or not text.isdigit() or int(text) <= 0:
            logger.warning(f"bilibili_live: invalid room ID on line {line_number} of {ROOMS_PATH}")
            continue
        room_id = int(text)
        if room_id not in rooms:
            rooms.append(room_id)
    return rooms


def fetch_live_room(room_id: int) -> LiveRoom:
    request = Request(
        f"{ROOM_INFO_URL}?{urlencode({'room_id': room_id})}",
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://live.bilibili.com/"},
    )
    with urlopen(request, timeout=15) as response:
        payload = json.load(response)

    if not isinstance(payload, dict) or payload.get("code") != 0:
        raise ValueError(f"Bilibili room {room_id}: unsuccessful response: {payload}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError(f"Bilibili room {room_id}: missing room data")

    # Missing or unexpected statuses are errors, never an offline observation.
    canonical_id = data.get("room_id")
    live_status = data.get("live_status")
    if type(canonical_id) is not int or canonical_id <= 0 or type(live_status) is not int or live_status not in (0, 1, 2):
        raise ValueError(f"Bilibili room {room_id}: invalid room ID or live status")
    live_time = str(data.get("live_time") or "").strip()
    if live_time == "0000-00-00 00:00:00":
        live_time = ""
    return LiveRoom(
        room_id=canonical_id,
        live_status=live_status,
        title=str(data.get("title") or "").strip(),
        live_time=live_time,
    )


def next_room_state(room: LiveRoom, previous: LiveRoomState | None) -> LiveRoomState:
    same_session = (
        room.live_status == 1
        and previous is not None
        and previous.live_status == 1
        and not (room.live_time and previous.live_time and room.live_time != previous.live_time)
    )
    return LiveRoomState(
        live_status=room.live_status,
        live_time=room.live_time or (previous.live_time if same_session and previous else ""),
        notified_groups=set(previous.notified_groups) if same_session and previous else set(),
    )


def load_live_state() -> dict[int, LiveRoomState]:
    if not STATE_PATH.exists():
        return {}

    # Fail visibly on a damaged file instead of forgetting sent notifications.
    payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("rooms"), dict):
        raise ValueError(f"Invalid Bilibili live state file: {STATE_PATH}")
    states: dict[int, LiveRoomState] = {}
    for room_id, entry in payload["rooms"].items():
        if not room_id.isascii() or not room_id.isdigit() or int(room_id) <= 0 or not isinstance(entry, dict):
            raise ValueError(f"Invalid Bilibili live state entry: {room_id}")
        status = entry.get("live_status")
        live_time = entry.get("live_time", "")
        groups = entry.get("notified_groups", [])
        if (
            type(status) is not int
            or status not in (0, 1, 2)
            or not isinstance(live_time, str)
            or not isinstance(groups, list)
            or any(type(group) is not int or group <= 0 for group in groups)
        ):
            raise ValueError(f"Invalid Bilibili live state entry: {room_id}")
        states[int(room_id)] = LiveRoomState(status, live_time, set(groups))
    return states


def save_live_state(states: dict[int, LiveRoomState]) -> None:
    payload = {
        "rooms": {
            str(room_id): {
                "live_status": state.live_status,
                "live_time": state.live_time,
                "notified_groups": sorted(state.notified_groups),
            }
            for room_id, state in states.items()
        }
    }
    temporary_path = STATE_PATH.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(STATE_PATH)
