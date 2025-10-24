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
    
    # <<< 商店配置接口 >>>
    @classmethod
    def get_shop_config(cls) -> dict:
        """
        (类方法) 返回该NFT在商店中的创建配置。
        如果返回非空字典，表示该NFT可以通过商店创建。
        返回格式:
        {
            "creatable": True,
            "cost": 10.0, # 创建所需FC
            "name": "秘密愿望",
            "description": "支付FC来封存一个秘密，它将在指定时间后消失。",
            "fields": [
                {"name": "description", "label": "公开描述", "type": "textarea", "required": True},
                {"name": "content", "label": "秘密内容", "type": "textarea", "required": True},
                {"name": "destroy_in_days", "label": "销毁天数", "type": "number", "required": True, "default": 7}
            ]
        }
        """
        return {"creatable": False}
    
    # <<< --- “可交易性”检查接口 --- >>>
    def is_tradable(self, nft: dict) -> (bool, str):
        """
        (可选实现) 检查该NFT当前是否满足特定类型的交易条件。
        这个检查发生在所有通用检查（如所有权、状态）之后。
        :param nft: 从数据库中获取的完整 NFT 对象。
        :return: (是否可交易, 消息)。
        """
        # 默认情况下，所有NFT都是可交易的。
        # 只有像“秘密愿望”这样有时间限制的NFT才需要重写此方法。
        return True, "OK"
    
    # <<< 新增功能：交易描述函数 >>>
    def get_trade_description(self, nft: dict) -> str:
        """
        (可选实现) 获取该NFT在市场中展示的动态描述。
        这个描述可以基于NFT的内部数据动态生成。
        :param nft: 从数据库中获取的完整 NFT 对象。
        :return: 一个用于市场展示的字符串。
        """
        # 默认实现：返回 data 字典中的 'name' 或 'description'
        # 这为老插件提供了向后兼容性
        data = nft.get('data', {})
        ret_str = 'NTF'
        if 'name' in data:
            ret_str+= "名称："+str(data['name'])+';'
        if 'description' in data:
            ret_str+= '描述：'+str(data['description'])+';'
        return ret_str