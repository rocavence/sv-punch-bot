"""
User management API routes for CRUD operations, bulk import, and Slack synchronization.
"""

import csv
import io
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserInDB
from app.utils.auth import get_current_active_user, get_current_admin_user
from app.utils.validators import (
    DataValidator, 
    CSVValidator, 
    validate_pagination_params,
    validate_request_data
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])

# Response models
class UserListResponse(BaseModel):
    """用戶列表回應模型"""
    users: List[UserResponse]
    total: int
    skip: int
    limit: int

class BulkImportResponse(BaseModel):
    """批量匯入回應模型"""
    success: bool
    message: str
    imported_count: int
    failed_count: int
    errors: List[dict] = []

class UserSyncResponse(BaseModel):
    """用戶同步回應模型"""
    success: bool
    message: str
    updated_fields: List[str] = []

class UserSearchParams(BaseModel):
    """用戶搜尋參數"""
    search: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

@router.get("/", response_model=UserListResponse, summary="取得用戶列表")
async def get_users(
    skip: int = Query(0, ge=0, description="跳過的記錄數"),
    limit: int = Query(100, ge=1, le=1000, description="返回的記錄數"),
    search: Optional[str] = Query(None, description="搜尋關鍵字（姓名、email）"),
    department: Optional[str] = Query(None, description="部門篩選"),
    role: Optional[str] = Query(None, description="角色篩選"),
    is_active: Optional[bool] = Query(None, description="啟用狀態篩選"),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    取得用戶列表，支援搜尋和篩選。
    
    - 僅管理員可以訪問
    - 支援分頁查詢
    - 支援按姓名、email、部門、角色篩選
    """
    try:
        # 驗證分頁參數
        skip, limit = validate_pagination_params(skip, limit)
        
        # 構建查詢
        query = db.query(User)
        
        # 應用篩選條件
        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                or_(
                    User.internal_real_name.ilike(search_filter),
                    User.slack_real_name.ilike(search_filter),
                    User.slack_email.ilike(search_filter),
                    User.slack_username.ilike(search_filter),
                    User.slack_display_name.ilike(search_filter)
                )
            )
        
        if department:
            query = query.filter(User.department.ilike(f"%{department}%"))
        
        if role:
            query = query.filter(User.role == role)
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        # 取得總數
        total = query.count()
        
        # 應用分頁並執行查詢
        users = query.offset(skip).limit(limit).all()
        
        return UserListResponse(
            users=[UserResponse.from_orm(user) for user in users],
            total=total,
            skip=skip,
            limit=limit
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get users: {str(e)}"
        )

@router.post("/", response_model=UserResponse, summary="建立新用戶")
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    建立新用戶。
    
    - 僅管理員可以建立用戶
    - 檢查 Slack 用戶 ID 是否已存在
    - 驗證用戶資料格式
    """
    try:
        # 檢查 Slack 用戶 ID 是否已存在
        existing_user = db.query(User).filter(
            User.slack_user_id == user_data.slack_user_id
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this Slack ID already exists"
            )
        
        # 建立新用戶
        user_service = UserService(db)
        new_user = user_service.create_user(user_data)
        
        return UserResponse.from_orm(new_user)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )

@router.get("/{user_id}", response_model=UserResponse, summary="取得用戶詳情")
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    取得指定用戶的詳細資料。
    
    - 用戶可以查看自己的資料
    - 管理員可以查看所有用戶資料
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # 檢查權限：用戶只能查看自己的資料，管理員可以查看所有
        if current_user.role != "admin" and current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied"
            )
        
        return UserResponse.from_orm(user)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user: {str(e)}"
        )

@router.put("/{user_id}", response_model=UserResponse, summary="更新用戶資料")
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    更新用戶資料。
    
    - 用戶可以更新自己的部分資料
    - 管理員可以更新所有用戶的所有資料
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # 檢查權限
        if current_user.role != "admin" and current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied"
            )
        
        # 非管理員用戶不能修改某些欄位
        if current_user.role != "admin":
            restricted_fields = ["role", "is_active", "standard_hours"]
            for field in restricted_fields:
                if getattr(user_data, field, None) is not None:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied to modify {field}"
                    )
        
        # 更新用戶資料
        user_service = UserService(db)
        updated_user = user_service.update_user(user_id, user_data)
        
        return UserResponse.from_orm(updated_user)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )

