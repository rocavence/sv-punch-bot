import re
from datetime import datetime, date
from typing import Optional


def validate_email(email: str) -> bool:
    """驗證 Email 格式"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_slack_user_id(user_id: str) -> bool:
    """驗證 Slack 用戶 ID 格式"""
    # Slack 用戶 ID 格式: U + 8-10 個字符
    pattern = r'^U[A-Z0-9]{8,10}$'
    return re.match(pattern, user_id) is not None


def validate_slack_username(username: str) -> bool:
    """驗證 Slack 用戶名格式"""
    # Slack 用戶名只能包含小寫字母、數字、點、連字符、底線
    pattern = r'^[a-z0-9._-]+$'
    return re.match(pattern, username) is not None


def validate_department_name(department: str) -> bool:
    """驗證部門名稱"""
    if not department or len(department.strip()) == 0:
        return False
    
    # 部門名稱不能超過 50 個字符
    if len(department) > 50:
        return False
    
    # 不能包含特殊字符（除了中文、英文、數字、空格、連字符）
    pattern = r'^[\u4e00-\u9fff\w\s-]+$'
    return re.match(pattern, department) is not None


def validate_real_name(name: str) -> bool:
    """驗證真實姓名"""
    if not name or len(name.strip()) == 0:
        return False
    
    # 姓名不能超過 100 個字符
    if len(name) > 100:
        return False
    
    # 只能包含中文、英文、空格
    pattern = r'^[\u4e00-\u9fff\w\s]+$'
    return re.match(pattern, name) is not None


def validate_timezone(timezone_str: str) -> bool:
    """驗證時區格式"""
    try:
        import pytz
        pytz.timezone(timezone_str)
        return True
    except:
        return False


def validate_date_format(date_str: str) -> Optional[date]:
    """驗證並解析日期格式 (YYYY-MM-DD)"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def validate_datetime_format(datetime_str: str) -> Optional[datetime]:
    """驗證並解析日期時間格式 (YYYY-MM-DD HH:MM:SS)"""
    formats_to_try = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d"
    ]
    
    for fmt in formats_to_try:
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    
    return None


def validate_work_hours(hours: int) -> bool:
    """驗證工作時數"""
    return 1 <= hours <= 24


def validate_note_length(note: str) -> bool:
    """驗證備註長度"""
    if note is None:
        return True
    return len(note) <= 500


def validate_leave_reason(reason: str) -> bool:
    """驗證請假原因"""
    if reason is None or len(reason.strip()) == 0:
        return True  # 原因可以為空
    
    return len(reason) <= 200


def validate_attendance_action(action: str) -> bool:
    """驗證打卡動作"""
    valid_actions = ['in', 'out', 'break', 'back']
    return action in valid_actions


def validate_leave_type(leave_type: str) -> bool:
    """驗證請假類型"""
    valid_types = [
        'vacation',      # 年假
        'sick',          # 病假
        'personal',      # 事假
        'emergency',     # 急假
        'maternity',     # 產假
        'paternity',     # 陪產假
        'funeral',       # 喪假
        'official',      # 公假
        'compensatory'   # 補假
    ]
    return leave_type in valid_types


def validate_user_role(role: str) -> bool:
    """驗證用戶角色"""
    valid_roles = ['user', 'admin', 'hr', 'manager']
    return role in valid_roles


def validate_date_range(start_date: date, end_date: date) -> bool:
    """驗證日期範圍"""
    if start_date > end_date:
        return False
    
    # 請假天數不能超過 365 天
    if (end_date - start_date).days > 365:
        return False
    
    return True


def validate_slack_mention(mention: str) -> Optional[str]:
    """驗證並解析 Slack mention 格式"""
    # 格式: <@U1234567890> 或 <@U1234567890|username>
    pattern = r'^<@(U[A-Z0-9]{8,10})(\|[a-z0-9._-]+)?>$'
    match = re.match(pattern, mention)
    
    if match:
        return match.group(1)  # 返回用戶 ID
    
    return None


def validate_file_extension(filename: str, allowed_extensions: list) -> bool:
    """驗證檔案副檔名"""
    if '.' not in filename:
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in [ext.lower() for ext in allowed_extensions]


def validate_file_size(file_size: int, max_size: int) -> bool:
    """驗證檔案大小"""
    return 0 < file_size <= max_size


def sanitize_input(text: str) -> str:
    """清理輸入文字"""
    if not text:
        return ""
    
    # 移除前後空白
    text = text.strip()
    
    # 移除多餘的空白字符
    text = re.sub(r'\s+', ' ', text)
    
    return text


def validate_password_strength(password: str) -> tuple[bool, list]:
    """驗證密碼強度"""
    errors = []
    
    if len(password) < 8:
        errors.append("密碼長度至少需要 8 個字符")
    
    if not re.search(r'[A-Z]', password):
        errors.append("密碼需要包含至少一個大寫字母")
    
    if not re.search(r'[a-z]', password):
        errors.append("密碼需要包含至少一個小寫字母")
    
    if not re.search(r'\d', password):
        errors.append("密碼需要包含至少一個數字")
    
    if not re.search(r'[!@#$%^&*()_+=\-\[\]{};:\'",.<>?/\\|`~]', password):
        errors.append("密碼需要包含至少一個特殊字符")
    
    return len(errors) == 0, errors


