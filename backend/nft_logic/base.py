# backend/nft_logic/base.py

from abc import ABC, abstractmethod
import time
class NFTLogicHandler(ABC):
    """
    所有 NFT 逻辑插件的抽象基类。
    定义了每个 NFT 类型必须实现的标准化接口。
    """

    @classmethod
    def get_display_name(cls) -> str:
        """
        (类方法) 返回该 NFT 类型的中文显示名称。
        这是为了实现前端UI的解耦。
        """
        # 提供一个安全的默认值，以防有插件忘记实现它
        return cls.__name__.replace("Handler", "")
    # <<< --- 新增代码结束 --- >>>
    @abstractmethod
    def mint(self, owner_key: str, data: dict, owner_username: str = None) -> (bool, str, dict):
         """
         处理铸造新 NFT 的逻辑。
         :param owner_key: 新 NFT 的所有者公钥。
         :param data: 来自管理员或用户的初始数据。
         :param owner_username: (可选) 新 NFT 的所有者用户名。
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
        if action == 'destroy':
            if nft.get('owner_key') != requester_key:
                return False, "只有所有者才能销毁此物品"
            return True, "可以销毁"

        return False, f"不支持的动作: {action}"

    @abstractmethod
    def perform_action(self, nft: dict, action: str, action_data: dict, requester_key: str, conn=None) -> (bool, str, dict): # <<< (1) 新增 conn=None
        """
        执行一个已验证合法的操作，并返回更新后的 NFT data。
        :param nft: 从数据库中获取的完整 NFT 对象。
        :param action: 动作名称。
        :param action_data: 伴随该动作的数据。
        :param requester_key: 发起请求的用户的公钥。
        :param conn: (可选) 数据库连接对象，用于事务。
        :return: (是否成功, 消息, 更新后的 data 字典)。
        """
        # --- 新增：通用销毁操作执行 ---
        if action == 'destroy':
            updated_data = nft.get('data', {}).copy()
            # 特殊协议：告诉数据库将此 NFT 状态改为 'DESTROYED'
            updated_data['__new_status__'] = 'DESTROYED'
            # (可选) 清理数据
            updated_data['destroyed_at'] = time.time()
            return True, "物品已成功销毁", updated_data
        return False, "内部错误：执行了未验证的动作", {}
    
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
            "action_type": "create", # 新增：动作类型, create 是默认值
            "action_label": "支付并铸造", # 新增：按钮标签
            "description": "支付FC来封存一个秘密，它将在指定时间后消失。",
            "fields": [
                {"name": "description", "label": "公开描述", "type": "textarea", "required": True},
                {"name": "content", "label": "秘密内容", "type": "textarea", "required": True},
                {"name": "destroy_in_days", "label": "销毁天数", "type": "number", "required": True, "default": 7}
            ]
        }
        """
        return {"creatable": False}
    
    @classmethod
    def execute_shop_action(cls, owner_key: str, owner_username: str, data: dict, conn) -> (bool, str, str):
        """
        (类方法, 可选实现) 处理一个更复杂的商店动作，比如概率性铸造。
        只有当 get_shop_config() 中 action_type != 'create' 时才会被调用。
        :param owner_key: 发起动作的用户公钥。
        :param owner_username: 发起动作的用户名。
        :param data: 来自前端的表单数据。
        :param conn: 数据库连接对象 (用于事务处理)。
        :return: (是否成功, 消息, 新铸造的 NFT ID 或 None)。
        """
        # 默认情况下，不支持非创建类型的动作
        return False, "该物品类型不支持此商店动作", None
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