#!/bin/bash

# Punch Bot 啟動腳本
set -e

echo "🤖 啟動 Punch Bot..."

# 檢查必要的環境變數
required_vars=("SLACK_BOT_TOKEN" "SLACK_SIGNING_SECRET" "DATABASE_URL")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "❌ 缺少必要的環境變數: ${missing_vars[*]}"
    echo "請設定這些環境變數或建立 .env 檔案"
    exit 1
fi

# 載入環境變數（如果 .env 檔案存在）
if [ -f .env ]; then
    echo "📄 載入 .env 檔案"
    set -a
    source .env
    set +a
fi

# 檢查 Python 版本
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "🐍 Python 版本: $python_version"

# 安裝依賴（如果需要）
if [ "$1" = "--install" ]; then
    echo "📦 安裝 Python 依賴..."
    pip3 install -r requirements.txt
fi

# 執行資料庫遷移（如果需要）
if [ "$1" = "--migrate" ] || [ "$2" = "--migrate" ]; then
    echo "🗄️ 執行資料庫遷移..."
    alembic upgrade head
fi

# 檢查資料庫連線
echo "🔗 檢查資料庫連線..."
python3 -c "
import os
import sys
from sqlalchemy import create_engine

try:
    database_url = os.environ.get('DATABASE_URL', '')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    engine = create_engine(database_url)
    connection = engine.connect()
    connection.execute('SELECT 1')
    connection.close()
    print('✅ 資料庫連線成功')
except Exception as e:
    print(f'❌ 資料庫連線失敗: {e}')
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ 資料庫連線失敗，程式退出"
    exit 1
fi

# 檢查 Slack API 連線
echo "🔗 檢查 Slack API 連線..."
python3 -c "
import os
import sys
from slack_sdk import WebClient

try:
    client = WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))
    response = client.api_test()
    if response['ok']:
        print('✅ Slack API 連線成功')
    else:
        print('❌ Slack API 連線失敗')
        sys.exit(1)
except Exception as e:
    print(f'❌ Slack API 連線失敗: {e}')
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Slack API 連線失敗，程式退出"
    exit 1
fi

# 設定預設值
HOST=${HOST:-"0.0.0.0"}
PORT=${PORT:-8000}
LOG_LEVEL=${LOG_LEVEL:-"info"}

echo "🚀 啟動 Punch Bot 服務"
echo "   主機: $HOST"
echo "   端口: $PORT"
echo "   日誌級別: $LOG_LEVEL"
echo "   模式: $([ -n "$SLACK_APP_TOKEN" ] && echo "Socket Mode" || echo "HTTP Mode")"

# 啟動應用程式
if [ "$DEBUG" = "true" ] || [ "$DEBUG" = "True" ]; then
    echo "🔧 開發模式啟動"
    python3 -m uvicorn app.main:app --host "$HOST" --port "$PORT" --reload --log-level "$LOG_LEVEL"
else
    echo "🏭 生產模式啟動"
    python3 -m uvicorn app.main:app --host "$HOST" --port "$PORT" --log-level "$LOG_LEVEL" --workers 1
fi