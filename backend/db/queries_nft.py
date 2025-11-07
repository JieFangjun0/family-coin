# backend/db/queries_nft.py

import json
import uuid
import psycopg2.errors
from backend.db.database import get_db_connection
from psycopg2.extras import DictCursor



def mint_nft(owner_key: str, nft_type: str, data: dict, conn=None) -> (bool, str, str):
    """(底层) 将一个新的 NFT 记录到数据库中。"""
    def run_logic(connection):
        try:
            with connection.cursor(cursor_factory=DictCursor) as cursor:
                nft_id = str(uuid.uuid4())
                data_json = json.dumps(data, ensure_ascii=False)

                cursor.execute("SELECT 1 FROM users WHERE public_key = %s", (owner_key,))
                if not cursor.fetchone():
                    return False, "NFT所有者不存在", None

                cursor.execute(
                    "INSERT INTO nfts (nft_id, owner_key, nft_type, data, status) VALUES (%s, %s, %s, %s, 'ACTIVE')",
                    (nft_id, owner_key, nft_type, data_json)
                )
            return True, "NFT 铸造成功", nft_id
        except Exception as e:
            # 捕捉外键约束等错误
            return False, f"NFT 铸造时数据库出错: {e}", None

    if conn:
        # 已在事务中
        return run_logic(conn)
    else:
        # 创建新事务
        with get_db_connection() as new_conn:
            success, detail, nft_id = run_logic(new_conn)
            if success:
                new_conn.commit()
            else:
                new_conn.rollback()
            return success, detail, nft_id

def get_nft_by_id(nft_id: str) -> dict:
    """根据 ID 获取单个 NFT 的详细信息。"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            query = """
                SELECT nft_id, owner_key, nft_type, data, status, 
                       EXTRACT(EPOCH FROM created_at) as created_at
                FROM nfts 
                WHERE nft_id = %s
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
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            query = """
                SELECT nft_id, owner_key, nft_type, data, status, 
                       EXTRACT(EPOCH FROM created_at) as created_at
                FROM nfts 
                WHERE owner_key = %s AND status = 'ACTIVE' 
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
    with get_db_connection() as conn:
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                data_json = json.dumps(new_data, ensure_ascii=False)
                
                if new_status:
                    cursor.execute(
                        "UPDATE nfts SET data = %s, status = %s WHERE nft_id = %s",
                        (data_json, new_status, nft_id)
                    )
                else:
                    cursor.execute("UPDATE nfts SET data = %s WHERE nft_id = %s", (data_json, nft_id))

                if cursor.rowcount == 0:
                    conn.rollback() # 确保回滚
                    return False, "未找到要更新的 NFT"
            
            conn.commit()
            return True, "NFT 更新成功"
        except Exception as e:
            conn.rollback()
            return False, f"更新 NFT 时数据库出错: {e}"

