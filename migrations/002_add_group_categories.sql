-- Migration: 그룹별 카테고리 동적 관리
-- Date: 2025-11-01
-- Description: group_categories 테이블 추가

-- 1. group_categories 테이블 생성
CREATE TABLE IF NOT EXISTS group_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    order_index INTEGER DEFAULT 999,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(group_id, name),
    FOREIGN KEY (group_id) REFERENCES user_groups(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_group_categories_group_id ON group_categories(group_id);
CREATE INDEX IF NOT EXISTS idx_group_categories_order ON group_categories(group_id, order_index);

-- Migration 완료
-- 롤백이 필요하면:
-- DROP TABLE IF EXISTS group_categories;
