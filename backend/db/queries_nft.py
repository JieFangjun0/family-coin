# backend/db/queries_nft.py

import json
import uuid
from backend.db.database import LEDGER_LOCK, get_db_connection
from backend.nft_logic import get_handler

def _validate_nft_for_trade(cursor, nft_id: str, expected_owner: str) -> (bool, str, dict):
    """
    (内部通用函数) 验证一个NFT是否可以被交易。
    返回: (是否可交易, 错误信息, NFT数据字典)
    """
    cursor.execute("SELECT nft_id, owner_key, nft_type, data, status FROM nfts WHERE nft_id = ?", (nft_id,))
    nft_row = cursor.fetchone()

    if not nft_row:
        return False, "NFT不存在", None
    
    nft = dict(nft_row)
    nft['data'] = json.loads(nft['data']) # 提前解析data

    if nft['status'] != 'ACTIVE':
        return False, "NFT不是活跃状态", nft
    
    if nft['owner_key'] != expected_owner:
        return False, "你不是该NFT的所有者", nft

    handler = get_handler(nft['nft_type'])
    if not handler:
        return False, f"未找到类型为 {nft['nft_type']} 的处理器，交易被拒绝", nft

    is_ok, reason = handler.is_tradable(nft)
    if not is_ok:
        return False, reason, nft
            
    return True, "验证通过", nft

def mint_nft(owner_key: str, nft_type: str, data: dict, conn=None) -> (bool, str, str):
    """(底层) 将一个新的 NFT 记录到数据库中。"""
    def run_logic(connection):
        try:
            cursor = connection.cursor()
            nft_id = str(uuid.uuid4())
            data_json = json.dumps(data, ensure_ascii=False)

            cursor.execute("SELECT 1 FROM users WHERE public_key = ?", (owner_key,))
            if not cursor.fetchone():
                return False, "NFT所有者不存在", None

            cursor.execute(
                "INSERT INTO nfts (nft_id, owner_key, nft_type, data, status) VALUES (?, ?, ?, ?, 'ACTIVE')",
                (nft_id, owner_key, nft_type, data_json)
            )
            return True, "NFT 铸造成功", nft_id
        except Exception as e:
            return False, f"NFT 铸造时数据库出错: {e}", None

    if conn:
        return run_logic(conn)
    else:
        with LEDGER_LOCK, get_db_connection() as new_conn:
            success, detail, nft_id = run_logic(new_conn)
            if success:
                new_conn.commit()
            else:
                new_conn.rollback()
            return success, detail, nft_id

def get_nft_by_id(nft_id: str) -> dict:
    """根据 ID 获取单个 NFT 的详细信息。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT nft_id, owner_key, nft_type, data, status, 
                   CAST(strftime('%s', created_at) AS REAL) as created_at
            FROM nfts 
            WHERE nft_id = ?
        """
        cursor.execute(query, (nft_id,))
        nft = cursor.fetchone()
        if not nft:
            return None
        nft_dict = dict(nft)
        nft_dict['data'] = json.loads(nft_dict['data'])
        return nft_dict

def get_nfts_by_owner(owner_key: str) -> list:
    """获取指定所有者的所有 NFT。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT nft_id, owner_key, nft_type, data, status, 
                   CAST(strftime('%s', created_at) AS REAL) as created_at
            FROM nfts 
            WHERE owner_key = ? AND status = 'ACTIVE' 
            ORDER BY created_at DESC
        """
        cursor.execute(query, (owner_key,))
        nfts = []
        for row in cursor.fetchall():
            nft_dict = dict(row)
            nft_dict['data'] = json.loads(nft_dict['data'])
            nfts.append(nft_dict)
        return nfts

def update_nft(nft_id: str, new_data: dict, new_status: str = None) -> (bool, str):
    """更新 NFT 的 data 或 status 字段。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            data_json = json.dumps(new_data, ensure_ascii=False)
            
            if new_status:
                cursor.execute(
                    "UPDATE nfts SET data = ?, status = ? WHERE nft_id = ?",
                    (data_json, new_status, nft_id)
                )
            else:
                cursor.execute("UPDATE nfts SET data = ? WHERE nft_id = ?", (data_json, nft_id))

            if cursor.rowcount == 0:
                return False, "未找到要更新的 NFT"
            
            conn.commit()
            return True, "NFT 更新成功"
        except Exception as e:
            conn.rollback()
            return False, f"更新 NFT 时数据库出错: {e}"

def _change_nft_owner(nft_id: str, new_owner_key: str, conn) -> (bool, str):
    """(内部函数) 转移NFT所有权"""
    cursor = conn.cursor()
    cursor.execute("UPDATE nfts SET owner_key = ? WHERE nft_id = ?", (new_owner_key, nft_id))
    if cursor.rowcount == 0:
        return False, f"转移NFT所有权失败: 未找到NFT {nft_id}"
    return True, "NFT所有权转移成功"