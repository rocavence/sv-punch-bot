import csv
import io
from datetime import datetime, date, timedelta
from typing import List
from slack_bolt import App
from sqlalchemy import func

from app.database import get_db
from app.models.user import User
from app.models.attendance import AttendanceRecord
from app.slack.services.punch_service import PunchService
from app.slack.services.user_sync import UserSyncService
from app.utils.datetime_utils import get_today, get_week_start, format_date


def register_admin_handlers(app: App):
    """註冊管理員指令處理程序"""
    
    @app.command("/punch")
    def handle_admin_commands(ack, respond, command, client):
        """處理管理員相關的 /punch 指令"""
        ack()
        
        user_id = command["user_id"]
        text = command["text"].strip()
        
        # 檢查是否為管理員指令
        if not text.startswith("admin"):
            return  # 讓其他處理程序處理
        
        try:
            # 檢查管理員權限
            if not _is_admin(user_id):
                respond("❌ 您沒有管理員權限！")
                return
            
            # 獲取資料庫連接
            db = next(get_db())
            punch_service = PunchService(db)
            user_sync_service = UserSyncService()
            
            # 解析管理員指令
            args = text.split()[1:]  # 移除 'admin'
            
            if not args:
                respond(_get_admin_help_message())
                return
            
            admin_action = args[0].lower()
            
            if admin_action == "invite":
                # 邀請用戶
                _handle_invite_user(db, args[1:], respond, client)
            
            elif admin_action == "remove":
                # 移除用戶
                _handle_remove_user(db, args[1:], respond)
            
            elif admin_action == "users":
                # 查看所有用戶
                _handle_list_users(db, respond)
            
            elif admin_action == "team":
                # 查看團隊狀態
                _handle_team_status(db, respond)
            
            elif admin_action == "export":
                # 匯出報表
                _handle_export_report(db, args[1:], respond, client, user_id)
            
            elif admin_action == "sync":
                # 同步用戶資料
                _handle_sync_user(db, user_sync_service, args[1:], respond, client)
            
            elif admin_action == "stats":
                # 查看系統統計
                _handle_system_stats(db, respond)
            
            elif admin_action == "help":
                # 管理員幫助
                respond(_get_admin_help_message())
            
            else:
                respond(f"❌ 不認識的管理員指令: `{admin_action}`\n\n" + _get_admin_help_message())
        
        except Exception as e:
            respond(f"❌ 執行管理員指令時發生錯誤: {str(e)}")
        finally:
            db.close()


def _is_admin(user_id: str) -> bool:
    """檢查用戶是否為管理員"""
    try:
        db = next(get_db())
        user = db.query(User).filter(User.slack_user_id == user_id).first()
        return user and user.role == "admin"
    except:
        return False
    finally:
        db.close()


