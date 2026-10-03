from __future__ import annotations

import asyncio
import random

from nonebot import get_driver, on_command, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageSegment
from nonebot.adapters.onebot.v11.permission import GROUP
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER

from .audio import export_audio_fragment, probe_audio_duration_ms
from .config import DB_PATH, DIFFICULTY_MS, MUSIC_DIR, ONE_TURN_TIME, SCORE, TEMP_AUDIO, load_allow_groups
from .game import GuessSongManager
from .logic import GuessSongService
from .store import GuessSongStore


ALLOW_GROUPS = load_allow_groups()
store = GuessSongStore(DB_PATH)
manager = GuessSongManager()
service = GuessSongService(manager, store, SCORE)
TRIGGER_NAMES = {"原曲识别", "猜原曲", "歌曲识别"}

try:
    driver = get_driver()
    _NONEBOT_INITIALIZED = True
    NICKNAMES = {str(name).strip() for name in driver.config.nickname if str(name).strip()}
except ValueError:
    _NONEBOT_INITIALIZED = False
    NICKNAMES = set()


def build_record_message(file_path) -> Message:
    return Message(MessageSegment.record(file=str(file_path)))


def parse_song_answers(song_name: str) -> tuple[list[str], str]:
    parts = song_name.rsplit(".", 1)[0].split("_", 1)
    left_name = parts[0].strip().lower()
    right_name = parts[1].strip().lower() if len(parts) > 1 else left_name

    answers = [left_name, right_name]
    for sep in ("~", "～"):
        if sep in left_name:
            answers.extend(part.strip() for part in left_name.split(sep) if part.strip())

    reveal_name = song_name.rsplit(".", 1)[0].replace("_", " / ")
    return answers, reveal_name


async def random_fragment(difficulty: str) -> tuple[list[str], str]:
    songs = [path for path in MUSIC_DIR.iterdir() if path.is_file()]
    if not songs:
        raise RuntimeError(f"no music files found under {MUSIC_DIR}")
    song = random.choice(songs)

    clip_ms = DIFFICULTY_MS[difficulty]
    duration_ms = probe_audio_duration_ms(song)
    max_start = max(duration_ms - clip_ms, 0)
    start_ms = random.randint(0, max_start) if max_start else 0
    export_audio_fragment(song, TEMP_AUDIO, start_ms, clip_ms)

    answers, reveal_name = parse_song_answers(song.name)
    return answers, reveal_name


async def get_user_card(bot: Bot, group_id: int, user_id: int) -> str:
    members = await bot.get_group_member_list(group_id=group_id)
    for member in members:
        if int(member["user_id"]) == user_id:
            return member["card"] or member["nickname"]
    return str(user_id)


def parse_nickname_trigger(text: str) -> str | None:
    plain = text.strip()
    if not plain or not NICKNAMES:
        return None

    for nickname in sorted(NICKNAMES, key=len, reverse=True):
        if not plain.startswith(nickname):
            continue
        rest = plain[len(nickname) :].strip()
        if not rest:
            return None

        for trigger_name in TRIGGER_NAMES:
            if rest.startswith(trigger_name):
                difficulty = rest[len(trigger_name) :].strip().upper()
                return difficulty or "N"
    return None


async def start_song_game(bot: Bot, group_id: int, difficulty: str) -> tuple[bool, str]:
    if ALLOW_GROUPS and group_id not in ALLOW_GROUPS:
        return False, "这个群没有开启猜原曲。"

    if difficulty not in DIFFICULTY_MS:
        difficulty = "N"

    answers, reveal_name = await random_fragment(difficulty)
    started = await service.start_round(group_id, answers, reveal_name, difficulty)
    if not started:
        return False, "本轮还没结束"

    game = await service.get_round(group_id)
    if not game:
        return False, "初始化题目失败。"

    async def timeout() -> None:
        try:
            await asyncio.sleep(ONE_TURN_TIME)
            finished = await manager.finish_game(group_id)
            if finished and finished.winner_id is None:
                await bot.send_group_msg(group_id=group_id, message=f"正确答案是：{finished.reveal_name}")
        except asyncio.CancelledError:
            return

    game.timeout_task = asyncio.create_task(timeout())
    try:
        await bot.send_group_msg(group_id=group_id, message=build_record_message(TEMP_AUDIO))
        await bot.send_group_msg(group_id=group_id, message=f"{ONE_TURN_TIME} 秒后公布答案")
    except Exception as error:
        if game.timeout_task:
            game.timeout_task.cancel()
        await manager.finish_game(group_id)
        return False, f"题目音频发送失败：{error}"
    return True, ""