@router.delete("/{user_id}", response_model=dict, summary="刪除用戶")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    刪除用戶（軟刪除，設定為非活躍狀態）。
    
    - 僅管理員可以刪除用戶
    - 實際上是將用戶設定為非活躍狀態
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # 不能刪除自己
        if user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete yourself"
            )
        
        # 軟刪除：設定為非活躍狀態
        user.is_active = False
        db.commit()
        
        return {
            "success": True,
            "message": "User deactivated successfully",
            "user_id": user_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}"
        )

@router.post("/import", response_model=BulkImportResponse, summary="批量匯入用戶")
async def import_users(
    file: UploadFile = File(..., description="CSV 檔案"),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    從 CSV 檔案批量匯入用戶。
    
    - 僅管理員可以批量匯入
    - CSV 格式：slack_user_id, internal_real_name, department, slack_email, role, standard_hours
    - 支援錯誤報告和部分匯入
    """
    try:
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only CSV files are allowed"
            )
        
        # 讀取檔案內容
        content = await file.read()
        csv_data = io.StringIO(content.decode('utf-8'))
        reader = csv.DictReader(csv_data)
        
        # 驗證 CSV headers
        validator = CSVValidator()
        validator.validate_user_csv_headers(reader.fieldnames)
        
        imported_count = 0
        failed_count = 0
        errors = []
        
        user_service = UserService(db)
        
        for row_num, row in enumerate(reader, start=2):  # Start from 2 (accounting for header)
            try:
                # 驗證行資料
                validated_row = validator.validate_user_csv_row(row)
                
                # 檢查用戶是否已存在
                existing_user = db.query(User).filter(
                    User.slack_user_id == validated_row['slack_user_id']
                ).first()
                
                if existing_user:
                    # 更新現有用戶
                    update_data = UserUpdate(**validated_row)
                    user_service.update_user(existing_user.id, update_data)
                else:
                    # 建立新用戶
                    create_data = UserCreate(**validated_row)
                    user_service.create_user(create_data)
                
                imported_count += 1
                
            except Exception as e:
                failed_count += 1
                errors.append({
                    "row": row_num,
                    "data": row,
                    "error": str(e)
                })
        
        return BulkImportResponse(
            success=True,
            message=f"Import completed: {imported_count} successful, {failed_count} failed",
            imported_count=imported_count,
            failed_count=failed_count,
            errors=errors
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import users: {str(e)}"
        )

@router.post("/{user_id}/sync", response_model=UserSyncResponse, summary="同步 Slack 用戶資料")
async def sync_user_slack_data(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    同步指定用戶的 Slack 資料。
    
    - 僅管理員可以同步
    - 從 Slack API 取得最新的用戶資料並更新
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # 使用 UserService 同步 Slack 資料
        user_service = UserService(db)
        updated_user, updated_fields = await user_service.sync_slack_user_data(user.slack_user_id)
        
        return UserSyncResponse(
            success=True,
            message=f"User Slack data synchronized successfully",
            updated_fields=updated_fields
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync user data: {str(e)}"
        )

@router.get("/slack/{slack_user_id}", response_model=UserResponse, summary="透過 Slack ID 取得用戶")
async def get_user_by_slack_id(
    slack_user_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    透過 Slack 用戶 ID 取得用戶資料。
    
    - 僅管理員可以使用
    - 主要用於 Slack Bot 整合
    """
    try:
        user = db.query(User).filter(User.slack_user_id == slack_user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserResponse.from_orm(user)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user: {str(e)}"
        )

@router.get("/stats/summary", response_model=dict, summary="用戶統計摘要")
async def get_users_stats(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    取得用戶統計摘要。
    
    - 僅管理員可以查看
    - 包含總用戶數、活躍用戶數、部門分佈等
    """
    try:
        # 總用戶數
        total_users = db.query(User).count()
        
        # 活躍用戶數
        active_users = db.query(User).filter(User.is_active == True).count()
        
        # 按角色分組
        role_stats = db.query(
            User.role,
            func.count(User.id).label('count')
        ).group_by(User.role).all()
        
        # 按部門分組
        department_stats = db.query(
            User.department,
            func.count(User.id).label('count')
        ).filter(
            User.department.isnot(None),
            User.is_active == True
        ).group_by(User.department).all()
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": total_users - active_users,
            "role_distribution": {role: count for role, count in role_stats},
            "department_distribution": {dept: count for dept, count in department_stats},
            "last_updated": func.now()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user stats: {str(e)}"
        )