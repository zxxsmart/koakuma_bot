from pathlib import Path

from koakuma_bot.services.project_paths import project_data_path

PLUGIN_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PLUGIN_DIR.parents[2]
DATA_DIR = project_data_path()
CHCARD_DIR = DATA_DIR / "chcard_data"
MUSIC_DIR = project_data_path("touhou_music")
NAPCAT_CACHE_DIR = Path.home() / "Library/Containers/com.tencent.qq/Data/Library/Application Support/QQ/NapCat/cache"
TEMP_AUDIO = NAPCAT_CACHE_DIR / "koakuma_temp_guess_song.silk" if NAPCAT_CACHE_DIR.exists() else project_data_path("temp_guess_song.silk")
DB_PATH = project_data_path("song_data.db")
ALLOW_GROUP_FILE = project_data_path("chcard_data", "allow_group.txt")
ALLOW_GROUP_TEMPLATE = "# One group ID per line.\n# Leave empty to allow all groups.\n"

ONE_TURN_TIME = 50
DIFFICULTY_MS = {"E": 5000, "N": 3000, "H": 1750, "L": 1000}
SCORE = {"E": 1, "N": 2, "H": 3, "L": 5}


def load_allow_groups() -> set[int]:
    if not ALLOW_GROUP_FILE.exists():
        CHCARD_DIR.mkdir(parents=True, exist_ok=True)
        ALLOW_GROUP_FILE.write_text(ALLOW_GROUP_TEMPLATE, encoding="utf-8")
        return set()
    return {
        int(line.strip())
        for line in ALLOW_GROUP_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#") and line.strip().isdigit()
    }
