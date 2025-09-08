from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from enum import Enum

class LeaveStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class LeaveType(str, Enum):
    VACATION = "vacation"
    SICK = "sick"
    PERSONAL = "personal"
    ANNUAL = "annual"

class LeaveBase(BaseModel):
    user_id: int
    start_date: date
    end_date: date
    leave_type: LeaveType = LeaveType.VACATION
    reason: Optional[str] = None
    status: LeaveStatus = LeaveStatus.APPROVED

class LeaveCreate(LeaveBase):
    pass

class LeaveUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    leave_type: Optional[LeaveType] = None
    reason: Optional[str] = None
    status: Optional[LeaveStatus] = None

class LeaveResponse(LeaveBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True