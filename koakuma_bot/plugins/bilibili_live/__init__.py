from __future__ import annotations

import asyncio

from nonebot import get_bots, get_driver, logger, on_command, require
from nonebot.adapters.onebot.v11 import Bot, MessageSegment

from koakuma_bot.services.bilibili_live import (
    ensure_room_file,
    fetch_live_room,
    load_live_state,
    load_room_ids,
    next_room_state,
    save_live_state,
)
from koakuma_bot.services.group_targets import ensure_group_target_file, load_group_targets


require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler


ensure_room_file()
ensure_group_target_file("bilibili_live")
poll_lock = asyncio.Lock()
bilibili_live_status = on_command(
    "bilibili_live_status",
    aliases={"B站直播状态", "b站直播状态", "直播"},
    block=True,
    priority=10,
)


def get_online_bot() -> Bot | None:
    bots = [bot for bot in get_bots().values() if isinstance(bot, Bot)]
    return bots[0] if bots else None


async def broadcast_live_notifications() -> int:
    async with poll_lock:
        bot = get_online_bot()
        if bot is None:
            return 0
        try:
            groups = list(dict.fromkeys(group for group in load_group_targets("bilibili_live") if group > 0))
            room_ids = load_room_ids()
            if not groups or not room_ids:
                return 0
            states = load_live_state()
        except Exception as error:
            logger.warning(f"bilibili_live: failed to read configuration/state: {error}")
            return 0

        count = 0
        processed_rooms: set[int] = set()
        for configured_id in room_ids:
            try:
                # urllib runs in a thread so it cannot block QQ message handlers.
                room = await asyncio.to_thread(fetch_live_room, configured_id)
            except Exception as error:
                logger.warning(f"bilibili_live: failed to fetch room {configured_id}: {error}")
                continue
            if room.room_id in processed_rooms:
                continue
            processed_rooms.add(room.room_id)
            states[room.room_id] = state = next_room_state(room, states.get(room.room_id))
            try:
                # Persist the observed session even if all sends fail this time.
                save_live_state(states)
                if room.live_status != 1:
                    continue
                message = MessageSegment.text(room.format_message())
                for group_id in groups:
                    if group_id in state.notified_groups:
                        continue
                    try:
                        await bot.send_group_msg(group_id=group_id, message=message)
                    except Exception as error:
                        logger.warning(f"bilibili_live: failed to send room {room.room_id} to group {group_id}: {error}")
                        continue
                    state.notified_groups.add(group_id)
                    save_live_state(states)
                    count += 1
            except Exception as error:
                logger.warning(f"bilibili_live: failed to save notification state: {error}")
                return count
        if count:
            logger.info(f"bilibili_live: sent {count} live notifications")
        return count


@scheduler.scheduled_job("interval", seconds=60, id="bilibili_live_broadcast", max_instances=1, coalesce=True)
async def _bilibili_live_job() -> None:
    await broadcast_live_notifications()


@get_driver().on_bot_connect
async def _bilibili_live_connect(bot: Bot) -> None:
    if isinstance(bot, Bot):
        await broadcast_live_notifications()


@bilibili_live_status.handle()
async def _() -> None:
    room_ids = load_room_ids()
    if not room_ids:
        await bilibili_live_status.finish("尚未配置直播间，请在 data/bilibili_live_rooms.txt 中每行填写一个直播间号。")

    messages: list[str] = []
    for room_id in room_ids:
        try:
            room = await asyncio.to_thread(fetch_live_room, room_id)
        except Exception as error:
            logger.warning(f"bilibili_live: failed to query room {room_id}: {error}")
            messages.append(f"直播间 {room_id}：查询失败，请稍后重试。")
            continue
        status = {0: "未开播", 1: "直播中", 2: "轮播中"}[room.live_status]
        messages.append(f"直播间 {room.room_id}：{status}\n{room.title}\nhttps://live.bilibili.com/{room.room_id}")
    await bilibili_live_status.finish(MessageSegment.text("\n\n".join(messages)))
