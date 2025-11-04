# backend/bots/__init__.py

from .example_bots import ShopEnthusiastBot, BargainHunterBot, SellerBot
# +++ 1. 导入你的新机器人 +++
from .complex_bot import ComplexBot
from .base_bot import BaseBot

# (新增) 机器人逻辑注册表
BOT_LOGIC_MAP = {
    "ShopEnthusiastBot": ShopEnthusiastBot,
    "BargainHunterBot": BargainHunterBot,
    "SellerBot": SellerBot,
    # +++ 2. 在这里注册新机器人 +++
    "ComplexBot": ComplexBot,
}