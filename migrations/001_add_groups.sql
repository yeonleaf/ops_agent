-- Migration: 그룹 협업 기능 추가
-- Date: 2025-11-01
-- Description: user_groups, group_members 테이블 추가 및 기존 테이블에 그룹 관련 컬럼 추가

-- 1. user_groups 테이블 생성
CREATE TABLE IF NOT EXISTS user_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES report_users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_groups_created_by ON user_groups(created_by);


-- 2. group_members 테이블 생성
CREATE TABLE IF NOT EXISTS group_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role VARCHAR(20) DEFAULT 'member' NOT NULL,  -- 'owner' or 'member'
    system VARCHAR(50),  -- NCMS, EUXP, EDMP, ACS 등
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(group_id, user_id),
    FOREIGN KEY (group_id) REFERENCES user_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES report_users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_group_members_group_id ON group_members(group_id);
CREATE INDEX IF NOT EXISTS idx_group_members_user_id ON group_members(user_id);
CREATE INDEX IF NOT EXISTS idx_group_members_role ON group_members(role);


-- 3. prompt_templates 테이블에 그룹 관련 컬럼 추가
ALTER TABLE prompt_templates ADD COLUMN group_id INTEGER;
ALTER TABLE prompt_templates ADD COLUMN system VARCHAR(50);

-- 외래키 제약조건 추가 (SQLite에서는 ALTER TABLE로 FK 추가 불가, 기존 데이터 없으면 재생성)
-- SQLite limitation: 외래키는 테이블 생성 시에만 추가 가능
-- 운영 환경에서는 테이블 재생성이 필요할 수 있음

CREATE INDEX IF NOT EXISTS idx_prompt_templates_group_id ON prompt_templates(group_id);
CREATE INDEX IF NOT EXISTS idx_prompt_templates_system ON prompt_templates(system);


-- 4. reports 테이블에 그룹 관련 컬럼 추가
ALTER TABLE reports ADD COLUMN group_id INTEGER;
ALTER TABLE reports ADD COLUMN report_type VARCHAR(20) DEFAULT 'personal' NOT NULL;

CREATE INDEX IF NOT EXISTS idx_reports_group_id ON reports(group_id);
CREATE INDEX IF NOT EXISTS idx_reports_report_type ON reports(report_type);


-- 5. 기존 데이터 마이그레이션 (report_type 기본값 설정)
UPDATE reports SET report_type = 'personal' WHERE report_type IS NULL;


-- Migration 완료
-- 롤백이 필요하면 다음 명령어 실행:
-- DROP TABLE IF EXISTS group_members;
-- DROP TABLE IF EXISTS user_groups;
-- ALTER TABLE prompt_templates DROP COLUMN group_id;  -- SQLite는 DROP COLUMN 미지원
-- ALTER TABLE prompt_templates DROP COLUMN system;
-- ALTER TABLE reports DROP COLUMN group_id;
-- ALTER TABLE reports DROP COLUMN report_type;
