"""
Reports web routes for Punch Bot
"""
from fastapi import APIRouter, Request, Depends, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc, extract
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List
import calendar

from app.database import get_db
from app.models.user import User
from app.models.attendance import AttendanceRecord
from app.models.leave import LeaveRecord

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/", response_class=HTMLResponse)
async def reports_dashboard(request: Request, db: Session = Depends(get_db)):
    """報表儀表板頁面"""
    today = datetime.now().date()
    current_month = today.replace(day=1)
    last_month = (current_month - timedelta(days=1)).replace(day=1)
    
    # 本月統計
    current_month_stats = get_monthly_stats(db, current_month.year, current_month.month)
    
    # 上月統計
    last_month_stats = get_monthly_stats(db, last_month.year, last_month.month)
    
    # 部門統計
    department_stats = get_department_stats(db, current_month.year, current_month.month)
    
    return templates.TemplateResponse("reports/dashboard.html", {
        "request": request,
        "current_month": current_month,
        "last_month": last_month,
        "current_month_stats": current_month_stats,
        "last_month_stats": last_month_stats,
        "department_stats": department_stats
    })


@router.get("/monthly", response_class=HTMLResponse)
async def monthly_report(
    request: Request,
    year: int = Query(default=datetime.now().year),
    month: int = Query(default=datetime.now().month),
    department: str = Query(default=""),
    db: Session = Depends(get_db)
):
    """月度報表頁面"""
    # 獲取月度統計
    stats = get_monthly_stats(db, year, month, department)
    
    # 獲取用戶詳細工時
    user_details = get_user_monthly_details(db, year, month, department)
    
    # 獲取所有部門用於過濾
    departments = db.query(User.department).distinct().filter(
        User.department.isnot(None)
    ).all()
    departments = [d[0] for d in departments if d[0]]
    
    # 月份導航
    current_date = date(year, month, 1)
    prev_month = current_date - timedelta(days=1)
    next_month = (current_date.replace(day=28) + timedelta(days=4)).replace(day=1)
    
    return templates.TemplateResponse("reports/monthly.html", {
        "request": request,
        "year": year,
        "month": month,
        "month_name": calendar.month_name[month],
        "department": department,
        "stats": stats,
        "user_details": user_details,
        "departments": departments,
        "prev_month": prev_month,
        "next_month": next_month
    })


@router.get("/weekly", response_class=HTMLResponse)
async def weekly_report(
    request: Request,
    start_date: str = Query(default=""),
    department: str = Query(default=""),
    db: Session = Depends(get_db)
):
    """週報表頁面"""
    if not start_date:
        today = datetime.now().date()
        start_date = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
    
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = start_dt + timedelta(days=6)
    except ValueError:
        today = datetime.now().date()
        start_dt = today - timedelta(days=today.weekday())
        end_dt = start_dt + timedelta(days=6)
        start_date = start_dt.strftime('%Y-%m-%d')
    
    # 獲取週統計
    stats = get_weekly_stats(db, start_dt, end_dt, department)
    
    # 獲取用戶詳細工時
    user_details = get_user_weekly_details(db, start_dt, end_dt, department)
    
    # 獲取所有部門用於過濾
    departments = db.query(User.department).distinct().filter(
        User.department.isnot(None)
    ).all()
    departments = [d[0] for d in departments if d[0]]
    
    # 週導航
    prev_week = start_dt - timedelta(days=7)
    next_week = start_dt + timedelta(days=7)
    
    return templates.TemplateResponse("reports/weekly.html", {
        "request": request,
        "start_date": start_date,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "department": department,
        "stats": stats,
        "user_details": user_details,
        "departments": departments,
        "prev_week": prev_week.strftime('%Y-%m-%d'),
        "next_week": next_week.strftime('%Y-%m-%d')
    })


@router.get("/daily", response_class=HTMLResponse)
async def daily_report(
    request: Request,
    report_date: str = Query(default=""),
    department: str = Query(default=""),
    db: Session = Depends(get_db)
):
    """日報表頁面"""
    if not report_date:
        report_date = datetime.now().date().strftime('%Y-%m-%d')
    
    try:
        target_date = datetime.strptime(report_date, '%Y-%m-%d').date()
    except ValueError:
        target_date = datetime.now().date()
        report_date = target_date.strftime('%Y-%m-%d')
    
    # 獲取日統計
    stats = get_daily_stats(db, target_date, department)
    
    # 獲取用戶詳細記錄
    user_details = get_user_daily_details(db, target_date, department)
    
    # 獲取所有部門用於過濾
    departments = db.query(User.department).distinct().filter(
        User.department.isnot(None)
    ).all()
    departments = [d[0] for d in departments if d[0]]
    
    # 日期導航
    prev_date = target_date - timedelta(days=1)
    next_date = target_date + timedelta(days=1)
    
    return templates.TemplateResponse("reports/daily.html", {
        "request": request,
        "report_date": report_date,
        "target_date": target_date,
        "department": department,
        "stats": stats,
        "user_details": user_details,
        "departments": departments,
        "prev_date": prev_date.strftime('%Y-%m-%d'),
        "next_date": next_date.strftime('%Y-%m-%d')
    })


