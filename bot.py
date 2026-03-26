from pathlib import Path

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter


nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)

BASE_DIR = Path(__file__).resolve().parent
nonebot.load_plugins(str(BASE_DIR / "koakuma_bot" / "plugins"))

if __name__ == "__main__":
    nonebot.run()
