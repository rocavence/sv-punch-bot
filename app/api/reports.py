"""
Reports API routes for generating attendance reports and analytics.
"""

import io
import csv
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from enum import Enum

from app.database import get_db
from app.models.user import User
from app.models.attendance import AttendanceRecord
from app.utils.auth import get_current_active_user, get_current_admin_user
from app.utils.validators import validate_pagination_params, DataValidator
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])

# Enums for report types and formats
class ReportType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly" 
    MONTHLY = "monthly"
    CUSTOM = "custom"

class ExportFormat(str, Enum):
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"

class ReportPeriod(str, Enum):
    TODAY = "today"
    YESTERDAY = "yesterday"
    THIS_WEEK = "this_week"
    LAST_WEEK = "last_week"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"

# Response models
class WorkHoursSummary(BaseModel):
    """工時摘要模型"""
    user_id: int
    user_name: str
    department: Optional[str]
    total_work_hours: float
    total_break_hours: float
    expected_hours: float
    overtime_hours: float
    attendance_rate: float
    days_worked: int
    days_expected: int

class AttendanceReport(BaseModel):
    """出勤報表模型"""
    report_type: ReportType
    start_date: date
    end_date: date
    generated_at: datetime
    total_users: int
    work_hours_summary: List[WorkHoursSummary]
    department_stats: Dict[str, Any]
    overall_stats: Dict[str, Any]

class ExportResponse(BaseModel):
    """匯出回應模型"""
    success: bool
    message: str
    filename: str
    download_url: Optional[str] = None

@router.get("/daily/{report_date}", response_model=AttendanceReport, summary="取得日報表")
async def get_daily_report(
    report_date: date,
    department: Optional[str] = Query(None, description="部門篩選"),
    user_id: Optional[int] = Query(None, description="用戶篩選"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    取得指定日期的出勤日報表。
    
    - 普通用戶只能查看自己的報表
    - 管理員可以查看所有用戶的報表
    """
    try:
        # 權限檢查
        if current_user.role != "admin":
            user_id = current_user.id
            department = None
        
        # 使用 ReportService 生成報表
        report_service = ReportService(db)
        report = await report_service.generate_daily_report(
            report_date, department, user_id
        )
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate daily report: {str(e)}"
        )

@router.get("/weekly/{start_date}", response_model=AttendanceReport, summary="取得週報表")
async def get_weekly_report(
    start_date: date,
    department: Optional[str] = Query(None, description="部門篩選"),
    user_id: Optional[int] = Query(None, description="用戶篩選"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    取得指定週的出勤週報表。
    
    - start_date 為該週的開始日期（週一）
    - 普通用戶只能查看自己的報表
    """
    try:
        # 權限檢查
        if current_user.role != "admin":
            user_id = current_user.id
            department = None
        
        # 計算週的結束日期
        end_date = start_date + timedelta(days=6)
        
        # 使用 ReportService 生成報表
        report_service = ReportService(db)
        report = await report_service.generate_weekly_report(
            start_date, end_date, department, user_id
        )
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate weekly report: {str(e)}"
        )

@router.get("/monthly/{year}/{month}", response_model=AttendanceReport, summary="取得月報表")
async def get_monthly_report(
    year: int,
    month: int,
    department: Optional[str] = Query(None, description="部門篩選"),
    user_id: Optional[int] = Query(None, description="用戶篩選"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    取得指定月份的出勤月報表。
    
    - 普通用戶只能查看自己的報表
    """
    try:
        # 權限檢查
        if current_user.role != "admin":
            user_id = current_user.id
            department = None
        
        # 驗證月份
        if month < 1 or month > 12:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid month. Must be between 1 and 12"
            )
        
        # 計算月份的開始和結束日期
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        # 使用 ReportService 生成報表
        report_service = ReportService(db)
        report = await report_service.generate_monthly_report(
            start_date, end_date, department, user_id
        )
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate monthly report: {str(e)}"
        )

@router.get("/custom", response_model=AttendanceReport, summary="取得自訂期間報表")
async def get_custom_report(
    start_date: date = Query(..., description="開始日期"),
    end_date: date = Query(..., description="結束日期"),
    department: Optional[str] = Query(None, description="部門篩選"),
    user_id: Optional[int] = Query(None, description="用戶篩選"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    取得自訂時間期間的出勤報表。
    
    - 普通用戶只能查看自己的報表
    - 時間範圍不能超過 3 個月
    """
    try:
        # 權限檢查
        if current_user.role != "admin":
            user_id = current_user.id
            department = None
        
        # 驗證日期範圍
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date must be before or equal to end date"
            )
        
        # 檢查日期範圍是否過長（3個月限制）
        if (end_date - start_date).days > 90:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Date range cannot exceed 90 days"
            )
        
        # 使用 ReportService 生成報表
        report_service = ReportService(db)
        report = await report_service.generate_custom_report(
            start_date, end_date, department, user_id
        )
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate custom report: {str(e)}"
        )

