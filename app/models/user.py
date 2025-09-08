from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base

class Workspace(Base):
    __tablename__ = "workspaces"
    
    id = Column(Integer, primary_key=True, index=True)
    slack_team_id = Column(String(20), unique=True, nullable=False, index=True)
    team_name = Column(String(100), nullable=False)
    team_domain = Column(String(100))
    bot_token = Column(String(200), nullable=False)  # Bot User OAuth Token
    bot_user_id = Column(String(50))
    is_active = Column(Boolean, default=True)
    installed_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    slack_user_id = Column(String(50), nullable=False, index=True)
    slack_username = Column(String(100))
    slack_display_name = Column(String(100))
    slack_real_name = Column(String(100))
    slack_email = Column(String(120))
    slack_avatar_url = Column(String(500))
    internal_real_name = Column(String(100), nullable=False)
    department = Column(String(50))
    role = Column(String(20), default="user")
    standard_hours = Column(Integer, default=8)
    timezone = Column(String(50), default="Asia/Taipei")
    is_active = Column(Boolean, default=True)
    slack_data_updated_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    workspace = relationship("Workspace", backref="users")
    
    __table_args__ = (
        UniqueConstraint('slack_user_id', 'workspace_id', name='uix_user_workspace'),
    )