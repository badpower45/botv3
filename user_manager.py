# -*- coding: utf-8 -*-
"""
نظام إدارة العملاء للبوت
يتعامل مع تسجيل وتحديث بيانات المستخدمين
"""

import os
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any

class UserManager:
    """إدارة العملاء في قاعدة البيانات"""
    
    def __init__(self, db_path="instance/admin_bot.db"):
        self.db_path = db_path
        self.ensure_database_exists()
    
    def ensure_database_exists(self):
        """التأكد من وجود قاعدة البيانات وإنشاء الجداول إذا لزم الأمر"""
        if not os.path.exists(os.path.dirname(self.db_path)):
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def get_connection(self):
        """الحصول على اتصال بقاعدة البيانات"""
        return sqlite3.connect(self.db_path)
    
    def register_or_update_user(self, telegram_user) -> bool:
        """تسجيل أو تحديث المستخدم"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # البحث عن المستخدم أولاً
            cursor.execute("SELECT id, total_interactions FROM user WHERE telegram_id = ?", 
                         (telegram_user.id,))
            existing_user = cursor.fetchone()
            
            if existing_user:
                # تحديث المستخدم الموجود
                user_id, current_interactions = existing_user
                cursor.execute("""
                    UPDATE user SET 
                        first_name = ?,
                        last_name = ?,
                        username = ?,
                        last_interaction = ?,
                        total_interactions = ?
                    WHERE telegram_id = ?
                """, (
                    telegram_user.first_name or '',
                    telegram_user.last_name or '',
                    telegram_user.username or '',
                    datetime.utcnow().isoformat(),
                    current_interactions + 1,
                    telegram_user.id
                ))
                print(f"✅ تم تحديث المستخدم: {telegram_user.first_name} (المعرف: {telegram_user.id})")
            else:
                # إضافة مستخدم جديد
                cursor.execute("""
                    INSERT INTO user (
                        telegram_id, first_name, last_name, username,
                        is_active, first_interaction, last_interaction,
                        total_interactions, preferred_language, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    telegram_user.id,
                    telegram_user.first_name or '',
                    telegram_user.last_name or '',
                    telegram_user.username or '',
                    True,  # is_active
                    datetime.utcnow().isoformat(),  # first_interaction
                    datetime.utcnow().isoformat(),  # last_interaction
                    1,  # total_interactions
                    'ar',  # preferred_language
                    datetime.utcnow().isoformat()  # created_at
                ))
                print(f"🆕 تم تسجيل مستخدم جديد: {telegram_user.first_name} (المعرف: {telegram_user.id})")
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ خطأ في تسجيل/تحديث المستخدم: {e}")
            if 'conn' in locals():
                conn.close()
            return False
    
    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """الحصول على بيانات المستخدم بمعرف تيليجرام"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM user WHERE telegram_id = ?
            """, (telegram_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
            
        except Exception as e:
            print(f"❌ خطأ في جلب بيانات المستخدم: {e}")
            return None
    
    def update_user_interaction(self, telegram_id: int) -> bool:
        """تحديث آخر تفاعل للمستخدم"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE user SET 
                    last_interaction = ?,
                    total_interactions = total_interactions + 1
                WHERE telegram_id = ?
            """, (datetime.utcnow().isoformat(), telegram_id))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ خطأ في تحديث تفاعل المستخدم: {e}")
            return False
    
    def get_user_stats(self) -> Dict[str, int]:
        """إحصائيات المستخدمين"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # إجمالي المستخدمين
            cursor.execute("SELECT COUNT(*) FROM user")
            total_users = cursor.fetchone()[0]
            
            # المستخدمين النشطين
            cursor.execute("SELECT COUNT(*) FROM user WHERE is_active = 1")
            active_users = cursor.fetchone()[0]
            
            # المستخدمين الجدد اليوم
            today = datetime.utcnow().strftime('%Y-%m-%d')
            cursor.execute("SELECT COUNT(*) FROM user WHERE DATE(created_at) = ?", (today,))
            new_today = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total': total_users,
                'active': active_users,
                'new_today': new_today
            }
            
        except Exception as e:
            print(f"❌ خطأ في جلب إحصائيات المستخدمين: {e}")
            return {'total': 0, 'active': 0, 'new_today': 0}
    
    def is_user_active(self, telegram_id: int) -> bool:
        """التحقق من نشاط المستخدم"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT is_active FROM user WHERE telegram_id = ?", (telegram_id,))
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result else False
            
        except Exception as e:
            print(f"❌ خطأ في التحقق من نشاط المستخدم: {e}")
            return False

# إنشاء نسخة مشتركة من مدير المستخدمين
user_manager = UserManager()