from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml
from nonebot import get_bots, logger, require
from nonebot.adapters.onebot.v11 import Bot

from koakuma_bot.services.group_targets import load_group_targets
from koakuma_bot.services.project_paths import project_data_path


require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler


DAYS_DIR = project_data_path("days")
GROUPS_FILE = project_data_path("calendar_groups.txt")
DEFAULT_GROUPS = [
    630043089,
    280569556,
    758377325,
    1047110422,
    782829102,
    574039316,
    538232983,
    1018561106,
]


def load_month_entries(month: int) -> list[dict]:
    month_path = DAYS_DIR / f"{month}.yaml"
    if not month_path.exists():
        logger.warning(f"calendar data file missing: {month_path}")
        return []

    with month_path.open("r", encoding="utf-8") as file:
        return [item for item in yaml.safe_load_all(file) if item]


def format_calendar_entry(entry: dict) -> str:
    message = str(entry.get("message", "")).strip()
    name = str(entry.get("name", "")).strip()
    characters = ", ".join(str(item).strip() for item in entry.get("characters", []) if str(item).strip())
    explanation = str(entry.get("explanation", "")).strip()

    tag_list = entry.get("tags", [])
    tag_name = ""
    if isinstance(tag_list, list) and tag_list:
        first_tag = tag_list[0] or {}
        tag_name = str(first_tag.get("name", "")).strip()

    parts = [part for part in [message, name, characters, explanation, tag_name] if part]
    return "\n".join(parts)


def find_today_messages(now: datetime | None = None) -> list[str]:
    current = now or datetime.now()
    entries = load_month_entries(current.month)

    messages: list[str] = []
    for entry in entries:
        day = entry.get("day")
        if not isinstance(day, int):
            try:
                day = int(day)
            except Exception:
                continue
        if day != current.day:
            continue
        messages.append(format_calendar_entry(entry))
    return messages


async def broadcast_today_calendar() -> None:
    messages = find_today_messages()
    if not messages:
        logger.info("calendar: no entries for today")
        return

    groups = load_group_targets("calendar", DEFAULT_GROUPS)
    if not groups:
        logger.info("calendar: no target groups configured")
        return

    bots = [bot for bot in get_bots().values() if isinstance(bot, Bot)]
    if not bots:
        logger.warning("calendar: no online OneBot v11 bot available")
        return

    bot = bots[0]
    for message in messages:
        for group_id in groups:
            try:
                await bot.send_group_msg(group_id=group_id, message=message)
            except Exception as error:
                logger.warning(f"calendar: failed to send to group {group_id}: {error}")


@scheduler.scheduled_job("cron", hour="0,9-10,18,22", id="calendar_broadcast")
async def _calendar_job() -> None:
    await broadcast_today_calendar()
