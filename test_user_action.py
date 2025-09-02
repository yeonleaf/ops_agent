#!/usr/bin/env python3
"""user_action 테이블 직접 확인"""

import sqlite3
import json

def check_user_actions():
    """user_action 테이블을 직접 확인합니다."""
    
    try:
        # SQLite 연결
        with sqlite3.connect("tickets.db") as conn:
            cursor = conn.cursor()
            
            print("🔍 user_action 테이블 확인")
            print("=" * 50)
            
            # 테이블 존재 여부 확인
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='user_actions'
            """)
            
            if cursor.fetchone():
                print("✅ user_actions 테이블이 존재합니다.")
                
                # 테이블 구조 확인
                cursor.execute("PRAGMA table_info(user_actions)")
                columns = cursor.fetchall()
                print("\n📋 테이블 구조:")
                for col in columns:
                    print(f"  • {col[1]} ({col[2]})")
                
                # 최근 user_action 조회
                cursor.execute("""
                    SELECT action_type, action_description, old_value, new_value, created_at, ticket_id
                    FROM user_actions 
                    ORDER BY created_at DESC 
                    LIMIT 10
                """)
                
                actions = cursor.fetchall()
                if actions:
                    print(f"\n📋 최근 user_action 기록 ({len(actions)}개):")
                    for i, action in enumerate(actions, 1):
                        action_type, description, old_val, new_val, created_at, ticket_id = action
                        print(f"  {i}. {action_type}")
                        print(f"     설명: {description}")
                        print(f"     이전값: {old_val}")
                        print(f"     새값: {new_val}")
                        print(f"     티켓ID: {ticket_id}")
                        print(f"     시간: {created_at}")
                        print()
                else:
                    print("\n📋 user_action 기록이 없습니다.")
                    
            else:
                print("❌ user_actions 테이블이 존재하지 않습니다.")
                
                # 테이블 생성
                print("\n🔧 user_actions 테이블을 생성합니다...")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_actions (
                        action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticket_id INTEGER,
                        message_id TEXT,
                        action_type TEXT,
                        action_description TEXT,
                        old_value TEXT,
                        new_value TEXT,
                        context TEXT,
                        created_at TEXT,
                        user_id TEXT
                    )
                """)
                conn.commit()
                print("✅ user_actions 테이블 생성 완료!")
                
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        import traceback
        print(f"❌ 오류 상세: {traceback.format_exc()}")

if __name__ == "__main__":
    check_user_actions()
