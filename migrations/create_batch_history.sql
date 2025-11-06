-- Batch History 테이블 생성
-- Jira 동기화 배치의 실행 이력을 저장

CREATE TABLE IF NOT EXISTS batch_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    batch_type VARCHAR(50) NOT NULL,       -- 'jira_sync'
    last_run_at TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL,           -- 'success' | 'failed'
    processed_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 유저별, 배치 타입별로 하나의 레코드만 유지 (UPSERT용)
    UNIQUE(user_id, batch_type)
);

-- 인덱스 생성 (조회 성능 향상)
CREATE INDEX IF NOT EXISTS idx_batch_history_user_type
ON batch_history(user_id, batch_type);

CREATE INDEX IF NOT EXISTS idx_batch_history_status
ON batch_history(status);

-- 코멘트 (SQLite는 COMMENT 미지원이므로 참고용)
-- user_id: integration 테이블의 user_id와 연결
-- batch_type: 'jira_sync' (향후 다른 타입 추가 가능)
-- last_run_at: 마지막 성공 실행 시각 (다음 배치의 시작 시점)
-- status: 'success' 또는 'failed'
-- processed_count: 처리된 청크 개수
-- error_message: 실패 시 에러 메시지
