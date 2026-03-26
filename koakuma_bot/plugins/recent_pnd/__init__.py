from __future__ import annotations

from nonebot import get_bots, logger, on_command, require
from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent, MessageSegment
from nonebot.permission import SUPERUSER

from koakuma_bot.services.group_targets import load_group_targets
from koakuma_bot.services.pnd_feed import fetch_recent_entries, find_new_recent_entries, load_seen_keys, prime_recent_state


require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler


DEFAULT_GROUPS = [630043089, 280569556, 758377325, 418520896, 728660903, 1047110422]

recent_pnd_sync = on_command("recent_pnd_sync", permission=SUPERUSER, block=True, priority=10)
recent_pnd_latest = on_command(
    "recent_pnd_latest",
    aliases={"最新PND", "最新pnd", "最近PND", "最近pnd"},
    block=True,
    priority=10,
)


def get_online_bot() -> Bot | None:
    bots = [bot for bot in get_bots().values() if isinstance(bot, Bot)]
    return bots[0] if bots else None


def get_target_groups() -> list[int]:
    return load_group_targets("recent_pnd", DEFAULT_GROUPS)


async def broadcast_new_entries() -> int:
    if not load_seen_keys():
        entries = prime_recent_state(limit=20)
        logger.info(f"recent_pnd: initialized state with {len(entries)} entries")
        return 0

    entries = find_new_recent_entries(limit=20)
    if not entries:
        logger.info("recent_pnd: no new entries")
        return 0

    groups = get_target_groups()
    if not groups:
        logger.info("recent_pnd: no target groups configured")
        return 0

    bot = get_online_bot()
    if bot is None:
        logger.warning("recent_pnd: no online OneBot v11 bot available")
        return 0

    count = 0
    for entry in entries:
        message = entry.format_message()
        for group_id in groups:
            try:
                await bot.send_group_msg(group_id=group_id, message=message)
            except Exception as error:
                logger.warning(f"recent_pnd: failed to send to group {group_id}: {error}")
        count += 1
    return count


@scheduler.scheduled_job("cron", minute="*/30", second="30", id="recent_pnd_broadcast")
async def _recent_pnd_job() -> None:
    await broadcast_new_entries()


@recent_pnd_sync.handle()
async def _() -> None:
    entries = prime_recent_state(limit=20)
    await recent_pnd_sync.finish(f"已同步 recent_pnd 状态，当前记录最近 {len(entries)} 条。")


@recent_pnd_latest.handle()
async def _(event: MessageEvent) -> None:
    entries = fetch_recent_entries(limit=1)
    if not entries:
        await recent_pnd_latest.finish("没有获取到最近的 PND 记录。")

    message = Message()
    message.append(MessageSegment.at(event.user_id))
    message.append(MessageSegment.text("\n"))
    message.append(MessageSegment.text(entries[0].format_message()))
    await recent_pnd_latest.finish(message)
