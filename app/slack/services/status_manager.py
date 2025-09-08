from typing import Optional, Dict, Any
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class StatusManager:
    """Slack 狀態管理服務"""
    
    def __init__(self):
        # 預定義的狀態配置
        self.status_configs = {
            "in": {
                "text": "工作中",
                "emoji": ":office:",
                "expiration": 0  # 不過期
            },
            "out": {
                "text": "",
                "emoji": "",
                "expiration": 0  # 清除狀態
            },
            "break": {
                "text": "休息中",
                "emoji": ":coffee:",
                "expiration": 0  # 不過期
            },
            "back": {
                "text": "工作中",
                "emoji": ":office:",
                "expiration": 0  # 不過期
            },
            "leave": {
                "text": "請假中",
                "emoji": ":palm_tree:",
                "expiration": 0  # 不過期
            }
        }
    
    def update_work_status(self, client: WebClient, user_id: str, action: str) -> bool:
        """更新用戶工作狀態"""
        try:
            if action not in self.status_configs:
                print(f"未知的狀態動作: {action}")
                return False
            
            config = self.status_configs[action]
            
            # 設置用戶狀態
            response = client.users_profile_set(
                user=user_id,
                profile={
                    "status_text": config["text"],
                    "status_emoji": config["emoji"],
                    "status_expiration": config["expiration"]
                }
            )
            
            if response["ok"]:
                print(f"已更新用戶 {user_id} 的狀態: {action}")
                return True
            else:
                print(f"更新用戶 {user_id} 狀態失敗: {response}")
                return False
                
        except SlackApiError as e:
            print(f"更新 Slack 狀態時發生 API 錯誤: {e}")
            return False
        except Exception as e:
            print(f"更新狀態時發生錯誤: {e}")
            return False
    
    def set_custom_status(self, client: WebClient, user_id: str, 
                         text: str, emoji: str = "", expiration: int = 0) -> bool:
        """設置自定義狀態"""
        try:
            response = client.users_profile_set(
                user=user_id,
                profile={
                    "status_text": text,
                    "status_emoji": emoji,
                    "status_expiration": expiration
                }
            )
            
            if response["ok"]:
                print(f"已設置用戶 {user_id} 的自定義狀態: {text}")
                return True
            else:
                print(f"設置自定義狀態失敗: {response}")
                return False
                
        except SlackApiError as e:
            print(f"設置自定義狀態時發生 API 錯誤: {e}")
            return False
        except Exception as e:
            print(f"設置自定義狀態時發生錯誤: {e}")
            return False
    
    def clear_status(self, client: WebClient, user_id: str) -> bool:
        """清除用戶狀態"""
        try:
            response = client.users_profile_set(
                user=user_id,
                profile={
                    "status_text": "",
                    "status_emoji": "",
                    "status_expiration": 0
                }
            )
            
            if response["ok"]:
                print(f"已清除用戶 {user_id} 的狀態")
                return True
            else:
                print(f"清除狀態失敗: {response}")
                return False
                
        except SlackApiError as e:
            print(f"清除狀態時發生 API 錯誤: {e}")
            return False
        except Exception as e:
            print(f"清除狀態時發生錯誤: {e}")
            return False
    
    def get_user_status(self, client: WebClient, user_id: str) -> Optional[Dict[str, Any]]:
        """獲取用戶當前狀態"""
        try:
            response = client.users_profile_get(user=user_id)
            
            if response["ok"]:
                profile = response["profile"]
                return {
                    "status_text": profile.get("status_text", ""),
                    "status_emoji": profile.get("status_emoji", ""),
                    "status_expiration": profile.get("status_expiration", 0)
                }
            else:
                print(f"獲取用戶狀態失敗: {response}")
                return None
                
        except SlackApiError as e:
            print(f"獲取用戶狀態時發生 API 錯誤: {e}")
            return None
        except Exception as e:
            print(f"獲取用戶狀態時發生錯誤: {e}")
            return None
    
    def update_presence(self, client: WebClient, user_id: str, presence: str) -> bool:
        """更新用戶在線狀態"""
        try:
            # 注意: 只能設置自己的在線狀態
            response = client.users_setPresence(presence=presence)
            
            if response["ok"]:
                print(f"已更新在線狀態: {presence}")
                return True
            else:
                print(f"更新在線狀態失敗: {response}")
                return False
                
        except SlackApiError as e:
            print(f"更新在線狀態時發生 API 錯誤: {e}")
            return False
        except Exception as e:
            print(f"更新在線狀態時發生錯誤: {e}")
            return False
    
    def get_presence(self, client: WebClient, user_id: str) -> Optional[Dict[str, Any]]:
        """獲取用戶在線狀態"""
        try:
            response = client.users_getPresence(user=user_id)
            
            if response["ok"]:
                return {
                    "presence": response.get("presence"),
                    "online": response.get("online"),
                    "auto_away": response.get("auto_away"),
                    "manual_away": response.get("manual_away"),
                    "connection_count": response.get("connection_count", 0),
                    "last_activity": response.get("last_activity")
                }
            else:
                print(f"獲取在線狀態失敗: {response}")
                return None
                
        except SlackApiError as e:
            print(f"獲取在線狀態時發生 API 錯誤: {e}")
            return None
        except Exception as e:
            print(f"獲取在線狀態時發生錯誤: {e}")
            return None
    
    def set_dnd_status(self, client: WebClient, minutes: int) -> bool:
        """設置勿擾狀態"""
        try:
            response = client.dnd_setSnooze(num_minutes=minutes)
            
            if response["ok"]:
                print(f"已設置勿擾狀態 {minutes} 分鐘")
                return True
            else:
                print(f"設置勿擾狀態失敗: {response}")
                return False
                
        except SlackApiError as e:
            print(f"設置勿擾狀態時發生 API 錯誤: {e}")
            return False
        except Exception as e:
            print(f"設置勿擾狀態時發生錯誤: {e}")
            return False
    
    def end_dnd_status(self, client: WebClient) -> bool:
        """結束勿擾狀態"""
        try:
            response = client.dnd_endSnooze()
            
            if response["ok"]:
                print("已結束勿擾狀態")
                return True
            else:
                print(f"結束勿擾狀態失敗: {response}")
                return False
                
        except SlackApiError as e:
            print(f"結束勿擾狀態時發生 API 錯誤: {e}")
            return False
        except Exception as e:
            print(f"結束勿擾狀態時發生錯誤: {e}")
            return False
    
    def get_dnd_status(self, client: WebClient, user_id: str = None) -> Optional[Dict[str, Any]]:
        """獲取勿擾狀態"""
        try:
            if user_id:
                response = client.dnd_info(user=user_id)
            else:
                response = client.dnd_info()
            
            if response["ok"]:
                return {
                    "dnd_enabled": response.get("dnd_enabled"),
                    "next_dnd_start_ts": response.get("next_dnd_start_ts"),
                    "next_dnd_end_ts": response.get("next_dnd_end_ts"),
                    "snooze_enabled": response.get("snooze_enabled"),
                    "snooze_endtime": response.get("snooze_endtime"),
                    "snooze_remaining": response.get("snooze_remaining")
                }
            else:
                print(f"獲取勿擾狀態失敗: {response}")
                return None
                
        except SlackApiError as e:
            print(f"獲取勿擾狀態時發生 API 錯誤: {e}")
            return None
        except Exception as e:
            print(f"獲取勿擾狀態時發生錯誤: {e}")
            return None
    
    def batch_update_status(self, client: WebClient, user_status_map: Dict[str, str]) -> Dict[str, bool]:
        """批量更新多個用戶的狀態"""
        results = {}
        
        for user_id, action in user_status_map.items():
            success = self.update_work_status(client, user_id, action)
            results[user_id] = success
        
        return results
    
    def schedule_status_change(self, client: WebClient, user_id: str, 
                             action: str, delay_minutes: int) -> bool:
        """計劃狀態變更（透過設置過期時間）"""
        try:
            if action not in self.status_configs:
                print(f"未知的狀態動作: {action}")
                return False
            
            config = self.status_configs[action].copy()
            
            # 計算過期時間（Unix 時間戳）
            import time
            expiration_time = int(time.time()) + (delay_minutes * 60)
            config["expiration"] = expiration_time
            
            response = client.users_profile_set(
                user=user_id,
                profile={
                    "status_text": config["text"],
                    "status_emoji": config["emoji"],
                    "status_expiration": config["expiration"]
                }
            )
            
            if response["ok"]:
                print(f"已計劃用戶 {user_id} 在 {delay_minutes} 分鐘後變更狀態: {action}")
                return True
            else:
                print(f"計劃狀態變更失敗: {response}")
                return False
                
        except Exception as e:
            print(f"計劃狀態變更時發生錯誤: {e}")
            return False
    
    def get_status_config(self, action: str) -> Optional[Dict[str, Any]]:
        """獲取狀態配置"""
        return self.status_configs.get(action)
    
    def add_custom_status_config(self, action: str, text: str, emoji: str = "", expiration: int = 0):
        """添加自定義狀態配置"""
        self.status_configs[action] = {
            "text": text,
            "emoji": emoji,
            "expiration": expiration
        }
        print(f"已添加自定義狀態配置: {action}")
    
    def remove_status_config(self, action: str) -> bool:
        """移除狀態配置"""
        if action in self.status_configs:
            del self.status_configs[action]
            print(f"已移除狀態配置: {action}")
            return True
        else:
            print(f"狀態配置不存在: {action}")
            return False
    
    def list_status_configs(self) -> Dict[str, Dict[str, Any]]:
        """列出所有狀態配置"""
        return self.status_configs.copy()
    
    def is_status_enabled(self, client: WebClient, user_id: str) -> bool:
        """檢查用戶是否啟用狀態功能"""
        try:
            # 嘗試獲取用戶狀態來檢查權限
            response = client.users_profile_get(user=user_id)
            return response["ok"]
        except Exception as e:
            print(f"檢查狀態功能時發生錯誤: {e}")
            return False