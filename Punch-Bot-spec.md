# Punch-Bot 完整系統開發規劃書

## 專案概述
基於 Python 開發的 Slack 打卡機器人系統，支援混合辦公制度，包含 Slack Bot 和 Web 管理介面。部署在 Render.com 平台。

## 技術架構

### 後端技術棧
- **主框架**: FastAPI 0.104+
- **資料庫**: PostgreSQL + SQLAlchemy 2.0
- **Slack SDK**: slack-bolt-python
- **認證**: JWT Token + OAuth2
- **任務排程**: APScheduler
- **容器化**: Docker
- **部署**: Render.com

### 前端技術棧
- **模板引擎**: Jinja2
- **CSS 框架**: Bootstrap 5.3
- **JavaScript**: Vanilla JS + Fetch API
- **圖表**: Chart.js

## 專案結構

```
punch-bot/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 主應用
│   ├── config.py              # 配置管理
│   ├── database.py            # 資料庫連接
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py            # 用戶模型
│   │   ├── attendance.py      # 打卡記錄模型
│   │   └── leave.py           # 休假記錄模型
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py            # 用戶 Pydantic 模型
│   │   ├── attendance.py      # 打卡 Pydantic 模型
│   │   └── leave.py           # 休假 Pydantic 模型
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py            # 認證相關 API
│   │   ├── users.py           # 用戶管理 API
│   │   ├── attendance.py      # 打卡記錄 API
│   │   └── reports.py         # 報表 API
│   ├── slack/
│   │   ├── __init__.py
│   │   ├── bot.py             # Slack Bot 主程式
│   │   ├── handlers/
│   │   │   ├── __init__.py
│   │   │   ├── punch.py       # 打卡指令處理
│   │   │   ├── admin.py       # 管理員指令處理
│   │   │   └── events.py      # Slack 事件處理
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── punch_service.py     # 打卡業務邏輯
│   │       ├── user_sync.py         # Slack 用戶同步
│   │       └── status_manager.py    # Slack 狀態管理
│   ├── web/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── dashboard.py   # 儀表板頁面
│   │   │   ├── users.py       # 用戶管理頁面
│   │   │   ├── attendance.py  # 打卡記錄頁面
│   │   │   └── reports.py     # 報表頁面
│   │   └── templates/
│   │       ├── base.html      # 基礎模板
│   │       ├── dashboard.html # 儀表板模板
│   │       ├── users/         # 用戶管理模板
│   │       ├── attendance/    # 打卡記錄模板
│   │       └── reports/       # 報表模板
│   ├── services/
│   │   ├── __init__.py
│   │   ├── attendance_service.py   # 打卡業務邏輯
│   │   ├── user_service.py         # 用戶管理業務邏輯
│   │   ├── report_service.py       # 報表業務邏輯
│   │   └── notification_service.py # 通知服務
│   └── utils/
│       ├── __init__.py
│       ├── auth.py            # 認證工具
│       ├── datetime_utils.py  # 時間處理工具
│       └── validators.py      # 驗證工具
├── static/
│   ├── css/
│   │   └── custom.css
│   ├── js/
│   │   ├── dashboard.js
│   │   ├── users.js
│   │   └── attendance.js
│   └── img/
├── migrations/                # Alembic 遷移文件
├── tests/
│   ├── __init__.py
│   ├── test_api/
│   ├── test_slack/
│   └── test_services/
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── alembic.ini
└── README.md
```

## 資料庫設計

### 用戶表 (users)
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    slack_user_id VARCHAR(50) UNIQUE NOT NULL,
    slack_username VARCHAR(100),
    slack_display_name VARCHAR(100),
    slack_real_name VARCHAR(100),
    slack_email VARCHAR(120),
    slack_avatar_url VARCHAR(500),
    internal_real_name VARCHAR(100) NOT NULL,
    department VARCHAR(50),
    role VARCHAR(20) DEFAULT 'user',
    standard_hours INTEGER DEFAULT 8,
    timezone VARCHAR(50) DEFAULT 'Asia/Taipei',
    is_active BOOLEAN DEFAULT true,
    slack_data_updated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 打卡記錄表 (attendance_records)