if _NONEBOT_INITIALIZED:
    song_recog = on_command("song_recog", aliases={"guess_song", "原曲识别"}, permission=GROUP, block=True, priority=10)
    leaderboard = on_command("leaderboard", aliases={"song_rank", "排行榜"}, permission=GROUP, block=True, priority=10)
    reset_scores = on_command(
        "reset_song_score",
        aliases={"reset_song_rank", "清空原曲积分"},
        permission=SUPERUSER,
        block=True,
        priority=10,
    )
    kill_game = on_command("kill", permission=SUPERUSER, block=True, priority=10)
    nickname_trigger = on_message(permission=GROUP, priority=11, block=False)
    answer_listener = on_message(permission=GROUP, priority=5, block=False)

    @song_recog.handle()
    async def handle_song_recog(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()) -> None:
        difficulty = args.extract_plain_text().strip().upper() or "N"
        ok, error = await start_song_game(bot, event.group_id, difficulty)
        if not ok:
            await song_recog.finish(error)

    @nickname_trigger.handle()
    async def handle_nickname_trigger(bot: Bot, event: GroupMessageEvent) -> None:
        difficulty = parse_nickname_trigger(event.get_plaintext())
        if difficulty is None:
            return

        ok, error = await start_song_game(bot, event.group_id, difficulty)
        if not ok:
            await nickname_trigger.finish(error)
        await nickname_trigger.finish()

    @answer_listener.handle()
    async def handle_answer(bot: Bot, event: GroupMessageEvent) -> None:
        if ALLOW_GROUPS and event.group_id not in ALLOW_GROUPS:
            return

        game = await service.get_round(event.group_id)
        if not game:
            return

        guess = event.get_plaintext().strip().lower()
        if not guess:
            return

        result = await service.submit_answer(event.group_id, event.user_id, guess)
        if not result.matched:
            return

        if game.timeout_task:
            game.timeout_task.cancel()
        user_card = await get_user_card(bot, event.group_id, event.user_id)
        await answer_listener.send(f"正确答案是：{result.reveal_name}\n{user_card} 回答正确，得分 +{result.gained_score}，当前积分 {result.total_score}")

    @leaderboard.handle()
    async def handle_leaderboard(bot: Bot, event: GroupMessageEvent) -> None:
        members = await bot.get_group_member_list(group_id=event.group_id)
        ranking: list[tuple[str, int]] = []
        for member in members:
            user_id = int(member["user_id"])
            name = member["card"] or member["nickname"]
            ranking.append((name, store.get_score(event.group_id, user_id)))

        ranking.sort(key=lambda item: item[1], reverse=True)
        lines = ["原曲识别排行榜"]
        for index, (name, points) in enumerate(ranking[:10], start=1):
            if points <= 0:
                continue
            lines.append(f"{index}. {name} - {points}")

        await leaderboard.finish("\n".join(lines))

    @reset_scores.handle()
    async def handle_reset_scores(event: GroupMessageEvent, args: Message = CommandArg()) -> None:
        scope = args.extract_plain_text().strip().lower()
        if scope == "all":
            store.clear_all_scores()
            await reset_scores.finish("已清空所有群的原曲积分。")

        store.clear_group_scores(event.group_id)
        await reset_scores.finish("已清空本群的原曲积分。")

    @kill_game.handle()
    async def handle_kill(event: GroupMessageEvent) -> None:
        finished = await manager.finish_game(event.group_id)
        if not finished:
            await kill_game.finish("当前没有进行中的猜原曲。")

        if finished.timeout_task:
            finished.timeout_task.cancel()

        await kill_game.finish(f"已结束当前题目，答案是：{finished.reveal_name}")
