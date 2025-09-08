from datetime import datetime
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from slack_sdk import WebClient

from app.models.user import User


class UserSyncService:
    """Slack 用戶同步服務"""
    
    def __init__(self):
        pass
    
    def sync_single_user(self, db: Session, client: WebClient, slack_user_id: str) -> bool:
        """同步單一用戶的 Slack 資料"""
        try:
            # 獲取 Slack 用戶資訊
            slack_user_info = client.users_info(user=slack_user_id)
            slack_user = slack_user_info["user"]
            
            # 查找現有用戶
            user = db.query(User).filter(User.slack_user_id == slack_user_id).first()
            
            if not user:
                print(f"用戶 {slack_user_id} 不在系統中，跳過同步")
                return False
            
            # 更新 Slack 資料
            user.slack_username = slack_user.get("name")
            user.slack_display_name = slack_user.get("display_name")
            user.slack_real_name = slack_user.get("real_name")
            user.slack_email = slack_user.get("profile", {}).get("email")
            user.slack_avatar_url = slack_user.get("profile", {}).get("image_192")
            user.slack_data_updated_at = datetime.utcnow()
            
            db.commit()
            print(f"已同步用戶 {slack_user_id} 的 Slack 資料")
            return True
            
        except Exception as e:
            print(f"同步用戶 {slack_user_id} 失敗: {e}")
            db.rollback()
            return False
    
    def sync_all_users(self, db: Session, client: WebClient) -> Dict[str, int]:
        """同步所有系統用戶的 Slack 資料"""
        result = {"success": 0, "failed": 0, "not_found": 0}
        
        # 獲取所有活躍用戶
        users = db.query(User).filter(User.is_active == True).all()
        
        for user in users:
            try:
                success = self.sync_single_user(db, client, user.slack_user_id)
                if success:
                    result["success"] += 1
                else:
                    result["failed"] += 1
            except Exception as e:
                if "user_not_found" in str(e):
                    result["not_found"] += 1
                    # 標記用戶為非活躍（可能已離開團隊）
                    user.is_active = False
                    db.commit()
                    print(f"用戶 {user.slack_user_id} 可能已離開團隊，已標記為非活躍")
                else:
                    result["failed"] += 1
                    print(f"同步用戶 {user.slack_user_id} 時發生錯誤: {e}")
        
        return result
    
    def sync_team_members(self, db: Session, client: WebClient) -> Dict[str, int]:
        """同步團隊所有成員（發現新用戶但不自動加入系統）"""
        result = {"existing": 0, "new_found": 0, "updated": 0}
        
        try:
            # 獲取團隊所有成員
            team_members = []
            cursor = None
            
            while True:
                response = client.users_list(cursor=cursor, limit=200)
                members = response["members"]
                
                # 過濾掉 Bot 和已刪除的用戶
                active_members = [
                    member for member in members
                    if not member.get("is_bot", False) 
                    and not member.get("deleted", False)
                    and member.get("id") != "USLACKBOT"
                ]
                
                team_members.extend(active_members)
                
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
            
            print(f"團隊共有 {len(team_members)} 位活躍成員")
            
            # 獲取系統中的所有用戶
            system_users = {user.slack_user_id: user for user in db.query(User).all()}
            
            # 處理每個團隊成員
            for member in team_members:
                slack_user_id = member["id"]
                
                if slack_user_id in system_users:
                    # 用戶已在系統中，更新資料
                    user = system_users[slack_user_id]
                    self._update_user_from_slack_data(user, member)
                    result["existing"] += 1
                    result["updated"] += 1
                else:
                    # 發現新用戶
                    result["new_found"] += 1
                    print(f"發現新團隊成員: {member.get('real_name')} ({member.get('name')})")
            
            db.commit()
            
        except Exception as e:
            print(f"同步團隊成員時發生錯誤: {e}")
            db.rollback()
        
        return result
    
    def _update_user_from_slack_data(self, user: User, slack_data: dict):
        """從 Slack 資料更新用戶資訊"""
        user.slack_username = slack_data.get("name")
        user.slack_display_name = slack_data.get("display_name")
        user.slack_real_name = slack_data.get("real_name")
        user.slack_email = slack_data.get("profile", {}).get("email")
        user.slack_avatar_url = slack_data.get("profile", {}).get("image_192")
        user.slack_data_updated_at = datetime.utcnow()
    
    def get_slack_user_info(self, client: WebClient, slack_user_id: str) -> Optional[dict]:
        """獲取 Slack 用戶資訊"""
        try:
            response = client.users_info(user=slack_user_id)
            return response["user"]
        except Exception as e:
            print(f"獲取 Slack 用戶資訊失敗: {e}")
            return None
    
    def validate_user_exists(self, client: WebClient, slack_user_id: str) -> bool:
        """驗證 Slack 用戶是否存在"""
        try:
            response = client.users_info(user=slack_user_id)
            user = response["user"]
            
            # 檢查用戶是否有效（非 Bot、未被刪除）
            if user.get("is_bot", False) or user.get("deleted", False):
                return False
            
            return True
            
        except Exception as e:
            print(f"驗證用戶存在性失敗: {e}")
            return False
    
    def get_user_profile_info(self, client: WebClient, slack_user_id: str) -> Dict[str, str]:
        """獲取用戶詳細資料"""
        try:
            response = client.users_profile_get(user=slack_user_id)
            profile = response["profile"]
            
            return {
                "display_name": profile.get("display_name", ""),
                "real_name": profile.get("real_name", ""),
                "email": profile.get("email", ""),
                "phone": profile.get("phone", ""),
                "title": profile.get("title", ""),
                "avatar_url": profile.get("image_192", ""),
                "status_text": profile.get("status_text", ""),
                "status_emoji": profile.get("status_emoji", "")
            }
            
        except Exception as e:
            print(f"獲取用戶資料失敗: {e}")
            return {}
    
    def get_team_info(self, client: WebClient) -> Optional[dict]:
        """獲取團隊資訊"""
        try:
            response = client.team_info()
            return response["team"]
        except Exception as e:
            print(f"獲取團隊資訊失敗: {e}")
            return None
    
    def find_users_by_email(self, client: WebClient, email: str) -> List[dict]:
        """根據 email 查找用戶"""
        try:
            response = client.users_lookupByEmail(email=email)
            return [response["user"]] if response.get("user") else []
        except Exception as e:
            print(f"根據 email 查找用戶失敗: {e}")
            return []
    
    def batch_sync_users(self, db: Session, client: WebClient, 
                        slack_user_ids: List[str]) -> Dict[str, List[str]]:
        """批量同步指定用戶"""
        result = {
            "success": [],
            "failed": [],
            "not_found": []
        }
        
        for slack_user_id in slack_user_ids:
            try:
                success = self.sync_single_user(db, client, slack_user_id)
                if success:
                    result["success"].append(slack_user_id)
                else:
                    result["failed"].append(slack_user_id)
            except Exception as e:
                if "user_not_found" in str(e):
                    result["not_found"].append(slack_user_id)
                else:
                    result["failed"].append(slack_user_id)
        
        return result
    
    def sync_user_status(self, client: WebClient, slack_user_id: str) -> Optional[dict]:
        """同步用戶當前狀態"""
        try:
            response = client.users_getPresence(user=slack_user_id)
            return {
                "presence": response.get("presence"),  # active, away
                "online": response.get("online"),
                "auto_away": response.get("auto_away"),
                "manual_away": response.get("manual_away"),
                "connection_count": response.get("connection_count", 0),
                "last_activity": response.get("last_activity")
            }
        except Exception as e:
            print(f"獲取用戶狀態失敗: {e}")
            return None
    
    def create_user_from_slack_data(self, db: Session, slack_data: dict, 
                                  internal_name: str, department: str = None) -> User:
        """從 Slack 資料創建新用戶"""
        try:
            user = User(
                slack_user_id=slack_data["id"],
                slack_username=slack_data.get("name"),
                slack_display_name=slack_data.get("display_name"),
                slack_real_name=slack_data.get("real_name"),
                slack_email=slack_data.get("profile", {}).get("email"),
                slack_avatar_url=slack_data.get("profile", {}).get("image_192"),
                internal_real_name=internal_name,
                department=department,
                slack_data_updated_at=datetime.utcnow()
            )
            
            db.add(user)
            db.commit()
            db.refresh(user)
            
            print(f"已創建新用戶: {internal_name} ({slack_data['id']})")
            return user
            
        except Exception as e:
            print(f"創建用戶失敗: {e}")
            db.rollback()
            raise