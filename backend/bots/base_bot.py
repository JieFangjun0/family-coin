# backend/bots/base_bot.py

from abc import ABC, abstractmethod
from backend.bots.bot_client import BotClient
from backend import ledger  # +++ 导入 ledger +++
import json # +++ 导入 json +++
class BaseBot(ABC):
    """
    所有机器人逻辑的抽象基类。
    """
    
    def __init__(self, client: BotClient):
        self.client = client
        self.username = client.username
        # +++ (修改) 定义日志前缀，供 print 使用 +++
        self.log_prefix = f"🤖 '{self.username}' ({self.__class__.__name__}):"
        print(f"💡 Bot logic '{self.__class__.__name__}' 已附加到 client '{self.username}'")

    # +++ (新增) 中心的、可写入数据库的 log 方法 +++
    def log(self, message: str, action_type: str = "INFO", data_snapshot: dict = None):
        """
        记录一条日志。
        它会同时 print 到控制台并尝试写入 `bot_logs` 数据库表。
        """
        # 1. 打印到控制台 (保持不变)
        print(f"{self.log_prefix} {message}")
        
        # 2. 尝试写入数据库
        try:
            # (这是一个线程安全的函数)
            ledger.log_bot_action(
                bot_key=self.client.public_key,
                bot_username=self.username,
                action_type=action_type.upper(),
                message=message,
                data_snapshot=data_snapshot
            )
        except Exception as e:
            # 写入日志失败绝不能让机器人崩溃
            print(f"❌ {self.log_prefix} 无法将日志写入数据库: {e}")
            
    # +++ (新增) 辅助函数，用于记录回合快照 +++
    def log_turn_snapshot(self, balance: float, nfts: list, listings: list):
        """记录一个包含关键指标的回合开始快照"""
        try:
            snapshot = {
                "balance": balance,
                "active_nft_count": len(nfts),
                "active_listing_count": len(listings)
            }
            self.log(
                f"开始评估。状态: {balance:.2f} FC, {len(nfts)} 个NFT, {len(listings)} 个挂单。",
                action_type="EVALUATE_START",
                data_snapshot=snapshot
            )
        except Exception as e:
            self.log(f"记录快照失败: {e}", action_type="ERROR")

    @abstractmethod
    async def execute_turn(self):
        """
        执行一个机器人的逻辑回合。
        这个方法会被 bot_runner 定期调用。
        """
        pass