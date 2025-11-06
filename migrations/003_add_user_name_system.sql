-- Migration: users 테이블에 user_name, system_name 추가
-- Date: 2025-11-01
-- Description: 사용자 이름과 담당 시스템 정보 추가

-- 1. users 테이블에 컬럼 추가
ALTER TABLE users ADD COLUMN user_name VARCHAR(100);
ALTER TABLE users ADD COLUMN system_name VARCHAR(50);

-- 2. user 1번 데이터 업데이트
UPDATE users SET user_name = '조주연', system_name = 'NCMS' WHERE id = 1;

-- Migration 완료
-- 롤백이 필요하면:
-- ALTER TABLE users DROP COLUMN user_name;
-- ALTER TABLE users DROP COLUMN system_name;
