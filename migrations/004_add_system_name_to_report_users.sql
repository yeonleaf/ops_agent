-- Migration: report_users 테이블에 system_name 추가 및 user 1번 데이터 추가
-- Date: 2025-11-01
-- Description: 보고서 시스템 사용자 테이블에 system_name 추가

-- 1. report_users 테이블에 system_name 컬럼 추가
ALTER TABLE report_users ADD COLUMN system_name VARCHAR(50);

-- 2. user 1번 데이터 추가 (dpffpsk907@gmail.com)
INSERT OR IGNORE INTO report_users (id, username, email, password_hash, system_name, created_at)
SELECT id, user_name, email, password_hash, system_name, created_at
FROM (SELECT 1 as id, '조주연' as user_name, 'dpffpsk907@gmail.com' as email,
      '$2b$12$dummy_hash' as password_hash, 'NCMS' as system_name,
      datetime('now') as created_at);

-- tickets.db의 user 1번 데이터를 가져와서 삽입하려면 수동으로 해야 합니다
-- 아래 명령어를 수동으로 실행하거나, 스크립트에서 처리:
-- UPDATE report_users SET password_hash = (SELECT password_hash FROM users WHERE id = 1 LIMIT 1) WHERE id = 1;

-- Migration 완료
-- 롤백이 필요하면:
-- ALTER TABLE report_users DROP COLUMN system_name;
-- DELETE FROM report_users WHERE id = 1;
