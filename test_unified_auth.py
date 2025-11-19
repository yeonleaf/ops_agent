#!/usr/bin/env python3
"""
통합 인증 시스템 테스트 스크립트
"""
import sqlite3
import bcrypt
import sys

def check_user(email):
    """사용자 정보 확인"""
    conn = sqlite3.connect('tickets.db')
    cursor = conn.cursor()

    cursor.execute(
        'SELECT id, email, user_name, password_hash FROM users WHERE email = ?',
        (email,)
    )
    user = cursor.fetchone()
    conn.close()

    if user:
        user_id, email, user_name, password_hash = user
        print(f"✅ 사용자 발견:")
        print(f"   ID: {user_id}")
        print(f"   Email: {email}")
        print(f"   Name: {user_name}")
        print(f"   Password Hash: {password_hash[:50]}...")
        return True
    else:
        print(f"❌ 사용자를 찾을 수 없습니다: {email}")
        return False

def verify_password(email, password):
    """비밀번호 확인"""
    conn = sqlite3.connect('tickets.db')
    cursor = conn.cursor()

    cursor.execute(
        'SELECT password_hash FROM users WHERE email = ?',
        (email,)
    )
    result = cursor.fetchone()
    conn.close()

    if result:
        password_hash = result[0]
        if bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
            print(f"✅ 비밀번호가 일치합니다!")
            return True
        else:
            print(f"❌ 비밀번호가 일치하지 않습니다.")
            return False
    return False

def update_password(email, new_password):
    """비밀번호 업데이트"""
    password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    conn = sqlite3.connect('tickets.db')
    cursor = conn.cursor()

    cursor.execute(
        'UPDATE users SET password_hash = ? WHERE email = ?',
        (password_hash, email)
    )
    conn.commit()
    conn.close()

    print(f"✅ 비밀번호가 업데이트되었습니다: {email}")

if __name__ == "__main__":
    print("=== 통합 인증 시스템 테스트 ===\n")

    email = "dpffpsk907@gmail.com"

    # 1. 사용자 확인
    print("1. 사용자 정보 확인:")
    if not check_user(email):
        sys.exit(1)

    print("\n2. 비밀번호 테스트:")
    test_passwords = ["test1234", "password", "1234"]

    for pwd in test_passwords:
        print(f"   테스트: '{pwd}'")
        if verify_password(email, pwd):
            print(f"\n✅ 현재 비밀번호: {pwd}")
            break
    else:
        print("\n⚠️  알려진 테스트 비밀번호로 로그인할 수 없습니다.")
        print("   비밀번호를 'test1234'로 재설정하시겠습니까? (y/n)")

        choice = input().strip().lower()
        if choice == 'y':
            update_password(email, "test1234")
            print("\n✅ 이제 'test1234'로 로그인할 수 있습니다.")
