from slack_bolt import App
from app.database import get_db
from app.slack.services.user_sync import UserSyncService


def register_event_handlers(app: App, user_sync_service: UserSyncService):
    """註冊 Slack 事件處理程序"""
    
    @app.event("user_change")
    def handle_user_change(event, client):
        """處理用戶資料變更事件"""
        try:
            user_info = event["user"]
            slack_user_id = user_info["id"]
            
            # 獲取資料庫連接
            db = next(get_db())
            
            # 同步用戶資料
            user_sync_service.sync_single_user(db, client, slack_user_id)
            
            print(f"已同步用戶資料: {slack_user_id}")
        
        except Exception as e:
            print(f"處理用戶變更事件錯誤: {e}")
        finally:
            db.close()
    
    @app.event("team_join")
    def handle_team_join(event, client):
        """處理新用戶加入團隊事件"""
        try:
            user_info = event["user"]
            slack_user_id = user_info["id"]
            
            # 發送歡迎訊息
            client.chat_postMessage(
                channel=slack_user_id,
                text="🎉 歡迎加入我們的團隊！\n\n"
                     "我是 Punch Bot，協助您管理打卡和工時。\n"
                     "請聯絡管理員將您加入打卡系統。\n\n"
                     "如果您已經被加入系統，可以使用 `/punch help` 查看所有可用指令。"
            )
            
            print(f"已發送歡迎訊息給新用戶: {slack_user_id}")
        
        except Exception as e:
            print(f"處理新用戶加入事件錯誤: {e}")
    
    @app.event("app_home_opened")
    def handle_app_home_opened(event, client):
        """處理 App Home 頁面開啟事件"""
        try:
            user_id = event["user"]
            
            # 檢查用戶是否在系統中
            db = next(get_db())
            from app.models.user import User
            user = db.query(User).filter(User.slack_user_id == user_id).first()
            
            if user:
                # 用戶已在系統中，顯示個人化首頁
                _publish_user_home(client, user_id, user)
            else:
                # 用戶不在系統中，顯示引導頁面
                _publish_welcome_home(client, user_id)
        
        except Exception as e:
            print(f"處理 App Home 開啟事件錯誤: {e}")
        finally:
            db.close()
    
    @app.event("message")
    def handle_direct_message(event, client):
        """處理私訊事件（簡單的自動回覆）"""
        try:
            # 只處理直接傳給 Bot 的訊息
            if event.get("channel_type") != "im":
                return
            
            # 避免回應 Bot 自己的訊息
            if event.get("subtype") == "bot_message":
                return
            
            user_id = event["user"]
            text = event.get("text", "").lower()
            
            # 簡單的關鍵字回應
            if any(keyword in text for keyword in ["help", "幫助", "說明"]):
                client.chat_postMessage(
                    channel=user_id,
                    text="🤖 我是 Punch Bot！\n\n"
                         "我可以幫您:\n"
                         "• 打卡管理 (`/punch in`, `/punch out`)\n"
                         "• 工時統計 (`/punch today`, `/punch week`)\n"
                         "• 請假申請 (`/punch ooo`)\n\n"
                         "使用 `/punch help` 查看完整指令列表！"
                )
            elif any(keyword in text for keyword in ["status", "狀態"]):
                # 獲取用戶當前狀態
                from app.slack.services.punch_service import PunchService
                db = next(get_db())
                punch_service = PunchService(db)
                summary = punch_service.get_today_summary(user_id)
                
                client.chat_postMessage(
                    channel=user_id,
                    text=f"📊 您的當前狀態:\n\n{summary}"
                )
                db.close()
            elif any(keyword in text for keyword in ["hi", "hello", "你好", "嗨"]):
                client.chat_postMessage(
                    channel=user_id,
                    text="👋 您好！我是 Punch Bot，有什麼可以幫您的嗎？\n"
                         "輸入「幫助」查看我能做什麼！"
                )
        
        except Exception as e:
            print(f"處理直接訊息錯誤: {e}")


