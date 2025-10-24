# **FamilyCoin NFT 插件开发指南 (V1.0)**

## **1\. 架构概览**

欢迎来到 FamilyCoin 插件开发！本系统采用“前后端分离”的插件化架构，允许你轻松添加新的 NFT 类型，而无需修改任何核心代码。

其设计理念如下：

* **后端 (backend/nft\_logic/)**: 采用“策略模式”。你只需要定义一个 Handler 类（一个“逻辑处理器”），它负责处理该 NFT 类型的所有独特逻辑（如铸造、执行动作）。  
* **前端 (frontend/nft\_renderers/)**: 采用“动态发现”。你只需要提供一个 \_renderer.py 文件（一个“渲染器”），它负责两件事：  
  1. 在“我的收藏”中如何展示这个 NFT。  
  2. 在“管理员面板”中为铸造提供帮助信息。

主应用 (main.py 和 app.py) 会自动发现并注册你的插件。

## **2\. 我们的目标：创建 "生物DNA宠物" 插件**

在本教程中，我们将从零开始，完整地创建并集成一个新的 NFT 插件：“生物DNA宠物” (BIO\_DNA)。

**我们的宠物将具有以下功能：**

1. **铸造 (mint)**: 管理员铸造时，可以指定一个名字，系统将为其随机生成一套DNA序列和稀有度。  
2. **展示 (render)**: 在“我的收藏”中，宠物将显示其名字、DNA序列和稀有度分数。  
3. **动作 (action)**: 我们将实现一个简单的动作，rename（重命名），允许所有者给宠物改名。

## **3\. 步骤一：实现后端逻辑 (Handler)**

首先，我们定义宠物的核心规则和数据结构。

1. **创建新文件**: backend/nft\_logic/bio\_dna.py  
2. **编写代码**:

\# backend/nft\_logic/bio\_dna.py

import random  
from .base import NFTLogicHandler

class BioDNAHandler(NFTLogicHandler):  
    """  
    “生物DNA宠物”NFT 的逻辑处理器。  
    """

    def \_generate\_dna(self):  
        """辅助函数：生成随机DNA序列。"""  
        parts \= \["CAT", "DOG", "FOX", "BIRD"\]  
        colors \= \["BLACK", "WHITE", "GOLD", "BLUE"\]  
        patterns \= \["SOLID", "STRIPED", "SPOTTED"\]  
        return \[random.choice(parts), random.choice(colors), random.choice(patterns)\]

    def \_calculate\_rarity(self, dna):  
        """辅助函数：根据DNA计算稀有度。"""  
        score \= 0  
        if "GOLD" in dna:  
            score \+= 50  
        if "SPOTTED" in dna:  
            score \+= 30  
        return score \+ random.randint(1, 20\)

    \# \--- 必须实现的接口 \---

    def mint(self, owner\_key: str, data: dict) \-\> (bool, str, dict):  
        """  
        处理铸造新宠物的逻辑。  
        管理员需要提供:   
        \- name (str): 宠物的初始名字。  
        """  
        name \= data.get('name')  
        if not name:  
            return False, "必须提供宠物的 'name' (名字)", {}

        \# 1\. 生成宠物的独特属性  
        dna \= self.\_generate\_dna()  
        rarity\_score \= self.\_calculate\_rarity(dna)  
          
        \# 2\. 这是将要存入数据库 nfts.data 字段的 JSON 对象  
        db\_data \= {  
            "name": name,  
            "dna": dna,  
            "generation": 1,  
            "rarity\_score": rarity\_score  
        }  
        return True, f"成功孵化出一只新宠物: {name}！", db\_data

    def validate\_action(self, nft: dict, action: str, action\_data: dict, requester\_key: str) \-\> (bool, str):  
        """  
        验证用户对宠物执行的某个操作是否合法。  
        """  
        \# 1\. 检查是否为所有者  
        if nft\['owner\_key'\] \!= requester\_key:  
            return False, "你不是此宠物的所有者"

        \# 2\. 验证 'rename' 动作  
        if action \== 'rename':  
            new\_name \= action\_data.get('new\_name')  
            if not new\_name or len(new\_name) \< 3 or len(new\_name) \> 20:  
                return False, "新名字必须在 3 到 20 个字符之间"  
            return True, "可以重命名"  
          
        \# 3\. （未来扩展）验证 'breed' 动作  
        if action \== 'breed':  
            return False, "繁殖功能暂未开放"

        return False, f"不支持的动作: {action}"

    def perform\_action(self, nft: dict, action: str, action\_data: dict, requester\_key: str) \-\> (bool, str, dict):  
        """  
        执行一个已验证合法的操作，并返回更新后的 NFT data。  
        """  
        updated\_data \= nft\['data'\].copy()

        if action \== 'rename':  
            new\_name \= action\_data.get('new\_name')  
            updated\_data\['name'\] \= new\_name  
            return True, f"宠物已成功重命名为: {new\_name}", updated\_data  
              
        return False, "内部错误：执行了未验证的动作", {}

