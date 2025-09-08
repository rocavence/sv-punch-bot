"""
Attendance management API routes for CRUD operations on punch records.
"""

from datetime import datetime, date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.attendance import AttendanceRecord
from app.schemas.attendance import (
    AttendanceCreate, 
    AttendanceUpdate, 
    AttendanceResponse, 
    AttendanceAction
)
from app.utils.auth import get_current_active_user, get_current_admin_user
from app.utils.validators import validate_pagination_params, DataValidator
from app.services.attendance_service import AttendanceService

router = APIRouter(prefix="/attendance", tags=["attendance"])

# Response models
class AttendanceListResponse(BaseModel):
    """打卡記錄列表回應模型"""
    records: List[AttendanceResponse]
    total: int
    skip: int
    limit: int

class AttendanceDailySummary(BaseModel):
    """每日打卡摘要"""
    date: date
    user_id: int
    user_name: str
    first_in: Optional[datetime] = None
    last_out: Optional[datetime] = None
    total_work_minutes: int = 0
    total_break_minutes: int = 0
    records_count: int
    is_complete: bool

class AttendanceStats(BaseModel):
    """打卡統計"""
    total_records: int
    today_records: int
    users_punched_today: int
    most_common_action: str

class PunchRequest(BaseModel):
    """打卡請求模型"""
    action: AttendanceAction
    timestamp: Optional[datetime] = None
    note: Optional[str] = None

@router.get("/", response_model=AttendanceListResponse, summary="取得打卡記錄列表")
async def get_attendance_records(
    skip: int = Query(0, ge=0, description="跳過的記錄數"),
    limit: int = Query(100, ge=1, le=1000, description="返回的記錄數"),
    user_id: Optional[int] = Query(None, description="用戶ID篩選"),
    action: Optional[AttendanceAction] = Query(None, description="動作類型篩選"),
    start_date: Optional[date] = Query(None, description="開始日期"),
    end_date: Optional[date] = Query(None, description="結束日期"),
    is_auto: Optional[bool] = Query(None, description="是否自動打卡"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    取得打卡記錄列表，支援多種篩選條件。
    
    - 普通用戶只能查看自己的記錄
    - 管理員可以查看所有用戶的記錄
    """
    try:
        # 驗證分頁參數
        skip, limit = validate_pagination_params(skip, limit)
        
        # 構建查詢
        query = db.query(AttendanceRecord).join(User)
        
        # 權限檢查：普通用戶只能查看自己的記錄
        if current_user.role != "admin":
            if user_id and user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Permission denied to view other users' records"
                )
            query = query.filter(AttendanceRecord.user_id == current_user.id)
        elif user_id:
            query = query.filter(AttendanceRecord.user_id == user_id)
        
        # 應用篩選條件
        if action:
            query = query.filter(AttendanceRecord.action == action.value)
        
        if start_date:
            query = query.filter(func.date(AttendanceRecord.timestamp) >= start_date)
        
        if end_date:
            query = query.filter(func.date(AttendanceRecord.timestamp) <= end_date)
        
        if is_auto is not None:
            query = query.filter(AttendanceRecord.is_auto == is_auto)
        
        # 取得總數
        total = query.count()
        
        # 按時間戳排序並應用分頁
        records = query.order_by(desc(AttendanceRecord.timestamp)).offset(skip).limit(limit).all()
        
        return AttendanceListResponse(
            records=[AttendanceResponse.from_orm(record) for record in records],
            total=total,
            skip=skip,
            limit=limit
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get attendance records: {str(e)}"
        )

@router.post("/", response_model=AttendanceResponse, summary="新增打卡記錄")
async def create_attendance_record(
    record_data: AttendanceCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    新增打卡記錄。
    
    - 用戶可以為自己新增記錄
    - 管理員可以為任何用戶新增記錄
    """
    try:
        # 權限檢查
        if current_user.role != "admin" and record_data.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied to create record for other users"
            )
        
        # 檢查用戶是否存在
        target_user = db.query(User).filter(User.id == record_data.user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target user not found"
            )
        
        # 使用 AttendanceService 建立記錄
        attendance_service = AttendanceService(db)
        new_record = attendance_service.create_record(record_data)
        
        return AttendanceResponse.from_orm(new_record)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create attendance record: {str(e)}"
        )

@router.post("/punch", response_model=AttendanceResponse, summary="用戶打卡")
async def punch(
    punch_data: PunchRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    用戶打卡端點。
    
    - 用戶為自己打卡
    - 自動設定用戶 ID 和時間戳（如果未提供）
    - 驗證打卡序列的邏輯性
    """
    try:
        # 設定時間戳（如果未提供）
        timestamp = punch_data.timestamp or datetime.utcnow()
        
        # 建立打卡記錄資料
        record_data = AttendanceCreate(
            user_id=current_user.id,
            action=punch_data.action,
            timestamp=timestamp,
            is_auto=False,
            note=punch_data.note
        )
        
        # 使用 AttendanceService 建立記錄（包含序列驗證）
        attendance_service = AttendanceService(db)
        new_record = attendance_service.punch(current_user.id, punch_data.action, timestamp, punch_data.note)
        
        return AttendanceResponse.from_orm(new_record)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to punch: {str(e)}"
        )

@router.put("/{record_id}", response_model=AttendanceResponse, summary="更新打卡記錄")
async def update_attendance_record(
    record_id: int,
    record_data: AttendanceUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    更新打卡記錄。
    
    - 用戶可以更新自己的記錄
    - 管理員可以更新任何記錄
    - 檢查記錄序列的邏輯性
    """
    try:
        record = db.query(AttendanceRecord).filter(AttendanceRecord.id == record_id).first()
        
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attendance record not found"
            )
        
        # 權限檢查
        if current_user.role != "admin" and record.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied to update this record"
            )
        
        # 使用 AttendanceService 更新記錄
        attendance_service = AttendanceService(db)
        updated_record = attendance_service.update_record(record_id, record_data)
        
        return AttendanceResponse.from_orm(updated_record)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update attendance record: {str(e)}"
        )

