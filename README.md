# Koakuma Bot

This is a NoneBot2 + OneBot V11 bot for the migrated legacy QQ bot plugins.

## Structure

- `bot.py`: entrypoint
- `.env`: runtime config
- `koakuma_bot/plugins/guess_song`: guess song plugin
- `koakuma_bot/plugins/image_tagger`: image character tagger
- `koakuma_bot/plugins/random_thcharacter`: random character
- `koakuma_bot/plugins/random_thplay`: random play loadout
- `koakuma_bot/plugins/random_thsound`: random music
- `koakuma_bot/plugins/random_thspellcard`: random spell card
- `koakuma_bot/services/touhou_random_catalog.py`: CSV-backed random data service
- `data/`: all runtime data used by the bot
- `data/group_targets/`: per-plugin target group lists for scheduled/broadcast plugins
- `data/chcard_data/`: local-only group allowlist config for guess_song

## Run

```powershell
cd migration_examples\koakuma_bot
python bot.py
```

If your shell does not expose `python`, run the interpreter command that works in your environment.

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
- Group target files and `allow_group.txt` are local-only config files and should not be committed with real group IDs.
- Character label mappings are stored in `data/character_labels_full.csv`.
- If you want to seed extra old label mappings, you can place them in `data/labels_legacy.txt`.
- Audio slicing uses `ffprobe` and `ffmpeg` directly.
- You can set `FFMPEG_BIN` in `.env` to point to the ffmpeg `bin` directory.
- If `FFMPEG_BIN` is empty, the bot will try to use `ffmpeg` and `ffprobe` from PATH.