def _publish_user_home(client, user_id: str, user):
    """發布用戶個人化首頁"""
    try:
        from app.slack.services.punch_service import PunchService
        db = next(get_db())
        punch_service = PunchService(db)
        
        # 獲取今日摘要
        today_summary = punch_service.get_today_summary(user_id)
        
        home_view = {
            "type": "home",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*👋 歡迎回來，{user.internal_real_name}！*"
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*📊 今日狀態*"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"```{today_summary}```"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "🟢 上班打卡"
                            },
                            "style": "primary",
                            "action_id": "quick_punch_in"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "🔴 下班打卡"
                            },
                            "style": "danger",
                            "action_id": "quick_punch_out"
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*🚀 快速動作*"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "📅 今日記錄"
                            },
                            "action_id": "view_today"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "📊 本週統計"
                            },
                            "action_id": "view_week"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "🏖️ 請假紀錄"
                            },
                            "action_id": "view_holidays"
                        }
                    ]
                }
            ]
        }
        
        client.views_publish(
            user_id=user_id,
            view=home_view
        )
        
        db.close()
    
    except Exception as e:
        print(f"發布用戶首頁錯誤: {e}")


def _publish_welcome_home(client, user_id: str):
    """發布歡迎頁面給未註冊用戶"""
    try:
        home_view = {
            "type": "home",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*👋 歡迎使用 Punch Bot！*"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "看起來您還沒有被加入打卡系統。"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "請聯絡您的管理員，使用以下指令將您加入系統："
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"```/punch admin invite <@{user_id}> \"您的真實姓名\" \"您的部門\"```"
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*🤖 關於 Punch Bot*\n\nPunch Bot 是一個強大的打卡管理系統，可以幫助您："
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "• 📍 簡單的打卡操作\n• ⏰ 自動工時計算\n• 📊 詳細的工時統計\n• 🏖️ 便捷的請假管理\n• 🔔 智能提醒功能"
                    }
                }
            ]
        }
        
        client.views_publish(
            user_id=user_id,
            view=home_view
        )
    
    except Exception as e:
        print(f"發布歡迎頁面錯誤: {e}")


# 註冊 App Home 按鈕互動
def register_home_interactions(app: App):
    """註冊 App Home 頁面的互動處理"""
    
    @app.action("view_today")
    def handle_view_today(ack, body, client):
        """處理查看今日記錄按鈕"""
        ack()
        
        user_id = body["user"]["id"]
        
        try:
            from app.slack.services.punch_service import PunchService
            db = next(get_db())
            punch_service = PunchService(db)
            
            summary = punch_service.get_today_summary(user_id)
            
            client.chat_postMessage(
                channel=user_id,
                text=f"📅 **今日記錄**\n\n{summary}"
            )
            
            db.close()
        
        except Exception as e:
            client.chat_postMessage(
                channel=user_id,
                text=f"❌ 獲取今日記錄失敗: {str(e)}"
            )
    
    @app.action("view_week")
    def handle_view_week(ack, body, client):
        """處理查看本週統計按鈕"""
        ack()
        
        user_id = body["user"]["id"]
        
        try:
            from app.slack.services.punch_service import PunchService
            db = next(get_db())
            punch_service = PunchService(db)
            
            summary = punch_service.get_week_summary(user_id)
            
            client.chat_postMessage(
                channel=user_id,
                text=f"📊 **本週統計**\n\n{summary}"
            )
            
            db.close()
        
        except Exception as e:
            client.chat_postMessage(
                channel=user_id,
                text=f"❌ 獲取本週統計失敗: {str(e)}"
            )
    
    @app.action("view_holidays")
    def handle_view_holidays(ack, body, client):
        """處理查看請假記錄按鈕"""
        ack()
        
        user_id = body["user"]["id"]
        
        try:
            from app.slack.services.punch_service import PunchService
            db = next(get_db())
            punch_service = PunchService(db)
            
            summary = punch_service.get_leave_history(user_id)
            
            client.chat_postMessage(
                channel=user_id,
                text=f"🏖️ **請假記錄**\n\n{summary}"
            )
            
            db.close()
        
        except Exception as e:
            client.chat_postMessage(
                channel=user_id,
                text=f"❌ 獲取請假記錄失敗: {str(e)}"
            )