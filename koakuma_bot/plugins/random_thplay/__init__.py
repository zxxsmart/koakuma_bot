from nonebot import on_command
from nonebot.adapters.onebot.v11 import Message, MessageEvent, MessageSegment
from nonebot.params import ArgPlainText, CommandArg

from koakuma_bot.services.touhou_random_catalog import random_play


random_play_cmd = on_command(
    "random_THplay",
    aliases={"随个机体", "随机机体"},
    block=True,
    priority=10,
)


@random_play_cmd.handle()
async def handle_random_play(args=CommandArg()) -> None:
    title = args.extract_plain_text().strip() if args is not None else ""
    if title:
        random_play_cmd.set_arg("title", args)


@random_play_cmd.got("title", prompt="想玩哪个作品？")
async def handle_random_play_got(event: MessageEvent, title_text: str = ArgPlainText("title")) -> None:
    title_text = title_text.strip()
    if not title_text:
        await random_play_cmd.finish("那这次就先不随机机体了。")

    result = random_play(title_text)
    message = Message()
    message.append(MessageSegment.at(event.user_id))
    message.append(MessageSegment.text("\n"))
    message.append(MessageSegment.text(result))
    await random_play_cmd.finish(message)
