"""
Report service layer for generating attendance reports and analytics.
"""

import io
import csv
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc

from app.models.user import User
from app.models.attendance import AttendanceRecord
from app.services.attendance_service import AttendanceService
from app.config import settings

logger = logging.getLogger(__name__)

class ReportService:
    """報表業務邏輯服務"""
    
    def __init__(self, db: Session):
        self.db = db
        self.attendance_service = AttendanceService(db)
    
    async def generate_daily_report(
        self, 
        report_date: date, 
        department: str = None, 
        user_id: int = None
    ) -> Dict[str, Any]:
        """
        生成日報表。
        
        Args:
            report_date: 報表日期
            department: 部門篩選
            user_id: 用戶篩選
        
        Returns:
            日報表資料
        """
        try:
            # 取得每日摘要
            daily_summaries = self.attendance_service.get_daily_summary(report_date, user_id)
            
            # 應用部門篩選
            if department:
                department_users = self._get_users_by_department(department)
                department_user_ids = [u.id for u in department_users]
                daily_summaries = [s for s in daily_summaries if s['user_id'] in department_user_ids]
            
            # 計算工時摘要
            work_hours_summary = []
            for summary in daily_summaries:
                user = self.db.query(User).filter(User.id == summary['user_id']).first()
                if user:
                    work_hours = summary['total_work_minutes'] / 60
                    break_hours = summary['total_break_minutes'] / 60
                    expected_hours = user.standard_hours
                    overtime_hours = max(0, work_hours - expected_hours)
                    
                    work_hours_summary.append({
                        "user_id": user.id,
                        "user_name": user.internal_real_name,
                        "department": user.department,
                        "total_work_hours": round(work_hours, 2),
                        "total_break_hours": round(break_hours, 2),
                        "expected_hours": expected_hours,
                        "overtime_hours": round(overtime_hours, 2),
                        "attendance_rate": 100.0 if summary['is_complete'] else 0.0,
                        "days_worked": 1 if summary['is_complete'] else 0,
                        "days_expected": 1
                    })
            
            # 計算部門統計
            department_stats = self._calculate_department_stats(work_hours_summary)
            
            # 計算整體統計
            overall_stats = self._calculate_overall_stats(work_hours_summary, report_date, report_date)
            
            return {
                "report_type": "daily",
                "start_date": report_date,
                "end_date": report_date,
                "generated_at": datetime.utcnow(),
                "total_users": len(work_hours_summary),
                "work_hours_summary": work_hours_summary,
                "department_stats": department_stats,
                "overall_stats": overall_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to generate daily report: {str(e)}")
            raise ValueError(f"Failed to generate daily report: {str(e)}")
    
    async def generate_weekly_report(
        self, 
        start_date: date, 
        end_date: date, 
        department: str = None, 
        user_id: int = None
    ) -> Dict[str, Any]:
        """
        生成週報表。
        
        Args:
            start_date: 開始日期
            end_date: 結束日期
            department: 部門篩選
            user_id: 用戶篩選
        
        Returns:
            週報表資料
        """
        try:
            # 取得用戶列表
            users_query = self.db.query(User).filter(User.is_active == True)
            
            if user_id:
                users_query = users_query.filter(User.id == user_id)
            
            if department:
                users_query = users_query.filter(User.department.ilike(f"%{department}%"))
            
            users = users_query.all()
            
            # 計算每個用戶的週工時統計
            work_hours_summary = []
            for user in users:
                stats = self.attendance_service.get_work_time_stats(
                    user.id, start_date, end_date
                )
                
                work_hours_summary.append({
                    "user_id": user.id,
                    "user_name": user.internal_real_name,
                    "department": user.department,
                    "total_work_hours": stats["total_work_hours"],
                    "total_break_hours": stats["total_break_hours"],
                    "expected_hours": stats["expected_total_hours"],
                    "overtime_hours": stats["overtime_hours"],
                    "attendance_rate": stats["attendance_rate"],
                    "days_worked": stats["working_days"],
                    "days_expected": (end_date - start_date).days + 1
                })
            
            # 計算部門統計
            department_stats = self._calculate_department_stats(work_hours_summary)
            
            # 計算整體統計
            overall_stats = self._calculate_overall_stats(work_hours_summary, start_date, end_date)
            
            return {
                "report_type": "weekly",
                "start_date": start_date,
                "end_date": end_date,
                "generated_at": datetime.utcnow(),
                "total_users": len(work_hours_summary),
                "work_hours_summary": work_hours_summary,
                "department_stats": department_stats,
                "overall_stats": overall_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to generate weekly report: {str(e)}")
            raise ValueError(f"Failed to generate weekly report: {str(e)}")
    
    async def generate_monthly_report(
        self, 
        start_date: date, 
        end_date: date, 
        department: str = None, 
        user_id: int = None
    ) -> Dict[str, Any]:
        """
        生成月報表。
        
        Args:
            start_date: 開始日期
            end_date: 結束日期
            department: 部門篩選
            user_id: 用戶篩選
        
        Returns:
            月報表資料
        """
        try:
            # 使用週報表的邏輯，但加上月度特定分析
            report = await self.generate_weekly_report(start_date, end_date, department, user_id)
            
            # 更新報表類型
            report["report_type"] = "monthly"
            
            # 加入月度特定統計
            report["monthly_stats"] = await self._calculate_monthly_specific_stats(
                start_date, end_date, department, user_id
            )
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate monthly report: {str(e)}")
            raise ValueError(f"Failed to generate monthly report: {str(e)}")
    
    async def generate_custom_report(
        self, 
        start_date: date, 
        end_date: date, 
        department: str = None, 
        user_id: int = None
    ) -> Dict[str, Any]:
        """
        生成自訂期間報表。
        
        Args:
            start_date: 開始日期
            end_date: 結束日期
            department: 部門篩選
            user_id: 用戶篩選
        
        Returns:
            自訂報表資料
        """
        try:
            # 使用週報表邏輯作為基礎
            report = await self.generate_weekly_report(start_date, end_date, department, user_id)
            
            # 更新報表類型
            report["report_type"] = "custom"
            
            # 加入期間長度資訊
            period_days = (end_date - start_date).days + 1
            report["period_info"] = {
                "total_days": period_days,
                "work_days": self._calculate_work_days(start_date, end_date),
                "period_type": self._determine_period_type(period_days)
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate custom report: {str(e)}")
            raise ValueError(f"Failed to generate custom report: {str(e)}")
    
    async def generate_user_report(
        self, 
        user_id: int, 
        start_date: date, 
        end_date: date
    ) -> Dict[str, Any]:
        """
        生成個人報表。
        
        Args:
            user_id: 用戶 ID
            start_date: 開始日期
            end_date: 結束日期
        
        Returns:
            個人報表資料
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            # 取得用戶工時統計
            stats = self.attendance_service.get_work_time_stats(user_id, start_date, end_date)
            
            # 取得每日詳細記錄
            daily_details = []
            current_date = start_date
            while current_date <= end_date:
                daily_records = self.attendance_service.get_user_daily_records(user_id, current_date)
                if daily_records:
                    work_minutes, break_minutes = self.attendance_service._calculate_work_time_from_records(
                        daily_records
                    )
                    
                    daily_details.append({
                        "date": current_date,
                        "records": [
                            {
                                "action": r.action,
                                "timestamp": r.timestamp,
                                "is_auto": r.is_auto,
                                "note": r.note
                            } for r in daily_records
                        ],
                        "work_minutes": work_minutes,
                        "break_minutes": break_minutes,
                        "work_hours": round(work_minutes / 60, 2)
                    })
                
                current_date += timedelta(days=1)
            
            return {
                "report_type": "user",
                "user_id": user_id,
                "user_name": user.internal_real_name,
                "department": user.department,
                "start_date": start_date,
                "end_date": end_date,
                "generated_at": datetime.utcnow(),
                "summary": {
                    "total_work_hours": stats["total_work_hours"],
                    "total_break_hours": stats["total_break_hours"],
                    "working_days": stats["working_days"],
                    "avg_daily_hours": stats["avg_daily_hours"],
                    "expected_total_hours": stats["expected_total_hours"],
                    "overtime_hours": stats["overtime_hours"],
                    "attendance_rate": stats["attendance_rate"]
                },
                "daily_details": daily_details
            }
            
        except Exception as e:
            logger.error(f"Failed to generate user report: {str(e)}")
            raise ValueError(f"Failed to generate user report: {str(e)}")
    
    async def generate_department_analytics(
        self, 
        start_date: date, 
        end_date: date
    ) -> Dict[str, Any]:
        """
        生成部門分析報表。
        
        Args:
            start_date: 開始日期
            end_date: 結束日期
        
        Returns:
            部門分析資料
        """
        try:
            # 取得所有部門的用戶
            departments = self.db.query(User.department).filter(
                User.is_active == True,
                User.department.isnot(None)
            ).distinct().all()
            
            department_analytics = {}
            
            for (dept,) in departments:
                dept_users = self.db.query(User).filter(
                    User.department == dept,
                    User.is_active == True
                ).all()
                
                dept_stats = []
                for user in dept_users:
                    stats = self.attendance_service.get_work_time_stats(
                        user.id, start_date, end_date
                    )
                    dept_stats.append(stats)
                
                if dept_stats:
                    department_analytics[dept] = {
                        "users_count": len(dept_stats),
                        "total_work_hours": sum(s["total_work_hours"] for s in dept_stats),
                        "avg_work_hours": sum(s["total_work_hours"] for s in dept_stats) / len(dept_stats),
                        "total_overtime_hours": sum(s["overtime_hours"] for s in dept_stats),
                        "avg_attendance_rate": sum(s["attendance_rate"] for s in dept_stats) / len(dept_stats),
                        "most_productive_user": max(dept_stats, key=lambda x: x["total_work_hours"]),
                        "least_productive_user": min(dept_stats, key=lambda x: x["total_work_hours"])
                    }
            
            return {
                "start_date": start_date,
                "end_date": end_date,
                "generated_at": datetime.utcnow(),
                "departments": department_analytics,
                "comparison": self._compare_departments(department_analytics)
            }
            
        except Exception as e:
            logger.error(f"Failed to generate department analytics: {str(e)}")
            raise ValueError(f"Failed to generate department analytics: {str(e)}")
    
    async def generate_overtime_analytics(
        self, 
        start_date: date, 
        end_date: date, 
        department: str = None
    ) -> List[Dict[str, Any]]:
        """
        生成加班分析報表。
        
        Args:
            start_date: 開始日期
            end_date: 結束日期
            department: 部門篩選
        
        Returns:
            加班分析資料列表
        """
        try:
            # 取得用戶列表
            users_query = self.db.query(User).filter(User.is_active == True)
            
            if department:
                users_query = users_query.filter(User.department.ilike(f"%{department}%"))
            
            users = users_query.all()
            
            overtime_analytics = []
            for user in users:
                stats = self.attendance_service.get_work_time_stats(
                    user.id, start_date, end_date
                )
                
                if stats["overtime_hours"] > 0:
                    overtime_analytics.append({
                        "user_id": user.id,
                        "user_name": user.internal_real_name,
                        "department": user.department,
                        "total_work_hours": stats["total_work_hours"],
                        "expected_hours": stats["expected_total_hours"],
                        "overtime_hours": stats["overtime_hours"],
                        "overtime_percentage": (stats["overtime_hours"] / stats["expected_total_hours"]) * 100,
                        "working_days": stats["working_days"],
                        "avg_daily_overtime": stats["overtime_hours"] / stats["working_days"] if stats["working_days"] > 0 else 0
                    })
            
            # 按加班時數排序
            overtime_analytics.sort(key=lambda x: x["overtime_hours"], reverse=True)
            
            return overtime_analytics
            
        except Exception as e:
            logger.error(f"Failed to generate overtime analytics: {str(e)}")
            raise ValueError(f"Failed to generate overtime analytics: {str(e)}")
    
    async def export_daily_report(
        self, 
        report_date: date, 
        export_format: str, 
        department: str = None, 
        user_id: int = None
    ) -> Tuple[bytes, str, str]:
        """
        匯出日報表。
        
        Args:
            report_date: 報表日期
            export_format: 匯出格式 (csv, excel, pdf)
            department: 部門篩選
            user_id: 用戶篩選
        
        Returns:
            (檔案內容, 檔案名稱, 內容類型) 的元組
        """
        try:
            report = await self.generate_daily_report(report_date, department, user_id)
            
            filename_date = report_date.strftime("%Y%m%d")
            dept_suffix = f"_{department}" if department else ""
            
            if export_format.lower() == "csv":
                content = self._export_to_csv(report["work_hours_summary"])
                filename = f"daily_report_{filename_date}{dept_suffix}.csv"
                content_type = "text/csv"
            else:
                raise ValueError(f"Unsupported export format: {export_format}")
            
            return content, filename, content_type
            
        except Exception as e:
            logger.error(f"Failed to export daily report: {str(e)}")
            raise ValueError(f"Failed to export daily report: {str(e)}")
    
    async def export_weekly_report(
        self, 
        start_date: date, 
        end_date: date, 
        export_format: str, 
        department: str = None, 
        user_id: int = None
    ) -> Tuple[bytes, str, str]:
        """匯出週報表"""
        try:
            report = await self.generate_weekly_report(start_date, end_date, department, user_id)
            
            filename_date = f"{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}"
            dept_suffix = f"_{department}" if department else ""
            
            if export_format.lower() == "csv":
                content = self._export_to_csv(report["work_hours_summary"])
                filename = f"weekly_report_{filename_date}{dept_suffix}.csv"
                content_type = "text/csv"
            else:
                raise ValueError(f"Unsupported export format: {export_format}")
            
            return content, filename, content_type
            
        except Exception as e:
            logger.error(f"Failed to export weekly report: {str(e)}")
            raise ValueError(f"Failed to export weekly report: {str(e)}")
    
    async def export_monthly_report(
        self, 
        year: int, 
        month: int, 
        export_format: str, 
        department: str = None, 
        user_id: int = None
    ) -> Tuple[bytes, str, str]:
        """匯出月報表"""
        try:
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
            
            report = await self.generate_monthly_report(start_date, end_date, department, user_id)
            
            filename_date = f"{year}{month:02d}"
            dept_suffix = f"_{department}" if department else ""
            
            if export_format.lower() == "csv":
                content = self._export_to_csv(report["work_hours_summary"])
                filename = f"monthly_report_{filename_date}{dept_suffix}.csv"
                content_type = "text/csv"
            else:
                raise ValueError(f"Unsupported export format: {export_format}")
            
            return content, filename, content_type
            
        except Exception as e:
            logger.error(f"Failed to export monthly report: {str(e)}")
            raise ValueError(f"Failed to export monthly report: {str(e)}")
    
    async def export_custom_report(
        self, 
        start_date: date, 
        end_date: date, 
        export_format: str, 
        department: str = None, 
        user_id: int = None
    ) -> Tuple[bytes, str, str]:
        """匯出自訂報表"""
        try:
            report = await self.generate_custom_report(start_date, end_date, department, user_id)
            
            filename_date = f"{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}"
            dept_suffix = f"_{department}" if department else ""
            
            if export_format.lower() == "csv":
                content = self._export_to_csv(report["work_hours_summary"])
                filename = f"custom_report_{filename_date}{dept_suffix}.csv"
                content_type = "text/csv"
            else:
                raise ValueError(f"Unsupported export format: {export_format}")
            
            return content, filename, content_type
            
        except Exception as e:
            logger.error(f"Failed to export custom report: {str(e)}")
            raise ValueError(f"Failed to export custom report: {str(e)}")
    
    def _get_users_by_department(self, department: str) -> List[User]:
        """取得指定部門的用戶"""
        return self.db.query(User).filter(
            User.department.ilike(f"%{department}%"),
            User.is_active == True
        ).all()
    
    def _calculate_department_stats(self, work_hours_summary: List[Dict]) -> Dict[str, Any]:
        """計算部門統計"""
        dept_stats = {}
        
        for summary in work_hours_summary:
            dept = summary.get("department") or "Unassigned"
            
            if dept not in dept_stats:
                dept_stats[dept] = {
                    "users_count": 0,
                    "total_work_hours": 0,
                    "total_overtime_hours": 0,
                    "total_attendance_rate": 0
                }
            
            dept_stats[dept]["users_count"] += 1
            dept_stats[dept]["total_work_hours"] += summary["total_work_hours"]
            dept_stats[dept]["total_overtime_hours"] += summary["overtime_hours"]
            dept_stats[dept]["total_attendance_rate"] += summary["attendance_rate"]
        
        # 計算平均值
        for dept, stats in dept_stats.items():
            if stats["users_count"] > 0:
                stats["avg_work_hours"] = stats["total_work_hours"] / stats["users_count"]
                stats["avg_overtime_hours"] = stats["total_overtime_hours"] / stats["users_count"]
                stats["avg_attendance_rate"] = stats["total_attendance_rate"] / stats["users_count"]
        
        return dept_stats
    
    def _calculate_overall_stats(
        self, 
        work_hours_summary: List[Dict], 
        start_date: date, 
        end_date: date
    ) -> Dict[str, Any]:
        """計算整體統計"""
        if not work_hours_summary:
            return {}
        
        total_users = len(work_hours_summary)
        total_work_hours = sum(s["total_work_hours"] for s in work_hours_summary)
        total_overtime_hours = sum(s["overtime_hours"] for s in work_hours_summary)
        avg_attendance_rate = sum(s["attendance_rate"] for s in work_hours_summary) / total_users
        
        return {
            "total_users": total_users,
            "total_work_hours": round(total_work_hours, 2),
            "avg_work_hours_per_user": round(total_work_hours / total_users, 2),
            "total_overtime_hours": round(total_overtime_hours, 2),
            "avg_overtime_hours_per_user": round(total_overtime_hours / total_users, 2),
            "avg_attendance_rate": round(avg_attendance_rate, 2),
            "report_period_days": (end_date - start_date).days + 1
        }
    
    async def _calculate_monthly_specific_stats(
        self, 
        start_date: date, 
        end_date: date, 
        department: str = None, 
        user_id: int = None
    ) -> Dict[str, Any]:
        """計算月度特定統計"""
        # 計算工作日數量
        work_days = self._calculate_work_days(start_date, end_date)
        
        # 計算每週統計
        weekly_stats = []
        current_week_start = start_date
        
        while current_week_start <= end_date:
            week_end = min(current_week_start + timedelta(days=6), end_date)
            week_report = await self.generate_weekly_report(
                current_week_start, week_end, department, user_id
            )
            
            weekly_stats.append({
                "week_start": current_week_start,
                "week_end": week_end,
                "total_work_hours": week_report["overall_stats"]["total_work_hours"],
                "avg_attendance_rate": week_report["overall_stats"]["avg_attendance_rate"]
            })
            
            current_week_start = week_end + timedelta(days=1)
        
        return {
            "work_days": work_days,
            "total_days": (end_date - start_date).days + 1,
            "weekly_breakdown": weekly_stats
        }
    
    def _calculate_work_days(self, start_date: date, end_date: date) -> int:
        """計算工作日數量（排除週末）"""
        work_days = 0
        current_date = start_date
        
        while current_date <= end_date:
            # 0-6 代表週一到週日，0-4 是工作日
            if current_date.weekday() < 5:
                work_days += 1
            current_date += timedelta(days=1)
        
        return work_days
    
    def _determine_period_type(self, days: int) -> str:
        """根據天數判斷期間類型"""
        if days == 1:
            return "daily"
        elif days <= 7:
            return "weekly"
        elif days <= 31:
            return "monthly"
        elif days <= 92:
            return "quarterly"
        else:
            return "custom_long"
    
    def _compare_departments(self, department_analytics: Dict) -> Dict:
        """比較部門表現"""
        if not department_analytics:
            return {}
        
        # 找出最佳和最差表現的部門
        best_productivity = max(
            department_analytics.items(),
            key=lambda x: x[1]["avg_work_hours"]
        )
        
        worst_productivity = min(
            department_analytics.items(),
            key=lambda x: x[1]["avg_work_hours"]
        )
        
        best_attendance = max(
            department_analytics.items(),
            key=lambda x: x[1]["avg_attendance_rate"]
        )
        
        return {
            "most_productive_department": {
                "name": best_productivity[0],
                "avg_work_hours": best_productivity[1]["avg_work_hours"]
            },
            "least_productive_department": {
                "name": worst_productivity[0],
                "avg_work_hours": worst_productivity[1]["avg_work_hours"]
            },
            "best_attendance_department": {
                "name": best_attendance[0],
                "avg_attendance_rate": best_attendance[1]["avg_attendance_rate"]
            }
        }
    
    def _export_to_csv(self, data: List[Dict]) -> bytes:
        """匯出資料為 CSV 格式"""
        if not data:
            return b"No data available"
        
        output = io.StringIO()
        fieldnames = data[0].keys()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        
        writer.writeheader()
        for row in data:
            writer.writerow(row)
        
        return output.getvalue().encode('utf-8')