@router.get("/user/{user_id}", response_model=AttendanceReport, summary="取得個人報表")
async def get_user_report(
    user_id: int,
    start_date: date = Query(..., description="開始日期"),
    end_date: date = Query(..., description="結束日期"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    取得指定用戶的個人出勤報表。
    
    - 用戶只能查看自己的報表
    - 管理員可以查看任何用戶的報表
    """
    try:
        # 權限檢查
        if current_user.role != "admin" and user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied to view other users' reports"
            )
        
        # 檢查目標用戶是否存在
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # 使用 ReportService 生成個人報表
        report_service = ReportService(db)
        report = await report_service.generate_user_report(
            user_id, start_date, end_date
        )
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate user report: {str(e)}"
        )

@router.post("/export", summary="匯出報表")
async def export_report(
    report_type: ReportType,
    export_format: ExportFormat,
    start_date: date,
    end_date: Optional[date] = None,
    department: Optional[str] = None,
    user_id: Optional[int] = None,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    匯出報表為指定格式。
    
    - 僅管理員可以匯出報表
    - 支援 CSV、Excel、PDF 格式
    """
    try:
        # 使用 ReportService 生成匯出檔案
        report_service = ReportService(db)
        
        if report_type == ReportType.DAILY:
            file_content, filename, content_type = await report_service.export_daily_report(
                start_date, export_format, department, user_id
            )
        elif report_type == ReportType.WEEKLY:
            end_date = end_date or start_date + timedelta(days=6)
            file_content, filename, content_type = await report_service.export_weekly_report(
                start_date, end_date, export_format, department, user_id
            )
        elif report_type == ReportType.MONTHLY:
            file_content, filename, content_type = await report_service.export_monthly_report(
                start_date.year, start_date.month, export_format, department, user_id
            )
        else:  # CUSTOM
            end_date = end_date or start_date
            file_content, filename, content_type = await report_service.export_custom_report(
                start_date, end_date, export_format, department, user_id
            )
        
        # 返回檔案下載回應
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export report: {str(e)}"
        )

@router.get("/quick/{period}", response_model=AttendanceReport, summary="取得快速報表")
async def get_quick_report(
    period: ReportPeriod,
    department: Optional[str] = Query(None, description="部門篩選"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    取得快速預定義期間的報表。
    
    - 支援今日、昨日、本週、上週、本月、上月等預定義期間
    - 普通用戶只能查看自己的資料
    """
    try:
        # 權限檢查
        user_id = None if current_user.role == "admin" else current_user.id
        if current_user.role != "admin":
            department = None
        
        # 計算日期範圍
        today = date.today()
        
        if period == ReportPeriod.TODAY:
            start_date = end_date = today
        elif period == ReportPeriod.YESTERDAY:
            start_date = end_date = today - timedelta(days=1)
        elif period == ReportPeriod.THIS_WEEK:
            days_since_monday = today.weekday()
            start_date = today - timedelta(days=days_since_monday)
            end_date = start_date + timedelta(days=6)
        elif period == ReportPeriod.LAST_WEEK:
            days_since_monday = today.weekday()
            this_monday = today - timedelta(days=days_since_monday)
            start_date = this_monday - timedelta(days=7)
            end_date = start_date + timedelta(days=6)
        elif period == ReportPeriod.THIS_MONTH:
            start_date = today.replace(day=1)
            if today.month == 12:
                end_date = date(today.year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)
        elif period == ReportPeriod.LAST_MONTH:
            if today.month == 1:
                start_date = date(today.year - 1, 12, 1)
                end_date = date(today.year, 1, 1) - timedelta(days=1)
            else:
                start_date = date(today.year, today.month - 1, 1)
                end_date = date(today.year, today.month, 1) - timedelta(days=1)
        
        # 使用 ReportService 生成報表
        report_service = ReportService(db)
        report = await report_service.generate_custom_report(
            start_date, end_date, department, user_id
        )
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate quick report: {str(e)}"
        )

@router.get("/analytics/department", response_model=Dict[str, Any], summary="部門分析報表")
async def get_department_analytics(
    start_date: date = Query(..., description="開始日期"),
    end_date: date = Query(..., description="結束日期"),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    取得部門分析報表。
    
    - 僅管理員可以查看
    - 比較各部門的出勤狀況
    """
    try:
        # 使用 ReportService 生成部門分析
        report_service = ReportService(db)
        analytics = await report_service.generate_department_analytics(start_date, end_date)
        
        return analytics
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate department analytics: {str(e)}"
        )

@router.get("/analytics/overtime", response_model=List[Dict[str, Any]], summary="加班分析報表")
async def get_overtime_analytics(
    start_date: date = Query(..., description="開始日期"),
    end_date: date = Query(..., description="結束日期"),
    department: Optional[str] = Query(None, description="部門篩選"),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    取得加班時數分析報表。
    
    - 僅管理員可以查看
    - 分析各用戶的加班狀況
    """
    try:
        # 使用 ReportService 生成加班分析
        report_service = ReportService(db)
        analytics = await report_service.generate_overtime_analytics(
            start_date, end_date, department
        )
        
        return analytics
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate overtime analytics: {str(e)}"
        )