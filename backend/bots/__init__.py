# backend/bots/__init__.py

# +++ (核心修改) 1. 从新的单一文件导入所有星球机器人 +++
# 移除旧的机器人，只导入新的
from .planet_bots import PlanetCapitalistBot
# from .bio_dna import BioDnaHandler 
# 假设你的 bio_dna 机器人逻辑在另一个文件
# from .bio_dna_bots import ... 

from .base_bot import BaseBot

# (新增) 机器人逻辑注册表
BOT_LOGIC_MAP = {
    # +++ (核心修改) 2. 注册所有星球机器人 +++
    # (移除了 PlanetCollectorBot, PlanetSpeculatorBot, PlanetGamblerBot)
    "PlanetCapitalistBot": PlanetCapitalistBot,
    
    # (假设你还想要保留 BIO_DNA 机器人)
    # "BioDnaBot": BioDnaBot, 
}