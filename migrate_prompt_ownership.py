#!/usr/bin/env python3
"""
프롬프트 소유권 마이그레이션 스크립트

기존 reports.db의 user_id 1 (testuser)의 프롬프트를
user_id 2 (dpffpsk907@gmail.com)로 이전
"""
import sqlite3

def migrate_prompts(from_user_id, to_user_id):
    """프롬프트 소유권 이전"""
    conn = sqlite3.connect('reports.db')
    cursor = conn.cursor()

    # 이전할 프롬프트 확인
    cursor.execute(
        'SELECT id, title, category FROM prompt_templates WHERE user_id = ?',
        (from_user_id,)
    )
    prompts = cursor.fetchall()

    if not prompts:
        print(f"❌ user_id {from_user_id}의 프롬프트가 없습니다.")
        conn.close()
        return

    print(f"📋 이전할 프롬프트 목록 (user_id {from_user_id} → {to_user_id}):")
    for prompt_id, title, category in prompts:
        print(f"   {prompt_id}. {title} ({category})")

    # 소유권 업데이트
    cursor.execute(
        'UPDATE prompt_templates SET user_id = ? WHERE user_id = ?',
        (to_user_id, from_user_id)
    )
    conn.commit()

    affected_rows = cursor.rowcount
    print(f"\n✅ {affected_rows}개 프롬프트의 소유권이 이전되었습니다.")

    # 확인
    cursor.execute(
        'SELECT COUNT(*) FROM prompt_templates WHERE user_id = ?',
        (to_user_id,)
    )
    count = cursor.fetchone()[0]
    print(f"✅ user_id {to_user_id}의 프롬프트 수: {count}")

    conn.close()

if __name__ == "__main__":
    print("=== 프롬프트 소유권 마이그레이션 ===\n")

    # testuser (user_id 1) → dpffpsk907@gmail.com (user_id 2)
    migrate_prompts(from_user_id=1, to_user_id=2)