## **4\. 步骤二：注册后端插件**

现在，让后端系统“知道”这个新插件的存在。

1. **打开文件**: backend/nft\_logic/\_\_init\_\_.py  
2. **修改代码**:

\# backend/nft\_logic/\_\_init\_\_.py

from .base import NFTLogicHandler  
from .time\_capsule import TimeCapsuleHandler  
\# \<\<\< 步骤 2.1: 导入你的新 Handler \>\>\>  
from .bio\_dna import BioDNAHandler

\# \<\<\< NFT 架构升级: 插件注册表 \>\>\>  
NFT\_HANDLERS \= {  
    "TIME\_CAPSULE": TimeCapsuleHandler,  
    \# \<\<\< 步骤 2.2: 在字典中添加新条目 \>\>\>  
    "BIO\_DNA": BioDNAHandler,   
}

def get\_handler(nft\_type: str) \-\> NFTLogicHandler:  
    \# ... (此函数保持不变)  
    handler\_class \= NFT\_HANDLERS.get(nft\_type)  
    if not handler\_class:  
        return None  
    return handler\_class()

def get\_available\_nft\_types() \-\> list:  
    \# ... (此函数保持不变)  
    return list(NFT\_HANDLERS.keys())

**恭喜！** 你的后端现在已完全支持 BIO\_DNA 宠物的铸造、查询和重命名了。

## **5\. 步骤三：实现前端渲染器 (Renderer)**

接下来，我们创建前端 UI，让用户能看到他们的宠物并与之互动。

1. 创建新文件: frontend/nft\_renderers/bio\_dna\_renderer.py  
   (注意：文件名必须以 \_renderer.py 结尾，bio\_dna 必须小写，以对应后端的 BIO\_DNA 类型)  
2. **编写代码**:

\# frontend/nft\_renderers/bio\_dna\_renderer.py

import streamlit as st

\# \--- 1\. 管理员铸造表单 (可选但推荐) \---  
def get\_admin\_mint\_info():  
    """  
    为管理员铸造表单提供帮助信息和默认数据。  
    """  
    return {  
        "help\_text": '对于生物DNA宠物, 请提供: {"name": "宠物的初始名字"}',  
        "default\_json": '{\\n  "name": "皮卡丘"\\n}'  
    }