```sql
CREATE TABLE attendance_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(20) NOT NULL, -- 'in', 'out', 'break', 'back'
    timestamp TIMESTAMP NOT NULL,
    is_auto BOOLEAN DEFAULT false,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 休假記錄表 (leave_records)
```sql
CREATE TABLE leave_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    leave_type VARCHAR(50) DEFAULT 'vacation',
    reason TEXT,
    status VARCHAR(20) DEFAULT 'approved', -- 'pending', 'approved', 'rejected'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 核心功能規格

### 1. Slack Bot 功能

#### 打卡指令 (/punch)
```python
# 支援的指令格式
/punch in          # 開始工作
/punch out         # 結束工作
/punch break       # 開始休息
/punch back        # 結束休息
/punch today       # 查看今日記錄
/punch week        # 查看本週統計
/punch ooo         # 今日休假
/punch ooo 2024-12-25  # 預約休假
/punch ooo 2024-12-24 to 2024-12-26  # 連續休假
/punch cancel 2024-12-25  # 取消休假
/punch holidays    # 查看休假記錄
```

#### 管理員指令 (/punch admin)
```python
# 管理員專用指令
/punch admin invite @user "王小明" "產品部"  # 邀請用戶
/punch admin remove @user               # 移除用戶
/punch admin users                      # 查看所有用戶
/punch admin team                       # 查看團隊狀態
/punch admin export                     # 匯出報表
/punch admin sync @user                 # 同步用戶資料
```

#### 自動功能
- 8 小時工作提醒（30 分鐘無回應自動打卡）
- Slack 狀態自動更新
- 每日/每週工時統計提醒
- 忘記打卡提醒

### 2. Web 管理介面功能

#### 儀表板 (/dashboard)
- 今日出勤統計
- 本週工時趨勢圖
- 休假申請待處理
- 異常打卡提醒

#### 用戶管理 (/admin/users)
- 用戶列表（搜尋、篩選、分頁）
- 新增/編輯/停用用戶
- 批量匯入用戶 (CSV)
- Slack 資料同步

#### 打卡記錄 (/admin/attendance)
- 全員打卡記錄查詢
- 異常記錄標記
- 手動補登功能
- 記錄修正功能

#### 報表中心 (/admin/reports)
- 工時統計報表
- 出勤率分析
- 加班時數統計
- 部門比較分析
- CSV/Excel 匯出

#### 系統設定 (/admin/settings)
- 工時標準設定
- 自動打卡時間設定
- 休假類型管理
- Slack 狀態設定

### 3. API 規格

#### 認證 API
```python
POST /api/auth/login          # 管理員登入
POST /api/auth/refresh        # Token 刷新
POST /api/auth/logout         # 登出
```

#### 用戶管理 API
```python
GET    /api/users             # 用戶列表
POST   /api/users             # 新增用戶
GET    /api/users/{id}        # 用戶詳情
PUT    /api/users/{id}        # 更新用戶
DELETE /api/users/{id}        # 刪除用戶
POST   /api/users/import      # 批量匯入
POST   /api/users/{id}/sync   # 同步 Slack 資料
```

#### 打卡記錄 API
```python
GET    /api/attendance        # 打卡記錄列表
POST   /api/attendance        # 新增打卡記錄
PUT    /api/attendance/{id}   # 修改打卡記錄
DELETE /api/attendance/{id}   # 刪除打卡記錄
GET    /api/attendance/user/{user_id}  # 用戶打卡記錄
```

#### 報表 API
```python
GET /api/reports/daily/{date}           # 日報表
GET /api/reports/weekly/{start_date}    # 週報表
GET /api/reports/monthly/{year}/{month} # 月報表
GET /api/reports/user/{user_id}         # 個人報表
POST /api/reports/export               # 匯出報表
```

## 開發任務分配

### Agent 1: 資料庫與模型層
**負責檔案:**
- `app/database.py`
- `app/models/`
- `app/schemas/`
- `migrations/`
- `alembic.ini`

**主要任務:**
1. 設定 SQLAlchemy 連接
2. 建立所有資料模型
3. 設定 Pydantic 驗證模型
4. 建立資料庫遷移腳本

