# backend/bots/__init__.py

from .example_bots import ShopEnthusiastBot, BargainHunterBot, SellerBot
from .base_bot import BaseBot

# (新增) 机器人逻辑注册表
BOT_LOGIC_MAP = {
    "ShopEnthusiastBot": ShopEnthusiastBot,
    "BargainHunterBot": BargainHunterBot,
    "SellerBot": SellerBot,
    # 你未来新的 Bot 逻辑类添加在这里
}