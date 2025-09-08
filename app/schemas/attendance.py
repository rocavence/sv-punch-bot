from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class AttendanceAction(str, Enum):
    IN = "in"
    OUT = "out"
    BREAK = "break"
    BACK = "back"

class AttendanceBase(BaseModel):
    user_id: int
    action: AttendanceAction
    timestamp: datetime
    is_auto: bool = False
    note: Optional[str] = None

class AttendanceCreate(AttendanceBase):
    pass

class AttendanceUpdate(BaseModel):
    action: Optional[AttendanceAction] = None
    timestamp: Optional[datetime] = None
    is_auto: Optional[bool] = None
    note: Optional[str] = None

class AttendanceResponse(AttendanceBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True