@router.delete("/{record_id}", response_model=dict, summary="刪除打卡記錄")
async def delete_attendance_record(
    record_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    刪除打卡記錄。
    
    - 僅管理員可以刪除記錄
    """
    try:
        record = db.query(AttendanceRecord).filter(AttendanceRecord.id == record_id).first()
        
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attendance record not found"
            )
        
        # 刪除記錄
        db.delete(record)
        db.commit()
        
        return {
            "success": True,
            "message": "Attendance record deleted successfully",
            "record_id": record_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete attendance record: {str(e)}"
        )

@router.get("/user/{user_id}", response_model=AttendanceListResponse, summary="取得指定用戶的打卡記錄")
async def get_user_attendance_records(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    取得指定用戶的打卡記錄。
    
    - 用戶可以查看自己的記錄
    - 管理員可以查看任何用戶的記錄
    """
    try:
        # 權限檢查
        if current_user.role != "admin" and user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied to view other users' records"
            )
        
        # 檢查用戶是否存在
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # 驗證分頁參數
        skip, limit = validate_pagination_params(skip, limit)
        
        # 構建查詢
        query = db.query(AttendanceRecord).filter(AttendanceRecord.user_id == user_id)
        
        if start_date:
            query = query.filter(func.date(AttendanceRecord.timestamp) >= start_date)
        
        if end_date:
            query = query.filter(func.date(AttendanceRecord.timestamp) <= end_date)
        
        # 取得總數和記錄
        total = query.count()
        records = query.order_by(desc(AttendanceRecord.timestamp)).offset(skip).limit(limit).all()
        
        return AttendanceListResponse(
            records=[AttendanceResponse.from_orm(record) for record in records],
            total=total,
            skip=skip,
            limit=limit
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user attendance records: {str(e)}"
        )

@router.get("/daily/{target_date}", response_model=List[AttendanceDailySummary], summary="取得指定日期的打卡摘要")
async def get_daily_attendance_summary(
    target_date: date,
    user_id: Optional[int] = Query(None, description="指定用戶ID，不指定則返回所有用戶"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    取得指定日期的每日打卡摘要。
    
    - 管理員可以查看所有用戶的摘要
    - 普通用戶只能查看自己的摘要
    """
    try:
        # 權限檢查
        if current_user.role != "admin":
            user_id = current_user.id
        
        # 使用 AttendanceService 取得每日摘要
        attendance_service = AttendanceService(db)
        summaries = attendance_service.get_daily_summary(target_date, user_id)
        
        return summaries
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get daily attendance summary: {str(e)}"
        )

@router.get("/today/me", response_model=List[AttendanceResponse], summary="取得我今日的打卡記錄")
async def get_my_today_records(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    取得當前用戶今日的打卡記錄。
    
    - 用戶查看自己今日的所有打卡記錄
    """
    try:
        today = date.today()
        
        records = db.query(AttendanceRecord).filter(
            AttendanceRecord.user_id == current_user.id,
            func.date(AttendanceRecord.timestamp) == today
        ).order_by(AttendanceRecord.timestamp).all()
        
        return [AttendanceResponse.from_orm(record) for record in records]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get today's records: {str(e)}"
        )

@router.get("/stats/overview", response_model=AttendanceStats, summary="取得打卡統計概覽")
async def get_attendance_stats(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    取得打卡統計概覽。
    
    - 僅管理員可以查看
    - 包含總記錄數、今日記錄數等統計資料
    """
    try:
        today = date.today()
        
        # 總記錄數
        total_records = db.query(AttendanceRecord).count()
        
        # 今日記錄數
        today_records = db.query(AttendanceRecord).filter(
            func.date(AttendanceRecord.timestamp) == today
        ).count()
        
        # 今日有打卡的用戶數
        users_punched_today = db.query(AttendanceRecord.user_id).filter(
            func.date(AttendanceRecord.timestamp) == today
        ).distinct().count()
        
        # 最常見的打卡動作
        most_common_action_result = db.query(
            AttendanceRecord.action,
            func.count(AttendanceRecord.id).label('count')
        ).group_by(AttendanceRecord.action).order_by(desc('count')).first()
        
        most_common_action = most_common_action_result[0] if most_common_action_result else "none"
        
        return AttendanceStats(
            total_records=total_records,
            today_records=today_records,
            users_punched_today=users_punched_today,
            most_common_action=most_common_action
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get attendance stats: {str(e)}"
        )

@router.get("/validate/sequence/{user_id}", response_model=dict, summary="驗證用戶打卡序列")
async def validate_attendance_sequence(
    user_id: int,
    start_date: Optional[date] = Query(None, description="開始日期"),
    end_date: Optional[date] = Query(None, description="結束日期"),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    驗證用戶打卡序列的邏輯性。
    
    - 僅管理員可以使用
    - 檢查打卡動作的順序是否合理
    """
    try:
        # 使用 AttendanceService 驗證序列
        attendance_service = AttendanceService(db)
        validation_result = attendance_service.validate_user_sequence(user_id, start_date, end_date)
        
        return validation_result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate attendance sequence: {str(e)}"
        )