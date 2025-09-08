"""
User management service layer for user CRUD operations and Slack synchronization.
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.utils.validators import DataValidator
from app.config import settings

logger = logging.getLogger(__name__)

class UserService:
    """用戶管理業務邏輯服務"""
    
    def __init__(self, db: Session):
        self.db = db
        self.validator = DataValidator()
    
    def create_user(self, user_data: UserCreate) -> User:
        """
        建立新用戶。
        
        Args:
            user_data: 用戶建立資料
        
        Returns:
            新建立的用戶
        
        Raises:
            ValueError: 如果用戶已存在或資料無效
        """
        try:
            # 驗證資料
            self._validate_user_data(user_data)
            
            # 檢查 Slack 用戶 ID 是否已存在
            existing_user = self.db.query(User).filter(
                User.slack_user_id == user_data.slack_user_id
            ).first()
            
            if existing_user:
                raise ValueError("User with this Slack ID already exists")
            
            # 建立新用戶
            new_user = User(
                slack_user_id=user_data.slack_user_id,
                slack_username=user_data.slack_username,
                slack_display_name=user_data.slack_display_name,
                slack_real_name=user_data.slack_real_name,
                slack_email=user_data.slack_email,
                slack_avatar_url=user_data.slack_avatar_url,
                internal_real_name=user_data.internal_real_name,
                department=user_data.department,
                role=user_data.role,
                standard_hours=user_data.standard_hours,
                timezone=user_data.timezone,
                is_active=user_data.is_active
            )
            
            self.db.add(new_user)
            self.db.commit()
            self.db.refresh(new_user)
            
            logger.info(f"Created new user: {new_user.slack_user_id} - {new_user.internal_real_name}")
            return new_user
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create user: {str(e)}")
            raise ValueError(f"Failed to create user: {str(e)}")
    
    def update_user(self, user_id: int, update_data: UserUpdate) -> User:
        """
        更新用戶資料。
        
        Args:
            user_id: 用戶 ID
            update_data: 更新資料
        
        Returns:
            更新後的用戶
        
        Raises:
            ValueError: 如果用戶不存在或更新失敗
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            
            if not user:
                raise ValueError("User not found")
            
            # 準備更新資料
            update_dict = update_data.dict(exclude_unset=True, exclude_none=True)
            
            # 驗證更新資料
            if update_dict:
                self._validate_user_update(update_dict)
            
            # 應用更新
            for field, value in update_dict.items():
                if hasattr(user, field):
                    setattr(user, field, value)
            
            # 更新 updated_at 時間戳
            user.updated_at = func.now()
            
            self.db.commit()
            self.db.refresh(user)
            
            logger.info(f"Updated user: {user.slack_user_id} - {user.internal_real_name}")
            return user
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update user {user_id}: {str(e)}")
            raise ValueError(f"Failed to update user: {str(e)}")
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        根據 ID 取得用戶。
        
        Args:
            user_id: 用戶 ID
        
        Returns:
            用戶物件或 None
        """
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_user_by_slack_id(self, slack_user_id: str) -> Optional[User]:
        """
        根據 Slack 用戶 ID 取得用戶。
        
        Args:
            slack_user_id: Slack 用戶 ID
        
        Returns:
            用戶物件或 None
        """
        return self.db.query(User).filter(User.slack_user_id == slack_user_id).first()
    
    def get_users_list(
        self, 
        skip: int = 0, 
        limit: int = 100, 
        search: str = None,
        department: str = None,
        role: str = None,
        is_active: bool = None
    ) -> Tuple[List[User], int]:
        """
        取得用戶列表，支援篩選和分頁。
        
        Args:
            skip: 跳過的記錄數
            limit: 限制返回的記錄數
            search: 搜尋關鍵字
            department: 部門篩選
            role: 角色篩選
            is_active: 啟用狀態篩選
        
        Returns:
            (用戶列表, 總數) 的元組
        """
        try:
            # 構建查詢
            query = self.db.query(User)
            
            # 應用篩選條件
            if search:
                search_filter = f"%{search}%"
                query = query.filter(
                    or_(
                        User.internal_real_name.ilike(search_filter),
                        User.slack_real_name.ilike(search_filter),
                        User.slack_email.ilike(search_filter),
                        User.slack_username.ilike(search_filter),
                        User.slack_display_name.ilike(search_filter)
                    )
                )
            
            if department:
                query = query.filter(User.department.ilike(f"%{department}%"))
            
            if role:
                query = query.filter(User.role == role)
            
            if is_active is not None:
                query = query.filter(User.is_active == is_active)
            
            # 取得總數
            total = query.count()
            
            # 應用分頁並取得結果
            users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
            
            return users, total
            
        except Exception as e:
            logger.error(f"Failed to get users list: {str(e)}")
            raise ValueError(f"Failed to get users list: {str(e)}")
    
    def deactivate_user(self, user_id: int) -> User:
        """
        停用用戶（軟刪除）。
        
        Args:
            user_id: 用戶 ID
        
        Returns:
            停用後的用戶
        
        Raises:
            ValueError: 如果用戶不存在
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            
            if not user:
                raise ValueError("User not found")
            
            user.is_active = False
            user.updated_at = func.now()
            
            self.db.commit()
            self.db.refresh(user)
            
            logger.info(f"Deactivated user: {user.slack_user_id} - {user.internal_real_name}")
            return user
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to deactivate user {user_id}: {str(e)}")
            raise ValueError(f"Failed to deactivate user: {str(e)}")
    
    def activate_user(self, user_id: int) -> User:
        """
        啟用用戶。
        
        Args:
            user_id: 用戶 ID
        
        Returns:
            啟用後的用戶
        
        Raises:
            ValueError: 如果用戶不存在
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            
            if not user:
                raise ValueError("User not found")
            
            user.is_active = True
            user.updated_at = func.now()
            
            self.db.commit()
            self.db.refresh(user)
            
            logger.info(f"Activated user: {user.slack_user_id} - {user.internal_real_name}")
            return user
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to activate user {user_id}: {str(e)}")
            raise ValueError(f"Failed to activate user: {str(e)}")
    
    def bulk_import_users(self, users_data: List[Dict]) -> Dict:
        """
        批量匯入用戶。
        
        Args:
            users_data: 用戶資料列表
        
        Returns:
            匯入結果統計
        """
        try:
            imported_count = 0
            failed_count = 0
            errors = []
            
            for i, user_dict in enumerate(users_data):
                try:
                    # 檢查用戶是否已存在
                    existing_user = self.db.query(User).filter(
                        User.slack_user_id == user_dict['slack_user_id']
                    ).first()
                    
                    if existing_user:
                        # 更新現有用戶
                        update_data = UserUpdate(**user_dict)
                        self.update_user(existing_user.id, update_data)
                    else:
                        # 建立新用戶
                        create_data = UserCreate(**user_dict)
                        self.create_user(create_data)
                    
                    imported_count += 1
                    
                except Exception as e:
                    failed_count += 1
                    errors.append({
                        "row": i + 1,
                        "data": user_dict,
                        "error": str(e)
                    })
                    logger.error(f"Failed to import user at row {i + 1}: {str(e)}")
            
            result = {
                "imported_count": imported_count,
                "failed_count": failed_count,
                "total_processed": len(users_data),
                "errors": errors,
                "success_rate": (imported_count / len(users_data)) * 100 if users_data else 0
            }
            
            logger.info(f"Bulk import completed: {imported_count} successful, {failed_count} failed")
            return result
            
        except Exception as e:
            logger.error(f"Bulk import failed: {str(e)}")
            raise ValueError(f"Bulk import failed: {str(e)}")
    
    async def sync_slack_user_data(self, slack_user_id: str) -> Tuple[User, List[str]]:
        """
        同步 Slack 用戶資料。
        
        Args:
            slack_user_id: Slack 用戶 ID
        
        Returns:
            (更新後的用戶, 更新的欄位列表) 的元組
        
        Note:
            這是一個範例實作，實際應該使用 Slack API 取得用戶資料
        """
        try:
            user = self.get_user_by_slack_id(slack_user_id)
            
            if not user:
                raise ValueError("User not found")
            
            # 這裡應該使用 Slack API 取得用戶資料
            # 目前使用模擬資料
            updated_fields = []
            
            # 模擬從 Slack API 取得的資料
            slack_data = await self._fetch_slack_user_data(slack_user_id)
            
            if slack_data:
                # 比較並更新欄位
                fields_to_check = [
                    'slack_username', 'slack_display_name', 'slack_real_name', 
                    'slack_email', 'slack_avatar_url'
                ]
                
                for field in fields_to_check:
                    slack_value = slack_data.get(field)
                    current_value = getattr(user, field)
                    
                    if slack_value and slack_value != current_value:
                        setattr(user, field, slack_value)
                        updated_fields.append(field)
                
                if updated_fields:
                    user.slack_data_updated_at = func.now()
                    user.updated_at = func.now()
                    self.db.commit()
                    self.db.refresh(user)
                    
                    logger.info(f"Synced Slack data for user {slack_user_id}: {updated_fields}")
            
            return user, updated_fields
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to sync Slack data for {slack_user_id}: {str(e)}")
            raise ValueError(f"Failed to sync Slack data: {str(e)}")
    
    def get_department_stats(self) -> Dict:
        """
        取得部門統計資料。
        
        Returns:
            部門統計字典
        """
        try:
            # 按部門分組統計
            department_stats = self.db.query(
                User.department,
                func.count(User.id).label('total'),
                func.sum(func.case((User.is_active == True, 1), else_=0)).label('active'),
                func.sum(func.case((User.role == 'admin', 1), else_=0)).label('admins')
            ).group_by(User.department).all()
            
            stats = {}
            total_users = 0
            total_active = 0
            
            for dept, total, active, admins in department_stats:
                dept_name = dept or "Unassigned"
                stats[dept_name] = {
                    "total": total,
                    "active": active,
                    "inactive": total - active,
                    "admins": admins,
                    "activity_rate": (active / total) * 100 if total > 0 else 0
                }
                total_users += total
                total_active += active
            
            return {
                "departments": stats,
                "overall": {
                    "total_users": total_users,
                    "active_users": total_active,
                    "inactive_users": total_users - total_active,
                    "departments_count": len(stats),
                    "overall_activity_rate": (total_active / total_users) * 100 if total_users > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get department stats: {str(e)}")
            raise ValueError(f"Failed to get department stats: {str(e)}")
    
    def get_role_distribution(self) -> Dict:
        """
        取得角色分佈統計。
        
        Returns:
            角色分佈字典
        """
        try:
            role_stats = self.db.query(
                User.role,
                func.count(User.id).label('count'),
                func.sum(func.case((User.is_active == True, 1), else_=0)).label('active')
            ).group_by(User.role).all()
            
            distribution = {}
            for role, count, active in role_stats:
                distribution[role] = {
                    "total": count,
                    "active": active,
                    "inactive": count - active
                }
            
            return distribution
            
        except Exception as e:
            logger.error(f"Failed to get role distribution: {str(e)}")
            raise ValueError(f"Failed to get role distribution: {str(e)}")
    
    def search_users(self, query: str, limit: int = 10) -> List[User]:
        """
        搜尋用戶。
        
        Args:
            query: 搜尋查詢字串
            limit: 限制返回結果數
        
        Returns:
            符合條件的用戶列表
        """
        try:
            search_filter = f"%{query}%"
            
            users = self.db.query(User).filter(
                and_(
                    User.is_active == True,
                    or_(
                        User.internal_real_name.ilike(search_filter),
                        User.slack_real_name.ilike(search_filter),
                        User.slack_email.ilike(search_filter),
                        User.slack_username.ilike(search_filter),
                        User.slack_display_name.ilike(search_filter),
                        User.department.ilike(search_filter)
                    )
                )
            ).limit(limit).all()
            
            return users
            
        except Exception as e:
            logger.error(f"Failed to search users: {str(e)}")
            raise ValueError(f"Failed to search users: {str(e)}")
    
    def _validate_user_data(self, user_data: UserCreate):
        """驗證用戶建立資料"""
        # 驗證 Slack 用戶 ID
        self.validator.validate_slack_user_id(user_data.slack_user_id)
        
        # 驗證 email（如果提供）
        if user_data.slack_email:
            self.validator.validate_email(user_data.slack_email)
        
        # 驗證部門（如果提供）
        if user_data.department:
            self.validator.validate_department(user_data.department)
        
        # 驗證角色
        self.validator.validate_role(user_data.role)
        
        # 驗證時區
        self.validator.validate_timezone(user_data.timezone)
        
        # 驗證標準工時
        self.validator.validate_standard_hours(user_data.standard_hours)
    
    def _validate_user_update(self, update_dict: Dict):
        """驗證用戶更新資料"""
        if 'slack_email' in update_dict and update_dict['slack_email']:
            self.validator.validate_email(update_dict['slack_email'])
        
        if 'department' in update_dict and update_dict['department']:
            self.validator.validate_department(update_dict['department'])
        
        if 'role' in update_dict:
            self.validator.validate_role(update_dict['role'])
        
        if 'timezone' in update_dict:
            self.validator.validate_timezone(update_dict['timezone'])
        
        if 'standard_hours' in update_dict:
            self.validator.validate_standard_hours(update_dict['standard_hours'])
    
    async def _fetch_slack_user_data(self, slack_user_id: str) -> Optional[Dict]:
        """
        從 Slack API 取得用戶資料（範例實作）。
        
        Args:
            slack_user_id: Slack 用戶 ID
        
        Returns:
            Slack 用戶資料字典或 None
        
        Note:
            實際實作應該使用 Slack Web API 取得用戶資料
        """
        try:
            # 這裡應該整合 Slack API
            # 目前返回 None，表示沒有可用的同步資料
            logger.info(f"Fetching Slack data for user: {slack_user_id}")
            
            # 實際實作範例：
            # from slack_sdk import WebClient
            # slack_client = WebClient(token=settings.SLACK_BOT_TOKEN)
            # response = slack_client.users_info(user=slack_user_id)
            # if response["ok"]:
            #     user_info = response["user"]
            #     return {
            #         "slack_username": user_info.get("name"),
            #         "slack_display_name": user_info.get("profile", {}).get("display_name"),
            #         "slack_real_name": user_info.get("profile", {}).get("real_name"),
            #         "slack_email": user_info.get("profile", {}).get("email"),
            #         "slack_avatar_url": user_info.get("profile", {}).get("image_192")
            #     }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to fetch Slack user data: {str(e)}")
            return None