def _handle_invite_user(db, args, respond, client):
    """處理邀請用戶"""
    if len(args) < 3:
        respond("❌ 邀請用戶指令格式錯誤！\n"
                "用法: `/punch admin invite @username \"真實姓名\" \"部門\"`")
        return
    
    try:
        # 解析參數
        slack_user_mention = args[0]
        real_name = args[1].strip('"')
        department = args[2].strip('"') if len(args) > 2 else "未分配"
        
        # 從 mention 中提取用戶 ID
        if slack_user_mention.startswith('<@') and slack_user_mention.endswith('>'):
            slack_user_id = slack_user_mention[2:-1]
            if '|' in slack_user_id:
                slack_user_id = slack_user_id.split('|')[0]
        else:
            respond("❌ 請使用 @username 格式指定用戶！")
            return
        
        # 獲取 Slack 用戶資訊
        try:
            slack_user_info = client.users_info(user=slack_user_id)
            slack_user = slack_user_info["user"]
        except Exception as e:
            respond(f"❌ 無法獲取 Slack 用戶資訊: {str(e)}")
            return
        
        # 檢查用戶是否已存在
        existing_user = db.query(User).filter(User.slack_user_id == slack_user_id).first()
        if existing_user:
            respond(f"❌ 用戶 {slack_user['real_name']} 已經在系統中！")
            return
        
        # 創建新用戶
        new_user = User(
            slack_user_id=slack_user_id,
            slack_username=slack_user.get("name"),
            slack_display_name=slack_user.get("display_name"),
            slack_real_name=slack_user.get("real_name"),
            slack_email=slack_user.get("profile", {}).get("email"),
            slack_avatar_url=slack_user.get("profile", {}).get("image_192"),
            internal_real_name=real_name,
            department=department,
            slack_data_updated_at=datetime.utcnow()
        )
        
        db.add(new_user)
        db.commit()
        
        # 發送歡迎訊息給新用戶
        try:
            client.chat_postMessage(
                channel=slack_user_id,
                text=f"🎉 歡迎加入 Punch Bot！\n\n"
                     f"您已被加入打卡系統：\n"
                     f"• 姓名: {real_name}\n"
                     f"• 部門: {department}\n\n"
                     f"使用 `/punch help` 查看所有可用指令。\n"
                     f"開始您的第一次打卡: `/punch in` 🚀"
            )
        except Exception as e:
            print(f"發送歡迎訊息失敗: {e}")
        
        respond(f"✅ 成功邀請用戶 {real_name} 加入系統！\n"
                f"• Slack 用戶: {slack_user['real_name']}\n"
                f"• 部門: {department}")
    
    except Exception as e:
        respond(f"❌ 邀請用戶失敗: {str(e)}")


def _handle_remove_user(db, args, respond):
    """處理移除用戶"""
    if not args:
        respond("❌ 移除用戶指令格式錯誤！\n"
                "用法: `/punch admin remove @username`")
        return
    
    slack_user_mention = args[0]
    
    # 從 mention 中提取用戶 ID
    if slack_user_mention.startswith('<@') and slack_user_mention.endswith('>'):
        slack_user_id = slack_user_mention[2:-1]
        if '|' in slack_user_id:
            slack_user_id = slack_user_id.split('|')[0]
    else:
        respond("❌ 請使用 @username 格式指定用戶！")
        return
    
    try:
        user = db.query(User).filter(User.slack_user_id == slack_user_id).first()
        if not user:
            respond("❌ 用戶不存在於系統中！")
            return
        
        # 軟刪除 - 設置為非活躍狀態
        user.is_active = False
        db.commit()
        
        respond(f"✅ 已移除用戶 {user.internal_real_name} 的系統存取權限")
    
    except Exception as e:
        respond(f"❌ 移除用戶失敗: {str(e)}")


def _handle_list_users(db, respond):
    """處理查看所有用戶"""
    try:
        users = db.query(User).filter(User.is_active == True).order_by(User.department, User.internal_real_name).all()
        
        if not users:
            respond("📋 目前系統中沒有活躍用戶")
            return
        
        # 按部門分組
        departments = {}
        for user in users:
            dept = user.department or "未分配"
            if dept not in departments:
                departments[dept] = []
            departments[dept].append(user)
        
        response = ["👥 **系統用戶列表**\n"]
        
        for dept_name, dept_users in departments.items():
            response.append(f"**{dept_name}** ({len(dept_users)} 人)")
            for user in dept_users:
                role_emoji = "👑" if user.role == "admin" else "👤"
                response.append(f"{role_emoji} {user.internal_real_name} (@{user.slack_username})")
            response.append("")
        
        response.append(f"📊 總計: {len(users)} 位活躍用戶")
        
        respond("\n".join(response))
    
    except Exception as e:
        respond(f"❌ 查看用戶列表失敗: {str(e)}")


