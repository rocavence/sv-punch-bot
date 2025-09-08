# 🚀 超簡單 Render.com 部署指南

## 🎯 新架構特色

✅ **零手動配置** - 系統自動處理所有 Slack 設定  
✅ **管理員一鍵安裝** - 訪問頁面即可安裝到任何工作區  
✅ **即部即用** - 部署完成後立即支援多工作區  

---

## 🏗️ 部署步驟 (超簡單)

### 步驟 1: 建立 PostgreSQL 資料庫

1. **登入 Render.com**
   - 前往 [render.com](https://render.com)
   - 使用 GitHub 帳號登入

2. **建立資料庫**
   - 點擊 **"New +"** 
   - 選擇 **"PostgreSQL"**
   - 設定：
     ```
     Name: punch-bot-db
     Database: punchbot
     User: punchbot_user
     Region: Singapore (Southeast Asia)
     Plan: Free
     ```
   - 點擊 **"Create Database"**

3. **取得資料庫 URL**
   - 建立完成後，點擊進入資料庫詳細頁面
   - 複製 **"External Database URL"**
   - 格式類似：`postgres://user:pass@host:5432/db`
   - **保存此 URL** 🔖

### 步驟 2: 部署 Web Service

1. **建立 Web Service**
   - 回到 Render Dashboard
   - 點擊 **"New +"** 
   - 選擇 **"Web Service"**

2. **連接 GitHub**
   - 選擇 **"Build and deploy from a Git repository"**
   - 點擊 **"Connect"** 連接 GitHub
   - 搜尋 `StreetVoice/sv-punch-bot`
   - 點擊 **"Connect"**

3. **基本設定**
   ```
   Name: sv-punch-bot
   Region: Singapore (Southeast Asia)
   Branch: main
   Runtime: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

4. **環境變數設定**
   
   在 **"Environment Variables"** 區域添加：

   ```env
   # 資料庫配置 (使用步驟1的URL)
   DATABASE_URL=postgres://user:pass@host:5432/db
   
   # JWT 配置 
   SECRET_KEY=your-super-secret-key-change-this-32-characters-long
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   
   # 應用配置
   DEBUG=False
   TIMEZONE=Asia/Taipei
   DEFAULT_WORK_HOURS=8
   AUTO_PUNCH_TIMEOUT_MINUTES=30
   
   # Render 配置
   PORT=10000
   ```

5. **開始部署**
   - 點擊 **"Create Web Service"**
   - 等待部署完成 (約 5-10 分鐘)

### 步驟 3: 建立 Slack App (使用 Manifest)

1. **部署完成後**
   - 確認服務狀態為 **"Live"**
   - 測試健康檢查：`https://sv-punch-bot.onrender.com/health`

2. **使用 App Manifest 建立 Slack App**
   - 前往 [api.slack.com/apps](https://api.slack.com/apps)
   - 點擊 **"Create New App"**
   - 選擇 **"From an app manifest"**
   - 選擇任一工作區 (只用於建立，之後可安裝到其他工作區)
   
3. **貼上 App Manifest**
   
   複製以下 YAML 內容：
   
   ```yaml
   display_information:
     name: Punch Bot
     description: 智能打卡機器人 - 支援混合辦公制度的團隊打卡管理系統
     background_color: "#4A154B"
   
   features:
     app_home:
       home_tab_enabled: true
       messages_tab_enabled: false
     bot_user:
       display_name: Punch Bot
       always_online: true
     slash_commands:
       - command: /punch
         url: https://sv-punch-bot.onrender.com/slack/commands
         description: 打卡系統指令
         usage_hint: in | out | break | back | today | week | ooo | help
   
   oauth_config:
     redirect_urls:
       - https://sv-punch-bot.onrender.com/oauth/callback
     scopes:
       bot:
         - app_mentions:read
         - channels:read
         - chat:write
         - commands
         - groups:read
         - im:read
         - mpim:read
         - team:read
         - users:read
         - users:read.email
         - users:write
   
   settings:
     event_subscriptions:
       request_url: https://sv-punch-bot.onrender.com/slack/events
       bot_events:
         - app_home_opened
         - team_join
         - user_change
     interactivity:
       is_enabled: true
       request_url: https://sv-punch-bot.onrender.com/slack/interactive
     org_deploy_enabled: false
     socket_mode_enabled: false
   ```

4. **建立 App**
   - 貼上 Manifest 後點擊 **"Next"**
   - 檢查設定後點擊 **"Create"**
   - Slack 會自動配置所有設定！

### 步驟 4: 更新環境變數

1. **取得 App 憑證**
   - Slack App 建立後，前往 **"Basic Information"**
   - 複製以下資訊：
     ```
     Client ID: 1234567890.0987654321
     Client Secret: abcdef1234567890abcdef1234567890
     Signing Secret: 1234567890abcdef1234567890abcdef12345678
     ```

2. **更新 Render 環境變數**
   - 回到 Render Web Service 設定
   - 在 **"Environment Variables"** 中添加：
   
   ```env
   SLACK_CLIENT_ID=1234567890.0987654321
   SLACK_CLIENT_SECRET=abcdef1234567890abcdef1234567890
   SLACK_SIGNING_SECRET=1234567890abcdef1234567890abcdef12345678
   SLACK_REDIRECT_URI=https://sv-punch-bot.onrender.com/oauth/callback
   ```

3. **重新部署**
   - 點擊 **"Manual Deploy"** → **"Deploy latest commit"**

### 步驟 5: 執行資料庫遷移

1. **開啟 Render Shell**
   - 在 Web Service 頁面，點擊 **"Shell"** 標籤
   - 或使用 **"Connect"** 按鈕開啟終端

2. **執行遷移**
   ```bash
   alembic upgrade head
   ```

---

## 🎉 完成！系統現在可以使用了

### 🔗 重要連結

- **應用程式**: https://sv-punch-bot.onrender.com
- **安裝頁面**: https://sv-punch-bot.onrender.com/oauth/install
- **健康檢查**: https://sv-punch-bot.onrender.com/health
- **API 文件**: https://sv-punch-bot.onrender.com/docs

### 📱 工作區安裝流程

1. **分享安裝連結**給工作區管理員：
   ```
   https://sv-punch-bot.onrender.com/oauth/install
   ```

2. **管理員點擊安裝**
   - 會跳轉到 Slack 授權頁面
   - 選擇工作區並確認權限
   - 系統自動完成所有配置

3. **立即可用**
   - 安裝完成後，用戶可立即使用：
   ```
   /punch in      # 開始工作
   /punch out     # 結束工作
   /punch today   # 查看記錄
   /punch help    # 查看說明
   ```

### 🛠️ 管理介面

- **Web Dashboard**: https://sv-punch-bot.onrender.com
- **用戶管理**: https://sv-punch-bot.onrender.com/admin/users
- **打卡記錄**: https://sv-punch-bot.onrender.com/admin/attendance
- **統計報表**: https://sv-punch-bot.onrender.com/admin/reports

---

## ✅ 部署檢查清單

- [ ] PostgreSQL 資料庫已建立
- [ ] Web Service 部署成功 (狀態: Live)
- [ ] 健康檢查正常回應
- [ ] Slack App 使用 Manifest 建立成功
- [ ] 環境變數配置完整
- [ ] 資料庫遷移執行完成
- [ ] 安裝頁面可正常訪問

完成以上步驟後，您的多工作區 Punch-Bot 就準備好接受無限工作區的安裝了！🚀

## 🚨 故障排除

如果遇到問題，請檢查：

1. **Render Logs**: Web Service → Logs 標籤
2. **環境變數**: 確認所有必要變數都已設定
3. **資料庫連線**: 檢查 DATABASE_URL 格式
4. **Slack App 設定**: 確認所有 URL 指向正確的 Render 網址