### Agent 2: Slack Bot 核心
**負責檔案:**
- `app/slack/`
- `app/services/punch_service.py`
- `app/services/notification_service.py`

**主要任務:**
1. Slack Bot 基礎架構
2. 打卡指令處理
3. 管理員指令處理
4. 自動提醒功能
5. Slack 狀態管理

### Agent 3: Web API 層
**負責檔案:**
- `app/api/`
- `app/services/` (除了 punch_service.py)
- `app/utils/`

**主要任務:**
1. FastAPI 路由設定
2. 用戶管理 API
3. 打卡記錄 API
4. 報表 API
5. 認證授權系統

### Agent 4: Web 介面層
**負責檔案:**
- `app/web/`
- `static/`
- `app/main.py` (Web 路由部分)

**主要任務:**
1. HTML 模板設計
2. Web 路由處理
3. 前端 JavaScript
4. CSS 樣式設計
5. 響應式佈局

### Agent 5: 部署與配置
**負責檔案:**
- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`
- `.env.example`
- `app/config.py`
- `README.md`

**主要任務:**
1. Docker 容器化
2. Render.com 部署配置
3. 環境變數管理
4. 依賴管理
5. 部署文件撰寫

## 環境變數配置

```env
# Slack 設定
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_APP_TOKEN=xapp-your-app-token

# 資料庫設定
DATABASE_URL=postgresql://user:password@localhost/punchbot

# JWT 設定
SECRET_KEY=your-super-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# 應用設定
DEBUG=False
TIMEZONE=Asia/Taipei
DEFAULT_WORK_HOURS=8
AUTO_PUNCH_TIMEOUT_MINUTES=30

# Render.com 設定
PORT=10000
```

## 部署指南

### Render.com 配置
1. **Web Service 設定:**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

2. **PostgreSQL 資料庫:**
   - 建立 PostgreSQL 服務
   - 設定 DATABASE_URL 環境變數

3. **環境變數設定:**
   - 在 Render Dashboard 設定所有必要環境變數

### Slack App 設定
1. **Bot Token Scopes:**
   - `chat:write`
   - `users:read`
   - `users:read.email`
   - `users:write`
   - `commands`

2. **Event Subscriptions:**
   - `user_change`
   - Request URL: `https://your-app.onrender.com/slack/events`

3. **Slash Commands:**
   - Command: `/punch`
   - Request URL: `https://your-app.onrender.com/slack/commands`

## 開發流程

### 階段 1: 基礎架構 (Week 1)
- Agent 1: 完成資料庫模型
- Agent 5: 完成 Docker 配置
- Agent 3: 完成基本 API 架構

### 階段 2: 核心功能 (Week 2)
- Agent 2: 完成基本打卡功能
- Agent 3: 完成用戶管理 API
- Agent 4: 完成基本 Web 介面

### 階段 3: 進階功能 (Week 3)
- Agent 2: 完成自動提醒功能
- Agent 3: 完成報表 API
- Agent 4: 完成管理介面

### 階段 4: 部署測試 (Week 4)
- Agent 5: Render.com 部署
- 所有 Agent: 整合測試
- 文件完善

## 測試策略

### 單元測試
- 每個 Agent 負責自己模組的測試
- 使用 pytest 框架
- 覆蓋率目標: 80%+

### 整合測試
- Slack Bot 指令測試
- API 端到端測試
- Web 介面功能測試

### 部署測試
- Render.com 環境測試
- 效能測試
- 安全性測試

## 注意事項

1. **時區處理**: 所有時間都使用 UTC 儲存，顯示時轉換為用戶時區
2. **錯誤處理**: 完整的異常捕捉和用戶友善的錯誤訊息
3. **安全性**: API 需要適當的認證授權機制
4. **效能**: 資料庫查詢優化，適當的索引設計
5. **擴展性**: 模組化設計，便於未來功能擴展

## 交付標準

每個 Agent 交付時需包含:
1. 完整的程式碼實作
2. 單元測試
3. API 文件 (如適用)
4. 模組使用說明
5. 已知問題列表

專案完成標準:
1. 所有核心功能正常運作
2. 在 Render.com 成功部署
3. 通過所有測試案例
4. 完整的使用文件
5. 管理員操作手冊