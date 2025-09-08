from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class WorkspaceBase(BaseModel):
    slack_team_id: str
    team_name: str
    team_domain: Optional[str] = None
    bot_token: str
    bot_user_id: Optional[str] = None
    is_active: bool = True

class WorkspaceCreate(WorkspaceBase):
    pass

class WorkspaceUpdate(BaseModel):
    team_name: Optional[str] = None
    team_domain: Optional[str] = None
    bot_token: Optional[str] = None
    bot_user_id: Optional[str] = None
    is_active: Optional[bool] = None

class WorkspaceResponse(WorkspaceBase):
    id: int
    installed_at: datetime
    updated_at: datetime
    users_count: Optional[int] = None

    class Config:
        from_attributes = True