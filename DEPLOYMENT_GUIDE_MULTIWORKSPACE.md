# 🚀 多工作區 Punch-Bot 部署指南

## 新架構特色

✅ **多工作區支援** - 一次部署，支援無限工作區  
✅ **一鍵安裝** - 管理員點擊安裝按鈕即可自動配置  
✅ **自動 OAuth** - 無需手動配置 Slack tokens  
✅ **動態載入** - 新工作區安裝後立即可用，無需重啟  

---

## 🏗️ 部署步驟

### 步驟 1: 建立 Slack App (一次性設定)

1. **建立 Slack App**
   - 前往 [api.slack.com/apps](https://api.slack.com/apps)
   - 點擊 "Create New App" → "From scratch"
   - **App Name**: `Punch Bot`
   - **Workspace**: 選擇任一開發用工作區 (之後可安裝到其他工作區)

2. **設定 App Credentials**
   - 左側選單 → "Basic Information"
   - 記錄以下資訊：
     ```
     Client ID: 123456789.987654321
     Client Secret: abcdef1234567890abcdef1234567890
     Signing Secret: 1234567890abcdef1234567890abcdef12345678
     ```

3. **設定 OAuth & Permissions**
   - 左側選單 → "OAuth & Permissions" 
   - **Redirect URLs** 添加：
     ```
     https://your-app-name.onrender.com/oauth/callback
     ```
   - **Bot Token Scopes** 添加：
     ```
     chat:write
     users:read
     users:read.email
     users:write
     commands
     app_mentions:read
     channels:read
     groups:read
     im:read
     mpim:read
     team:read
     ```

4. **設定 Slash Commands**
   - 左側選單 → "Slash Commands"
   - 建立指令：
     - **Command**: `/punch`
     - **Request URL**: `https://your-app-name.onrender.com/slack/commands`
     - **Short Description**: `智能打卡機器人`
     - **Usage Hint**: `in | out | break | back | today | week | help`

5. **設定 Event Subscriptions (選擇性)**
   - 左側選單 → "Event Subscriptions"
   - 啟用 "Enable Events"
   - **Request URL**: `https://your-app-name.onrender.com/slack/events`
   - **Subscribe to Bot Events**:
     ```
     user_change
     team_join
     app_home_opened
     ```

### 步驟 2: 部署到 Render.com

1. **建立 PostgreSQL 資料庫**
   - Render Dashboard → "New +" → "PostgreSQL"
   - **Name**: `punch-bot-db`
   - **Region**: Singapore (Southeast Asia)
   - 複製 **External Database URL** 備用

2. **建立 Web Service**
   - Render Dashboard → "New +" → "Web Service"
   - 連接 GitHub: `StreetVoice/sv-punch-bot`
   - **Name**: `sv-punch-bot`
   - **Region**: Singapore
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

3. **設定環境變數**
   ```env
   # Slack App 配置
   SLACK_CLIENT_ID=123456789.987654321
   SLACK_CLIENT_SECRET=abcdef1234567890abcdef1234567890
   SLACK_SIGNING_SECRET=1234567890abcdef1234567890abcdef12345678
   SLACK_REDIRECT_URI=https://sv-punch-bot.onrender.com/oauth/callback

   # 資料庫配置
   DATABASE_URL=postgresql://user:pass@host/db

   # JWT 配置
   SECRET_KEY=your-super-secret-key-32-chars-long
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30

   # 應用配置
   DEBUG=False
   TIMEZONE=Asia/Taipei
   DEFAULT_WORK_HOURS=8
   AUTO_PUNCH_TIMEOUT_MINUTES=30
   PORT=10000
   ```

4. **部署並測試**
   - 點擊 "Create Web Service"
   - 等待部署完成 (約 5-10 分鐘)
   - 測試健康檢查: `https://sv-punch-bot.onrender.com/health`

### 步驟 3: 設定 Slack App Distribution

1. **配置分發設定**
   - Slack App 設定 → "Manage Distribution"
   - 啟用 "Public Distribution"
   - 完成 App Review 檢查清單

2. **測試安裝頁面**
   - 訪問: `https://sv-punch-bot.onrender.com/oauth/install`
   - 確認安裝頁面正常顯示

---

## 🎯 工作區安裝流程

### 管理員安裝步驟

1. **訪問安裝頁面**
   ```
   https://sv-punch-bot.onrender.com/oauth/install
   ```

2. **點擊安裝按鈕**
   - 會跳轉到 Slack OAuth 授權頁面
   - 選擇要安裝的工作區
   - 確認權限並授權

3. **自動配置完成**
   - 系統自動儲存工作區配置
   - Bot 立即在該工作區可用
   - 顯示安裝成功頁面

### 用戶開始使用

安裝完成後，用戶可立即使用：
```
/punch in      # 開始工作
/punch out     # 結束工作  
/punch today   # 查看今日記錄
/punch help    # 查看說明
```

---

## 🔧 系統管理

### 查看已安裝工作區

```bash
curl https://sv-punch-bot.onrender.com/oauth/workspaces
```

### 停用工作區

```bash
curl -X POST https://sv-punch-bot.onrender.com/oauth/workspaces/{id}/deactivate
```

### 資料庫遷移

```bash
# 在 Render Console 執行
alembic upgrade head
```

---

## 🚨 故障排除

### 常見問題

1. **OAuth 回調失敗**
   - 檢查 SLACK_REDIRECT_URI 是否正確
   - 確認 Slack App 的 Redirect URL 設定

2. **工作區未載入**
   - 檢查資料庫連線
   - 查看應用日誌中的錯誤訊息

3. **指令無回應**  
   - 確認 Request URL 設定正確
   - 檢查 SLACK_SIGNING_SECRET

### 除錯工具

1. **查看系統日誌**
   ```
   Render Dashboard → Your Service → Logs
   ```

2. **健康檢查**
   ```
   GET https://sv-punch-bot.onrender.com/health
   ```

3. **API 文件**
   ```
   https://sv-punch-bot.onrender.com/docs
   ```

---

## 🎉 完成！

您的多工作區 Punch-Bot 現已準備就緒：

- ✅ 支援無限工作區
- ✅ 管理員一鍵安裝
- ✅ 自動 OAuth 流程
- ✅ 即時可用，無需重啟

### 分享安裝連結

將以下連結分享給各工作區的管理員：
```
https://sv-punch-bot.onrender.com/oauth/install
```

他們點擊安裝後，Punch-Bot 就會自動在他們的工作區中可用！