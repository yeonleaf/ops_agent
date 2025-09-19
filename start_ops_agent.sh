#!/bin/bash

echo "🚀 OPS Agent 시작 스크립트"
echo "================================"

# 1. 포트 죽이기
echo "1️⃣ 포트 8001, 8501 종료 중..."
lsof -ti:8001 | xargs kill -9 2>/dev/null || echo "포트 8001이 이미 비어있습니다"
lsof -ti:8501 | xargs kill -9 2>/dev/null || echo "포트 8501이 이미 비어있습니다"
echo "✅ 포트 정리 완료"

# 2. 데이터베이스 리셋
echo ""
echo "2️⃣ 데이터베이스 리셋 중..."
python reset_databases.py
if [ $? -eq 0 ]; then
    echo "✅ 데이터베이스 리셋 완료"
else
    echo "❌ 데이터베이스 리셋 실패"
    exit 1
fi

# 3. FastMCP 서버 시작 (백그라운드)
echo ""
echo "3️⃣ FastMCP 서버 시작 중..."
python fastmcp_server.py &
FASTMCP_PID=$!
echo "✅ FastMCP 서버 시작됨 (PID: $FASTMCP_PID)"

# 서버가 시작될 때까지 잠시 대기
sleep 3

# 4. Streamlit 앱 시작
echo ""
echo "4️⃣ Streamlit 앱 시작 중..."
echo "================================"
echo "🌐 브라우저에서 http://localhost:8501 을 열어주세요"
echo "================================"

# Streamlit 앱 시작 (포그라운드)
streamlit run fastmcp_chatbot_app.py

# 스크립트 종료 시 FastMCP 서버도 종료
echo ""
echo "🛑 FastMCP 서버 종료 중..."
kill $FASTMCP_PID 2>/dev/null
echo "✅ 모든 프로세스 종료 완료"
