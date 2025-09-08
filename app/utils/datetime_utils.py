from datetime import datetime, date, timedelta
from typing import Optional, Union
import pytz


def get_user_timezone(timezone_str: str = "Asia/Taipei") -> pytz.BaseTzInfo:
    """獲取用戶時區"""
    try:
        return pytz.timezone(timezone_str)
    except pytz.UnknownTimeZoneError:
        return pytz.timezone("Asia/Taipei")


def utc_now() -> datetime:
    """獲取當前 UTC 時間"""
    return datetime.now(pytz.UTC)


def user_now(timezone_str: str = "Asia/Taipei") -> datetime:
    """獲取用戶時區當前時間"""
    user_tz = get_user_timezone(timezone_str)
    return utc_now().astimezone(user_tz)


def to_utc(dt: datetime, timezone_str: str = "Asia/Taipei") -> datetime:
    """將用戶時區時間轉換為 UTC"""
    if dt.tzinfo is None:
        user_tz = get_user_timezone(timezone_str)
        dt = user_tz.localize(dt)
    return dt.astimezone(pytz.UTC)


def to_user_timezone(dt: datetime, timezone_str: str = "Asia/Taipei") -> datetime:
    """將 UTC 時間轉換為用戶時區"""
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    user_tz = get_user_timezone(timezone_str)
    return dt.astimezone(user_tz)


def format_datetime(dt: datetime, timezone_str: str = "Asia/Taipei", format_str: str = "%Y-%m-%d %H:%M") -> str:
    """格式化時間為用戶時區字符串"""
    user_dt = to_user_timezone(dt, timezone_str)
    return user_dt.strftime(format_str)


def format_time(dt: datetime, timezone_str: str = "Asia/Taipei") -> str:
    """格式化為時間字符串 (HH:MM)"""
    return format_datetime(dt, timezone_str, "%H:%M")


def format_date(dt: Union[datetime, date]) -> str:
    """格式化為日期字符串 (YYYY-MM-DD)"""
    if isinstance(dt, datetime):
        return dt.date().strftime("%Y-%m-%d")
    return dt.strftime("%Y-%m-%d")


def parse_date(date_str: str) -> Optional[date]:
    """解析日期字符串"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def get_today(timezone_str: str = "Asia/Taipei") -> date:
    """獲取用戶時區今天日期"""
    return user_now(timezone_str).date()


def get_week_start(dt: Union[datetime, date], timezone_str: str = "Asia/Taipei") -> date:
    """獲取週開始日期 (週一)"""
    if isinstance(dt, datetime):
        dt = to_user_timezone(dt, timezone_str).date()
    
    days_since_monday = dt.weekday()
    return dt - timedelta(days=days_since_monday)


def get_week_end(dt: Union[datetime, date], timezone_str: str = "Asia/Taipei") -> date:
    """獲取週結束日期 (週日)"""
    week_start = get_week_start(dt, timezone_str)
    return week_start + timedelta(days=6)


def calculate_duration(start_dt: datetime, end_dt: datetime) -> timedelta:
    """計算時間差"""
    return end_dt - start_dt


def duration_to_hours(duration: timedelta) -> float:
    """將時間差轉換為小時數"""
    return duration.total_seconds() / 3600


def is_same_day(dt1: datetime, dt2: datetime, timezone_str: str = "Asia/Taipei") -> bool:
    """判斷兩個時間是否為同一天"""
    user_dt1 = to_user_timezone(dt1, timezone_str)
    user_dt2 = to_user_timezone(dt2, timezone_str)
    return user_dt1.date() == user_dt2.date()


def get_work_days_in_range(start_date: date, end_date: date) -> int:
    """計算日期範圍內的工作日數量 (排除週末)"""
    total_days = (end_date - start_date).days + 1
    work_days = 0
    
    current_date = start_date
    for _ in range(total_days):
        if current_date.weekday() < 5:  # 週一到週五
            work_days += 1
        current_date += timedelta(days=1)
    
    return work_days


def convert_timezone(dt: datetime, from_timezone: str = "UTC", to_timezone: str = "Asia/Taipei") -> datetime:
    """轉換時區"""
    # 如果沒有時區信息，假設為來源時區
    if dt.tzinfo is None:
        from_tz = pytz.timezone(from_timezone)
        dt = from_tz.localize(dt)
    
    # 轉換到目標時區
    to_tz = get_user_timezone(to_timezone)
    return dt.astimezone(to_tz)


def get_user_timezone_datetime(user_timezone: str = "Asia/Taipei") -> datetime:
    """獲取用戶時區當前時間 (別名函數)"""
    return user_now(user_timezone)


def create_user_datetime(dt: datetime, user_timezone: str = "Asia/Taipei") -> datetime:
    """為用戶時區創建時間對象"""
    return to_user_timezone(dt, user_timezone)


def parse_datetime_with_timezone(datetime_str: str, user_timezone: str = "Asia/Taipei") -> Optional[datetime]:
    """解析帶時區的日期時間字符串"""
    try:
        # 嘗試多種格式
        formats_to_try = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
        ]
        
        for fmt in formats_to_try:
            try:
                naive_dt = datetime.strptime(datetime_str, fmt)
                # 添加用戶時區信息
                user_tz = get_user_timezone(user_timezone)
                return user_tz.localize(naive_dt)
            except ValueError:
                continue
        
        return None
    except Exception:
        return None


def get_timezone_offset(timezone_str: str = "Asia/Taipei") -> timedelta:
    """獲取時區相對於 UTC 的偏移量"""
    try:
        tz = get_user_timezone(timezone_str)
        now = datetime.now()
        utc_now = pytz.UTC.localize(now)
        local_now = utc_now.astimezone(tz)
        return local_now.utcoffset()
    except:
        return timedelta(hours=8)  # 預設為 UTC+8


def is_business_hour(dt: datetime, timezone_str: str = "Asia/Taipei", 
                    start_hour: int = 9, end_hour: int = 18) -> bool:
    """判斷是否為營業時間"""
    user_dt = to_user_timezone(dt, timezone_str)
    hour = user_dt.hour
    weekday = user_dt.weekday()
    
    # 週一到週五 + 在營業時間內
    return weekday < 5 and start_hour <= hour < end_hour


def round_to_minutes(dt: datetime, minutes: int = 15) -> datetime:
    """將時間四捨五入到指定分鐘數"""
    # 計算需要四捨五入的分鐘數
    remainder = dt.minute % minutes
    if remainder >= minutes // 2:
        # 向上四捨五入
        rounded_minutes = dt.minute + (minutes - remainder)
    else:
        # 向下四捨五入
        rounded_minutes = dt.minute - remainder
    
    # 處理分鐘數溢出
    if rounded_minutes >= 60:
        dt = dt.replace(hour=dt.hour + 1, minute=0, second=0, microsecond=0)
    else:
        dt = dt.replace(minute=rounded_minutes, second=0, microsecond=0)
    
    return dt