import os
import logging
from typing import Dict, Optional
from slack_bolt import App
from slack_bolt.request import BoltRequest
from slack_bolt.response import BoltResponse
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import get_db
from app.models import Workspace
from app.slack.handlers.punch import register_punch_handlers
from app.slack.handlers.admin import register_admin_handlers
from app.slack.handlers.events import register_event_handlers
from app.slack.services.user_sync import UserSyncService
from app.slack.services.status_manager import StatusManager

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MultiWorkspaceSlackBot:
    """
    多工作區 Slack Bot 主應用程式
    支援動態載入工作區配置，無需重啟
    """
    
    def __init__(self):
        # 使用通用的 signing secret (所有工作區共用)
        self.signing_secret = os.environ.get("SLACK_SIGNING_SECRET")
        
        # 工作區快取
        self.workspaces: Dict[str, dict] = {}
        
        # 初始化 Slack App，使用虛擬 token 或環境變數
        # 在多工作區模式下，實際的 token 來自動態解析
        dummy_token = os.environ.get("SLACK_BOT_TOKEN", "xoxb-dummy-token-for-multi-workspace")
        
        self.app = App(
            token=dummy_token,
            signing_secret=self.signing_secret,
            # 使用動態 token 驗證
            token_verification_enabled=False,  # 停用預設驗證，使用自訂邏輯
            process_before_response=True
        )
        
        # 初始化服務
        self.user_sync_service = UserSyncService()
        self.status_manager = StatusManager()
        
        # 初始化排程器
        self.scheduler = BackgroundScheduler()
        
        # 註冊處理程序
        self._register_handlers()
        
        # 設定動態 token 驗證
        self._setup_token_resolver()
        
        # 設定定時任務
        self._setup_scheduled_jobs()
        
        # 載入現有工作區
        self._load_workspaces()
        
        logger.info("多工作區 Slack Bot 初始化完成")
    
    def _setup_token_resolver(self):
        """設定動態 token 解析器"""
        @self.app.middleware
        def add_workspace_context(req: BoltRequest, resp: BoltResponse, next):
            # 從請求中提取 team_id
            team_id = None
            if req.body.get("team_id"):
                team_id = req.body["team_id"]
            elif req.body.get("team", {}).get("id"):
                team_id = req.body["team"]["id"]
            elif req.body.get("event", {}).get("team"):
                team_id = req.body["event"]["team"]
            
            if team_id and team_id in self.workspaces:
                # 設定工作區特定的 client
                workspace_info = self.workspaces[team_id]
                req.context["bot_token"] = workspace_info["bot_token"]
                req.context["workspace_info"] = workspace_info
            
            next()
        
        # 動態設定 client token
        def token_rotator(req: BoltRequest):
            team_id = None
            if req.body.get("team_id"):
                team_id = req.body["team_id"]
            elif req.body.get("team", {}).get("id"):
                team_id = req.body["team"]["id"]
            elif req.body.get("event", {}).get("team"):
                team_id = req.body["event"]["team"]
            
            if team_id and team_id in self.workspaces:
                return self.workspaces[team_id]["bot_token"]
            
            # 如果找不到對應工作區，嘗試從資料庫載入
            self._reload_workspace(team_id)
            if team_id in self.workspaces:
                return self.workspaces[team_id]["bot_token"]
            
            logger.warning(f"未找到工作區 {team_id} 的 token")
            return None
        
        self.app._token = token_rotator
    
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
    
    def _load_workspaces(self):
        """從資料庫載入所有工作區配置"""
        try:
            db = next(get_db())
            workspaces = db.query(Workspace).filter(Workspace.is_active == True).all()
            
            for workspace in workspaces:
                self.workspaces[workspace.slack_team_id] = {
                    "id": workspace.id,
                    "team_id": workspace.slack_team_id,
                    "team_name": workspace.team_name,
                    "team_domain": workspace.team_domain,
                    "bot_token": workspace.bot_token,
                    "bot_user_id": workspace.bot_user_id
                }
            
            logger.info(f"已載入 {len(self.workspaces)} 個工作區")
            
        except Exception as e:
            logger.error(f"載入工作區配置錯誤: {e}")
        finally:
            db.close()
    
    def _reload_workspace(self, team_id: str):
        """重新載入單個工作區配置"""
        if not team_id:
            return
            
        try:
            db = next(get_db())
            workspace = db.query(Workspace).filter(
                Workspace.slack_team_id == team_id,
                Workspace.is_active == True
            ).first()
            
            if workspace:
                self.workspaces[workspace.slack_team_id] = {
                    "id": workspace.id,
                    "team_id": workspace.slack_team_id,
                    "team_name": workspace.team_name,
                    "team_domain": workspace.team_domain,
                    "bot_token": workspace.bot_token,
                    "bot_user_id": workspace.bot_user_id
                }
                logger.info(f"已重新載入工作區: {workspace.team_name}")
            else:
                logger.warning(f"未找到工作區: {team_id}")
                
        except Exception as e:
            logger.error(f"重新載入工作區錯誤: {e}")
        finally:
            db.close()
    
    def add_workspace(self, workspace: Workspace):
        """添加新工作區到快取"""
        self.workspaces[workspace.slack_team_id] = {
            "id": workspace.id,
            "team_id": workspace.slack_team_id,
            "team_name": workspace.team_name,
            "team_domain": workspace.team_domain,
            "bot_token": workspace.bot_token,
            "bot_user_id": workspace.bot_user_id
        }
        logger.info(f"已添加工作區: {workspace.team_name}")
    
    def remove_workspace(self, team_id: str):
        """從快取中移除工作區"""
        if team_id in self.workspaces:
            team_name = self.workspaces[team_id]["team_name"]
            del self.workspaces[team_id]
            logger.info(f"已移除工作區: {team_name}")
    
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
        
        # 定期重新載入工作區配置 - 每小時
        self.scheduler.add_job(
            func=self._reload_workspaces_job,
            trigger=CronTrigger(minute=0, timezone='Asia/Taipei'),
            id='reload_workspaces',
            name='重新載入工作區',
            replace_existing=True
        )
        
        logger.info("定時任務設定完成")
    
    def _daily_reminder_job(self):
        """每日打卡提醒任務"""
        self._run_job_for_all_workspaces("daily_reminder")
    
    def _work_hour_reminder_job(self):
        """8小時工作提醒任務"""
        self._run_job_for_all_workspaces("work_hour_reminder")
    
    def _forgot_punch_reminder_job(self):
        """忘記打卡提醒任務"""
        self._run_job_for_all_workspaces("forgot_punch_reminder")
    
    def _weekly_report_job(self):
        """每週統計報告任務"""
        self._run_job_for_all_workspaces("weekly_report")
    
    def _reload_workspaces_job(self):
        """重新載入工作區配置任務"""
        old_count = len(self.workspaces)
        self._load_workspaces()
        new_count = len(self.workspaces)
        logger.info(f"工作區配置已更新: {old_count} -> {new_count}")
    
    def _run_job_for_all_workspaces(self, job_type: str):
        """為所有工作區執行特定任務"""
        from app.slack.services.punch_service import PunchService
        from slack_sdk import WebClient
        
        for team_id, workspace_info in self.workspaces.items():
            try:
                # 為每個工作區建立獨立的 client
                client = WebClient(token=workspace_info["bot_token"])
                
                db = next(get_db())
                punch_service = PunchService(db, workspace_id=workspace_info["id"])
                
                if job_type == "daily_reminder":
                    punch_service.send_daily_reminders(client)
                elif job_type == "work_hour_reminder":
                    punch_service.check_work_hour_reminders(client)
                elif job_type == "forgot_punch_reminder":
                    punch_service.send_forgot_punch_reminders(client)
                elif job_type == "weekly_report":
                    punch_service.send_weekly_reports(client)
                
                logger.info(f"{job_type} 完成 - 工作區: {workspace_info['team_name']}")
                
            except Exception as e:
                logger.error(f"{job_type} 錯誤 - 工作區: {workspace_info['team_name']}, 錯誤: {e}")
            finally:
                db.close()
    
    def start(self):
        """啟動多工作區 Slack Bot"""
        try:
            # 啟動排程器
            self.scheduler.start()
            logger.info("排程器已啟動")
            
            # 返回 app 實例供 FastAPI 使用
            logger.info("多工作區 Slack Bot 準備就緒")
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
multi_workspace_bot: Optional[MultiWorkspaceSlackBot] = None

def get_multi_workspace_bot() -> MultiWorkspaceSlackBot:
    """獲取多工作區 Slack Bot 實例"""
    global multi_workspace_bot
    if multi_workspace_bot is None:
        multi_workspace_bot = MultiWorkspaceSlackBot()
    return multi_workspace_bot

def start_multi_workspace_bot():
    """啟動多工作區 Slack Bot"""
    bot = get_multi_workspace_bot()
    return bot.start()

def stop_multi_workspace_bot():
    """停止多工作區 Slack Bot"""
    global multi_workspace_bot
    if multi_workspace_bot:
        multi_workspace_bot.stop()
        multi_workspace_bot = None