from __future__ import annotations

from pathlib import Path

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent, MessageSegment
from nonebot.matcher import Matcher
from nonebot.params import Arg, CommandArg

from koakuma_bot.services.image_fetch import download_image
from koakuma_bot.services.project_paths import project_data_path
from koakuma_bot.services.wdv3_character_tagger import classify_image

TEMP_IMAGE_PATH = project_data_path("classify_input.jpg")


image_tagger_cmd = on_command(
    "THclassify",
    aliases={"识图"},
    block=True,
    priority=10,
)


def extract_first_image_url(message: Message) -> str | None:
    for segment in message:
        if segment.type != "image":
            continue
        url = segment.data.get("url")
        if url:
            return url
    return None


async def extract_image_url(bot: Bot, message: Message) -> str | None:
    direct_url = extract_first_image_url(message)
    if direct_url:
        return direct_url

    for segment in message:
        if segment.type != "reply":
            continue
        message_id = segment.data.get("id")
        if not message_id:
            continue
        replied = await bot.get_msg(message_id=int(message_id))
        replied_message = replied.get("message")
        if isinstance(replied_message, Message):
            reply_url = extract_first_image_url(replied_message)
            if reply_url:
                return reply_url
            continue
        if replied_message is not None:
            reply_url = extract_first_image_url(Message(replied_message))
            if reply_url:
                return reply_url

    return None


@image_tagger_cmd.handle()
async def _(matcher: Matcher, bot: Bot, event: MessageEvent, args=CommandArg()) -> None:
    if args is None:
        return
    image_url = await extract_image_url(bot, event.get_message())
    if image_url:
        matcher.set_arg("image_input", event.get_message())


@image_tagger_cmd.got("image_input", prompt="图呢？")
async def _(bot: Bot, event: MessageEvent, image_input: Message = Arg("image_input")) -> None:
    image_url = await extract_image_url(bot, image_input)
    if not image_url:
        await image_tagger_cmd.finish("还是没看到图")

    image_path = await download_image(image_url, TEMP_IMAGE_PATH)
    result_data = classify_image(image_path)
    character_tags = result_data["characters"]
    rating_key = str(result_data["rating_key"])
    rating_score = float(result_data["rating_score"])

    lines: list[str] = []
    if character_tags:
        lines.extend(f"{name}: {score * 100:.2f}%" for name, score in character_tags)
    else:
        lines.append("没识别到明确的人物标签")
    lines.append(f"{rating_key}: {rating_score * 100:.2f}%")

    message = Message()
    message.append(MessageSegment.at(event.user_id))
    message.append(MessageSegment.text("\n"))
    message.append(MessageSegment.text("\n".join(lines)))
    await image_tagger_cmd.finish(message)
