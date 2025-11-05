# backend/bots/__init__.py
from .planet_bots import PlanetCapitalistBot
from .bio_dna_bots import BioDnaBot

from .base_bot import BaseBot

# 机器人逻辑注册表
BOT_LOGIC_MAP = {
    "PlanetCapitalistBot": PlanetCapitalistBot,
    "BIO_DNA_BOT": BioDnaBot,
}