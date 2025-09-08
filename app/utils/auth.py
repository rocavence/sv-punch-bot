"""
Authentication utilities for JWT token handling and OAuth2 authentication.
"""

from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token scheme
security = HTTPBearer()

class AuthError(Exception):
    """Custom authentication error"""
    pass

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Data to encode in the token
        expires_delta: Token expiration time delta
    
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> dict:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token to verify
    
    Returns:
        Decoded token payload
    
    Raises:
        AuthError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise AuthError("Could not validate credentials")

def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer credentials
        db: Database session
    
    Returns:
        Current user object
    
    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        payload = verify_token(token)
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except AuthError:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get the current active user.
    
    Args:
        current_user: Current user from token
    
    Returns:
        Current active user
    
    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get the current admin user.
    
    Args:
        current_user: Current active user
    
    Returns:
        Current admin user
    
    Raises:
        HTTPException: If user is not an admin
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

def create_admin_token(user_id: int, slack_user_id: str) -> str:
    """
    Create an admin access token for a user.
    
    Args:
        user_id: User ID
        slack_user_id: Slack user ID
    
    Returns:
        JWT token string
    """
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_id, "slack_user_id": slack_user_id},
        expires_delta=access_token_expires
    )
    return access_token

class SlackAuthenticator:
    """Slack-based authentication helper."""
    
    def __init__(self):
        self.admin_slack_ids = getattr(settings, 'ADMIN_SLACK_IDS', [])
    
    def is_slack_admin(self, slack_user_id: str) -> bool:
        """Check if a Slack user ID is an admin."""
        return slack_user_id in self.admin_slack_ids
    
    def authenticate_slack_user(self, slack_user_id: str, db: Session) -> Optional[User]:
        """
        Authenticate a user by their Slack ID.
        
        Args:
            slack_user_id: Slack user ID
            db: Database session
        
        Returns:
            User object if found and active, None otherwise
        """
        user = db.query(User).filter(
            User.slack_user_id == slack_user_id,
            User.is_active == True
        ).first()
        
        return user

# Global authenticator instance
slack_auth = SlackAuthenticator()