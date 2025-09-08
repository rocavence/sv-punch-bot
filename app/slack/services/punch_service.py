from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from slack_sdk import WebClient

from app.models.user import User
from app.models.attendance import AttendanceRecord
from app.models.leave import LeaveRecord
from app.utils.datetime_utils import (
    utc_now, user_now, to_utc, to_user_timezone, 
    format_datetime, format_time, format_date,
    get_today, get_week_start, get_week_end,
    calculate_duration, duration_to_hours,
    is_same_day, parse_date
)


class PunchService:
    """打卡業務邏輯服務"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_or_create_user(self, slack_user_id: str, slack_username: str = None) -> User:
        """獲取或創建用戶"""
        user = self.db.query(User).filter(User.slack_user_id == slack_user_id).first()
        
        if not user:
            user = User(
                slack_user_id=slack_user_id,
                slack_username=slack_username,
                internal_real_name=slack_username or f"User_{slack_user_id[:8]}"
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        
        return user
    
    def punch_in(self, slack_user_id: str, slack_username: str = None, note: str = None) -> Tuple[bool, str]:
        """上班打卡"""
        user = self.get_or_create_user(slack_user_id, slack_username)
        
        # 檢查今天是否已經有上班記錄
        today = get_today(user.timezone)
        today_records = self._get_daily_records(user.id, today)
        
        if any(record.action == 'in' for record in today_records):
            return False, "今天已經打過上班卡了！"
        
        # 檢查是否有未結束的休息
        if today_records and today_records[-1].action == 'break':
            return False, "請先結束休息再打上班卡！"
        
        # 創建打卡記錄
        record = AttendanceRecord(
            user_id=user.id,
            action='in',
            timestamp=utc_now(),
            note=note
        )
        
        self.db.add(record)
        self.db.commit()
        
        time_str = format_time(record.timestamp, user.timezone)
        return True, f"上班打卡成功！時間：{time_str}"
    
    def punch_out(self, slack_user_id: str, note: str = None) -> Tuple[bool, str]:
        """下班打卡"""
        user = self.db.query(User).filter(User.slack_user_id == slack_user_id).first()
        if not user:
            return False, "用戶不存在！"
        
        # 檢查今天的打卡記錄
        today = get_today(user.timezone)
        today_records = self._get_daily_records(user.id, today)
        
        if not today_records:
            return False, "今天還沒有上班記錄！"
        
        if not any(record.action == 'in' for record in today_records):
            return False, "今天還沒有上班記錄！"
        
        if any(record.action == 'out' for record in today_records):
            return False, "今天已經打過下班卡了！"
        
        # 檢查是否有未結束的休息
        if today_records and today_records[-1].action == 'break':
            return False, "請先結束休息再打下班卡！"
        
        # 創建打卡記錄
        record = AttendanceRecord(
            user_id=user.id,
            action='out',
            timestamp=utc_now(),
            note=note
        )
        
        self.db.add(record)
        self.db.commit()
        
        # 計算工作時間
        work_hours = self._calculate_daily_work_hours(user.id, today)
        time_str = format_time(record.timestamp, user.timezone)
        
        return True, f"下班打卡成功！時間：{time_str}\n今日工作時間：{work_hours:.1f} 小時"
    
    def punch_break(self, slack_user_id: str, note: str = None) -> Tuple[bool, str]:
        """開始休息"""
        user = self.db.query(User).filter(User.slack_user_id == slack_user_id).first()
        if not user:
            return False, "用戶不存在！"
        
        # 檢查今天的打卡記錄
        today = get_today(user.timezone)
        today_records = self._get_daily_records(user.id, today)
        
        if not today_records or not any(record.action == 'in' for record in today_records):
            return False, "請先打上班卡！"
        
        if any(record.action == 'out' for record in today_records):
            return False, "已經下班了，無法開始休息！"
        
        if today_records and today_records[-1].action == 'break':
            return False, "已經在休息中了！"
        
        # 創建打卡記錄
        record = AttendanceRecord(
            user_id=user.id,
            action='break',
            timestamp=utc_now(),
            note=note
        )
        
        self.db.add(record)
        self.db.commit()
        
        time_str = format_time(record.timestamp, user.timezone)
        return True, f"開始休息！時間：{time_str}"
    
    def punch_back(self, slack_user_id: str, note: str = None) -> Tuple[bool, str]:
        """結束休息"""
        user = self.db.query(User).filter(User.slack_user_id == slack_user_id).first()
        if not user:
            return False, "用戶不存在！"
        
        # 檢查今天的打卡記錄
        today = get_today(user.timezone)
        today_records = self._get_daily_records(user.id, today)
        
        if not today_records or today_records[-1].action != 'break':
            return False, "目前沒有在休息中！"
        
        # 創建打卡記錄
        record = AttendanceRecord(
            user_id=user.id,
            action='back',
            timestamp=utc_now(),
            note=note
        )
        
        self.db.add(record)
        self.db.commit()
        
        time_str = format_time(record.timestamp, user.timezone)
        return True, f"休息結束！時間：{time_str}"
    
    def get_today_summary(self, slack_user_id: str) -> str:
        """獲取今日打卡摘要"""
        user = self.db.query(User).filter(User.slack_user_id == slack_user_id).first()
        if not user:
            return "用戶不存在！"
        
        today = get_today(user.timezone)
        
        # 檢查是否請假
        if self._is_on_leave(user.id, today):
            return f"📅 {format_date(today)}\n🏖️ 今日請假"
        
        records = self._get_daily_records(user.id, today)
        if not records:
            return f"📅 {format_date(today)}\n❌ 今天還沒有打卡記錄"
        
        # 組織打卡記錄
        summary = [f"📅 {format_date(today)}"]
        current_status = self._get_current_status(records)
        
        for record in records:
            action_emoji = {
                'in': '🟢', 'out': '🔴', 
                'break': '🟡', 'back': '🟢'
            }
            action_name = {
                'in': '上班', 'out': '下班',
                'break': '休息', 'back': '回來'
            }
            
            time_str = format_time(record.timestamp, user.timezone)
            summary.append(f"{action_emoji[record.action]} {action_name[record.action]}: {time_str}")
        
        # 計算工作時間
        work_hours = self._calculate_daily_work_hours(user.id, today)
        if work_hours > 0:
            summary.append(f"\n⏰ 累計工作時間: {work_hours:.1f} 小時")
        
        # 顯示當前狀態
        summary.append(f"\n📍 當前狀態: {current_status}")
        
        return "\n".join(summary)
    
    def get_week_summary(self, slack_user_id: str) -> str:
        """獲取本週工時統計"""
        user = self.db.query(User).filter(User.slack_user_id == slack_user_id).first()
        if not user:
            return "用戶不存在！"
        
        today = get_today(user.timezone)
        week_start = get_week_start(today, user.timezone)
        week_end = get_week_end(today, user.timezone)
        
        summary = [f"📊 本週工時統計 ({format_date(week_start)} ~ {format_date(week_end)})"]
        
        total_hours = 0
        work_days = 0
        
        # 每天的工時統計
        for i in range(7):
            check_date = week_start + timedelta(days=i)
            if check_date > today:
                break
                
            if self._is_on_leave(user.id, check_date):
                day_name = check_date.strftime("%m/%d(%a)")
                summary.append(f"🏖️ {day_name}: 請假")
                continue
            
            daily_hours = self._calculate_daily_work_hours(user.id, check_date)
            if daily_hours > 0:
                work_days += 1
                total_hours += daily_hours
                day_name = check_date.strftime("%m/%d(%a)")
                summary.append(f"📅 {day_name}: {daily_hours:.1f} 小時")
        
        if work_days == 0:
            summary.append("❌ 本週還沒有工作記錄")
        else:
            avg_hours = total_hours / work_days
            summary.append(f"\n📈 總工時: {total_hours:.1f} 小時")
            summary.append(f"📊 工作天數: {work_days} 天")
            summary.append(f"⭐ 平均每日: {avg_hours:.1f} 小時")
        
        return "\n".join(summary)
    
    def request_leave(self, slack_user_id: str, start_date: date, end_date: date = None, 
                     reason: str = None) -> Tuple[bool, str]:
        """請假申請"""
        user = self.db.query(User).filter(User.slack_user_id == slack_user_id).first()
        if not user:
            return False, "用戶不存在！"
        
        if end_date is None:
            end_date = start_date
        
        if start_date > end_date:
            return False, "結束日期不能早於開始日期！"
        
        # 檢查是否已有重疊的請假記錄
        existing_leave = self.db.query(LeaveRecord).filter(
            LeaveRecord.user_id == user.id,
            or_(
                and_(LeaveRecord.start_date <= start_date, LeaveRecord.end_date >= start_date),
                and_(LeaveRecord.start_date <= end_date, LeaveRecord.end_date >= end_date),
                and_(LeaveRecord.start_date >= start_date, LeaveRecord.end_date <= end_date)
            )
        ).first()
        
        if existing_leave:
            return False, "該日期範圍已有請假記錄！"
        
        # 創建請假記錄
        leave_record = LeaveRecord(
            user_id=user.id,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            status="approved"  # 自動核准
        )
        
        self.db.add(leave_record)
        self.db.commit()
        
        if start_date == end_date:
            date_str = format_date(start_date)
            return True, f"請假申請成功！日期：{date_str}"
        else:
            start_str = format_date(start_date)
            end_str = format_date(end_date)
            days = (end_date - start_date).days + 1
            return True, f"請假申請成功！期間：{start_str} ~ {end_str} (共 {days} 天)"
    
    def cancel_leave(self, slack_user_id: str, target_date: date) -> Tuple[bool, str]:
        """取消請假"""
        user = self.db.query(User).filter(User.slack_user_id == slack_user_id).first()
        if not user:
            return False, "用戶不存在！"
        
        leave_record = self.db.query(LeaveRecord).filter(
            LeaveRecord.user_id == user.id,
            LeaveRecord.start_date <= target_date,
            LeaveRecord.end_date >= target_date
        ).first()
        
        if not leave_record:
            date_str = format_date(target_date)
            return False, f"{date_str} 沒有請假記錄！"
        
        self.db.delete(leave_record)
        self.db.commit()
        
        date_str = format_date(target_date)
        return True, f"已取消 {date_str} 的請假申請！"
    
    def get_leave_history(self, slack_user_id: str, limit: int = 10) -> str:
        """獲取請假歷史"""
        user = self.db.query(User).filter(User.slack_user_id == slack_user_id).first()
        if not user:
            return "用戶不存在！"
        
        leave_records = self.db.query(LeaveRecord).filter(
            LeaveRecord.user_id == user.id
        ).order_by(LeaveRecord.start_date.desc()).limit(limit).all()
        
        if not leave_records:
            return "🏖️ 還沒有請假記錄"
        
        summary = ["🏖️ 最近請假記錄:"]
        
        for record in leave_records:
            if record.start_date == record.end_date:
                date_str = format_date(record.start_date)
                summary.append(f"📅 {date_str}")
            else:
                start_str = format_date(record.start_date)
                end_str = format_date(record.end_date)
                days = (record.end_date - record.start_date).days + 1
                summary.append(f"📅 {start_str} ~ {end_str} (共 {days} 天)")
            
            if record.reason:
                summary.append(f"   原因: {record.reason}")
        
        return "\n".join(summary)
    
    def _get_daily_records(self, user_id: int, target_date: date) -> List[AttendanceRecord]:
        """獲取指定日期的打卡記錄"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return []
        
        # 轉換為用戶時區的日期範圍
        start_datetime = to_utc(
            datetime.combine(target_date, datetime.min.time()), 
            user.timezone
        )
        end_datetime = to_utc(
            datetime.combine(target_date + timedelta(days=1), datetime.min.time()), 
            user.timezone
        )
        
        return self.db.query(AttendanceRecord).filter(
            AttendanceRecord.user_id == user_id,
            AttendanceRecord.timestamp >= start_datetime,
            AttendanceRecord.timestamp < end_datetime
        ).order_by(AttendanceRecord.timestamp).all()
    
    def _is_on_leave(self, user_id: int, target_date: date) -> bool:
        """檢查指定日期是否請假"""
        leave_record = self.db.query(LeaveRecord).filter(
            LeaveRecord.user_id == user_id,
            LeaveRecord.start_date <= target_date,
            LeaveRecord.end_date >= target_date
        ).first()
        
        return leave_record is not None
    
    def _calculate_daily_work_hours(self, user_id: int, target_date: date) -> float:
        """計算指定日期的工作時間"""
        records = self._get_daily_records(user_id, target_date)
        if not records:
            return 0.0
        
        total_seconds = 0
        work_start = None
        break_start = None
        
        for record in records:
            if record.action == 'in':
                work_start = record.timestamp
            elif record.action == 'out' and work_start:
                total_seconds += (record.timestamp - work_start).total_seconds()
                work_start = None
            elif record.action == 'break' and work_start:
                total_seconds += (record.timestamp - work_start).total_seconds()
                break_start = record.timestamp
                work_start = None
            elif record.action == 'back' and break_start:
                work_start = record.timestamp
                break_start = None
        
        # 如果還在工作中，計算到現在的時間
        if work_start:
            total_seconds += (utc_now() - work_start).total_seconds()
        
        return total_seconds / 3600
    
    def _get_current_status(self, records: List[AttendanceRecord]) -> str:
        """獲取當前工作狀態"""
        if not records:
            return "未上班"
        
        last_action = records[-1].action
        
        if last_action == 'in':
            return "工作中"
        elif last_action == 'out':
            return "已下班"
        elif last_action == 'break':
            return "休息中"
        elif last_action == 'back':
            return "工作中"
        
        return "未知"
    
    # 自動提醒相關方法
    def send_daily_reminders(self, slack_client: WebClient):
        """發送每日打卡提醒"""
        # 獲取所有活躍用戶
        users = self.db.query(User).filter(User.is_active == True).all()
        
        for user in users:
            today = get_today(user.timezone)
            
            # 檢查是否請假
            if self._is_on_leave(user.id, today):
                continue
            
            # 檢查是否已打卡
            records = self._get_daily_records(user.id, today)
            if not any(record.action == 'in' for record in records):
                try:
                    slack_client.chat_postMessage(
                        channel=user.slack_user_id,
                        text="🌅 早安！記得要打卡上班喔！\n使用 `/punch in` 開始新的一天 💪"
                    )
                except Exception as e:
                    print(f"發送提醒給用戶 {user.slack_user_id} 失敗: {e}")
    
    def check_work_hour_reminders(self, slack_client: WebClient):
        """檢查 8 小時工作提醒"""
        users = self.db.query(User).filter(User.is_active == True).all()
        
        for user in users:
            today = get_today(user.timezone)
            records = self._get_daily_records(user.id, today)
            
            # 檢查是否已工作滿 8 小時
            work_hours = self._calculate_daily_work_hours(user.id, today)
            current_status = self._get_current_status(records)
            
            if work_hours >= user.standard_hours and current_status == "工作中":
                try:
                    slack_client.chat_postMessage(
                        channel=user.slack_user_id,
                        text=f"⏰ 您今天已經工作了 {work_hours:.1f} 小時！\n"
                             f"已達到標準工時 {user.standard_hours} 小時，記得適時休息 😊\n"
                             f"使用 `/punch out` 結束今日工作"
                    )
                except Exception as e:
                    print(f"發送工時提醒給用戶 {user.slack_user_id} 失敗: {e}")
    
    def send_forgot_punch_reminders(self, slack_client: WebClient):
        """發送忘記打卡提醒"""
        users = self.db.query(User).filter(User.is_active == True).all()
        
        for user in users:
            today = get_today(user.timezone)
            
            # 檢查是否請假
            if self._is_on_leave(user.id, today):
                continue
            
            records = self._get_daily_records(user.id, today)
            current_status = self._get_current_status(records)
            
            # 如果有上班記錄但沒有下班記錄
            if any(record.action == 'in' for record in records) and current_status != "已下班":
                try:
                    slack_client.chat_postMessage(
                        channel=user.slack_user_id,
                        text="🕕 下班時間到了！記得打卡下班喔！\n"
                             "使用 `/punch out` 結束今日工作 👋"
                    )
                except Exception as e:
                    print(f"發送下班提醒給用戶 {user.slack_user_id} 失敗: {e}")
    
    def send_weekly_reports(self, slack_client: WebClient):
        """發送每週統計報告"""
        users = self.db.query(User).filter(User.is_active == True).all()
        
        for user in users:
            try:
                weekly_summary = self.get_week_summary(user.slack_user_id)
                slack_client.chat_postMessage(
                    channel=user.slack_user_id,
                    text=f"📊 週報來了！\n\n{weekly_summary}"
                )
            except Exception as e:
                print(f"發送週報給用戶 {user.slack_user_id} 失敗: {e}")