import re
from datetime import datetime, date
from slack_bolt import App
from slack_bolt.request import BoltRequest
from slack_bolt.response import BoltResponse

from app.database import get_db
from app.slack.services.punch_service import PunchService
from app.slack.services.status_manager import StatusManager
from app.utils.datetime_utils import parse_date, format_date


def register_punch_handlers(app: App):
    """註冊打卡指令處理程序"""
    # 註冊主要指令處理
    _register_main_handlers(app)
    # 註冊互動式處理
    register_interactive_handlers(app)


def _register_main_handlers(app: App):
    """註冊主要指令處理程序"""
    
    @app.command("/punch")
    def handle_punch_command(ack, respond, command, client):
        """處理 /punch 指令"""
        ack()
        
        user_id = command["user_id"]
        username = command["user_name"]
        text = command["text"].strip()
        
        try:
            # 獲取資料庫連接
            db = next(get_db())
            punch_service = PunchService(db)
            status_manager = StatusManager()
            
            # 解析指令
            if not text or text == "help":
                respond(_get_help_message())
                return
            
            args = text.split()
            action = args[0].lower()
            
            if action == "in":
                # 上班打卡
                note = " ".join(args[1:]) if len(args) > 1 else None
                success, message = punch_service.punch_in(user_id, username, note)
                
                if success:
                    # 更新 Slack 狀態
                    status_manager.update_work_status(client, user_id, "in")
                
                respond(message)
            
            elif action == "out":
                # 下班打卡
                note = " ".join(args[1:]) if len(args) > 1 else None
                success, message = punch_service.punch_out(user_id, note)
                
                if success:
                    # 更新 Slack 狀態
                    status_manager.update_work_status(client, user_id, "out")
                
                respond(message)
            
            elif action == "break":
                # 開始休息
                note = " ".join(args[1:]) if len(args) > 1 else None
                success, message = punch_service.punch_break(user_id, note)
                
                if success:
                    # 更新 Slack 狀態
                    status_manager.update_work_status(client, user_id, "break")
                
                respond(message)
            
            elif action == "back":
                # 結束休息
                note = " ".join(args[1:]) if len(args) > 1 else None
                success, message = punch_service.punch_back(user_id, note)
                
                if success:
                    # 更新 Slack 狀態
                    status_manager.update_work_status(client, user_id, "back")
                
                respond(message)
            
            elif action == "today":
                # 查看今日記錄
                message = punch_service.get_today_summary(user_id)
                respond(message)
            
            elif action == "week":
                # 查看本週統計
                message = punch_service.get_week_summary(user_id)
                respond(message)
            
            elif action == "ooo":
                # 請假處理
                _handle_leave_request(punch_service, args[1:], user_id, respond)
            
            elif action == "cancel":
                # 取消請假
                _handle_cancel_leave(punch_service, args[1:], user_id, respond)
            
            elif action == "holidays":
                # 查看請假記錄
                message = punch_service.get_leave_history(user_id)
                respond(message)
            
            else:
                respond(f"❌ 不認識的指令: `{action}`\n\n" + _get_help_message())
        
        except Exception as e:
            respond(f"❌ 執行指令時發生錯誤: {str(e)}")
        finally:
            db.close()


def _handle_leave_request(punch_service: PunchService, args, user_id: str, respond):
    """處理請假請求"""
    if not args:
        # 今日請假
        today = punch_service.get_today(user_id)
        success, message = punch_service.request_leave(user_id, today)
        respond(message)
        return
    
    if len(args) == 1:
        # 指定日期請假
        target_date = parse_date(args[0])
        if not target_date:
            respond("❌ 日期格式錯誤！請使用 YYYY-MM-DD 格式")
            return
        
        success, message = punch_service.request_leave(user_id, target_date)
        respond(message)
        return
    
    if len(args) >= 3 and args[1].lower() == "to":
        # 連續請假
        start_date = parse_date(args[0])
        end_date = parse_date(args[2])
        
        if not start_date or not end_date:
            respond("❌ 日期格式錯誤！請使用 YYYY-MM-DD 格式")
            return
        
        reason = " ".join(args[3:]) if len(args) > 3 else None
        success, message = punch_service.request_leave(user_id, start_date, end_date, reason)
        respond(message)
        return
    
    respond("❌ 請假指令格式錯誤！\n"
            "用法:\n"
            "• `/punch ooo` - 今日請假\n"
            "• `/punch ooo 2024-12-25` - 指定日期請假\n" 
            "• `/punch ooo 2024-12-24 to 2024-12-26` - 連續請假")


