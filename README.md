# 🤖 Punch Bot - 智能打卡機器人

基於 Python FastAPI 和 Slack Bolt 開發的企業級打卡管理系統，支援混合辦公制度，提供完整的工時統計和自動化提醒功能。

## ✨ 主要功能

### 🎯 核心功能
- **智能打卡**: 支援上班、下班、休息、回來等多種打卡類型
- **工時統計**: 自動計算日/週/月工時，支援加班統計
- **請假管理**: 便捷的請假申請和管理系統
- **自動提醒**: 智能的打卡提醒和工時提醒
- **Slack 整合**: 原生 Slack 體驗，支援指令和互動式介面

### 📊 管理功能
- **用戶管理**: 完整的用戶生命週期管理
- **團隊監控**: 即時團隊狀態查看
- **報表匯出**: 支援 CSV 格式的詳細報表
- **Slack 同步**: 自動同步 Slack 用戶資料

### 🔔 自動化功能
- **每日提醒**: 早上提醒未打卡用戶
- **8小時提醒**: 工作滿 8 小時自動提醒
- **下班提醒**: 晚上提醒忘記下班打卡
- **週報推送**: 每週自動推送工時統計
- **狀態同步**: 自動更新 Slack 用戶狀態

## 🛠 技術架構

### 後端技術
- **FastAPI**: 現代化的 Python Web 框架
- **SQLAlchemy 2.0**: ORM 資料庫操作
- **PostgreSQL**: 主資料庫
- **Slack Bolt**: 官方 Slack 開發框架
- **APScheduler**: 任務排程系統
- **Alembic**: 資料庫遷移工具

### 部署方案
- **Docker**: 容器化部署
- **Render.com**: 雲端託管平台
- **Environment Variables**: 環境變數配置

## 🚀 快速開始

### 環境需求
- Python 3.11+
- PostgreSQL 12+
- Slack App (Bot Token, Signing Secret)

### 1. 克隆專案
```bash
git clone https://github.com/your-repo/punch-bot.git
cd punch-bot
```

### 2. 安裝依賴
```bash
pip install -r requirements.txt
```

### 3. 配置環境變數
```bash
cp .env.example .env
# 編輯 .env 檔案，填入必要的配置
```

### 4. 資料庫遷移
```bash
alembic upgrade head
```

### 5. 啟動應用
```bash
python app/main.py
```

## ⚙️ Slack App 設定

### 1. 建立 Slack App
1. 前往 [Slack API](https://api.slack.com/apps)
2. 建立新的 App
3. 設定 App 名稱和工作區

### 2. Bot Token Scopes
在 "OAuth & Permissions" 頁面添加以下 Bot Token Scopes：
- `chat:write` - 發送訊息
- `users:read` - 讀取用戶資訊
- `users:read.email` - 讀取用戶 Email
- `users:write` - 更新用戶狀態
- `commands` - 處理 Slash Commands

### 3. Event Subscriptions
在 "Event Subscriptions" 頁面設定：
- Request URL: `https://your-app.onrender.com/slack/events`
- Subscribe to Bot Events:
  - `user_change` - 用戶資料變更
  - `team_join` - 新用戶加入

### 4. Slash Commands
建立 `/punch` 指令：
- Command: `/punch`
- Request URL: `https://your-app.onrender.com/slack/commands`
- Short Description: `打卡機器人`
- Usage Hint: `[in|out|break|back|today|week|ooo|admin]`

### 5. Interactive Components
- Request URL: `https://your-app.onrender.com/slack/interactive`

## 📝 指令說明

### 基本打卡指令
```bash
/punch in          # 上班打卡
/punch out         # 下班打卡
/punch break       # 開始休息
/punch back        # 結束休息
```

### 查詢統計指令
```bash
/punch today       # 查看今日記錄
/punch week        # 查看本週統計
```

### 請假管理指令
```bash
/punch ooo                    # 今日請假
/punch ooo 2024-12-25        # 指定日期請假
/punch ooo 2024-12-24 to 2024-12-26  # 連續請假
/punch cancel 2024-12-25     # 取消請假
/punch holidays              # 查看請假記錄
```

### 管理員指令
```bash
/punch admin invite @user "姓名" "部門"  # 邀請用戶
/punch admin remove @user              # 移除用戶
/punch admin users                     # 查看所有用戶
/punch admin team                      # 查看團隊狀態
/punch admin export                    # 匯出報表
/punch admin sync @user                # 同步用戶資料
```

## 🐳 Docker 部署

### 本地 Docker 運行
```bash
# 建置映像
docker build -t punch-bot .

# 運行容器
docker run -p 8000:8000 --env-file .env punch-bot
```

### Docker Compose
```yaml
version: '3.8'
services:
  punch-bot:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - postgres
  
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: punchbot
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

## ☁️ Render.com 部署

### 1. 連接 GitHub
1. 登入 [Render.com](https://render.com)
2. 連接您的 GitHub 帳戶
3. 選擇 punch-bot 儲存庫

### 2. 建立 PostgreSQL 資料庫
1. 建立新的 PostgreSQL 服務
2. 記下 Database URL

### 3. 建立 Web Service
1. 選擇 "Web Service"
2. 設定：
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app/main.py`
   - **Environment**: Python 3.11

### 4. 設定環境變數
在 Render Dashboard 中設定所有 `.env.example` 中的環境變數。

### 5. 部署
點擊 "Deploy" 開始部署。

## 📊 資料庫結構

### 用戶表 (users)
- 基本用戶資訊
- Slack 用戶資料同步
- 部門和角色管理

### 打卡記錄表 (attendance_records)
- 打卡動作記錄
- 時間戳記和備註
- 自動/手動打卡標記

### 請假記錄表 (leave_records)
- 請假申請管理
- 日期範圍和原因
- 審核狀態追蹤

## 🔧 配置說明

### 環境變數配置
詳細的環境變數說明請參考 `.env.example` 檔案。

### 排程任務配置
- **每日提醒**: 上午 9:00
- **工時檢查**: 每 15 分鐘
- **下班提醒**: 下午 6:30
- **週報推送**: 週一上午 9:30

### Slack 狀態更新
系統會根據打卡狀態自動更新用戶的 Slack 狀態：
- 🟢 工作中
- 🟡 休息中
- 🏖️ 請假中

## 🧪 開發指南

### 本地開發環境
```bash
# 安裝依賴
pip install -r requirements.txt

# 設定開發環境變數
export DEBUG=True
export DATABASE_URL="postgresql://localhost/punchbot"

# 啟動開發伺服器
python app/main.py
```

### 資料庫遷移
```bash
# 建立新的遷移文件
alembic revision --autogenerate -m "描述"

# 執行遷移
alembic upgrade head
```

### 測試
```bash
# 執行測試
pytest

# 執行測試並產生覆蓋率報告
pytest --cov=app tests/
```

## 🤝 貢獻指南

1. Fork 此儲存庫
2. 建立功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交變更 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 開啟 Pull Request

## 📄 授權條款

此專案採用 MIT 授權條款 - 詳見 [LICENSE](LICENSE) 檔案

## 📞 支援與聯絡

- **GitHub Issues**: [問題回報](https://github.com/your-repo/punch-bot/issues)
- **文件**: [線上文件](https://your-docs-site.com)
- **Email**: support@yourcompany.com

## 🙏 致謝

- [Slack Bolt for Python](https://github.com/slackapi/bolt-python)
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://sqlalchemy.org/)
- [Render.com](https://render.com/)

---

**🚀 讓打卡變得更智能、更簡單！**