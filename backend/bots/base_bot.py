# backend/bots/base_bot.py

from abc import ABC, abstractmethod
from backend.bots.bot_client import BotClient

class BaseBot(ABC):
    """
    所有机器人逻辑的抽象基类。
    """
    
    def __init__(self, client: BotClient):
        self.client = client
        self.username = client.username
        print(f"💡 Bot logic '{self.__class__.__name__}' 已附加到 client '{self.username}'")

    @abstractmethod
    async def execute_turn(self):
        """
        执行一个机器人的逻辑回合。
        这个方法会被 bot_runner 定期调用。
        """
        pass