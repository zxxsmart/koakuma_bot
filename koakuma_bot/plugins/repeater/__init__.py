from __future__ import annotations

from nonebot import get_driver, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageSegment
from nonebot.rule import Rule

from koakuma_bot.services.repeater_state import RepeaterStateStore


driver = get_driver()
state_store = RepeaterStateStore()


def normalize_message(message: Message) -> str:
    normalized_segments: list[str] = []
    for segment in message:
        if segment.type == "image":
            file_value = segment.data.get("file", "")
            normalized_segments.append(f"[image:{file_value}]")
            continue
        normalized_segments.append(str(segment))
    return "".join(normalized_segments).strip()


def is_command_like(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False

    command_starts = getattr(driver.config, "command_start", {"/"})
    if any(stripped.startswith(prefix) for prefix in command_starts if prefix):
        return True

    nicknames = getattr(driver.config, "nickname", set())
    if any(stripped.startswith(nickname) for nickname in nicknames if nickname):
        return True

    return False


async def should_handle_group_message(bot: Bot, event: GroupMessageEvent) -> bool:
    return event.user_id != int(bot.self_id)


repeater = on_message(
    rule=Rule(should_handle_group_message),
    block=False,
    priority=100,
)


@repeater.handle()
async def _(bot: Bot, event: GroupMessageEvent) -> None:
    normalized_text = normalize_message(event.get_message())
    if not normalized_text:
        return
    if is_command_like(normalized_text):
        return
    if state_store.should_repeat(event.group_id, normalized_text):
        await repeater.finish(event.get_message())
