from __future__ import annotations

import asyncio
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import nonebot
from nonebot.adapters.onebot.v11 import Bot

from koakuma_bot.services import bilibili_live as service
from koakuma_bot.services.bilibili_live import LiveRoom, LiveRoomState


nonebot.init(_env_file=None, driver="~fastapi", log_level="ERROR")
loaded_plugin = nonebot.load_plugin("koakuma_bot.plugins.bilibili_live")
if loaded_plugin is None:
    raise RuntimeError("Bilibili live plugin failed to load")
plugin = loaded_plugin.module


class LiveServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.directory = Path(temporary_directory.name)
        for name, filename in [("ROOMS_PATH", "rooms.txt"), ("STATE_PATH", "state.json")]:
            patcher = patch.object(service, name, self.directory / filename)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_room_file_created_and_parses_ids_comments_duplicates_and_bom(self) -> None:
        self.assertEqual(service.load_room_ids(), [])
        self.assertTrue(service.ROOMS_PATH.exists())
        service.ROOMS_PATH.write_text("\ufeff# rooms\n6\n\n42 # full ID\n6\n0\n-1\nwrong\n", encoding="utf-8")
        self.assertEqual(service.load_room_ids(), [6, 42])

    def test_room_api_normalizes_short_id_and_zero_start_time(self) -> None:
        response = {"code": 0, "data": {"room_id": 42, "live_status": 1, "title": "测试直播", "live_time": "0000-00-00 00:00:00"}}
        with patch.object(service, "urlopen", return_value=io.BytesIO(json.dumps(response).encode())) as request:
            room = service.fetch_live_room(6)
        self.assertEqual(room, LiveRoom(42, 1, "测试直播"))
        self.assertIn("room_id=6", request.call_args.args[0].full_url)
        self.assertEqual(request.call_args.kwargs["timeout"], 15)
        self.assertIn("https://live.bilibili.com/42", room.format_message())

    def test_api_errors_and_missing_status_are_not_treated_as_offline(self) -> None:
        for response in [
            {"code": -352},
            {"code": 0, "data": None},
            {"code": 0, "data": {"room_id": 42}},
            {"code": 0, "data": {"room_id": 42, "live_status": 3}},
        ]:
            with self.subTest(response=response):
                with patch.object(service, "urlopen", return_value=io.BytesIO(json.dumps(response).encode())):
                    with self.assertRaises(ValueError):
                        service.fetch_live_room(42)

    def test_state_survives_save_and_reload_without_partial_file(self) -> None:
        states = {42: LiveRoomState(1, "2026-10-03 12:00:00", {10001, 10002})}
        service.save_live_state(states)
        self.assertEqual(service.load_live_state(), states)
        self.assertFalse(service.STATE_PATH.with_suffix(".json.tmp").exists())

    def test_damaged_state_is_not_silently_reset(self) -> None:
        for content in ["{", "[]", '{"rooms": []}', '{"rooms": {"42": {"live_status": 1, "notified_groups": ["invalid"]}}}']:
            with self.subTest(content=content):
                service.STATE_PATH.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    service.load_live_state()

    def test_temporarily_missing_start_time_preserves_deduplication(self) -> None:
        previous = LiveRoomState(1, "2026-10-03 12:00:00", {10001})
        current = service.next_room_state(LiveRoom(42, 1, "new title"), previous)
        self.assertEqual(current, previous)
        current.notified_groups.add(10002)
        self.assertEqual(previous.notified_groups, {10001})


class BroadcastTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.state_path = Path(temporary_directory.name) / "state.json"
        self.bot = Mock(spec=Bot)
        self.bot.send_group_msg = AsyncMock()
        self.fetch = Mock(return_value=LiveRoom(42, 1, "测试直播", "2026-10-03 12:00:00"))
        self.groups = Mock(return_value=[10001, 10002])
        self.rooms = Mock(return_value=[42])
        for target, name, value in [
            (service, "STATE_PATH", self.state_path),
            (plugin, "poll_lock", asyncio.Lock()),
            (plugin, "get_online_bot", Mock(return_value=self.bot)),
            (plugin, "load_group_targets", self.groups),
            (plugin, "load_room_ids", self.rooms),
            (plugin, "fetch_live_room", self.fetch),
        ]:
            patcher = patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_first_live_poll_notifies_once_using_persisted_state(self) -> None:
        self.assertEqual(await plugin.broadcast_live_notifications(), 2)
        self.assertEqual(await plugin.broadcast_live_notifications(), 0)
        self.assertEqual(self.bot.send_group_msg.await_count, 2)
        state = service.load_live_state()[42]
        self.assertEqual(state.notified_groups, {10001, 10002})

    async def test_offline_and_replay_do_not_notify_and_next_session_does(self) -> None:
        for status in [0, 2]:
            self.fetch.return_value = LiveRoom(42, status, "测试直播")
            self.assertEqual(await plugin.broadcast_live_notifications(), 0)
        self.fetch.return_value = LiveRoom(42, 1, "测试直播")
        self.assertEqual(await plugin.broadcast_live_notifications(), 2)
        self.fetch.return_value = LiveRoom(42, 0, "测试直播")
        self.assertEqual(await plugin.broadcast_live_notifications(), 0)
        self.fetch.return_value = LiveRoom(42, 1, "测试直播")
        self.assertEqual(await plugin.broadcast_live_notifications(), 2)

    async def test_new_start_time_notifies_even_when_offline_poll_was_missed(self) -> None:
        self.assertEqual(await plugin.broadcast_live_notifications(), 2)
        self.fetch.return_value = LiveRoom(42, 1, "changed title", "2026-10-03 12:00:00")
        self.assertEqual(await plugin.broadcast_live_notifications(), 0)
        self.fetch.return_value = LiveRoom(42, 1, "next stream", "2026-10-03 15:00:00")
        self.assertEqual(await plugin.broadcast_live_notifications(), 2)

    async def test_failed_group_retries_without_repeating_successful_group(self) -> None:
        failed_once = False

        async def send(*, group_id: int, message) -> None:
            nonlocal failed_once
            if group_id == 10002 and not failed_once:
                failed_once = True
                raise RuntimeError("temporary QQ send failure")

        self.bot.send_group_msg.side_effect = send
        self.assertEqual(await plugin.broadcast_live_notifications(), 1)
        self.assertEqual(await plugin.broadcast_live_notifications(), 1)
        self.assertEqual(await plugin.broadcast_live_notifications(), 0)
        self.assertEqual([call.kwargs["group_id"] for call in self.bot.send_group_msg.await_args_list], [10001, 10002, 10002])

    async def test_new_group_gets_current_stream_without_repeating_old_groups(self) -> None:
        self.assertEqual(await plugin.broadcast_live_notifications(), 2)
        self.groups.return_value = [10001, 10002, 10003, 10003]
        self.assertEqual(await plugin.broadcast_live_notifications(), 1)
        self.assertEqual(self.bot.send_group_msg.await_args.kwargs["group_id"], 10003)

    async def test_duplicate_short_and_full_room_ids_do_not_duplicate_messages(self) -> None:
        self.rooms.return_value = [6, 42]
        self.groups.return_value = [10001, 10001]
        self.assertEqual(await plugin.broadcast_live_notifications(), 1)

    async def test_no_bot_or_empty_configuration_does_not_consume_notifications(self) -> None:
        with patch.object(plugin, "get_online_bot", return_value=None):
            self.assertEqual(await plugin.broadcast_live_notifications(), 0)
        self.fetch.assert_not_called()
        self.groups.return_value = []
        self.assertEqual(await plugin.broadcast_live_notifications(), 0)
        self.fetch.assert_not_called()
        self.assertFalse(self.state_path.exists())
        self.groups.return_value = [10001]
        self.assertEqual(await plugin.broadcast_live_notifications(), 1)

    async def test_api_failure_preserves_state_and_other_rooms_still_notify(self) -> None:
        service.save_live_state({42: LiveRoomState(1, "2026-10-03 12:00:00", {10001, 10002})})
        self.rooms.return_value = [42, 43]

        def fetch(room_id: int) -> LiveRoom:
            if room_id == 42:
                raise TimeoutError("Bilibili unavailable")
            return LiveRoom(43, 1, "another room", "2026-10-03 12:00:00")

        self.fetch.side_effect = fetch
        self.assertEqual(await plugin.broadcast_live_notifications(), 2)
        self.assertEqual(service.load_live_state()[42].notified_groups, {10001, 10002})
        self.fetch.side_effect = None
        self.rooms.return_value = [42]
        self.assertEqual(await plugin.broadcast_live_notifications(), 0)

    async def test_damaged_state_prevents_notifications(self) -> None:
        self.state_path.write_text("{broken", encoding="utf-8")
        self.assertEqual(await plugin.broadcast_live_notifications(), 0)
        self.fetch.assert_not_called()
        self.bot.send_group_msg.assert_not_awaited()

    async def test_overlapping_connect_and_scheduled_checks_notify_once(self) -> None:
        counts = await asyncio.gather(plugin.broadcast_live_notifications(), plugin.broadcast_live_notifications())
        self.assertEqual(sum(counts), 2)
        self.assertEqual(self.bot.send_group_msg.await_count, 2)

    async def test_title_with_cq_syntax_is_sent_as_plain_text(self) -> None:
        self.fetch.return_value = LiveRoom(42, 1, "[CQ:at,qq=all]")
        await plugin.broadcast_live_notifications()
        message = self.bot.send_group_msg.await_args.kwargs["message"]
        self.assertEqual(message.type, "text")
        self.assertIn("[CQ:at,qq=all]", message.data["text"])


if __name__ == "__main__":
    unittest.main()