def _handle_team_status(db, respond):
    """處理查看團隊狀態"""
    try:
        punch_service = PunchService(db)
        users = db.query(User).filter(User.is_active == True).all()
        
        if not users:
            respond("📋 目前系統中沒有活躍用戶")
            return
        
        today = get_today()
        response = [f"👥 **團隊即時狀態** ({format_date(today)})\n"]
        
        status_counts = {"工作中": 0, "休息中": 0, "已下班": 0, "未上班": 0, "請假": 0}
        
        for user in users:
            # 檢查是否請假
            if punch_service._is_on_leave(user.id, today):
                status = "🏖️ 請假"
                status_counts["請假"] += 1
            else:
                records = punch_service._get_daily_records(user.id, today)
                current_status = punch_service._get_current_status(records)
                
                status_emoji = {
                    "工作中": "🟢", "休息中": "🟡", 
                    "已下班": "🔴", "未上班": "⚪"
                }
                
                status = f"{status_emoji.get(current_status, '⚪')} {current_status}"
                status_counts[current_status] += 1
            
            dept = user.department or "未分配"
            response.append(f"• {user.internal_real_name} ({dept}) - {status}")
        
        # 添加統計摘要
        response.append("\n📊 **狀態統計:**")
        for status_name, count in status_counts.items():
            if count > 0:
                response.append(f"• {status_name}: {count} 人")
        
        respond("\n".join(response))
    
    except Exception as e:
        respond(f"❌ 查看團隊狀態失敗: {str(e)}")


def _handle_export_report(db, args, respond, client, admin_user_id):
    """處理匯出報表"""
    try:
        # 解析日期範圍
        if not args:
            # 預設匯出本週
            today = get_today()
            start_date = get_week_start(today)
            end_date = today
        elif len(args) == 1:
            # 單日報表
            start_date = end_date = datetime.strptime(args[0], "%Y-%m-%d").date()
        elif len(args) >= 2:
            # 日期範圍
            start_date = datetime.strptime(args[0], "%Y-%m-%d").date()
            end_date = datetime.strptime(args[1], "%Y-%m-%d").date()
        else:
            respond("❌ 日期格式錯誤！請使用 YYYY-MM-DD 格式")
            return
        
        # 獲取資料
        records = db.query(AttendanceRecord).join(User).filter(
            AttendanceRecord.timestamp >= datetime.combine(start_date, datetime.min.time()),
            AttendanceRecord.timestamp <= datetime.combine(end_date + timedelta(days=1), datetime.min.time()),
            User.is_active == True
        ).order_by(AttendanceRecord.timestamp).all()
        
        if not records:
            respond(f"📊 {format_date(start_date)} 到 {format_date(end_date)} 期間沒有打卡記錄")
            return
        
        # 生成 CSV
        csv_content = _generate_csv_report(records, start_date, end_date)
        
        # 上傳檔案到 Slack
        filename = f"punch_report_{format_date(start_date)}_to_{format_date(end_date)}.csv"
        
        client.files_upload_v2(
            channel=admin_user_id,
            file=csv_content,
            filename=filename,
            title=f"打卡報表 ({format_date(start_date)} ~ {format_date(end_date)})",
            initial_comment=f"📊 打卡報表已生成\n期間: {format_date(start_date)} ~ {format_date(end_date)}\n共 {len(records)} 筆記錄"
        )
        
        respond(f"✅ 報表已生成並上傳！\n期間: {format_date(start_date)} ~ {format_date(end_date)}")
    
    except ValueError:
        respond("❌ 日期格式錯誤！請使用 YYYY-MM-DD 格式")
    except Exception as e:
        respond(f"❌ 匯出報表失敗: {str(e)}")


