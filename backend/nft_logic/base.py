# backend/nft_logic/base.py

from abc import ABC, abstractmethod

class NFTLogicHandler(ABC):
    """
    所有 NFT 逻辑插件的抽象基类。
    定义了每个 NFT 类型必须实现的标准化接口。
    """

    @abstractmethod
    def mint(self, owner_key: str, data: dict) -> (bool, str, dict):
        """
        处理铸造新 NFT 的逻辑。
        :param owner_key: 新 NFT 的所有者公钥。
        :param data: 来自管理员或用户的初始数据。
        :return: (是否成功, 消息, 存储到数据库的 data 字典)。
        """
        pass

    @abstractmethod
    def validate_action(self, nft: dict, action: str, action_data: dict, requester_key: str) -> (bool, str):
        """
        验证用户对 NFT 执行的某个操作是否合法。
        :param nft: 从数据库中获取的完整 NFT 对象 (包含 data)。
        :param action: 动作名称, e.g., 'reveal', 'breed'。
        :param action_data: 伴随该动作的数据。
        :param requester_key: 发起请求的用户的公钥。
        :return: (是否合法, 消息)。
        """
        pass

    @abstractmethod
    def perform_action(self, nft: dict, action: str, action_data: dict, requester_key: str) -> (bool, str, dict):
        """
        执行一个已验证合法的操作，并返回更新后的 NFT data。
        :param nft: 从数据库中获取的完整 NFT 对象。
        :param action: 动作名称。
        :param action_data: 伴随该动作的数据。
        :param requester_key: 发起请求的用户的公钥。
        :return: (是否成功, 消息, 更新后的 data 字典)。
        """
        pass