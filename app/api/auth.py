"""
Authentication API routes for JWT token management and OAuth2 authentication.
"""

from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.models.user import User
from app.utils.auth import (
    create_access_token,
    verify_token,
    AuthError,
    get_current_user,
    get_current_active_user,
    slack_auth
)
from app.config import settings

router = APIRouter(prefix="/auth", tags=["authentication"])

# Pydantic models for authentication
class Token(BaseModel):
    """Token response model"""
    access_token: str
    token_type: str
    expires_in: int
    user_id: int
    slack_user_id: str
    role: str

class TokenRefresh(BaseModel):
    """Token refresh request model"""
    refresh_token: str

class SlackAuthRequest(BaseModel):
    """Slack authentication request model"""
    slack_user_id: str
    slack_username: Optional[str] = None
    slack_display_name: Optional[str] = None
    slack_real_name: Optional[str] = None
    slack_email: Optional[EmailStr] = None
    slack_avatar_url: Optional[str] = None

class AdminLoginRequest(BaseModel):
    """Admin login request model"""
    slack_user_id: str
    secret_key: Optional[str] = None

class AuthResponse(BaseModel):
    """Authentication response model"""
    success: bool
    message: str
    user: Optional[dict] = None

@router.post("/slack", response_model=Token, summary="Slack用戶認證")
async def slack_authenticate(
    auth_request: SlackAuthRequest,
    db: Session = Depends(get_db)
):
    """
    Slack 用戶認證端點。
    
    - 驗證 Slack 用戶 ID
    - 返回 JWT access token
    - 自動更新用戶資料（如果存在）
    """
    try:
        # 查找用戶
        user = slack_auth.authenticate_slack_user(auth_request.slack_user_id, db)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # 更新 Slack 用戶資料
        update_data = {}
        if auth_request.slack_username:
            update_data['slack_username'] = auth_request.slack_username
        if auth_request.slack_display_name:
            update_data['slack_display_name'] = auth_request.slack_display_name
        if auth_request.slack_real_name:
            update_data['slack_real_name'] = auth_request.slack_real_name
        if auth_request.slack_email:
            update_data['slack_email'] = auth_request.slack_email
        if auth_request.slack_avatar_url:
            update_data['slack_avatar_url'] = auth_request.slack_avatar_url
        
        if update_data:
            for key, value in update_data.items():
                setattr(user, key, value)
            db.commit()
            db.refresh(user)
        
        # 創建 access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.id, "slack_user_id": user.slack_user_id},
            expires_delta=access_token_expires
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user_id=user.id,
            slack_user_id=user.slack_user_id,
            role=user.role
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication failed: {str(e)}"
        )

@router.post("/admin/login", response_model=Token, summary="管理員登入")
async def admin_login(
    login_request: AdminLoginRequest,
    db: Session = Depends(get_db)
):
    """
    管理員登入端點。
    
    - 驗證管理員權限
    - 返回 JWT access token
    - 僅供管理員使用
    """
    try:
        # 查找用戶
        user = db.query(User).filter(
            User.slack_user_id == login_request.slack_user_id,
            User.is_active == True
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # 檢查管理員權限
        if user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # 額外的安全檢查（可選）
        if login_request.secret_key:
            if login_request.secret_key != settings.SECRET_KEY:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid secret key"
                )
        
        # 創建 access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.id, "slack_user_id": user.slack_user_id, "role": "admin"},
            expires_delta=access_token_expires
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user_id=user.id,
            slack_user_id=user.slack_user_id,
            role=user.role
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Admin login failed: {str(e)}"
        )

@router.post("/refresh", response_model=Token, summary="刷新Token")
async def refresh_token(
    current_user: User = Depends(get_current_active_user)
):
    """
    刷新 JWT token。
    
    - 使用現有有效 token 獲取新 token
    - 延長認證時間
    """
    try:
        # 創建新的 access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": current_user.id, "slack_user_id": current_user.slack_user_id},
            expires_delta=access_token_expires
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user_id=current_user.id,
            slack_user_id=current_user.slack_user_id,
            role=current_user.role
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {str(e)}"
        )

@router.post("/logout", response_model=AuthResponse, summary="登出")
async def logout(
    current_user: User = Depends(get_current_user)
):
    """
    用戶登出端點。
    
    - 標記當前 token 為已登出（在實際應用中可能需要 token 黑名單）
    - 返回成功訊息
    """
    try:
        # 在實際應用中，這裡可以實作 token 黑名單機制
        # 目前只返回成功訊息，token 會在過期時間後自動失效
        
        return AuthResponse(
            success=True,
            message="Successfully logged out",
            user={
                "id": current_user.id,
                "slack_user_id": current_user.slack_user_id,
                "internal_real_name": current_user.internal_real_name
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {str(e)}"
        )

@router.get("/me", response_model=dict, summary="取得當前用戶資訊")
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """
    取得當前認證用戶的詳細資訊。
    
    - 需要有效的 JWT token
    - 返回用戶基本資料
    """
    try:
        return {
            "id": current_user.id,
            "slack_user_id": current_user.slack_user_id,
            "slack_username": current_user.slack_username,
            "slack_display_name": current_user.slack_display_name,
            "slack_real_name": current_user.slack_real_name,
            "slack_email": current_user.slack_email,
            "slack_avatar_url": current_user.slack_avatar_url,
            "internal_real_name": current_user.internal_real_name,
            "department": current_user.department,
            "role": current_user.role,
            "standard_hours": current_user.standard_hours,
            "timezone": current_user.timezone,
            "is_active": current_user.is_active,
            "created_at": current_user.created_at,
            "updated_at": current_user.updated_at
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user info: {str(e)}"
        )

@router.post("/verify", response_model=dict, summary="驗證Token")
async def verify_token_endpoint(
    current_user: User = Depends(get_current_user)
):
    """
    驗證 JWT token 是否有效。
    
    - 檢查 token 格式和過期時間
    - 驗證用戶是否存在且活躍
    """
    try:
        return {
            "valid": True,
            "user_id": current_user.id,
            "slack_user_id": current_user.slack_user_id,
            "role": current_user.role,
            "is_active": current_user.is_active,
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

@router.get("/status", response_model=dict, summary="認證服務狀態")
async def auth_status():
    """
    檢查認證服務狀態。
    
    - 返回服務健康狀態
    - 不需要認證
    """
    return {
        "service": "authentication",
        "status": "healthy",
        "version": "1.0.0",
        "algorithm": settings.ALGORITHM,
        "token_expire_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES
    }