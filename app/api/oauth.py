from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Workspace
from app.schemas.workspace import WorkspaceCreate
import httpx
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["OAuth"])

SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
SLACK_REDIRECT_URI = os.getenv("SLACK_REDIRECT_URI", "https://your-app.onrender.com/oauth/callback")

# Slack OAuth scopes needed for the bot
OAUTH_SCOPES = [
    "chat:write",
    "users:read", 
    "users:read.email",
    "users:write",
    "commands",
    "app_mentions:read",
    "channels:read",
    "groups:read",
    "im:read",
    "mpim:read",
    "team:read"
]

@router.get("/install")
async def install_slack_app():
    """
    Generate Slack App installation URL for workspace admins
    """
    if not SLACK_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Slack Client ID not configured")
    
    scopes = ",".join(OAUTH_SCOPES)
    slack_oauth_url = (
        f"https://slack.com/oauth/v2/authorize"
        f"?client_id={SLACK_CLIENT_ID}"
        f"&scope={scopes}"
        f"&redirect_uri={SLACK_REDIRECT_URI}"
        f"&state=install"
    )
    
    install_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>安裝 Punch Bot 到您的 Slack 工作區</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ 
                font-family: -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;
                margin: 0; padding: 40px; background: #f8f9fa; 
            }}
            .container {{ 
                max-width: 600px; margin: 0 auto; background: white;
                padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            h1 {{ color: #1d1c1d; margin-bottom: 20px; }}
            .feature {{ margin: 15px 0; padding: 10px 0; }}
            .feature strong {{ color: #611f69; }}
            .install-btn {{ 
                display: inline-block; background: #4A154B; color: white;
                padding: 12px 24px; text-decoration: none; border-radius: 4px;
                font-weight: 500; margin: 20px 0;
            }}
            .install-btn:hover {{ background: #611f69; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 安裝 Punch Bot 到您的 Slack 工作區</h1>
            
            <p>Punch Bot 是一個智能打卡機器人，支援混合辦公制度，讓團隊管理更輕鬆！</p>
            
            <h3>🚀 主要功能：</h3>
            <div class="feature"><strong>簡單打卡：</strong>/punch in、/punch out、/punch break</div>
            <div class="feature"><strong>智能提醒：</strong>自動提醒上下班、8小時工作提醒</div>
            <div class="feature"><strong>休假管理：</strong>/punch ooo 快速申請休假</div>
            <div class="feature"><strong>統計報表：</strong>查看個人和團隊工時統計</div>
            <div class="feature"><strong>Web 管理：</strong>完整的 Web 管理介面</div>
            
            <p>點擊下方按鈕即可安裝到您的 Slack 工作區（需要管理員權限）：</p>
            
            <a href="{slack_oauth_url}" class="install-btn">
                📱 安裝到 Slack
            </a>
            
            <p><small>安裝完成後，Punch Bot 會自動配置所有必要設定，立即可用！</small></p>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=install_html)

@router.get("/callback")
async def slack_oauth_callback(
    request: Request,
    code: str = None,
    error: str = None,
    state: str = None,
    db: Session = Depends(get_db)
):
    """
    Handle Slack OAuth callback and install the app to workspace
    """
    if error:
        logger.error(f"Slack OAuth error: {error}")
        return HTMLResponse(f"<h1>安裝失敗</h1><p>錯誤：{error}</p>", status_code=400)
    
    if not code:
        return HTMLResponse("<h1>安裝失敗</h1><p>缺少授權碼</p>", status_code=400)
    
    try:
        # Exchange code for access token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://slack.com/api/oauth.v2.access",
                data={{
                    "client_id": SLACK_CLIENT_ID,
                    "client_secret": SLACK_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": SLACK_REDIRECT_URI
                }}
            )
            
            oauth_data = response.json()
            
            if not oauth_data.get("ok"):
                logger.error(f"Slack OAuth failed: {{oauth_data}}")
                return HTMLResponse(f"<h1>安裝失敗</h1><p>錯誤：{{oauth_data.get('error', 'Unknown error')}}</p>", status_code=400)
            
            # Extract workspace and bot information
            team_info = oauth_data.get("team", {{}})
            bot_info = oauth_data.get("bot", {{}})
            access_token = oauth_data.get("access_token")
            
            team_id = team_info.get("id")
            team_name = team_info.get("name")
            bot_user_id = bot_info.get("user_id")
            
            if not team_id or not access_token:
                return HTMLResponse("<h1>安裝失敗</h1><p>無法取得工作區資訊</p>", status_code=400)
            
            # Check if workspace already exists
            existing_workspace = db.query(Workspace).filter(Workspace.slack_team_id == team_id).first()
            
            if existing_workspace:
                # Update existing workspace
                existing_workspace.team_name = team_name
                existing_workspace.bot_token = access_token
                existing_workspace.bot_user_id = bot_user_id
                existing_workspace.is_active = True
                workspace = existing_workspace
                action = "更新"
            else:
                # Create new workspace
                workspace_data = WorkspaceCreate(
                    slack_team_id=team_id,
                    team_name=team_name,
                    team_domain=team_info.get("domain"),
                    bot_token=access_token,
                    bot_user_id=bot_user_id
                )
                workspace = Workspace(**workspace_data.dict())
                db.add(workspace)
                action = "安裝"
            
            db.commit()
            
            success_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Punch Bot 安裝成功</title>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body {{ 
                        font-family: -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;
                        margin: 0; padding: 40px; background: #f8f9fa; text-align: center;
                    }}
                    .container {{ 
                        max-width: 500px; margin: 0 auto; background: white;
                        padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    }}
                    .success {{ color: #28a745; font-size: 48px; margin-bottom: 20px; }}
                    h1 {{ color: #1d1c1d; margin-bottom: 20px; }}
                    .command {{ 
                        background: #f8f9fa; padding: 10px; border-radius: 4px;
                        font-family: monospace; margin: 10px 0;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="success">✅</div>
                    <h1>Punch Bot {action}成功！</h1>
                    <p>已成功{action}到 <strong>{team_name}</strong> 工作區</p>
                    
                    <h3>🎉 立即開始使用：</h3>
                    <div class="command">/punch in</div>
                    <div class="command">/punch today</div>
                    <div class="command">/punch help</div>
                    
                    <p>您現在可以關閉此頁面，回到 Slack 開始使用 Punch Bot！</p>
                    
                    <p><small>如需管理功能，請訪問：<br>
                    <a href="{request.base_url}">Web 管理介面</a></small></p>
                </div>
            </body>
            </html>
            """
            
            return HTMLResponse(content=success_html)
            
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return HTMLResponse(f"<h1>安裝失敗</h1><p>系統錯誤：{str(e)}</p>", status_code=500)

@router.get("/workspaces")
async def list_workspaces(db: Session = Depends(get_db)):
    """
    List all installed workspaces (for admin purposes)
    """
    workspaces = db.query(Workspace).filter(Workspace.is_active == True).all()
    return {{
        "workspaces": [
            {{
                "id": ws.id,
                "team_name": ws.team_name,
                "team_id": ws.slack_team_id,
                "installed_at": ws.installed_at,
                "users_count": len(ws.users)
            }}
            for ws in workspaces
        ]
    }}

@router.post("/workspaces/{{workspace_id}}/deactivate")
async def deactivate_workspace(workspace_id: int, db: Session = Depends(get_db)):
    """
    Deactivate a workspace (soft delete)
    """
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    workspace.is_active = False
    db.commit()
    
    return {{"message": f"Workspace {{workspace.team_name}} deactivated successfully"}}