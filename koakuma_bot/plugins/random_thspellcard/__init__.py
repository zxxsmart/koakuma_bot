from nonebot import on_command
from nonebot.adapters.onebot.v11 import Message, MessageEvent, MessageSegment

from koakuma_bot.services.touhou_random_catalog import random_spellcard


random_spellcard_cmd = on_command(
    "random_THspellcard",
    aliases={"随个符卡", "随机符卡", "抽卡"},
    block=True,
    priority=10,
)


@random_spellcard_cmd.handle()
async def handle_random_spellcard(event: MessageEvent | None = None) -> None:
    result = random_spellcard()
    message = Message()
    if event is not None:
        message.append(MessageSegment.at(event.user_id))
        message.append(MessageSegment.text("\n"))
    message.append(MessageSegment.text(result))
    await random_spellcard_cmd.finish(message)
