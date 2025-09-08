import os
from typing import Optional


class Settings:
    """應用程式配置設定"""
    
    # Slack 設定
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_SIGNING_SECRET: str = os.getenv("SLACK_SIGNING_SECRET", "")
    SLACK_APP_TOKEN: str = os.getenv("SLACK_APP_TOKEN", "")
    
    # 資料庫設定
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/punchbot")
    
    # JWT 設定
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secret-key-change-this-in-production")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # 應用設定
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Taipei")
    DEFAULT_WORK_HOURS: int = int(os.getenv("DEFAULT_WORK_HOURS", "8"))
    
    # 自動打卡設定
    AUTO_PUNCH_TIMEOUT_MINUTES: int = int(os.getenv("AUTO_PUNCH_TIMEOUT_MINUTES", "30"))
    ENABLE_AUTO_PUNCH: bool = os.getenv("ENABLE_AUTO_PUNCH", "True").lower() == "true"
    
    # 提醒設定
    ENABLE_DAILY_REMINDER: bool = os.getenv("ENABLE_DAILY_REMINDER", "True").lower() == "true"
    ENABLE_WORK_HOUR_REMINDER: bool = os.getenv("ENABLE_WORK_HOUR_REMINDER", "True").lower() == "true"
    ENABLE_FORGOT_PUNCH_REMINDER: bool = os.getenv("ENABLE_FORGOT_PUNCH_REMINDER", "True").lower() == "true"
    ENABLE_WEEKLY_REPORT: bool = os.getenv("ENABLE_WEEKLY_REPORT", "True").lower() == "true"
    
    # 提醒時間設定
    DAILY_REMINDER_HOUR: int = int(os.getenv("DAILY_REMINDER_HOUR", "9"))
    DAILY_REMINDER_MINUTE: int = int(os.getenv("DAILY_REMINDER_MINUTE", "0"))
    FORGOT_PUNCH_REMINDER_HOUR: int = int(os.getenv("FORGOT_PUNCH_REMINDER_HOUR", "18"))
    FORGOT_PUNCH_REMINDER_MINUTE: int = int(os.getenv("FORGOT_PUNCH_REMINDER_MINUTE", "30"))
    WEEKLY_REPORT_DAY: int = int(os.getenv("WEEKLY_REPORT_DAY", "0"))  # 0 = 週一
    WEEKLY_REPORT_HOUR: int = int(os.getenv("WEEKLY_REPORT_HOUR", "9"))
    WEEKLY_REPORT_MINUTE: int = int(os.getenv("WEEKLY_REPORT_MINUTE", "30"))
    
    # 工作時間檢查間隔（分鐘）
    WORK_HOUR_CHECK_INTERVAL: int = int(os.getenv("WORK_HOUR_CHECK_INTERVAL", "15"))
    
    # Slack 狀態管理
    ENABLE_STATUS_UPDATE: bool = os.getenv("ENABLE_STATUS_UPDATE", "True").lower() == "true"
    ENABLE_DND_MANAGEMENT: bool = os.getenv("ENABLE_DND_MANAGEMENT", "False").lower() == "true"
    
    # 部署設定
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    
    # 日誌設定
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # 檔案上傳設定
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "10485760"))  # 10MB
    ALLOWED_FILE_EXTENSIONS: list = os.getenv("ALLOWED_FILE_EXTENSIONS", "csv,xlsx,pdf").split(",")
    
    # 報表設定
    DEFAULT_REPORT_LIMIT: int = int(os.getenv("DEFAULT_REPORT_LIMIT", "1000"))
    EXPORT_DATE_FORMAT: str = os.getenv("EXPORT_DATE_FORMAT", "%Y-%m-%d")
    EXPORT_DATETIME_FORMAT: str = os.getenv("EXPORT_DATETIME_FORMAT", "%Y-%m-%d %H:%M:%S")
    
    # 管理員設定
    DEFAULT_ADMIN_USERS: list = os.getenv("DEFAULT_ADMIN_USERS", "").split(",") if os.getenv("DEFAULT_ADMIN_USERS") else []
    
    # 快取設定
    ENABLE_REDIS: bool = os.getenv("ENABLE_REDIS", "False").lower() == "true"
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))  # 5 分鐘
    
    # API 設定
    API_VERSION: str = os.getenv("API_VERSION", "v1")
    API_PREFIX: str = f"/api/{API_VERSION}"
    
    @property
    def database_url(self) -> str:
        """獲取資料庫 URL，處理 Render.com 格式"""
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url
    
    @property
    def is_production(self) -> bool:
        """檢查是否為生產環境"""
        return not self.DEBUG
    
    @property
    def is_development(self) -> bool:
        """檢查是否為開發環境"""
        return self.DEBUG
    
    def get_slack_token(self) -> Optional[str]:
        """獲取 Slack Bot Token"""
        return self.SLACK_BOT_TOKEN if self.SLACK_BOT_TOKEN else None
    
    def get_signing_secret(self) -> Optional[str]:
        """獲取 Slack Signing Secret"""
        return self.SLACK_SIGNING_SECRET if self.SLACK_SIGNING_SECRET else None
    
    def get_app_token(self) -> Optional[str]:
        """獲取 Slack App Token（Socket Mode 用）"""
        return self.SLACK_APP_TOKEN if self.SLACK_APP_TOKEN else None
    
    def validate_required_settings(self) -> list:
        """驗證必要設定"""
        missing = []
        
        if not self.SLACK_BOT_TOKEN:
            missing.append("SLACK_BOT_TOKEN")
        
        if not self.SLACK_SIGNING_SECRET:
            missing.append("SLACK_SIGNING_SECRET")
        
        if not self.DATABASE_URL:
            missing.append("DATABASE_URL")
        
        if not self.SECRET_KEY or self.SECRET_KEY == "your-super-secret-key-change-this-in-production":
            missing.append("SECRET_KEY")
        
        return missing
    
    def get_scheduler_config(self) -> dict:
        """獲取排程器配置"""
        return {
            "daily_reminder": {
                "enabled": self.ENABLE_DAILY_REMINDER,
                "hour": self.DAILY_REMINDER_HOUR,
                "minute": self.DAILY_REMINDER_MINUTE
            },
            "work_hour_reminder": {
                "enabled": self.ENABLE_WORK_HOUR_REMINDER,
                "interval": self.WORK_HOUR_CHECK_INTERVAL
            },
            "forgot_punch_reminder": {
                "enabled": self.ENABLE_FORGOT_PUNCH_REMINDER,
                "hour": self.FORGOT_PUNCH_REMINDER_HOUR,
                "minute": self.FORGOT_PUNCH_REMINDER_MINUTE
            },
            "weekly_report": {
                "enabled": self.ENABLE_WEEKLY_REPORT,
                "day_of_week": self.WEEKLY_REPORT_DAY,
                "hour": self.WEEKLY_REPORT_HOUR,
                "minute": self.WEEKLY_REPORT_MINUTE
            }
        }
    
    def get_logging_config(self) -> dict:
        """獲取日誌配置"""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": self.LOG_FORMAT,
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": self.LOG_LEVEL,
                "handlers": ["default"],
            },
        }


# 全域設定實例
settings = Settings()

# 驗證設定
def validate_settings():
    """驗證應用程式設定"""
    missing = settings.validate_required_settings()
    
    if missing:
        raise ValueError(f"缺少必要的環境變數: {', '.join(missing)}")
    
    print("✅ 所有必要設定已配置完成")

# 匯出常用設定
SLACK_BOT_TOKEN = settings.SLACK_BOT_TOKEN
SLACK_SIGNING_SECRET = settings.SLACK_SIGNING_SECRET
SLACK_APP_TOKEN = settings.SLACK_APP_TOKEN
DATABASE_URL = settings.database_url
SECRET_KEY = settings.SECRET_KEY
DEBUG = settings.DEBUG
TIMEZONE = settings.TIMEZONE