\# \--- 2\. 用户收藏页渲染 (必需) \---  
def render(st, nft, balance, api\_call\_func, create\_signed\_message\_func):  
    """  
    专门用于渲染“生物DNA宠物”类型 NFT 的组件。  
    """  
    data \= nft.get('data', {})  
    nft\_id \= nft.get('nft\_id')  
      
    \# \--- 2.1 基本信息展示 \---  
    st.subheader(f"🧬 生物宠物: {data.get('name', '未命名')}")  
    st.caption(f"ID: \`{nft\_id\[:8\]}\` | 世代: {data.get('generation', 1)}")

    col1, col2 \= st.columns(2)  
    col1.metric("稀有度", f"{data.get('rarity\_score', 0)} 分")  
      
    dna\_str \= ", ".join(data.get('dna', \[\]))  
    col2.text\_input("DNA 序列", dna\_str, disabled=True)

    \# (可选) 根据DNA显示图片  
    if "GOLD" in data.get('dna', \[\]):  
        st.image("\[https://placehold.co/600x300/FFD700/000000?text=GOLD+Pet\](https://placehold.co/600x300/FFD700/000000?text=GOLD+Pet)\!",   
                 caption="这是一只稀有的金色宠物！")

    \# \--- 2.2 动作交互 \---  
    with st.expander("执行操作: 重命名"):  
        with st.form(key=f"rename\_form\_{nft\_id}"):  
            new\_name \= st.text\_input("输入新名字", max\_chars=20)  
            submitted \= st.form\_submit\_button("确认改名")

            if submitted:  
                if not new\_name or len(new\_name) \< 3:  
                    st.error("新名字必须在 3 到 20 个字符之间")  
                else:  
                    with st.spinner("正在签名并重命名..."):  
                        message\_dict \= {  
                            "owner\_key": nft\['owner\_key'\],  
                            "nft\_id": nft\_id,  
                            "action": "rename",  
                            "action\_data": {"new\_name": new\_name}  
                        }  
                        signed\_payload \= create\_signed\_message\_func(message\_dict)  
                        if signed\_payload:  
                            res\_data, error \= api\_call\_func('POST', '/nfts/action', payload=signed\_payload)  
                            if error:  
                                st.error(f"重命名失败: {error}")  
                            else:  
                                st.success(f"重命名成功！{res\_data.get('detail')}")  
                                st.cache\_data.clear() \# 清理缓存以便刷新  
                                st.rerun() \# 立即刷新页面

## **6\. 步骤四：前端自动注册**

**你什么都不用做！**

得益于我们的前端架构，frontend/nft\_renderers/\_\_init\_\_.py 会自动扫描 nft\_renderers 目录，找到你的 bio\_dna\_renderer.py 文件，并自动注册 render 和 get\_admin\_mint\_info 函数。

## **7\. 步骤五：部署与测试**

你的插件已经开发完毕，现在来验证它：

1. 重启服务:  
   在你的服务器上，回到 family-coin/ 根目录，执行：  
   docker-compose up \--build \-d

   *( \--build 会确保所有新添加的 Python 文件都被正确打包进镜像)*  
2. **测试管理员铸造**:  
   * 登录你的管理员账户。  
   * 进入 "⭐ 管理员 ⭐" \-\> "💎 NFT 管理" 标签页。  
   * 在 "选择要铸造的 NFT 类型" 下拉菜单中，你应该能看到新的 "BIO\_DNA" 选项。  
   * 选择 "BIO\_DNA"，下方的帮助文本和默认 JSON 会自动更新。  
   * 选择一个接收用户，点击 "确认铸造"。  
3. **测试用户展示与交互**:  
   * 登录你刚刚接收 NFT 的那个用户账户。  
   * 进入 "🖼️ 我的收藏" 标签页。  
   * 你应该能看到一个 "生物宠物" 卡片，显示着它的名字、稀有度和DNA。  
   * 展开 "执行操作: 重命名"，输入一个新名字并提交。  
   * 页面刷新后，宠物的名字应该已经更新。

## **8\. 总结**

你已经成功地为 FamilyCoin 添加了一个功能完整的 NFT 插件。

**回顾一下你的工作：**

1. **创建了 backend/nft\_logic/bio\_dna.py** 来定义所有后端逻辑。  
2. **修改了 backend/nft\_logic/\_\_init\_\_.py** 来注册这个后端插件。  
3. **创建了 frontend/nft\_renderers/bio\_dna\_renderer.py** 来定义所有前端 UI 和交互。

这个架构保证了你的新功能被完全封装在它自己的文件中，与核心系统保持低耦合，使得项目易于维护和扩展。