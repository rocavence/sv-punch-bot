"""
Attendance records web routes for Punch Bot
"""
from fastapi import APIRouter, Request, Depends, Form, HTTPException, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from datetime import datetime, date, timedelta
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.models.attendance import AttendanceRecord

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/", response_class=HTMLResponse)
async def attendance_list(
    request: Request,
    page: int = 1,
    per_page: int = 50,
    search: str = "",
    department: str = "",
    action: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """打卡記錄列表頁面"""
    query = db.query(AttendanceRecord).join(User)
    
    # 搜尋過濾
    if search:
        query = query.filter(
            or_(
                User.internal_real_name.ilike(f"%{search}%"),
                User.slack_username.ilike(f"%{search}%")
            )
        )
    
    # 部門過濾
    if department:
        query = query.filter(User.department == department)
    
    # 動作過濾
    if action:
        query = query.filter(AttendanceRecord.action == action)
    
    # 日期範圍過濾
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(func.date(AttendanceRecord.timestamp) >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(func.date(AttendanceRecord.timestamp) <= end_dt)
        except ValueError:
            pass
    
    # 排序
    query = query.order_by(desc(AttendanceRecord.timestamp))
    
    # 分頁
    total = query.count()
    records = query.offset((page - 1) * per_page).limit(per_page).all()
    
    # 獲取所有部門用於過濾選項
    departments = db.query(User.department).distinct().filter(
        User.department.isnot(None)
    ).all()
    departments = [d[0] for d in departments if d[0]]
    
    # 計算分頁信息
    total_pages = (total + per_page - 1) // per_page
    
    return templates.TemplateResponse("attendance/list.html", {
        "request": request,
        "records": records,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "search": search,
        "department": department,
        "action": action,
        "start_date": start_date,
        "end_date": end_date,
        "departments": departments,
        "actions": ["in", "out", "break", "back"],
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1,
        "next_page": page + 1
    })


@router.get("/add", response_class=HTMLResponse)
async def add_record_form(request: Request, db: Session = Depends(get_db)):
    """新增打卡記錄表單頁面"""
    users = db.query(User).filter(User.is_active == True).order_by(User.internal_real_name).all()
    
    return templates.TemplateResponse("attendance/add.html", {
        "request": request,
        "users": users,
        "actions": ["in", "out", "break", "back"]
    })


@router.post("/add")
async def add_record(
    user_id: int = Form(...),
    action: str = Form(...),
    timestamp: str = Form(...),
    note: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """新增打卡記錄處理"""
    # 驗證用戶存在
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用戶不存在")
    
    # 解析時間
    try:
        timestamp_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="時間格式錯誤")
    
    # 建立記錄
    record = AttendanceRecord(
        user_id=user_id,
        action=action,
        timestamp=timestamp_dt,
        note=note,
        is_auto=False
    )
    
    db.add(record)
    db.commit()
    
    return RedirectResponse(url="/admin/attendance", status_code=303)


@router.get("/{record_id}", response_class=HTMLResponse)
async def record_detail(request: Request, record_id: int, db: Session = Depends(get_db)):
    """打卡記錄詳情頁面"""
    record = db.query(AttendanceRecord).join(User).filter(
        AttendanceRecord.id == record_id
    ).first()
    
    if not record:
        raise HTTPException(status_code=404, detail="記錄不存在")
    
    return templates.TemplateResponse("attendance/detail.html", {
        "request": request,
        "record": record
    })


@router.get("/{record_id}/edit", response_class=HTMLResponse)
async def edit_record_form(request: Request, record_id: int, db: Session = Depends(get_db)):
    """編輯打卡記錄表單頁面"""
    record = db.query(AttendanceRecord).join(User).filter(
        AttendanceRecord.id == record_id
    ).first()
    
    if not record:
        raise HTTPException(status_code=404, detail="記錄不存在")
    
    users = db.query(User).filter(User.is_active == True).order_by(User.internal_real_name).all()
    
    return templates.TemplateResponse("attendance/edit.html", {
        "request": request,
        "record": record,
        "users": users,
        "actions": ["in", "out", "break", "back"]
    })


@router.post("/{record_id}/edit")
async def edit_record(
    record_id: int,
    action: str = Form(...),
    timestamp: str = Form(...),
    note: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """編輯打卡記錄處理"""
    record = db.query(AttendanceRecord).filter(AttendanceRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="記錄不存在")
    
    # 解析時間
    try:
        timestamp_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="時間格式錯誤")
    
    # 更新記錄
    record.action = action
    record.timestamp = timestamp_dt
    record.note = note
    
    db.commit()
    
    return RedirectResponse(url=f"/admin/attendance/{record_id}", status_code=303)


@router.post("/{record_id}/delete")
async def delete_record(record_id: int, db: Session = Depends(get_db)):
    """刪除打卡記錄"""
    record = db.query(AttendanceRecord).filter(AttendanceRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="記錄不存在")
    
    db.delete(record)
    db.commit()
    
    return {"status": "success"}


@router.get("/user/{user_id}", response_class=HTMLResponse)
async def user_attendance(
    request: Request,
    user_id: int,
    page: int = 1,
    per_page: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """特定用戶打卡記錄頁面"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用戶不存在")
    
    query = db.query(AttendanceRecord).filter(AttendanceRecord.user_id == user_id)
    
    # 日期範圍過濾
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(func.date(AttendanceRecord.timestamp) >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(func.date(AttendanceRecord.timestamp) <= end_dt)
        except ValueError:
            pass
    
    # 排序和分頁
    query = query.order_by(desc(AttendanceRecord.timestamp))
    total = query.count()
    records = query.offset((page - 1) * per_page).limit(per_page).all()
    
    # 計算分頁信息
    total_pages = (total + per_page - 1) // per_page
    
    return templates.TemplateResponse("attendance/user.html", {
        "request": request,
        "user": user,
        "records": records,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "start_date": start_date,
        "end_date": end_date,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1,
        "next_page": page + 1
    })


@router.get("/anomalies", response_class=HTMLResponse)
async def anomalies_list(request: Request, db: Session = Depends(get_db)):
    """異常打卡記錄頁面"""
    today = datetime.now().date()
    
    # 找出只有打卡進入但沒有打卡離開的用戶
    subquery = db.query(AttendanceRecord.user_id).filter(
        and_(
            func.date(AttendanceRecord.timestamp) == today,
            AttendanceRecord.action == 'out'
        )
    ).subquery()
    
    anomaly_records = db.query(AttendanceRecord).join(User).filter(
        and_(
            func.date(AttendanceRecord.timestamp) == today,
            AttendanceRecord.action == 'in',
            ~AttendanceRecord.user_id.in_(subquery),
            User.is_active == True
        )
    ).all()
    
    return templates.TemplateResponse("attendance/anomalies.html", {
        "request": request,
        "anomaly_records": anomaly_records,
        "today": today
    })


@router.get("/export/csv")
async def export_attendance_csv(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """匯出打卡記錄CSV"""
    from fastapi.responses import StreamingResponse
    
    query = db.query(AttendanceRecord).join(User)
    
    # 過濾條件
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(func.date(AttendanceRecord.timestamp) >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(func.date(AttendanceRecord.timestamp) <= end_dt)
        except ValueError:
            pass
    
    if user_id:
        query = query.filter(AttendanceRecord.user_id == user_id)
    
    records = query.order_by(desc(AttendanceRecord.timestamp)).all()
    
    def generate_csv():
        yield "用戶名稱,Slack用戶名,動作,時間,自動打卡,備註\n"
        for record in records:
            yield f"{record.user.internal_real_name},{record.user.slack_username},"
            yield f"{record.action},{record.timestamp},{record.is_auto},"
            yield f'"{record.note or ""}"\n'
    
    filename = "attendance_records.csv"
    if start_date and end_date:
        filename = f"attendance_{start_date}_to_{end_date}.csv"
    
    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )