"""
Main FastAPI application for Punch Bot with Multi-Workspace Support
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware
from slack_bolt.adapter.fastapi import SlackRequestHandler
import os
import logging
from pathlib import Path

# Import database
from app.database import engine, get_db
from app.models import user, attendance, leave

# Import API routes
from app.api import auth, users as api_users, attendance as api_attendance, reports as api_reports, oauth

# Import web routes  
from app.web.routes import dashboard, users, attendance as attendance_routes, reports

# Import multi-workspace Slack bot
from app.slack.multi_workspace_bot import get_multi_workspace_bot

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Punch Bot Management System",
    description="A comprehensive Slack-based punch clock system with web management interface and REST API",
    version="1.0.0",
    docs_url="/docs" if os.getenv("DEBUG", "false").lower() == "true" else None,
    redoc_url="/redoc" if os.getenv("DEBUG", "false").lower() == "true" else None,
    openapi_tags=[
        {
            "name": "authentication",
            "description": "Authentication and authorization operations",
        },
        {
            "name": "users-api",
            "description": "User management API operations",
        },
        {
            "name": "attendance-api",
            "description": "Attendance records API operations",
        },
        {
            "name": "reports-api",
            "description": "Reports and analytics API operations",
        },
        {
            "name": "dashboard",
            "description": "Web dashboard interface",
        },
        {
            "name": "users-web",
            "description": "Web user management interface",
        },
        {
            "name": "attendance-web",
            "description": "Web attendance management interface",
        },
        {
            "name": "reports-web",
            "description": "Web reports interface",
        }
    ]
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "your-secret-key-here"),
    max_age=86400  # 24 hours
)

# Add trusted host middleware for security
if not os.getenv("DEBUG", "false").lower() == "true":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # Configure appropriately for production
    )

# Mount static files
static_path = Path(__file__).parent.parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Initialize templates
templates = Jinja2Templates(directory="app/web/templates")

# Global template context
@app.middleware("http")
async def add_template_context(request: Request, call_next):
    """Add global context to all template responses"""
    response = await call_next(request)
    return response

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    """Handle 404 errors with custom template"""
    return templates.TemplateResponse(
        "errors/404.html", 
        {"request": request}, 
        status_code=404
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: HTTPException):
    """Handle 500 errors with custom template"""
    logger.error(f"Internal server error: {exc}")
    return templates.TemplateResponse(
        "errors/500.html", 
        {"request": request}, 
        status_code=500
    )

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Test database connection
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        return {
            "status": "healthy",
            "database": "connected",
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")

# Root redirect
@app.get("/")
async def root():
    """Redirect root to dashboard"""
    return RedirectResponse(url="/dashboard", status_code=302)

# Include API routes
from app.config import settings

# Initialize multi-workspace Slack bot
slack_bot = get_multi_workspace_bot()
slack_app = slack_bot.start()

# Create Slack request handler for FastAPI
slack_handler = SlackRequestHandler(slack_app)

# Include OAuth routes for Slack App installation
app.include_router(
    oauth.router,
    prefix="",
    tags=["oauth"]
)

app.include_router(
    auth.router,
    prefix=settings.API_PREFIX,
    tags=["authentication"]
)

app.include_router(
    api_users.router,
    prefix=settings.API_PREFIX,
    tags=["users-api"]
)

app.include_router(
    api_attendance.router,
    prefix=settings.API_PREFIX,
    tags=["attendance-api"]
)

app.include_router(
    api_reports.router,
    prefix=settings.API_PREFIX,
    tags=["reports-api"]
)

# Slack endpoints for events and commands
@app.post("/slack/events")
async def slack_events(req: Request):
    """Handle Slack events"""
    return await slack_handler.handle(req)

@app.post("/slack/commands") 
async def slack_commands(req: Request):
    """Handle Slack slash commands"""
    return await slack_handler.handle(req)

# Include web routes
app.include_router(
    dashboard.router,
    prefix="",
    tags=["dashboard"]
)

app.include_router(
    users.router,
    prefix="/admin/users",
    tags=["users-web"]
)

app.include_router(
    attendance_routes.router,
    prefix="/admin/attendance",
    tags=["attendance-web"]
)

app.include_router(
    reports.router,
    prefix="/admin/reports",
    tags=["reports-web"]
)

# Authentication routes (placeholder)
@app.get("/auth/login")
async def login_form(request: Request):
    """Login form (placeholder)"""
    return templates.TemplateResponse("auth/login.html", {"request": request})

@app.post("/auth/login")
async def login(request: Request):
    """Handle login (placeholder)"""
    # TODO: Implement proper authentication
    return RedirectResponse(url="/dashboard", status_code=302)

@app.get("/auth/logout")
async def logout(request: Request):
    """Handle logout (placeholder)"""
    # TODO: Implement proper logout
    return RedirectResponse(url="/auth/login", status_code=302)

# API routes for AJAX calls
@app.get("/api/stats/realtime")
async def get_realtime_stats(db = next(get_db())):
    """Get real-time statistics for dashboard"""
    try:
        from datetime import datetime, date
        from sqlalchemy import func, and_
        from app.models.user import User
        from app.models.attendance import AttendanceRecord
        
        today = datetime.now().date()
        
        # Get basic stats
        total_users = db.query(User).filter(User.is_active == True).count()
        
        today_records = db.query(AttendanceRecord).join(User).filter(
            and_(
                func.date(AttendanceRecord.timestamp) == today,
                User.is_active == True
            )
        ).all()
        
        users_punched_in = set()
        users_punched_out = set()
        
        for record in today_records:
            if record.action == 'in':
                users_punched_in.add(record.user_id)
            elif record.action == 'out':
                users_punched_out.add(record.user_id)
        
        return {
            "total_users": total_users,
            "present_count": len(users_punched_in),
            "completed_count": len(users_punched_out),
            "absent_count": total_users - len(users_punched_in),
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get realtime stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")

@app.get("/api/stats/weekly")
async def get_weekly_stats(db = next(get_db())):
    """Get weekly statistics for dashboard chart"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func, and_
        from app.models.user import User
        from app.models.attendance import AttendanceRecord
        import calendar
        
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        
        week_data = []
        for i in range(7):
            day = start_of_week + timedelta(days=i)
            day_records = db.query(AttendanceRecord).join(User).filter(
                and_(
                    func.date(AttendanceRecord.timestamp) == day,
                    User.is_active == True
                )
            ).count()
            
            week_data.append({
                'date': day.strftime('%m/%d'),
                'day': calendar.day_name[day.weekday()][:3],
                'records': day_records
            })
        
        return {"week_data": week_data}
    except Exception as e:
        logger.error(f"Failed to get weekly stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get weekly statistics")

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info("Starting Multi-Workspace Punch Bot Management System")
    
    # Create database tables if they don't exist
    try:
        from app.database import Base
        
        # This will create tables if they don't exist
        # In production, use Alembic migrations instead
        Base.metadata.create_all(bind=engine)
        
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    
    # Initialize multi-workspace bot
    try:
        logger.info("Multi-Workspace Slack Bot initialized and ready for installations")
    except Exception as e:
        logger.error(f"Failed to initialize Slack bot: {e}")
    
    logger.info("Multi-Workspace Punch Bot Management System started successfully")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    logger.info("Shutting down Multi-Workspace Punch Bot Management System")
    
    # Stop multi-workspace bot
    try:
        from app.slack.multi_workspace_bot import stop_multi_workspace_bot
        stop_multi_workspace_bot()
        logger.info("Multi-workspace Slack bot stopped")
    except Exception as e:
        logger.error(f"Error stopping Slack bot: {e}")

if __name__ == "__main__":
    import uvicorn
    
    # Development server
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true",
        log_level="info"
    )