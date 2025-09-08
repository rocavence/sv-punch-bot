"""
Attendance service layer for punch card business logic.
"""

from datetime import datetime, date, timedelta, time
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc

from app.models.user import User
from app.models.attendance import AttendanceRecord
from app.schemas.attendance import AttendanceCreate, AttendanceUpdate, AttendanceAction
from app.utils.validators import DataValidator, validate_request_data
from app.utils.datetime_utils import convert_timezone, get_user_timezone_datetime
from app.config import settings

class AttendanceService:
    """打卡業務邏輯服務"""
    
    def __init__(self, db: Session):
        self.db = db
        self.validator = DataValidator()
    
    def create_record(self, record_data: AttendanceCreate) -> AttendanceRecord:
        """
        建立打卡記錄。
        
        Args:
            record_data: 打卡記錄資料
        
        Returns:
            新建立的打卡記錄
        
        Raises:
            ValueError: 如果資料驗證失敗
        """
        try:
            # 驗證動作類型
            self.validator.validate_attendance_action(record_data.action.value)
            
            # 建立記錄
            new_record = AttendanceRecord(
                user_id=record_data.user_id,
                action=record_data.action.value,
                timestamp=record_data.timestamp,
                is_auto=record_data.is_auto,
                note=record_data.note
            )
            
            self.db.add(new_record)
            self.db.commit()
            self.db.refresh(new_record)
            
            return new_record
            
        except Exception as e:
            self.db.rollback()
            raise ValueError(f"Failed to create attendance record: {str(e)}")
    
    def update_record(self, record_id: int, update_data: AttendanceUpdate) -> AttendanceRecord:
        """
        更新打卡記錄。
        
        Args:
            record_id: 記錄 ID
            update_data: 更新資料
        
        Returns:
            更新後的打卡記錄
        
        Raises:
            ValueError: 如果記錄不存在或更新失敗
        """
        try:
            record = self.db.query(AttendanceRecord).filter(
                AttendanceRecord.id == record_id
            ).first()
            
            if not record:
                raise ValueError("Attendance record not found")
            
            # 更新欄位
            update_dict = update_data.dict(exclude_unset=True)
            
            for field, value in update_dict.items():
                if field == "action" and value:
                    self.validator.validate_attendance_action(value.value)
                    setattr(record, field, value.value)
                elif value is not None:
                    setattr(record, field, value)
            
            self.db.commit()
            self.db.refresh(record)
            
            return record
            
        except Exception as e:
            self.db.rollback()
            raise ValueError(f"Failed to update attendance record: {str(e)}")
    
    def punch(self, user_id: int, action: AttendanceAction, timestamp: datetime = None, note: str = None) -> AttendanceRecord:
        """
        用戶打卡功能，包含序列驗證。
        
        Args:
            user_id: 用戶 ID
            action: 打卡動作
            timestamp: 打卡時間戳（可選，默認當前時間）
            note: 備註（可選）
        
        Returns:
            新建立的打卡記錄
        
        Raises:
            ValueError: 如果打卡序列不正確
        """
        try:
            if timestamp is None:
                timestamp = datetime.utcnow()
            
            # 取得用戶今日的打卡記錄進行序列驗證
            today = timestamp.date()
            today_records = self.get_user_daily_records(user_id, today)
            
            # 驗證打卡序列
            self._validate_punch_sequence(today_records, action)
            
            # 建立打卡記錄
            record_data = AttendanceCreate(
                user_id=user_id,
                action=action,
                timestamp=timestamp,
                is_auto=False,
                note=note
            )
            
            return self.create_record(record_data)
            
        except Exception as e:
            raise ValueError(f"Punch failed: {str(e)}")
    
    def get_user_daily_records(self, user_id: int, target_date: date) -> List[AttendanceRecord]:
        """
        取得用戶指定日期的所有打卡記錄。
        
        Args:
            user_id: 用戶 ID
            target_date: 目標日期
        
        Returns:
            該日期的所有打卡記錄，按時間排序
        """
        return self.db.query(AttendanceRecord).filter(
            AttendanceRecord.user_id == user_id,
            func.date(AttendanceRecord.timestamp) == target_date
        ).order_by(AttendanceRecord.timestamp).all()
    
    def get_user_records_range(self, user_id: int, start_date: date, end_date: date) -> List[AttendanceRecord]:
        """
        取得用戶指定日期範圍的打卡記錄。
        
        Args:
            user_id: 用戶 ID
            start_date: 開始日期
            end_date: 結束日期
        
        Returns:
            日期範圍內的所有打卡記錄
        """
        return self.db.query(AttendanceRecord).filter(
            AttendanceRecord.user_id == user_id,
            func.date(AttendanceRecord.timestamp) >= start_date,
            func.date(AttendanceRecord.timestamp) <= end_date
        ).order_by(AttendanceRecord.timestamp).all()
    
    def get_daily_summary(self, target_date: date, user_id: int = None) -> List[Dict]:
        """
        取得每日打卡摘要。
        
        Args:
            target_date: 目標日期
            user_id: 用戶 ID（可選，不提供則返回所有用戶）
        
        Returns:
            每日摘要列表
        """
        try:
            # 構建查詢
            query = self.db.query(
                AttendanceRecord.user_id,
                User.internal_real_name,
                func.min(
                    func.case(
                        (AttendanceRecord.action == 'in', AttendanceRecord.timestamp),
                        else_=None
                    )
                ).label('first_in'),
                func.max(
                    func.case(
                        (AttendanceRecord.action == 'out', AttendanceRecord.timestamp),
                        else_=None
                    )
                ).label('last_out'),
                func.count(AttendanceRecord.id).label('records_count')
            ).join(User).filter(
                func.date(AttendanceRecord.timestamp) == target_date
            ).group_by(AttendanceRecord.user_id, User.internal_real_name)
            
            if user_id:
                query = query.filter(AttendanceRecord.user_id == user_id)
            
            results = query.all()
            
            summaries = []
            for result in results:
                # 計算工作時間和休息時間
                work_minutes, break_minutes = self._calculate_work_time(
                    result.user_id, target_date
                )
                
                summary = {
                    "date": target_date,
                    "user_id": result.user_id,
                    "user_name": result.internal_real_name,
                    "first_in": result.first_in,
                    "last_out": result.last_out,
                    "total_work_minutes": work_minutes,
                    "total_break_minutes": break_minutes,
                    "records_count": result.records_count,
                    "is_complete": result.first_in is not None and result.last_out is not None
                }
                summaries.append(summary)
            
            return summaries
            
        except Exception as e:
            raise ValueError(f"Failed to get daily summary: {str(e)}")
    
    def validate_user_sequence(self, user_id: int, start_date: date = None, end_date: date = None) -> Dict:
        """
        驗證用戶打卡序列的邏輯性。
        
        Args:
            user_id: 用戶 ID
            start_date: 開始日期（可選）
            end_date: 結束日期（可選）
        
        Returns:
            驗證結果字典
        """
        try:
            # 設定預設日期範圍（過去 30 天）
            if not end_date:
                end_date = date.today()
            if not start_date:
                start_date = end_date - timedelta(days=30)
            
            records = self.get_user_records_range(user_id, start_date, end_date)
            
            validation_result = {
                "user_id": user_id,
                "start_date": start_date,
                "end_date": end_date,
                "total_records": len(records),
                "valid_sequences": 0,
                "invalid_sequences": 0,
                "errors": [],
                "warnings": []
            }
            
            # 按日期分組記錄
            daily_records = {}
            for record in records:
                record_date = record.timestamp.date()
                if record_date not in daily_records:
                    daily_records[record_date] = []
                daily_records[record_date].append(record)
            
            # 驗證每日的打卡序列
            for record_date, day_records in daily_records.items():
                try:
                    self._validate_daily_sequence(day_records)
                    validation_result["valid_sequences"] += 1
                except ValueError as e:
                    validation_result["invalid_sequences"] += 1
                    validation_result["errors"].append({
                        "date": record_date,
                        "error": str(e),
                        "records": [
                            {
                                "action": r.action,
                                "timestamp": r.timestamp,
                                "note": r.note
                            } for r in day_records
                        ]
                    })
            
            return validation_result
            
        except Exception as e:
            raise ValueError(f"Failed to validate sequence: {str(e)}")
    
    def auto_punch_out(self, user_id: int, work_hours: int = None) -> Optional[AttendanceRecord]:
        """
        自動下班打卡功能。
        
        Args:
            user_id: 用戶 ID
            work_hours: 工作時數（可選，默認使用用戶設定）
        
        Returns:
            自動打卡記錄，如果不需要則返回 None
        """
        try:
            today = date.today()
            today_records = self.get_user_daily_records(user_id, today)
            
            if not today_records:
                return None
            
            # 檢查是否已經下班打卡
            last_record = today_records[-1]
            if last_record.action == 'out':
                return None
            
            # 取得用戶資料
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            
            work_hours = work_hours or user.standard_hours or settings.DEFAULT_WORK_HOURS
            
            # 找到第一個上班打卡記錄
            first_in = None
            for record in today_records:
                if record.action == 'in':
                    first_in = record
                    break
            
            if not first_in:
                return None
            
            # 計算應該下班的時間
            auto_out_time = first_in.timestamp + timedelta(hours=work_hours)
            current_time = datetime.utcnow()
            
            # 如果還未到自動下班時間，不執行自動打卡
            if current_time < auto_out_time:
                return None
            
            # 建立自動下班打卡記錄
            auto_record_data = AttendanceCreate(
                user_id=user_id,
                action=AttendanceAction.OUT,
                timestamp=auto_out_time,
                is_auto=True,
                note=f"Auto punch out after {work_hours} hours"
            )
            
            return self.create_record(auto_record_data)
            
        except Exception as e:
            raise ValueError(f"Auto punch out failed: {str(e)}")
    
    def get_work_time_stats(self, user_id: int, start_date: date, end_date: date) -> Dict:
        """
        取得工作時間統計。
        
        Args:
            user_id: 用戶 ID
            start_date: 開始日期
            end_date: 結束日期
        
        Returns:
            工作時間統計字典
        """
        try:
            records = self.get_user_records_range(user_id, start_date, end_date)
            
            total_work_minutes = 0
            total_break_minutes = 0
            working_days = set()
            
            # 按日期分組並計算每日工時
            daily_records = {}
            for record in records:
                record_date = record.timestamp.date()
                working_days.add(record_date)
                if record_date not in daily_records:
                    daily_records[record_date] = []
                daily_records[record_date].append(record)
            
            for record_date, day_records in daily_records.items():
                work_minutes, break_minutes = self._calculate_work_time_from_records(day_records)
                total_work_minutes += work_minutes
                total_break_minutes += break_minutes
            
            # 計算統計資料
            total_work_hours = total_work_minutes / 60
            total_break_hours = total_break_minutes / 60
            working_days_count = len(working_days)
            avg_daily_hours = total_work_hours / working_days_count if working_days_count > 0 else 0
            
            # 取得用戶標準工時
            user = self.db.query(User).filter(User.id == user_id).first()
            standard_hours = user.standard_hours if user else settings.DEFAULT_WORK_HOURS
            expected_total_hours = working_days_count * standard_hours
            overtime_hours = max(0, total_work_hours - expected_total_hours)
            
            return {
                "user_id": user_id,
                "period": f"{start_date} to {end_date}",
                "total_work_hours": round(total_work_hours, 2),
                "total_break_hours": round(total_break_hours, 2),
                "working_days": working_days_count,
                "avg_daily_hours": round(avg_daily_hours, 2),
                "expected_total_hours": expected_total_hours,
                "overtime_hours": round(overtime_hours, 2),
                "attendance_rate": round((working_days_count / ((end_date - start_date).days + 1)) * 100, 2),
                "standard_hours_per_day": standard_hours
            }
            
        except Exception as e:
            raise ValueError(f"Failed to get work time stats: {str(e)}")
    
    def _validate_punch_sequence(self, existing_records: List[AttendanceRecord], new_action: AttendanceAction):
        """
        驗證打卡序列的邏輯性。
        
        Args:
            existing_records: 現有記錄列表
            new_action: 新的打卡動作
        
        Raises:
            ValueError: 如果序列不正確
        """
        if not existing_records:
            # 第一次打卡必須是 'in'
            if new_action != AttendanceAction.IN:
                raise ValueError("First punch of the day must be 'in'")
            return
        
        last_action = existing_records[-1].action
        
        # 驗證動作序列邏輯
        if last_action == 'in' and new_action not in [AttendanceAction.OUT, AttendanceAction.BREAK]:
            raise ValueError(f"Cannot '{new_action.value}' after '{last_action}'")
        elif last_action == 'out' and new_action != AttendanceAction.IN:
            raise ValueError(f"Cannot '{new_action.value}' after '{last_action}', must punch 'in' first")
        elif last_action == 'break' and new_action not in [AttendanceAction.BACK, AttendanceAction.OUT]:
            raise ValueError(f"Cannot '{new_action.value}' after '{last_action}'")
        elif last_action == 'back' and new_action not in [AttendanceAction.OUT, AttendanceAction.BREAK]:
            raise ValueError(f"Cannot '{new_action.value}' after '{last_action}'")
    
    def _validate_daily_sequence(self, day_records: List[AttendanceRecord]):
        """
        驗證單日打卡序列的完整性。
        
        Args:
            day_records: 單日的打卡記錄
        
        Raises:
            ValueError: 如果序列不正確
        """
        if not day_records:
            return
        
        # 排序記錄
        sorted_records = sorted(day_records, key=lambda x: x.timestamp)
        
        last_action = None
        for record in sorted_records:
            action = record.action
            
            # 使用相同的序列驗證邏輯
            if last_action is None:
                if action != 'in':
                    raise ValueError("First punch must be 'in'")
            else:
                if last_action == 'in' and action not in ['out', 'break']:
                    raise ValueError(f"Invalid sequence: '{action}' cannot follow '{last_action}'")
                elif last_action == 'out' and action != 'in':
                    raise ValueError(f"Invalid sequence: '{action}' cannot follow '{last_action}'")
                elif last_action == 'break' and action not in ['back', 'out']:
                    raise ValueError(f"Invalid sequence: '{action}' cannot follow '{last_action}'")
                elif last_action == 'back' and action not in ['out', 'break']:
                    raise ValueError(f"Invalid sequence: '{action}' cannot follow '{last_action}'")
            
            last_action = action
    
    def _calculate_work_time(self, user_id: int, target_date: date) -> Tuple[int, int]:
        """
        計算指定日期的工作時間和休息時間。
        
        Args:
            user_id: 用戶 ID
            target_date: 目標日期
        
        Returns:
            (工作分鐘數, 休息分鐘數) 的元組
        """
        records = self.get_user_daily_records(user_id, target_date)
        return self._calculate_work_time_from_records(records)
    
    def _calculate_work_time_from_records(self, records: List[AttendanceRecord]) -> Tuple[int, int]:
        """
        從記錄列表計算工作時間和休息時間。
        
        Args:
            records: 打卡記錄列表
        
        Returns:
            (工作分鐘數, 休息分鐘數) 的元組
        """
        if not records:
            return 0, 0
        
        sorted_records = sorted(records, key=lambda x: x.timestamp)
        
        work_minutes = 0
        break_minutes = 0
        current_state = None
        state_start_time = None
        
        for record in sorted_records:
            if current_state and state_start_time:
                duration_minutes = int((record.timestamp - state_start_time).total_seconds() / 60)
                
                if current_state == 'working':
                    work_minutes += duration_minutes
                elif current_state == 'breaking':
                    break_minutes += duration_minutes
            
            # 更新狀態
            if record.action == 'in':
                current_state = 'working'
                state_start_time = record.timestamp
            elif record.action == 'out':
                current_state = None
                state_start_time = None
            elif record.action == 'break':
                current_state = 'breaking'
                state_start_time = record.timestamp
            elif record.action == 'back':
                current_state = 'working'
                state_start_time = record.timestamp
        
        return work_minutes, break_minutes