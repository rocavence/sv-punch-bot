from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    slack_user_id: str
    slack_username: Optional[str] = None
    slack_display_name: Optional[str] = None
    slack_real_name: Optional[str] = None
    slack_email: Optional[EmailStr] = None
    slack_avatar_url: Optional[str] = None
    internal_real_name: str
    department: Optional[str] = None
    role: str = "user"
    standard_hours: int = 8
    timezone: str = "Asia/Taipei"
    is_active: bool = True

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    slack_username: Optional[str] = None
    slack_display_name: Optional[str] = None
    slack_real_name: Optional[str] = None
    slack_email: Optional[EmailStr] = None
    slack_avatar_url: Optional[str] = None
    internal_real_name: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    standard_hours: Optional[int] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None

class UserInDB(UserBase):
    id: int
    slack_data_updated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserResponse(UserInDB):
    pass