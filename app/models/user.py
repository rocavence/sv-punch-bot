from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from app.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    slack_user_id = Column(String(50), unique=True, nullable=False, index=True)
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