def _handle_sync_user(db, user_sync_service, args, respond, client):
    """處理同步用戶資料"""
    if not args:
        respond("❌ 同步用戶指令格式錯誤！\n"
                "用法: `/punch admin sync @username`")
        return
    
    slack_user_mention = args[0]
    
    # 從 mention 中提取用戶 ID
    if slack_user_mention.startswith('<@') and slack_user_mention.endswith('>'):
        slack_user_id = slack_user_mention[2:-1]
        if '|' in slack_user_id:
            slack_user_id = slack_user_id.split('|')[0]
    else:
        respond("❌ 請使用 @username 格式指定用戶！")
        return
    
    try:
        user = db.query(User).filter(User.slack_user_id == slack_user_id).first()
        if not user:
            respond("❌ 用戶不存在於系統中！")
            return
        
        # 同步用戶資料
        success = user_sync_service.sync_single_user(db, client, slack_user_id)
        
        if success:
            respond(f"✅ 已成功同步用戶 {user.internal_real_name} 的 Slack 資料！")
        else:
            respond(f"❌ 同步用戶 {user.internal_real_name} 的資料失敗！")
    
    except Exception as e:
        respond(f"❌ 同步用戶資料失敗: {str(e)}")


def _handle_system_stats(db, respond):
    """處理系統統計"""
    try:
        # 基本統計
        total_users = db.query(User).filter(User.is_active == True).count()
        total_records = db.query(AttendanceRecord).count()
        
        # 今日統計
        today = get_today()
        today_records = db.query(AttendanceRecord).join(User).filter(
            func.date(AttendanceRecord.timestamp) == today,
            User.is_active == True
        ).count()
        
        # 本週統計
        week_start = get_week_start(today)
        week_records = db.query(AttendanceRecord).join(User).filter(
            func.date(AttendanceRecord.timestamp) >= week_start,
            User.is_active == True
        ).count()
        
        # 部門統計
        dept_stats = db.query(
            User.department,
            func.count(User.id)
        ).filter(User.is_active == True).group_by(User.department).all()
        
        response = [
            "📊 **系統統計資訊**\n",
            f"👥 總用戶數: {total_users}",
            f"📝 總打卡記錄: {total_records}",
            f"📅 今日打卡: {today_records} 次",
            f"📈 本週打卡: {week_records} 次",
            "",
            "🏢 **部門分布:**"
        ]
        
        for dept, count in dept_stats:
            dept_name = dept or "未分配"
            response.append(f"• {dept_name}: {count} 人")
        
        respond("\n".join(response))
    
    except Exception as e:
        respond(f"❌ 查看系統統計失敗: {str(e)}")


def _generate_csv_report(records: List[AttendanceRecord], start_date: date, end_date: date) -> str:
    """生成 CSV 報表"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 寫入標題
    writer.writerow([
        "日期", "時間", "姓名", "部門", "Slack用戶名", 
        "動作", "備註", "是否自動打卡"
    ])
    
    # 寫入資料
    for record in records:
        action_names = {
            'in': '上班', 'out': '下班',
            'break': '休息', 'back': '回來'
        }
        
        writer.writerow([
            record.timestamp.strftime("%Y-%m-%d"),
            record.timestamp.strftime("%H:%M:%S"),
            record.user.internal_real_name,
            record.user.department or "未分配",
            record.user.slack_username,
            action_names.get(record.action, record.action),
            record.note or "",
            "是" if record.is_auto else "否"
        ])
    
    return output.getvalue()


def _get_admin_help_message() -> str:
    """獲取管理員幫助訊息"""
    return """👑 **管理員指令說明**

**用戶管理:**
• `/punch admin invite @user "真實姓名" "部門"` - 邀請新用戶
• `/punch admin remove @user` - 移除用戶
• `/punch admin users` - 查看所有用戶
• `/punch admin sync @user` - 同步用戶 Slack 資料

**團隊監控:**
• `/punch admin team` - 查看團隊即時狀態
• `/punch admin stats` - 查看系統統計資訊

**報表匯出:**
• `/punch admin export` - 匯出本週報表
• `/punch admin export 2024-12-25` - 匯出指定日期報表
• `/punch admin export 2024-12-01 2024-12-31` - 匯出日期範圍報表

**其他:**
• `/punch admin help` - 查看此幫助訊息

⚠️ 注意: 這些指令僅限管理員使用"""