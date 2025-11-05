# backend/db/queries_notifications.py

import time
from typing import List, Optional
from backend.db.database import LEDGER_LOCK, get_db_connection

def get_notifications_by_user(user_key: str, limit: int = 20) -> dict:
    """获取用户最新的通知列表和未读计数。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. 获取未读计数
        cursor.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_key = ? AND is_read = 0",
            (user_key,)
        )
        unread_count = cursor.fetchone()[0]
        
        # 2. 获取通知列表
        query = """
            SELECT 
                notif_id, user_key, message, is_read, timestamp
            FROM notifications
            WHERE user_key = ?
            ORDER BY timestamp DESC
            LIMIT ?
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
    def run_logic(connection):
        cursor = connection.cursor()
        # 仅更新未读的通知
        cursor.execute(
            "UPDATE notifications SET is_read = 1 WHERE notif_id = ? AND user_key = ? AND is_read = 0",
            (notif_id, user_key)
        )
        if cursor.rowcount == 0:
            # 如果没有行被更新，可能是已读或不存在，不视为错误
            return False, "通知不存在或已读" 
        return True, "通知已标记为已读"
        
    if conn:
        return run_logic(conn)
    else:
        with LEDGER_LOCK, get_db_connection() as new_conn:
            success, detail = run_logic(new_conn)
            if success: new_conn.commit()
            else: new_conn.rollback()
            return success, detail