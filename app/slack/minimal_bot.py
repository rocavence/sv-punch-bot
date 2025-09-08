"""
Minimal Slack Bot for initialization without tokens
Used when no workspaces are installed yet
"""
import os
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class MinimalSlackBot:
    """
    最小化 Slack Bot，用於初始部署時沒有 tokens 的情況
    只提供基本結構，不初始化 slack-bolt App
    """
    
    def __init__(self):
        self.workspaces: Dict[str, dict] = {}
        self.app = None
        logger.info("MinimalSlackBot initialized - no Slack integration active")
    
    def start(self):
        """返回 None，表示沒有可用的 Slack App"""
        logger.info("MinimalSlackBot start() - no Slack App available")
        return None
    
    def stop(self):
        """最小化停止邏輯"""
        logger.info("MinimalSlackBot stopped")
    
    def add_workspace(self, workspace):
        """存儲工作區信息，但不初始化 Slack App"""
        logger.info(f"Workspace {workspace.team_name} added to MinimalSlackBot")
        # 這裡將來可以觸發升級到完整的 MultiWorkspaceSlackBot
    
    def remove_workspace(self, team_id: str):
        """移除工作區"""
        logger.info(f"Workspace {team_id} removed from MinimalSlackBot")


# 全域最小化 Bot 實例
minimal_bot: Optional[MinimalSlackBot] = None

def get_minimal_bot() -> MinimalSlackBot:
    """獲取最小化 Slack Bot 實例"""
    global minimal_bot
    if minimal_bot is None:
        minimal_bot = MinimalSlackBot()
    return minimal_bot