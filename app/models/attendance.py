from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base

class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(20), nullable=False)  # 'in', 'out', 'break', 'back'
    timestamp = Column(DateTime(timezone=True), nullable=False)
    is_auto = Column(Boolean, default=False)
    note = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", backref="attendance_records")