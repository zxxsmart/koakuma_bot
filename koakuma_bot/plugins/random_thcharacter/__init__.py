from nonebot import on_command
from nonebot.adapters.onebot.v11 import Message, MessageEvent, MessageSegment
from nonebot.params import CommandArg

from koakuma_bot.services.touhou_random_catalog import random_character


random_character_cmd = on_command(
    "random_ch",
    aliases={"随个人物", "随个角色", "随个老婆", "随个lp"},
    block=True,
    priority=10,
)


@random_character_cmd.handle()
async def handle_random_character(args=CommandArg(), event: MessageEvent | None = None) -> None:
    mode = args.extract_plain_text().strip()
    result = random_character(mode)

    message = Message()
    if event is not None:
        message.append(MessageSegment.at(event.user_id))
        message.append(MessageSegment.text("\n"))
    message.append(MessageSegment.text(result))
    await random_character_cmd.finish(message)
