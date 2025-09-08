from sqlalchemy import Column, Integer, String, Date, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from app.database import Base

class LeaveRecord(Base):
    __tablename__ = "leave_records"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    leave_type = Column(String(50), default="vacation")
    reason = Column(Text)
    status = Column(String(20), default="approved")  # 'pending', 'approved', 'rejected'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", backref="leave_records")