@router.get("/user/{user_id}", response_class=HTMLResponse)
async def user_report(
    request: Request,
    user_id: int,
    start_date: str = Query(default=""),
    end_date: str = Query(default=""),
    db: Session = Depends(get_db)
):
    """個人報表頁面"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用戶不存在")
    
    # 預設為本月
    if not start_date:
        today = datetime.now().date()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        end_date = end_date.strftime('%Y-%m-%d')
    
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        today = datetime.now().date()
        start_dt = today.replace(day=1)
        end_dt = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        start_date = start_dt.strftime('%Y-%m-%d')
        end_date = end_dt.strftime('%Y-%m-%d')
    
    # 獲取用戶統計
    stats = get_user_period_stats(db, user_id, start_dt, end_dt)
    
    # 獲取每日詳情
    daily_details = get_user_daily_breakdown(db, user_id, start_dt, end_dt)
    
    return templates.TemplateResponse("reports/user.html", {
        "request": request,
        "user": user,
        "start_date": start_date,
        "end_date": end_date,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "stats": stats,
        "daily_details": daily_details
    })


# 輔助函數

def get_monthly_stats(db: Session, year: int, month: int, department: str = "") -> Dict:
    """獲取月度統計"""
    query = db.query(User).filter(User.is_active == True)
    if department:
        query = query.filter(User.department == department)
    
    total_users = query.count()
    
    # 計算工作日
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)
    
    work_days = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # 週一到週五
            work_days += 1
        current += timedelta(days=1)
    
    # 打卡記錄統計
    attendance_query = db.query(AttendanceRecord).join(User).filter(
        and_(
            extract('year', AttendanceRecord.timestamp) == year,
            extract('month', AttendanceRecord.timestamp) == month,
            User.is_active == True
        )
    )
    if department:
        attendance_query = attendance_query.filter(User.department == department)
    
    total_records = attendance_query.count()
    
    return {
        "total_users": total_users,
        "work_days": work_days,
        "total_records": total_records,
        "avg_records_per_day": round(total_records / work_days, 2) if work_days > 0 else 0
    }


def get_department_stats(db: Session, year: int, month: int) -> List[Dict]:
    """獲取部門統計"""
    departments = db.query(User.department).distinct().filter(
        User.department.isnot(None)
    ).all()
    
    stats = []
    for dept in departments:
        dept_name = dept[0]
        dept_users = db.query(User).filter(
            and_(User.department == dept_name, User.is_active == True)
        ).count()
        
        dept_records = db.query(AttendanceRecord).join(User).filter(
            and_(
                User.department == dept_name,
                extract('year', AttendanceRecord.timestamp) == year,
                extract('month', AttendanceRecord.timestamp) == month,
                User.is_active == True
            )
        ).count()
        
        stats.append({
            "department": dept_name,
            "users": dept_users,
            "records": dept_records,
            "avg_per_user": round(dept_records / dept_users, 2) if dept_users > 0 else 0
        })
    
    return sorted(stats, key=lambda x: x["records"], reverse=True)


def get_user_monthly_details(db: Session, year: int, month: int, department: str = "") -> List[Dict]:
    """獲取用戶月度詳細數據"""
    query = db.query(User).filter(User.is_active == True)
    if department:
        query = query.filter(User.department == department)
    
    users = query.all()
    details = []
    
    for user in users:
        records = db.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.user_id == user.id,
                extract('year', AttendanceRecord.timestamp) == year,
                extract('month', AttendanceRecord.timestamp) == month
            )
        ).count()
        
        details.append({
            "user": user,
            "total_records": records,
            "expected_records": user.standard_hours * 2 * 22,  # 假設22個工作日
            "completion_rate": round((records / (user.standard_hours * 2 * 22)) * 100, 1) if records > 0 else 0
        })
    
    return sorted(details, key=lambda x: x["completion_rate"], reverse=True)


def get_weekly_stats(db: Session, start_date: date, end_date: date, department: str = "") -> Dict:
    """獲取週統計"""
    query = db.query(User).filter(User.is_active == True)
    if department:
        query = query.filter(User.department == department)
    
    total_users = query.count()
    
    attendance_query = db.query(AttendanceRecord).join(User).filter(
        and_(
            func.date(AttendanceRecord.timestamp) >= start_date,
            func.date(AttendanceRecord.timestamp) <= end_date,
            User.is_active == True
        )
    )
    if department:
        attendance_query = attendance_query.filter(User.department == department)
    
    total_records = attendance_query.count()
    
    return {
        "total_users": total_users,
        "total_records": total_records,
        "avg_records_per_user": round(total_records / total_users, 2) if total_users > 0 else 0
    }


def get_user_weekly_details(db: Session, start_date: date, end_date: date, department: str = "") -> List[Dict]:
    """獲取用戶週詳細數據"""
    query = db.query(User).filter(User.is_active == True)
    if department:
        query = query.filter(User.department == department)
    
    users = query.all()
    details = []
    
    for user in users:
        records = db.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.user_id == user.id,
                func.date(AttendanceRecord.timestamp) >= start_date,
                func.date(AttendanceRecord.timestamp) <= end_date
            )
        ).count()
        
        details.append({
            "user": user,
            "total_records": records
        })
    
    return sorted(details, key=lambda x: x["total_records"], reverse=True)


def get_daily_stats(db: Session, target_date: date, department: str = "") -> Dict:
    """獲取日統計"""
    query = db.query(User).filter(User.is_active == True)
    if department:
        query = query.filter(User.department == department)
    
    total_users = query.count()
    
    attendance_query = db.query(AttendanceRecord).join(User).filter(
        and_(
            func.date(AttendanceRecord.timestamp) == target_date,
            User.is_active == True
        )
    )
    if department:
        attendance_query = attendance_query.filter(User.department == department)
    
    total_records = attendance_query.count()
    
    # 統計各種動作
    actions_count = {}
    for action in ['in', 'out', 'break', 'back']:
        count = attendance_query.filter(AttendanceRecord.action == action).count()
        actions_count[action] = count
    
    return {
        "total_users": total_users,
        "total_records": total_records,
        "actions": actions_count,
        "attendance_rate": round((actions_count.get('in', 0) / total_users) * 100, 1) if total_users > 0 else 0
    }


def get_user_daily_details(db: Session, target_date: date, department: str = "") -> List[Dict]:
    """獲取用戶日詳細數據"""
    query = db.query(User).filter(User.is_active == True)
    if department:
        query = query.filter(User.department == department)
    
    users = query.all()
    details = []
    
    for user in users:
        records = db.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.user_id == user.id,
                func.date(AttendanceRecord.timestamp) == target_date
            )
        ).order_by(AttendanceRecord.timestamp).all()
        
        details.append({
            "user": user,
            "records": records,
            "total_records": len(records)
        })
    
    return details


def get_user_period_stats(db: Session, user_id: int, start_date: date, end_date: date) -> Dict:
    """獲取用戶期間統計"""
    records = db.query(AttendanceRecord).filter(
        and_(
            AttendanceRecord.user_id == user_id,
            func.date(AttendanceRecord.timestamp) >= start_date,
            func.date(AttendanceRecord.timestamp) <= end_date
        )
    ).all()
    
    actions_count = {}
    for action in ['in', 'out', 'break', 'back']:
        actions_count[action] = len([r for r in records if r.action == action])
    
    return {
        "total_records": len(records),
        "actions": actions_count,
        "period_days": (end_date - start_date).days + 1
    }


def get_user_daily_breakdown(db: Session, user_id: int, start_date: date, end_date: date) -> List[Dict]:
    """獲取用戶每日明細"""
    daily_data = []
    current = start_date
    
    while current <= end_date:
        records = db.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.user_id == user_id,
                func.date(AttendanceRecord.timestamp) == current
            )
        ).order_by(AttendanceRecord.timestamp).all()
        
        daily_data.append({
            "date": current,
            "records": records,
            "total_records": len(records)
        })
        
        current += timedelta(days=1)
    
    return daily_data


@router.get("/export/monthly")
async def export_monthly_csv(
    year: int = Query(default=datetime.now().year),
    month: int = Query(default=datetime.now().month),
    department: str = Query(default=""),
    db: Session = Depends(get_db)
):
    """匯出月度報表CSV"""
    user_details = get_user_monthly_details(db, year, month, department)
    
    def generate_csv():
        yield "用戶名稱,部門,總記錄數,完成率\n"
        for detail in user_details:
            user = detail["user"]
            yield f"{user.internal_real_name},{user.department or ''},"
            yield f"{detail['total_records']},{detail['completion_rate']}%\n"
    
    filename = f"monthly_report_{year}_{month:02d}.csv"
    if department:
        filename = f"monthly_report_{year}_{month:02d}_{department}.csv"
    
    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )