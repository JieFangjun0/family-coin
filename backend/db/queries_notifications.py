# backend/db/queries_notifications.py

import time
from typing import List, Optional
from backend.db.database import get_db_connection
from psycopg2.extras import DictCursor

def get_notifications_by_user(user_key: str, limit: int = 20) -> dict:
    """获取用户最新的通知列表和未读计数。"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            
            # 1. 获取未读计数
            cursor.execute(
                "SELECT COUNT(*) FROM notifications WHERE user_key = %s AND is_read = FALSE",
                (user_key,)
            )
            unread_count = cursor.fetchone()[0]
            
            # 2. 获取通知列表
            query = """
                SELECT 
                    notif_id, user_key, message, is_read, timestamp
                FROM notifications
                WHERE user_key = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """
            cursor.execute(query, (user_key, limit))
            
            notifications = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                row_dict['is_read'] = bool(row_dict['is_read'])
                notifications.append(row_dict)
                
            return {"notifications": notifications, "unread_count": unread_count}

def mark_notification_as_read(notif_id: str, user_key: str, conn=None) -> (bool, str):
    """将指定通知标记为已读。"""
    
    def run_logic(connection) -> (bool, str, bool):
        # 内部函数，返回 (success, detail, needs_commit)
        try:
            with connection.cursor() as cursor:
                # 仅更新未读的通知
                cursor.execute(
                    "UPDATE notifications SET is_read = TRUE WHERE notif_id = %s AND user_key = %s AND is_read = FALSE",
                    (notif_id, user_key)
                )
                if cursor.rowcount == 0:
                    # 如果没有行被更新，可能是已读或不存在，不视为错误
                    return False, "通知不存在或已读", False
                return True, "通知已标记为已读", True
        except Exception as e:
            print(f"Error in mark_notification_as_read (run_logic): {e}")
            return False, f"数据库错误: {e}", False

    if conn:
        # 已在事务中，不处理 commit/rollback
        success, detail, _ = run_logic(conn)
        return success, detail
    else:
        # 创建新事务
        with get_db_connection() as new_conn:
            try:
                success, detail, needs_commit = run_logic(new_conn)
                if needs_commit:
                    new_conn.commit()
                # 如果不需要提交 (例如 rowcount=0)，也不需要回滚
                return success, detail
            except Exception as e:
                # 捕获 run_logic 或 get_db_connection 的异常
                new_conn.rollback()
                print(f"Error in mark_notification_as_read (transaction): {e}")
                return False, f"数据库事务失败: {e}"