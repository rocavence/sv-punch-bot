# 📦 Punch Bot 安裝指南

本指南將幫助您快速部署和配置 Punch Bot 打卡機器人系統。

## 🎯 部署選項

### 選項 1: Render.com 雲端部署 (推薦)
### 選項 2: Docker 本地部署
### 選項 3: 直接 Python 運行

---

## 🚀 選項 1: Render.com 雲端部署

### 步驟 1: 準備工作
1. 建立 [Render.com](https://render.com) 帳戶
2. 準備 GitHub 儲存庫
3. 建立 Slack App

### 步驟 2: 建立資料庫
1. 在 Render Dashboard 點擊 "New +"
2. 選擇 "PostgreSQL"
3. 設定資料庫名稱：`punch-bot-db`
4. 選擇免費方案
5. 點擊 "Create Database"
6. 複製 "Internal Database URL"

### 步驟 3: 建立 Web 服務
1. 在 Render Dashboard 點擊 "New +"
2. 選擇 "Web Service"
3. 連接您的 GitHub 儲存庫
4. 設定：
   ```
   Name: punch-bot
   Region: Singapore (或最近的區域)
   Branch: main
   Build Command: pip install -r requirements.txt
   Start Command: ./start.sh --migrate
   ```

### 步驟 4: 設定環境變數
在 "Environment Variables" 區域添加：

```env
# Slack 設定
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_APP_TOKEN=xapp-your-app-token (可選，Socket Mode 用)

# 資料庫設定
DATABASE_URL=your-internal-database-url

# 安全設定
SECRET_KEY=your-super-secret-key-generate-a-random-one

# 應用設定
DEBUG=False
TIMEZONE=Asia/Taipei

# 提醒設定
ENABLE_DAILY_REMINDER=True
ENABLE_WORK_HOUR_REMINDER=True
ENABLE_FORGOT_PUNCH_REMINDER=True
ENABLE_WEEKLY_REPORT=True
```

### 步驟 5: 部署
1. 點擊 "Create Web Service"
2. 等待部署完成
3. 複製服務 URL (例如: `https://punch-bot-xyz.onrender.com`)

---

## 🐳 選項 2: Docker 部署

### 步驟 1: 安裝 Docker
確保您的系統已安裝 Docker 和 Docker Compose。

### 步驟 2: 準備配置
```bash
# 克隆儲存庫
git clone https://github.com/your-repo/punch-bot.git
cd punch-bot

# 複製環境變數範例
cp .env.example .env

# 編輯 .env 檔案，填入您的配置
nano .env
```

### 步驟 3: 使用 Docker Compose
建立 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - postgres
    restart: unless-stopped

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: punchbot
      POSTGRES_USER: user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres_data:
```

### 步驟 4: 啟動服務
```bash
# 啟動所有服務
docker-compose up -d

# 檢查日誌
docker-compose logs -f app

# 執行資料庫遷移
docker-compose exec app alembic upgrade head
```

---

## 🐍 選項 3: 直接 Python 運行

### 步驟 1: 環境準備
```bash
# Python 3.11+ 必需
python3 --version

# 安裝 PostgreSQL
# Ubuntu/Debian:
sudo apt-get install postgresql postgresql-contrib

# macOS:
brew install postgresql

# 建立資料庫
createdb punchbot
```

### 步驟 2: 安裝應用
```bash
# 克隆儲存庫
git clone https://github.com/your-repo/punch-bot.git
cd punch-bot

# 建立虛擬環境
python3 -m venv venv
source venv/bin/activate

# 安裝依賴
pip install -r requirements.txt

# 設定環境變數
cp .env.example .env
# 編輯 .env 檔案
```

### 步驟 3: 初始化資料庫
```bash
# 執行遷移
alembic upgrade head
```

### 步驟 4: 啟動應用
```bash
# 使用啟動腳本
./start.sh

# 或直接使用 uvicorn
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 🤖 Slack App 設定

### 步驟 1: 建立 Slack App
1. 前往 [Slack API](https://api.slack.com/apps)
2. 點擊 "Create New App"
3. 選擇 "From scratch"
4. 輸入 App 名稱：`Punch Bot`
5. 選擇您的工作區

### 步驟 2: 配置權限
在 "OAuth & Permissions" 頁面：

**Bot Token Scopes:**
```
chat:write
users:read
users:read.email
users:write
commands
```

**User Token Scopes:** (如果需要)
```
users:read
```

### 步驟 3: 安裝 App
1. 在 "OAuth & Permissions" 頁面
2. 點擊 "Install to Workspace"
3. 授權並複製 "Bot User OAuth Token"

### 步驟 4: 設定 Slash Commands
1. 前往 "Slash Commands" 頁面
2. 點擊 "Create New Command"
3. 設定：
   ```
   Command: /punch
   Request URL: https://your-app-url.com/slack/commands
   Short Description: 智能打卡機器人
   Usage Hint: [in|out|break|back|today|week|ooo|admin] [參數]
   ```

### 步驟 5: 設定事件訂閱
1. 前往 "Event Subscriptions" 頁面
2. 開啟 "Enable Events"
3. 設定 Request URL: `https://your-app-url.com/slack/events`
4. 訂閱 Bot Events：
   ```
   user_change
   team_join
   ```

### 步驟 6: 設定互動元件
1. 前往 "Interactivity & Shortcuts" 頁面
2. 開啟 "Interactivity"
3. 設定 Request URL: `https://your-app-url.com/slack/interactive`

### 步驟 7: App Home (可選)
1. 前往 "App Home" 頁面
2. 開啟 "Home Tab"
3. 開啟 "Messages Tab"

---

## ✅ 驗證安裝

### 1. 健康檢查
```bash
curl https://your-app-url.com/health
```

預期回應：
```json
{
  "status": "healthy",
  "service": "punch-bot",
  "database": "connected"
}
```

### 2. Slack 測試
在 Slack 中輸入：
```
/punch help
```

應該收到幫助訊息。

### 3. 基本功能測試
```
/punch in      # 測試上班打卡
/punch today   # 檢查今日記錄
/punch out     # 測試下班打卡
```

---

## 🛠 故障排除

### 常見問題

**問題 1: Slack 指令無回應**
- 檢查 Slack App Token 是否正確
- 確認 Request URL 可以被存取
- 檢查伺服器日誌

**問題 2: 資料庫連線失敗**
- 確認 DATABASE_URL 格式正確
- 檢查資料庫是否運行
- 確認網路連線

**問題 3: 權限錯誤**
- 確認 Slack App 權限設定正確
- 檢查 Bot 是否已安裝到工作區
- 確認用戶是否有適當權限

### 日誌檢查

**Docker 部署:**
```bash
docker-compose logs -f app
```

**直接運行:**
```bash
# 檢查應用日誌
tail -f punch-bot.log

# 或使用 journalctl (systemd)
journalctl -u punch-bot -f
```

### 偵錯模式
設定環境變數：
```env
DEBUG=True
LOG_LEVEL=DEBUG
```

---

## 📞 支援

如果您在安裝過程中遇到問題：

1. 檢查 [GitHub Issues](https://github.com/your-repo/punch-bot/issues)
2. 查看 [文件](https://your-docs-site.com)
3. 聯絡支援：support@yourcompany.com

---

## 🎉 安裝完成！

恭喜！您已成功安裝 Punch Bot。現在您可以：

1. 邀請團隊成員使用系統
2. 設定管理員帳戶
3. 自訂提醒設定
4. 開始使用智能打卡功能

**下一步：** 閱讀 [使用者手冊](USER_GUIDE.md) 瞭解如何使用所有功能。