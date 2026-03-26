from nonebot import on_command
from nonebot.adapters.onebot.v11 import Message, MessageEvent, MessageSegment

from koakuma_bot.services.touhou_random_catalog import random_sound


random_sound_cmd = on_command(
    "random_THsound",
    aliases={"随个音乐", "随机音乐"},
    block=True,
    priority=10,
)


@random_sound_cmd.handle()
async def handle_random_sound(event: MessageEvent | None = None) -> None:
    result = random_sound()
    message = Message()
    if event is not None:
        message.append(MessageSegment.at(event.user_id))
        message.append(MessageSegment.text("\n"))
    message.append(MessageSegment.text(result))
    await random_sound_cmd.finish(message)
