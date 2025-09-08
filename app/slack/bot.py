import os
import logging
from typing import Optional
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import get_db
from app.slack.handlers.punch import register_punch_handlers
from app.slack.handlers.admin import register_admin_handlers
from app.slack.handlers.events import register_event_handlers
from app.slack.services.user_sync import UserSyncService
from app.slack.services.status_manager import StatusManager

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SlackBot:
    """Slack Bot 主應用程式"""
    
    def __init__(self):
        # 初始化 Slack App
        self.app = App(
            token=os.environ.get("SLACK_BOT_TOKEN"),
            signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
        )
        
        # 初始化服務
        self.user_sync_service = UserSyncService()
        self.status_manager = StatusManager()
        
        # 初始化排程器
        self.scheduler = BackgroundScheduler()
        
        # 註冊所有處理程序
        self._register_handlers()
        
        # 設定定時任務
        self._setup_scheduled_jobs()
        
        logger.info("Slack Bot 初始化完成")
    
    def _register_handlers(self):
        """註冊所有 Slack 事件處理程序"""
        register_punch_handlers(self.app)
        register_admin_handlers(self.app)
        register_event_handlers(self.app, self.user_sync_service)
        
        # 註冊錯誤處理程序
        @self.app.error
        def global_error_handler(error, body, logger):
            logger.exception(f"未處理的錯誤: {error}")
            return "很抱歉，發生了錯誤。請稍後再試。"
    
    def _setup_scheduled_jobs(self):
        """設定定時任務"""
        # 每日提醒任務 - 上午 9:00 檢查未打卡用戶
        self.scheduler.add_job(
            func=self._daily_reminder_job,
            trigger=CronTrigger(hour=9, minute=0, timezone='Asia/Taipei'),
            id='daily_reminder',
            name='每日打卡提醒',
            replace_existing=True
        )
        
        # 8小時工作提醒 - 每15分鐘檢查一次
        self.scheduler.add_job(
            func=self._work_hour_reminder_job,
            trigger=CronTrigger(minute='*/15', timezone='Asia/Taipei'),
            id='work_hour_reminder',
            name='8小時工作提醒',
            replace_existing=True
        )
        
        # 晚上提醒忘記打卡 - 下午 6:30
        self.scheduler.add_job(
            func=self._forgot_punch_reminder_job,
            trigger=CronTrigger(hour=18, minute=30, timezone='Asia/Taipei'),
            id='forgot_punch_reminder',
            name='忘記打卡提醒',
            replace_existing=True
        )
        
        # 每週統計報告 - 週一上午 9:30
        self.scheduler.add_job(
            func=self._weekly_report_job,
            trigger=CronTrigger(day_of_week=0, hour=9, minute=30, timezone='Asia/Taipei'),
            id='weekly_report',
            name='每週統計報告',
            replace_existing=True
        )
        
        logger.info("定時任務設定完成")
    
    def _daily_reminder_job(self):
        """每日打卡提醒任務"""
        from app.slack.services.punch_service import PunchService
        
        try:
            db = next(get_db())
            punch_service = PunchService(db)
            punch_service.send_daily_reminders(self.app.client)
            logger.info("每日打卡提醒已發送")
        except Exception as e:
            logger.error(f"每日打卡提醒任務錯誤: {e}")
        finally:
            db.close()
    
    def _work_hour_reminder_job(self):
        """8小時工作提醒任務"""
        from app.slack.services.punch_service import PunchService
        
        try:
            db = next(get_db())
            punch_service = PunchService(db)
            punch_service.check_work_hour_reminders(self.app.client)
            logger.info("8小時工作提醒檢查完成")
        except Exception as e:
            logger.error(f"8小時工作提醒任務錯誤: {e}")
        finally:
            db.close()
    
    def _forgot_punch_reminder_job(self):
        """忘記打卡提醒任務"""
        from app.slack.services.punch_service import PunchService
        
        try:
            db = next(get_db())
            punch_service = PunchService(db)
            punch_service.send_forgot_punch_reminders(self.app.client)
            logger.info("忘記打卡提醒已發送")
        except Exception as e:
            logger.error(f"忘記打卡提醒任務錯誤: {e}")
        finally:
            db.close()
    
    def _weekly_report_job(self):
        """每週統計報告任務"""
        from app.slack.services.punch_service import PunchService
        
        try:
            db = next(get_db())
            punch_service = PunchService(db)
            punch_service.send_weekly_reports(self.app.client)
            logger.info("每週統計報告已發送")
        except Exception as e:
            logger.error(f"每週統計報告任務錯誤: {e}")
        finally:
            db.close()
    
    def start(self):
        """啟動 Slack Bot"""
        try:
            # 啟動排程器
            self.scheduler.start()
            logger.info("排程器已啟動")
            
            # 根據環境選擇運行模式
            if os.environ.get("SLACK_APP_TOKEN"):
                # Socket Mode (開發環境)
                handler = SocketModeHandler(self.app, os.environ["SLACK_APP_TOKEN"])
                logger.info("使用 Socket Mode 啟動 Slack Bot")
                handler.start()
            else:
                # HTTP Mode (生產環境)
                logger.info("使用 HTTP Mode 啟動 Slack Bot")
                # 這裡需要與 FastAPI 整合
                return self.app
                
        except Exception as e:
            logger.error(f"啟動 Slack Bot 失敗: {e}")
            raise
    
    def stop(self):
        """停止 Slack Bot"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown()
                logger.info("排程器已停止")
        except Exception as e:
            logger.error(f"停止 Slack Bot 錯誤: {e}")


# 全域 Bot 實例
slack_bot: Optional[SlackBot] = None

def get_slack_bot() -> SlackBot:
    """獲取 Slack Bot 實例"""
    global slack_bot
    if slack_bot is None:
        slack_bot = SlackBot()
    return slack_bot

def start_slack_bot():
    """啟動 Slack Bot"""
    bot = get_slack_bot()
    return bot.start()

def stop_slack_bot():
    """停止 Slack Bot"""
    global slack_bot
    if slack_bot:
        slack_bot.stop()
        slack_bot = None