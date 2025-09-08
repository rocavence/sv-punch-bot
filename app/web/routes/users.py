"""
Users management web routes for Punch Bot
"""
from fastapi import APIRouter, Request, Depends, Form, HTTPException, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import Optional
import csv
import io

from app.database import get_db
from app.models.user import User
from app.models.attendance import AttendanceRecord
from app.schemas.user import UserCreate, UserUpdate

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/", response_class=HTMLResponse)
async def users_list(
    request: Request,
    page: int = 1,
    per_page: int = 20,
    search: str = "",
    department: str = "",
    status: str = "",
    db: Session = Depends(get_db)
):
    """用戶列表頁面"""
    query = db.query(User)
    
    # 搜尋過濾
    if search:
        query = query.filter(
            or_(
                User.internal_real_name.ilike(f"%{search}%"),
                User.slack_username.ilike(f"%{search}%"),
                User.slack_email.ilike(f"%{search}%")
            )
        )
    
    # 部門過濾
    if department:
        query = query.filter(User.department == department)
    
    # 狀態過濾
    if status == "active":
        query = query.filter(User.is_active == True)
    elif status == "inactive":
        query = query.filter(User.is_active == False)
    
    # 分頁
    total = query.count()
    users = query.offset((page - 1) * per_page).limit(per_page).all()
    
    # 獲取所有部門用於過濾選項
    departments = db.query(User.department).distinct().filter(
        User.department.isnot(None)
    ).all()
    departments = [d[0] for d in departments if d[0]]
    
    # 計算分頁信息
    total_pages = (total + per_page - 1) // per_page
    
    return templates.TemplateResponse("users/list.html", {
        "request": request,
        "users": users,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "search": search,
        "department": department,
        "status": status,
        "departments": departments,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1,
        "next_page": page + 1
    })


@router.get("/add", response_class=HTMLResponse)
async def add_user_form(request: Request, db: Session = Depends(get_db)):
    """新增用戶表單頁面"""
    # 獲取所有部門用於選項
    departments = db.query(User.department).distinct().filter(
        User.department.isnot(None)
    ).all()
    departments = [d[0] for d in departments if d[0]]
    
    return templates.TemplateResponse("users/add.html", {
        "request": request,
        "departments": departments
    })


@router.post("/add")
async def add_user(
    slack_user_id: str = Form(...),
    slack_username: str = Form(...),
    internal_real_name: str = Form(...),
    slack_email: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    standard_hours: int = Form(8),
    role: str = Form("user"),
    db: Session = Depends(get_db)
):
    """新增用戶處理"""
    # 檢查是否已存在
    existing_user = db.query(User).filter(User.slack_user_id == slack_user_id).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="用戶已存在")
    
    # 建立新用戶
    user = User(
        slack_user_id=slack_user_id,
        slack_username=slack_username,
        internal_real_name=internal_real_name,
        slack_email=slack_email,
        department=department,
        standard_hours=standard_hours,
        role=role,
        is_active=True
    )
    
    db.add(user)
    db.commit()
    
    return RedirectResponse(url="/admin/users", status_code=303)


@router.get("/{user_id}", response_class=HTMLResponse)
async def user_detail(request: Request, user_id: int, db: Session = Depends(get_db)):
    """用戶詳情頁面"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用戶不存在")
    
    # 獲取最近的打卡記錄
    recent_records = db.query(AttendanceRecord).filter(
        AttendanceRecord.user_id == user_id
    ).order_by(AttendanceRecord.timestamp.desc()).limit(20).all()
    
    return templates.TemplateResponse("users/detail.html", {
        "request": request,
        "user": user,
        "recent_records": recent_records
    })


@router.get("/{user_id}/edit", response_class=HTMLResponse)
async def edit_user_form(request: Request, user_id: int, db: Session = Depends(get_db)):
    """編輯用戶表單頁面"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用戶不存在")
    
    # 獲取所有部門用於選項
    departments = db.query(User.department).distinct().filter(
        User.department.isnot(None)
    ).all()
    departments = [d[0] for d in departments if d[0]]
    
    return templates.TemplateResponse("users/edit.html", {
        "request": request,
        "user": user,
        "departments": departments
    })


@router.post("/{user_id}/edit")
async def edit_user(
    user_id: int,
    internal_real_name: str = Form(...),
    slack_email: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    standard_hours: int = Form(8),
    role: str = Form("user"),
    is_active: bool = Form(False),
    db: Session = Depends(get_db)
):
    """編輯用戶處理"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用戶不存在")
    
    # 更新用戶信息
    user.internal_real_name = internal_real_name
    user.slack_email = slack_email
    user.department = department
    user.standard_hours = standard_hours
    user.role = role
    user.is_active = is_active
    
    db.commit()
    
    return RedirectResponse(url=f"/admin/users/{user_id}", status_code=303)


@router.post("/{user_id}/toggle")
async def toggle_user_status(user_id: int, db: Session = Depends(get_db)):
    """切換用戶狀態（啟用/停用）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用戶不存在")
    
    user.is_active = not user.is_active
    db.commit()
    
    return {"status": "success", "is_active": user.is_active}


@router.get("/import/form", response_class=HTMLResponse)
async def import_users_form(request: Request):
    """批量匯入用戶表單頁面"""
    return templates.TemplateResponse("users/import.html", {
        "request": request
    })


@router.post("/import")
async def import_users(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """批量匯入用戶處理"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="請上傳CSV文件")
    
    content = await file.read()
    csv_content = content.decode('utf-8-sig')
    csv_reader = csv.DictReader(io.StringIO(csv_content))
    
    imported_count = 0
    errors = []
    
    for row_num, row in enumerate(csv_reader, start=2):
        try:
            # 檢查必填欄位
            if not all([row.get('slack_user_id'), row.get('slack_username'), row.get('internal_real_name')]):
                errors.append(f"第 {row_num} 行: 必填欄位不完整")
                continue
            
            # 檢查是否已存在
            existing_user = db.query(User).filter(
                User.slack_user_id == row['slack_user_id']
            ).first()
            if existing_user:
                errors.append(f"第 {row_num} 行: 用戶 {row['slack_user_id']} 已存在")
                continue
            
            # 建立新用戶
            user = User(
                slack_user_id=row['slack_user_id'],
                slack_username=row['slack_username'],
                internal_real_name=row['internal_real_name'],
                slack_email=row.get('slack_email'),
                department=row.get('department'),
                standard_hours=int(row.get('standard_hours', 8)),
                role=row.get('role', 'user'),
                is_active=True
            )
            
            db.add(user)
            imported_count += 1
            
        except Exception as e:
            errors.append(f"第 {row_num} 行: {str(e)}")
    
    if imported_count > 0:
        db.commit()
    
    return templates.TemplateResponse("users/import_result.html", {
        "request": Request,
        "imported_count": imported_count,
        "errors": errors
    })


@router.get("/export/csv")
async def export_users_csv(db: Session = Depends(get_db)):
    """匯出用戶CSV"""
    from fastapi.responses import StreamingResponse
    
    users = db.query(User).all()
    
    def generate_csv():
        yield "slack_user_id,slack_username,internal_real_name,slack_email,department,standard_hours,role,is_active,created_at\n"
        for user in users:
            yield f"{user.slack_user_id},{user.slack_username},{user.internal_real_name},"
            yield f"{user.slack_email or ''},{user.department or ''},{user.standard_hours},"
            yield f"{user.role},{user.is_active},{user.created_at}\n"
    
    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users.csv"}
    )