"""
Notification service layer for sending various types of notifications.
"""

import logging
from datetime import datetime, date, timedelta, time
from typing import List, Dict, Optional, Any
from enum import Enum
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.attendance import AttendanceRecord
from app.services.attendance_service import AttendanceService
from app.config import settings

logger = logging.getLogger(__name__)

class NotificationType(str, Enum):
    """通知類型枚舉"""
    DAILY_REMINDER = "daily_reminder"
    WORK_HOUR_REMINDER = "work_hour_reminder"
    FORGOT_PUNCH_REMINDER = "forgot_punch_reminder"
    AUTO_PUNCH_OUT = "auto_punch_out"
    WEEKLY_REPORT = "weekly_report"
    OVERTIME_ALERT = "overtime_alert"
    SYSTEM_ALERT = "system_alert"

class NotificationChannel(str, Enum):
    """通知渠道枚舉"""
    SLACK_DM = "slack_dm"
    SLACK_CHANNEL = "slack_channel"
    EMAIL = "email"
    WEBHOOK = "webhook"

class NotificationService:
    """通知服務業務邏輯"""
    
    def __init__(self, db: Session):
        self.db = db
        self.attendance_service = AttendanceService(db)
    
    async def send_daily_reminder(self, user_id: int = None) -> Dict[str, Any]:
        """
        發送每日打卡提醒。
        
        Args:
            user_id: 特定用戶 ID，None 表示發送給所有用戶
        
        Returns:
            發送結果統計
        """
        try:
            if not settings.ENABLE_DAILY_REMINDER:
                return {"success": False, "message": "Daily reminder is disabled"}
            
            # 取得目標用戶
            users_query = self.db.query(User).filter(User.is_active == True)
            if user_id:
                users_query = users_query.filter(User.id == user_id)
            
            users = users_query.all()
            
            sent_count = 0
            failed_count = 0
            errors = []
            
            for user in users:
                try:
                    # 檢查用戶今天是否已經打卡
                    today_records = self.attendance_service.get_user_daily_records(
                        user.id, date.today()
                    )
                    
                    if not today_records:
                        # 發送提醒訊息
                        message = self._build_daily_reminder_message(user)
                        await self._send_notification(
                            user, 
                            NotificationType.DAILY_REMINDER,
                            NotificationChannel.SLACK_DM,
                            message
                        )
                        sent_count += 1
                    
                except Exception as e:
                    failed_count += 1
                    errors.append({
                        "user_id": user.id,
                        "user_name": user.internal_real_name,
                        "error": str(e)
                    })
                    logger.error(f"Failed to send daily reminder to user {user.id}: {str(e)}")
            
            return {
                "success": True,
                "notification_type": NotificationType.DAILY_REMINDER,
                "sent_count": sent_count,
                "failed_count": failed_count,
                "total_users": len(users),
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Failed to send daily reminders: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to send daily reminders: {str(e)}"
            }
    
    async def send_work_hour_reminder(self, user_id: int) -> Dict[str, Any]:
        """
        發送工作時數提醒（接近標準工時時提醒）。
        
        Args:
            user_id: 用戶 ID
        
        Returns:
            發送結果
        """
        try:
            if not settings.ENABLE_WORK_HOUR_REMINDER:
                return {"success": False, "message": "Work hour reminder is disabled"}
            
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}
            
            # 取得今日工作時數
            today = date.today()
            today_records = self.attendance_service.get_user_daily_records(user_id, today)
            
            if not today_records:
                return {"success": False, "message": "No work records today"}
            
            work_minutes, _ = self.attendance_service._calculate_work_time_from_records(today_records)
            work_hours = work_minutes / 60
            
            # 檢查是否接近或超過標準工時
            standard_hours = user.standard_hours
            
            if work_hours >= standard_hours - 0.5:  # 接近標準工時時提醒
                message = self._build_work_hour_reminder_message(user, work_hours, standard_hours)
                
                await self._send_notification(
                    user,
                    NotificationType.WORK_HOUR_REMINDER,
                    NotificationChannel.SLACK_DM,
                    message
                )
                
                return {
                    "success": True,
                    "notification_type": NotificationType.WORK_HOUR_REMINDER,
                    "user_id": user_id,
                    "current_hours": round(work_hours, 2),
                    "standard_hours": standard_hours
                }
            
            return {
                "success": False,
                "message": "Not yet time for work hour reminder",
                "current_hours": round(work_hours, 2),
                "standard_hours": standard_hours
            }
            
        except Exception as e:
            logger.error(f"Failed to send work hour reminder: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to send work hour reminder: {str(e)}"
            }
    
    async def send_forgot_punch_reminder(self, user_id: int = None) -> Dict[str, Any]:
        """
        發送忘記打卡提醒。
        
        Args:
            user_id: 特定用戶 ID，None 表示檢查所有用戶
        
        Returns:
            發送結果統計
        """
        try:
            if not settings.ENABLE_FORGOT_PUNCH_REMINDER:
                return {"success": False, "message": "Forgot punch reminder is disabled"}
            
            # 取得目標用戶
            users_query = self.db.query(User).filter(User.is_active == True)
            if user_id:
                users_query = users_query.filter(User.id == user_id)
            
            users = users_query.all()
            
            sent_count = 0
            failed_count = 0
            errors = []
            
            for user in users:
                try:
                    # 檢查用戶今天的打卡狀況
                    today_records = self.attendance_service.get_user_daily_records(
                        user.id, date.today()
                    )
                    
                    reminder_needed = False
                    reminder_reason = ""
                    
                    if not today_records:
                        reminder_needed = True
                        reminder_reason = "No punch records today"
                    else:
                        # 檢查是否有未完成的打卡序列
                        last_record = today_records[-1]
                        current_time = datetime.now().time()
                        
                        # 如果最後一個動作是 'in' 或 'back'，且已經超過下班時間
                        if (last_record.action in ['in', 'back'] and 
                            current_time > time(settings.FORGOT_PUNCH_REMINDER_HOUR, 
                                               settings.FORGOT_PUNCH_REMINDER_MINUTE)):
                            reminder_needed = True
                            reminder_reason = f"Last action was '{last_record.action}', may have forgotten to punch out"
                    
                    if reminder_needed:
                        message = self._build_forgot_punch_reminder_message(user, reminder_reason)
                        await self._send_notification(
                            user,
                            NotificationType.FORGOT_PUNCH_REMINDER,
                            NotificationChannel.SLACK_DM,
                            message
                        )
                        sent_count += 1
                
                except Exception as e:
                    failed_count += 1
                    errors.append({
                        "user_id": user.id,
                        "user_name": user.internal_real_name,
                        "error": str(e)
                    })
                    logger.error(f"Failed to send forgot punch reminder to user {user.id}: {str(e)}")
            
            return {
                "success": True,
                "notification_type": NotificationType.FORGOT_PUNCH_REMINDER,
                "sent_count": sent_count,
                "failed_count": failed_count,
                "total_users": len(users),
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Failed to send forgot punch reminders: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to send forgot punch reminders: {str(e)}"
            }
    
    async def send_auto_punch_notification(self, user_id: int, record: AttendanceRecord) -> Dict[str, Any]:
        """
        發送自動打卡通知。
        
        Args:
            user_id: 用戶 ID
            record: 自動打卡記錄
        
        Returns:
            發送結果
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}
            
            message = self._build_auto_punch_notification_message(user, record)
            
            await self._send_notification(
                user,
                NotificationType.AUTO_PUNCH_OUT,
                NotificationChannel.SLACK_DM,
                message
            )
            
            return {
                "success": True,
                "notification_type": NotificationType.AUTO_PUNCH_OUT,
                "user_id": user_id,
                "record_id": record.id,
                "action": record.action,
                "timestamp": record.timestamp
            }
            
        except Exception as e:
            logger.error(f"Failed to send auto punch notification: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to send auto punch notification: {str(e)}"
            }
    
    async def send_weekly_report(self, user_id: int = None) -> Dict[str, Any]:
        """
        發送週報表通知。
        
        Args:
            user_id: 特定用戶 ID，None 表示發送給所有用戶
        
        Returns:
            發送結果統計
        """
        try:
            if not settings.ENABLE_WEEKLY_REPORT:
                return {"success": False, "message": "Weekly report is disabled"}
            
            # 計算上週的日期範圍
            today = date.today()
            days_since_monday = today.weekday()
            this_monday = today - timedelta(days=days_since_monday)
            last_monday = this_monday - timedelta(days=7)
            last_sunday = last_monday + timedelta(days=6)
            
            # 取得目標用戶
            users_query = self.db.query(User).filter(User.is_active == True)
            if user_id:
                users_query = users_query.filter(User.id == user_id)
            
            users = users_query.all()
            
            sent_count = 0
            failed_count = 0
            errors = []
            
            for user in users:
                try:
                    # 取得用戶上週的工時統計
                    stats = self.attendance_service.get_work_time_stats(
                        user.id, last_monday, last_sunday
                    )
                    
                    message = self._build_weekly_report_message(user, stats, last_monday, last_sunday)
                    
                    await self._send_notification(
                        user,
                        NotificationType.WEEKLY_REPORT,
                        NotificationChannel.SLACK_DM,
                        message
                    )
                    
                    sent_count += 1
                
                except Exception as e:
                    failed_count += 1
                    errors.append({
                        "user_id": user.id,
                        "user_name": user.internal_real_name,
                        "error": str(e)
                    })
                    logger.error(f"Failed to send weekly report to user {user.id}: {str(e)}")
            
            return {
                "success": True,
                "notification_type": NotificationType.WEEKLY_REPORT,
                "sent_count": sent_count,
                "failed_count": failed_count,
                "total_users": len(users),
                "report_period": f"{last_monday} to {last_sunday}",
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Failed to send weekly reports: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to send weekly reports: {str(e)}"
            }
    
    async def send_overtime_alert(self, user_id: int, overtime_hours: float) -> Dict[str, Any]:
        """
        發送加班提醒。
        
        Args:
            user_id: 用戶 ID
            overtime_hours: 加班時數
        
        Returns:
            發送結果
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}
            
            message = self._build_overtime_alert_message(user, overtime_hours)
            
            await self._send_notification(
                user,
                NotificationType.OVERTIME_ALERT,
                NotificationChannel.SLACK_DM,
                message
            )
            
            return {
                "success": True,
                "notification_type": NotificationType.OVERTIME_ALERT,
                "user_id": user_id,
                "overtime_hours": overtime_hours
            }
            
        except Exception as e:
            logger.error(f"Failed to send overtime alert: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to send overtime alert: {str(e)}"
            }
    
    async def send_system_alert(
        self, 
        message: str, 
        users: List[int] = None,
        channels: List[NotificationChannel] = None
    ) -> Dict[str, Any]:
        """
        發送系統警報通知。
        
        Args:
            message: 警報訊息
            users: 目標用戶列表，None 表示所有活躍用戶
            channels: 通知渠道列表
        
        Returns:
            發送結果統計
        """
        try:
            if channels is None:
                channels = [NotificationChannel.SLACK_DM]
            
            # 取得目標用戶
            users_query = self.db.query(User).filter(User.is_active == True)
            if users:
                users_query = users_query.filter(User.id.in_(users))
            
            target_users = users_query.all()
            
            sent_count = 0
            failed_count = 0
            errors = []
            
            for user in target_users:
                try:
                    for channel in channels:
                        await self._send_notification(
                            user,
                            NotificationType.SYSTEM_ALERT,
                            channel,
                            message
                        )
                    
                    sent_count += 1
                
                except Exception as e:
                    failed_count += 1
                    errors.append({
                        "user_id": user.id,
                        "user_name": user.internal_real_name,
                        "error": str(e)
                    })
                    logger.error(f"Failed to send system alert to user {user.id}: {str(e)}")
            
            return {
                "success": True,
                "notification_type": NotificationType.SYSTEM_ALERT,
                "sent_count": sent_count,
                "failed_count": failed_count,
                "total_users": len(target_users),
                "channels": [c.value for c in channels],
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Failed to send system alert: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to send system alert: {str(e)}"
            }
    
    async def _send_notification(
        self,
        user: User,
        notification_type: NotificationType,
        channel: NotificationChannel,
        message: str
    ):
        """
        發送單個通知（實際發送實作）。
        
        Args:
            user: 目標用戶
            notification_type: 通知類型
            channel: 通知渠道
            message: 訊息內容
        
        Note:
            這是一個範例實作，實際應該整合真實的通知服務
        """
        try:
            # 記錄通知發送日誌
            logger.info(
                f"Sending {notification_type.value} to user {user.id} "
                f"via {channel.value}: {message[:100]}..."
            )
            
            if channel == NotificationChannel.SLACK_DM:
                # 這裡應該整合 Slack API 發送私訊
                await self._send_slack_dm(user.slack_user_id, message)
            elif channel == NotificationChannel.SLACK_CHANNEL:
                # 這裡應該整合 Slack API 發送頻道訊息
                await self._send_slack_channel_message(message)
            elif channel == NotificationChannel.EMAIL:
                # 這裡應該整合 Email 服務
                await self._send_email(user.slack_email, message)
            elif channel == NotificationChannel.WEBHOOK:
                # 這裡應該發送 webhook
                await self._send_webhook(user, message)
            
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
            raise
    
    async def _send_slack_dm(self, slack_user_id: str, message: str):
        """發送 Slack 私訊（範例實作）"""
        # 實際實作應該使用 Slack SDK
        logger.info(f"Sending Slack DM to {slack_user_id}: {message}")
        pass
    
    async def _send_slack_channel_message(self, message: str):
        """發送 Slack 頻道訊息（範例實作）"""
        logger.info(f"Sending Slack channel message: {message}")
        pass
    
    async def _send_email(self, email: str, message: str):
        """發送 Email（範例實作）"""
        logger.info(f"Sending email to {email}: {message}")
        pass
    
    async def _send_webhook(self, user: User, message: str):
        """發送 Webhook（範例實作）"""
        logger.info(f"Sending webhook for user {user.id}: {message}")
        pass
    
    def _build_daily_reminder_message(self, user: User) -> str:
        """建立每日提醒訊息"""
        return (
            f"🌅 早安 {user.internal_real_name}！\n\n"
            f"別忘記開始工作時打卡哦！\n"
            f"使用 `/punch in` 指令來打卡上班。\n\n"
            f"祝你今天工作順利！ 💪"
        )
    
    def _build_work_hour_reminder_message(self, user: User, work_hours: float, standard_hours: int) -> str:
        """建立工作時數提醒訊息"""
        if work_hours >= standard_hours:
            return (
                f"⏰ {user.internal_real_name}，你今天已經工作了 {work_hours:.1f} 小時！\n\n"
                f"已達到標準工時 {standard_hours} 小時，記得適時休息哦！\n"
                f"如果要下班，可以使用 `/punch out` 指令打卡。\n\n"
                f"辛苦了！ 😊"
            )
        else:
            remaining = standard_hours - work_hours
            return (
                f"⏰ {user.internal_real_name}，你今天已經工作了 {work_hours:.1f} 小時。\n\n"
                f"距離標準工時 {standard_hours} 小時還有 {remaining:.1f} 小時。\n"
                f"繼續加油！ 💪"
            )
    
    def _build_forgot_punch_reminder_message(self, user: User, reason: str) -> str:
        """建立忘記打卡提醒訊息"""
        return (
            f"🔔 {user.internal_real_name}，打卡提醒！\n\n"
            f"檢測到：{reason}\n\n"
            f"如果還在工作，請記得打卡：\n"
            f"• 上班：`/punch in`\n"
            f"• 下班：`/punch out`\n"
            f"• 休息：`/punch break`\n"
            f"• 回來：`/punch back`\n\n"
            f"如有疑問，請聯絡管理員。"
        )
    
    def _build_auto_punch_notification_message(self, user: User, record: AttendanceRecord) -> str:
        """建立自動打卡通知訊息"""
        action_text = {
            'in': '上班',
            'out': '下班',
            'break': '休息',
            'back': '回來'
        }.get(record.action, record.action)
        
        return (
            f"🤖 {user.internal_real_name}，系統自動打卡通知\n\n"
            f"動作：{action_text}\n"
            f"時間：{record.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"原因：{record.note or '達到自動打卡條件'}\n\n"
            f"如有問題，請聯絡管理員。"
        )
    
    def _build_weekly_report_message(
        self, 
        user: User, 
        stats: Dict, 
        start_date: date, 
        end_date: date
    ) -> str:
        """建立週報表訊息"""
        return (
            f"📊 {user.internal_real_name} 的週報表\n"
            f"期間：{start_date} ~ {end_date}\n\n"
            f"📈 工時統計：\n"
            f"• 總工作時數：{stats['total_work_hours']:.1f} 小時\n"
            f"• 預期工時：{stats['expected_total_hours']:.1f} 小時\n"
            f"• 加班時數：{stats['overtime_hours']:.1f} 小時\n"
            f"• 出勤天數：{stats['working_days']} 天\n"
            f"• 平均每日：{stats['avg_daily_hours']:.1f} 小時\n"
            f"• 出勤率：{stats['attendance_rate']:.1f}%\n\n"
            f"{"🎉 表現優異！" if stats['attendance_rate'] >= 90 else "💪 繼續加油！"}"
        )
    
    def _build_overtime_alert_message(self, user: User, overtime_hours: float) -> str:
        """建立加班提醒訊息"""
        return (
            f"⚠️ {user.internal_real_name}，加班提醒\n\n"
            f"你今天已經加班 {overtime_hours:.1f} 小時。\n\n"
            f"請注意休息，保持工作與生活的平衡！\n"
            f"如果工作已完成，記得使用 `/punch out` 下班打卡。\n\n"
            f"健康最重要！ ❤️"
        )