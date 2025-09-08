"""
Dashboard web routes for Punch Bot
"""
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
import calendar

from app.database import get_db
from app.models.user import User
from app.models.attendance import AttendanceRecord
from app.models.leave import LeaveRecord

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """主儀表板頁面"""
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    # 今日統計
    total_users = db.query(User).filter(User.is_active == True).count()
    
    # 今日打卡統計
    today_records = db.query(AttendanceRecord).join(User).filter(
        and_(
            func.date(AttendanceRecord.timestamp) == today,
            User.is_active == True
        )
    ).all()
    
    # 統計今日打卡狀態
    users_punched_in = set()
    users_punched_out = set()
    
    for record in today_records:
        if record.action == 'in':
            users_punched_in.add(record.user_id)
        elif record.action == 'out':
            users_punched_out.add(record.user_id)
    
    present_count = len(users_punched_in)
    completed_count = len(users_punched_out)
    absent_count = total_users - present_count
    
    # 本週工時趨勢數據
    week_stats = []
    for i in range(7):
        day = start_of_week + timedelta(days=i)
        day_records = db.query(AttendanceRecord).join(User).filter(
            and_(
                func.date(AttendanceRecord.timestamp) == day,
                User.is_active == True
            )
        ).count()
        week_stats.append({
            'date': day.strftime('%Y-%m-%d'),
            'day_name': calendar.day_name[day.weekday()],
            'records': day_records
        })
    
    # 休假申請統計
    pending_leaves = db.query(LeaveRecord).filter(
        LeaveRecord.status == 'pending'
    ).count()
    
    # 異常打卡提醒（只有打卡進入但未打卡離開的記錄）
    anomaly_users = db.query(User).join(AttendanceRecord).filter(
        and_(
            func.date(AttendanceRecord.timestamp) == today,
            AttendanceRecord.action == 'in',
            User.is_active == True,
            ~User.id.in_([uid for uid in users_punched_out])
        )
    ).distinct().all()
    
    # 最近打卡記錄
    recent_records = db.query(AttendanceRecord).join(User).filter(
        User.is_active == True
    ).order_by(AttendanceRecord.timestamp.desc()).limit(10).all()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "today": today,
        "stats": {
            "total_users": total_users,
            "present_count": present_count,
            "completed_count": completed_count,
            "absent_count": absent_count,
            "pending_leaves": pending_leaves,
            "anomaly_count": len(anomaly_users)
        },
        "week_stats": week_stats,
        "anomaly_users": anomaly_users,
        "recent_records": recent_records
    })


@router.get("/api/stats/realtime")
async def get_realtime_stats(db: Session = Depends(get_db)):
    """獲取即時統計數據（AJAX API）"""
    today = datetime.now().date()
    
    # 即時統計
    total_users = db.query(User).filter(User.is_active == True).count()
    
    today_records = db.query(AttendanceRecord).join(User).filter(
        and_(
            func.date(AttendanceRecord.timestamp) == today,
            User.is_active == True
        )
    ).all()
    
    users_punched_in = set()
    users_punched_out = set()
    
    for record in today_records:
        if record.action == 'in':
            users_punched_in.add(record.user_id)
        elif record.action == 'out':
            users_punched_out.add(record.user_id)
    
    return {
        "total_users": total_users,
        "present_count": len(users_punched_in),
        "completed_count": len(users_punched_out),
        "absent_count": total_users - len(users_punched_in),
        "last_updated": datetime.now().isoformat()
    }


@router.get("/api/stats/weekly")
async def get_weekly_stats(db: Session = Depends(get_db)):
    """獲取週統計數據（AJAX API）"""
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    
    week_data = []
    for i in range(7):
        day = start_of_week + timedelta(days=i)
        day_records = db.query(AttendanceRecord).join(User).filter(
            and_(
                func.date(AttendanceRecord.timestamp) == day,
                User.is_active == True
            )
        ).count()
        
        week_data.append({
            'date': day.strftime('%m/%d'),
            'day': calendar.day_name[day.weekday()][:3],
            'records': day_records
        })
    
    return {"week_data": week_data}