class ValidationError(Exception):
    """驗證錯誤異常"""
    
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(self.message)


def validate_required_fields(data: dict, required_fields: list) -> list:
    """驗證必填欄位"""
    missing_fields = []
    
    for field in required_fields:
        if field not in data or data[field] is None or str(data[field]).strip() == '':
            missing_fields.append(field)
    
    return missing_fields


def validate_data_types(data: dict, field_types: dict) -> list:
    """驗證資料類型"""
    type_errors = []
    
    for field, expected_type in field_types.items():
        if field in data and data[field] is not None:
            if not isinstance(data[field], expected_type):
                type_errors.append(f"{field} 應該是 {expected_type.__name__} 類型")
    
    return type_errors


def validate_pagination_params(page: int, page_size: int) -> bool:
    """驗證分頁參數"""
    if page < 1 or page_size < 1:
        return False
    if page_size > 100:  # 限制每頁最大數量
        return False
    return True


def validate_request_data(data: dict, required_fields: list = None, max_length: dict = None) -> list:
    """驗證請求資料"""
    errors = []
    
    # 檢查必填欄位
    if required_fields:
        missing = validate_required_fields(data, required_fields)
        if missing:
            errors.extend([f"缺少必填欄位: {field}" for field in missing])
    
    # 檢查欄位長度
    if max_length:
        for field, max_len in max_length.items():
            if field in data and data[field] and len(str(data[field])) > max_len:
                errors.append(f"{field} 長度超過限制 ({max_len})")
    
    return errors


class DataValidator:
    """資料驗證器"""
    
    def __init__(self):
        pass
    
    def validate_user_data(self, user_data: dict) -> tuple[bool, list]:
        """驗證用戶資料"""
        errors = []
        
        # 檢查 Slack User ID
        if 'slack_user_id' in user_data:
            if not validate_slack_user_id(user_data['slack_user_id']):
                errors.append("Slack 用戶 ID 格式錯誤")
        
        # 檢查 Email
        if 'slack_email' in user_data and user_data['slack_email']:
            if not validate_email(user_data['slack_email']):
                errors.append("Email 格式錯誤")
        
        # 檢查真實姓名
        if 'internal_real_name' in user_data:
            if not validate_real_name(user_data['internal_real_name']):
                errors.append("真實姓名格式錯誤")
        
        # 檢查部門
        if 'department' in user_data and user_data['department']:
            if not validate_department_name(user_data['department']):
                errors.append("部門名稱格式錯誤")
        
        # 檢查工作時數
        if 'standard_hours' in user_data:
            if not validate_work_hours(user_data['standard_hours']):
                errors.append("工作時數必須在 1-24 之間")
        
        # 檢查時區
        if 'timezone' in user_data and user_data['timezone']:
            if not validate_timezone(user_data['timezone']):
                errors.append("時區格式錯誤")
        
        # 檢查角色
        if 'role' in user_data and user_data['role']:
            if not validate_user_role(user_data['role']):
                errors.append("用戶角色錯誤")
        
        return len(errors) == 0, errors
    
    def validate_attendance_data(self, attendance_data: dict) -> tuple[bool, list]:
        """驗證打卡資料"""
        errors = []
        
        # 檢查動作
        if 'action' in attendance_data:
            if not validate_attendance_action(attendance_data['action']):
                errors.append("打卡動作錯誤")
        
        # 檢查備註長度
        if 'note' in attendance_data:
            if not validate_note_length(attendance_data['note']):
                errors.append("備註長度超過限制")
        
        return len(errors) == 0, errors


class CSVValidator:
    """CSV 檔案驗證器"""
    
    def __init__(self):
        self.data_validator = DataValidator()
    
    def validate_csv_file(self, csv_content: str) -> tuple[bool, list, list]:
        """驗證 CSV 檔案內容"""
        errors = []
        valid_rows = []
        
        try:
            reader = csv.DictReader(io.StringIO(csv_content))
            
            # 檢查必要欄位
            required_fields = ['slack_user_id', 'internal_real_name']
            if not all(field in reader.fieldnames for field in required_fields):
                missing_fields = [field for field in required_fields if field not in reader.fieldnames]
                errors.append(f"CSV 缺少必要欄位: {', '.join(missing_fields)}")
                return False, errors, []
            
            for row_num, row in enumerate(reader, start=2):  # 從第2行開始 (第1行是標題)
                # 清理資料
                cleaned_row = {k: sanitize_input(v) if v else v for k, v in row.items()}
                
                # 驗證這一行資料
                is_valid, row_errors = self.data_validator.validate_user_data(cleaned_row)
                
                if not is_valid:
                    errors.extend([f"第{row_num}行 - {error}" for error in row_errors])
                else:
                    valid_rows.append(cleaned_row)
        
        except Exception as e:
            errors.append(f"CSV 解析錯誤: {str(e)}")
        
        return len(errors) == 0, errors, valid_rows