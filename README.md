# Koakuma Bot

This is a NoneBot2 + OneBot V11 bot for the migrated legacy QQ bot plugins.

## Structure

- `bot.py`: entrypoint
- `.env.example`: runtime configuration template (copy to local `.env`)
- `koakuma_bot/plugins/guess_song`: guess song plugin
- `koakuma_bot/plugins/image_tagger`: image character tagger
- `koakuma_bot/plugins/random_thcharacter`: random character
- `koakuma_bot/plugins/random_thplay`: random play loadout
- `koakuma_bot/plugins/random_thsound`: random music
- `koakuma_bot/plugins/random_thspellcard`: random spell card
- `koakuma_bot/plugins/bilibili_live`: Bilibili live-start notifications
- `koakuma_bot/plugins/calendar`: calendar broadcasts
- `koakuma_bot/plugins/recent_pnd`: recent PND score broadcasts
- `koakuma_bot/plugins/repeater`: group message repeater
- `koakuma_bot/services/touhou_random_catalog.py`: CSV-backed random data service
- `koakuma_bot/services/bilibili_live.py`: live room API, configuration, and notification state
- `data/`: all runtime data used by the bot
- `data/group_targets/`: per-plugin target group lists for scheduled/broadcast plugins
- `data/chcard_data/`: local-only group allowlist config for guess_song
- `tests/`: automated Bilibili notification tests
- `run_bot.sh`: start the bot using the local virtual environment
- `run_napcat.sh`: launch the installed macOS QQ application

## Run

Run from the repository root. On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python bot.py
```

Edit `.env` for your local connection settings before starting the bot. For a pinned deployment environment, use `requirements.deploy.txt` instead of `requirements.txt`.

On Windows, activate `.venv\Scripts\Activate.ps1` and copy `.env.example` to `.env` with `Copy-Item` before running `python bot.py`.

After setup, macOS and Linux users can start the bot with `./run_bot.sh`. macOS users can launch an installed QQ application with `./run_napcat.sh`; NapCat must already be installed and configured.

## NapCat reverse WebSocket

Set NapCat OneBot V11 reverse WebSocket target to one of:

- `ws://127.0.0.1:8080/onebot/v11/`
- `ws://127.0.0.1:8080/onebot/v11/ws`

If you use access token, keep it the same in both NapCat and `.env`.

## Notes

- All bot data is read from this project's `data/` directory.
- To deploy elsewhere, copy the whole `koakuma_bot` directory together with its `data/` directory.
- The question bank is loaded from `data/touhou_music`.
- The score database is stored at `data/song_data.db` and is created automatically if missing.
- Allowed groups are read from `data/chcard_data/allow_group.txt`.
- Random data plugins read `TH_character.csv`, `THplay.csv`, `TH_sound.csv`, and `TH_spellcard.csv` from `data/`.
- Calendar scheduled messages read YAML files from `data/days/` and target groups from `data/group_targets/calendar.txt`.
- Recent PND polling targets are configured in `data/group_targets/recent_pnd.txt`.
- Bilibili live notifications read room IDs from `data/bilibili_live_rooms.txt` and target groups from `data/group_targets/bilibili_live.txt`.
- Group target files and `allow_group.txt` are local-only config files and should not be committed with real group IDs.
- Character label mappings are stored in `data/character_labels_full.csv`.
- If you want to seed extra old label mappings, you can place them in `data/labels_legacy.txt`.
- Audio slicing uses `ffprobe` and `ffmpeg` directly.
- Guess-song audio is encoded as Tencent SILK with `silk-python`. On macOS, an existing NapCat cache directory is used for temporary audio; otherwise, audio is written under `data/`.
- You can set `FFMPEG_BIN` in `.env` to point to the ffmpeg `bin` directory.
- If `FFMPEG_BIN` is empty, the bot will try to use `ffmpeg` and `ffprobe` from PATH.

## Local configuration and privacy

Only `.env.example` is versioned. The local `.env`, QQ/NapCat configuration backups, real group IDs, Bilibili room selections, score databases, temporary audio/images, virtual environments, and local model/music assets are excluded by `.gitignore`.

Plugins create empty group/room configuration templates when needed. Keep real IDs and credentials in those local files and copy them separately when moving the bot to another machine.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Bilibili 开播通知

插件由 `bot.py` 自动加载，无需安装额外依赖。首次加载会生成空配置文件：

- `data/bilibili_live_rooms.txt`：每行一个 Bilibili **直播间号**（不是 UP 主 UID），支持短号和完整房间号。
- `data/group_targets/bilibili_live.txt`：每行一个 QQ 群号，格式与 `recent_pnd.txt` 相同。

空行和以 `#` 开头的注释行会被忽略。支持多个直播间和多个群；每个直播间的开播通知会发到所有配置的群。配置留空时不发送通知，修改配置后下次检查自动生效。

机器人连接时立即检查，此后每 60 秒检查一次。首次发现直播中会通知一次，之后仅在新一场直播时再次通知；轮播不通知。消息包含直播间号、标题、开播时间和链接。成功发送的群与直播场次保存在 `data/bilibili_live_state.json`，重启不会重复通知同一场直播；发送失败的群会在下次检查时重试。接口请求失败不会被当作下播。

发送 `/bilibili_live_status` 或 `/B站直播状态` 可查询配置的直播间状态。真实群号、直播间配置和运行状态均为本地文件，不提交到版本库。