def _handle_cancel_leave(punch_service: PunchService, args, user_id: str, respond):
    """處理取消請假"""
    if not args:
        respond("❌ 請指定要取消請假的日期！\n用法: `/punch cancel 2024-12-25`")
        return
    
    target_date = parse_date(args[0])
    if not target_date:
        respond("❌ 日期格式錯誤！請使用 YYYY-MM-DD 格式")
        return
    
    success, message = punch_service.cancel_leave(user_id, target_date)
    respond(message)


def _get_help_message() -> str:
    """獲取幫助訊息"""
    return """📝 **Punch Bot 使用說明**

**基本打卡:**
• `/punch in` - 上班打卡
• `/punch out` - 下班打卡  
• `/punch break` - 開始休息
• `/punch back` - 結束休息

**查詢統計:**
• `/punch today` - 查看今日記錄
• `/punch week` - 查看本週統計

**請假管理:**
• `/punch ooo` - 今日請假
• `/punch ooo 2024-12-25` - 指定日期請假
• `/punch ooo 2024-12-24 to 2024-12-26` - 連續請假
• `/punch cancel 2024-12-25` - 取消請假
• `/punch holidays` - 查看請假記錄

**小提示:**
• 可以在打卡時加上備註，例如: `/punch in 今天要加油！`
• 系統會自動提醒您打卡和工時管理
• 所有時間都會根據您的時區自動調整

需要更多幫助嗎？請聯絡管理員 👨‍💼"""


# 新增 Slack 互動處理
def register_interactive_handlers(app: App):
    """註冊互動式處理程序"""
    
    @app.action("quick_punch_in")
    def handle_quick_punch_in(ack, body, client):
        """快速上班打卡"""
        ack()
        user_id = body["user"]["id"]
        username = body["user"]["username"]
        
        try:
            db = next(get_db())
            punch_service = PunchService(db)
            status_manager = StatusManager()
            
            success, message = punch_service.punch_in(user_id, username)
            
            if success:
                status_manager.update_work_status(client, user_id, "in")
            
            # 更新原訊息
            client.chat_update(
                channel=body["channel"]["id"],
                ts=body["message"]["ts"],
                text=message,
                blocks=[]
            )
        
        except Exception as e:
            client.chat_postMessage(
                channel=user_id,
                text=f"❌ 快速打卡失敗: {str(e)}"
            )
        finally:
            db.close()
    
    @app.action("quick_punch_out")
    def handle_quick_punch_out(ack, body, client):
        """快速下班打卡"""
        ack()
        user_id = body["user"]["id"]
        
        try:
            db = next(get_db())
            punch_service = PunchService(db)
            status_manager = StatusManager()
            
            success, message = punch_service.punch_out(user_id)
            
            if success:
                status_manager.update_work_status(client, user_id, "out")
            
            # 更新原訊息
            client.chat_update(
                channel=body["channel"]["id"],
                ts=body["message"]["ts"],
                text=message,
                blocks=[]
            )
        
        except Exception as e:
            client.chat_postMessage(
                channel=user_id,
                text=f"❌ 快速打卡失敗: {str(e)}"
            )
        finally:
            db.close()


def create_quick_punch_blocks():
    """創建快速打卡按鈕"""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "⚡ 快速打卡"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "🟢 上班"
                    },
                    "style": "primary",
                    "action_id": "quick_punch_in"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "🔴 下班"
                    },
                    "style": "danger",
                    "action_id": "quick_punch_out"
                }
            ]
        }
    ]