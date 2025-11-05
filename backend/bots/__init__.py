# backend/bots/__init__.py


# +++ (核心修改) 1. 从新的单一文件导入所有星球机器人 +++
from .planet_bots import PlanetCollectorBot, PlanetSpeculatorBot, PlanetGamblerBot

from .base_bot import BaseBot

# (新增) 机器人逻辑注册表
BOT_LOGIC_MAP = {
    # +++ (核心修改) 2. 注册所有星球机器人 +++
    "PlanetCollectorBot": PlanetCollectorBot,   # 收藏家
    "PlanetSpeculatorBot": PlanetSpeculatorBot, # 投机商
    "PlanetGamblerBot": PlanetGamblerBot,       # 赌徒
}

# (确保这里没有从 planet_bot, planet_speculator_bot 等单独的文件导入)