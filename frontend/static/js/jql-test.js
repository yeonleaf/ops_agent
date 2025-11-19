/**
 * JQL Test - JQL 쿼리 테스트 및 결과 표시
 *
 * 기능:
 * - JQL 테스트 버튼 클릭 처리
 * - API 호출 및 결과 처리
 * - 결과 표시 (카드 뷰, 테이블 뷰, JSON 뷰)
 * - 에러 핸들링
 */

let currentJQLTestResults = null;
let currentJQLView = 'card';  // card, table, json

/**
 * JQL 테스트 초기화
 */
function initJQLTest() {
    const testButton = document.getElementById('test-jql-btn');

    if (testButton) {
        testButton.addEventListener('click', async () => {
            await runJQLTest();
        });
    }
}

/**
 * JQL 테스트 실행
 */
async function runJQLTest() {
    const testButton = document.getElementById('test-jql-btn');
    const resultsContainer = document.getElementById('jql-test-results');

    // JQL 가져오기
    let jql = '';
    if (window.jqlEditor && window.jqlEditor.getEditor()) {
        jql = window.jqlEditor.getValue();
    } else {
        jql = document.getElementById('prompt-content').value;
    }

    // JQL이 비어있는지 확인
    if (!jql.trim()) {
        showToast('JQL 쿼리를 입력해주세요', 'error');
        return;
    }

    // 로딩 상태 표시
    testButton.disabled = true;
    testButton.innerHTML = '<span class="test-icon">⏳</span> 실행 중...';
    resultsContainer.style.display = 'block';
    resultsContainer.innerHTML = `
        <div class="jql-loading">
            <div class="jql-loading-spinner"></div>
            <div class="jql-loading-text">쿼리를 실행하고 있습니다...</div>
        </div>
    `;

    try {
        // API 호출
        const response = await fetch('/api/v2/jira/test-jql', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
            },
            body: JSON.stringify({
                jql: jql,
                max_results: 20
            })
        });

        const result = await response.json();

        if (result.success) {
            // 성공 - 결과 저장 및 표시
            currentJQLTestResults = result;
            displayJQLResults(result, 'card');
            showToast(`✅ ${result.total}개 이슈 조회 완료 (${result.execution_time_ms.toFixed(0)}ms)`, 'success');
        } else {
            // 실패 - 에러 표시
            displayJQLError(result);
            showToast('❌ JQL 쿼리 실행 실패', 'error');
        }

    } catch (error) {
        // 네트워크 에러
        resultsContainer.innerHTML = `
            <div class="jql-error">
                <div class="jql-error-title">
                    <span>⚠️</span>
                    <span>네트워크 오류</span>
                </div>
                <div class="jql-error-message">
                    서버와 통신할 수 없습니다. 네트워크 연결을 확인해주세요.
                </div>
            </div>
        `;
        showToast('❌ 네트워크 오류', 'error');
    } finally {
        // 버튼 원래 상태로 복구
        testButton.disabled = false;
        testButton.innerHTML = '<span class="test-icon">▶</span> 테스트';
    }
}

/**
 * JQL 결과 표시
 */
function displayJQLResults(result, viewType = 'card') {
    const resultsContainer = document.getElementById('jql-test-results');
    currentJQLView = viewType;

    // 결과가 없는 경우
    if (result.total === 0) {
        resultsContainer.innerHTML = `
            <div class="jql-empty">
                <div class="jql-empty-icon">🔍</div>
                <div class="jql-empty-text">조건에 맞는 이슈가 없습니다</div>
            </div>
        `;
        return;
    }

    // 변수 치환 정보
    let substitutionInfo = '';
    if (result.substitutions && Object.keys(result.substitutions).length > 0) {
        const subsItems = Object.entries(result.substitutions)
            .map(([key, value]) => `<li><code>{{${key}}}</code> → <code>${escapeHtml(value)}</code></li>`)
            .join('');

        substitutionInfo = `
            <div class="jql-substitution-info">
                <div class="jql-substitution-title">🔄 변수 치환됨</div>
                <div class="jql-substitution-details">
                    <div><strong>원본 JQL:</strong> <code>${escapeHtml(result.original_jql)}</code></div>
                    <div><strong>치환된 JQL:</strong> <code>${escapeHtml(result.substituted_jql)}</code></div>
                    <div><strong>치환 내역:</strong></div>
                    <ul class="jql-substitution-list">${subsItems}</ul>
                </div>
            </div>
        `;
    }

    // 헤더 생성
    const header = `
        ${substitutionInfo}
        <div class="jql-results-header">
            <div class="jql-results-info">
                <span><strong>${result.total}</strong>개 이슈</span>
                <span>실행 시간: <strong>${result.execution_time_ms.toFixed(0)}ms</strong></span>
            </div>
            <div class="jql-view-toggle">
                <button class="jql-view-btn ${viewType === 'card' ? 'active' : ''}" data-view="card">카드</button>
                <button class="jql-view-btn ${viewType === 'table' ? 'active' : ''}" data-view="table">테이블</button>
                <button class="jql-view-btn ${viewType === 'json' ? 'active' : ''}" data-view="json">JSON</button>
            </div>
        </div>
    `;

    // 본문 생성
    let body = '';
    if (viewType === 'card') {
        body = renderCardView(result.issues);
    } else if (viewType === 'table') {
        body = renderTableView(result.issues);
    } else if (viewType === 'json') {
        body = renderJSONView(result);
    }

    resultsContainer.innerHTML = header + `<div class="jql-results-body">${body}</div>`;

    // 뷰 전환 버튼 이벤트 리스너
    document.querySelectorAll('.jql-view-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            displayJQLResults(result, btn.dataset.view);
        });
    });

    // 카드 클릭 이벤트 (Jira 이슈 페이지로 이동)
    document.querySelectorAll('.jql-issue-card, .jql-issue-key').forEach(el => {
        el.addEventListener('click', (e) => {
            if (e.target.tagName === 'A') return;  // 링크는 직접 처리
            const url = el.dataset.url || el.closest('.jql-issue-card')?.dataset.url;
            if (url) {
                window.open(url, '_blank');
            }
        });
    });
}

/**
 * 카드 뷰 렌더링
 */
function renderCardView(issues) {
    const cards = issues.map(issue => {
        // 상태 스타일 클래스
        let statusClass = 'todo';
        const statusLower = issue.status.toLowerCase();
        if (statusLower.includes('done') || statusLower.includes('완료')) {
            statusClass = 'done';
        } else if (statusLower.includes('progress') || statusLower.includes('진행')) {
            statusClass = 'in-progress';
        }

        // 우선순위 아이콘
        let priorityIcon = '●';
        let priorityClass = 'medium';
        const priorityLower = issue.priority.toLowerCase();
        if (priorityLower.includes('highest')) {
            priorityIcon = '▲▲';
            priorityClass = 'highest';
        } else if (priorityLower.includes('high')) {
            priorityIcon = '▲';
            priorityClass = 'high';
        } else if (priorityLower.includes('low')) {
            priorityIcon = '▼';
            priorityClass = 'low';
        } else if (priorityLower.includes('lowest')) {
            priorityIcon = '▼▼';
            priorityClass = 'lowest';
        }

        // 담당자 표시
        const assigneeHTML = issue.assigneeAvatar
            ? `<img src="${issue.assigneeAvatar}" alt="${issue.assignee}" class="jql-assignee-avatar" />`
            : `<div class="jql-assignee-default">👤</div>`;

        // 업데이트 날짜 상대 시간 변환
        const updatedRelative = getRelativeTime(issue.updated);

        return `
            <div class="jql-issue-card" data-url="${issue.url}">
                <div class="jql-issue-header">
                    <a href="${issue.url}" target="_blank" class="jql-issue-key" onclick="event.stopPropagation()">
                        ${issue.key}
                    </a>
                    <span class="jql-issue-type">${issue.type}</span>
                </div>
                <div class="jql-issue-summary">${escapeHtml(issue.summary)}</div>
                <div class="jql-issue-meta">
                    <span class="jql-issue-status ${statusClass}">${issue.status}</span>
                    <span class="jql-issue-priority">
                        <span class="jql-priority-icon ${priorityClass}">${priorityIcon}</span>
                        <span>${issue.priority}</span>
                    </span>
                    <span class="jql-issue-assignee">
                        ${assigneeHTML}
                        <span>${issue.assignee}</span>
                    </span>
                    <span class="jql-issue-updated">${updatedRelative}</span>
                </div>
            </div>
        `;
    }).join('');

    return `<div class="jql-cards-view">${cards}</div>`;
}

/**
 * 테이블 뷰 렌더링
 */
function renderTableView(issues) {
    const rows = issues.map(issue => `
        <tr>
            <td><a href="${issue.url}" target="_blank" class="jql-issue-key">${issue.key}</a></td>
            <td>${escapeHtml(issue.summary)}</td>
            <td>${issue.status}</td>
            <td>${issue.priority}</td>
            <td>${issue.assignee}</td>
            <td>${getRelativeTime(issue.updated)}</td>
        </tr>
    `).join('');

    return `
        <div class="jql-table-view">
            <table>
                <thead>
                    <tr>
                        <th>이슈 키</th>
                        <th>제목</th>
                        <th>상태</th>
                        <th>우선순위</th>
                        <th>담당자</th>
                        <th>업데이트</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows}
                </tbody>
            </table>
        </div>
    `;
}

/**
 * JSON 뷰 렌더링
 */
function renderJSONView(result) {
    const jsonString = JSON.stringify(result, null, 2);

    return `
        <div class="jql-json-view">
            <div class="jql-json-header">
                <span>원본 데이터</span>
                <button onclick="copyJSONToClipboard()">📋 복사</button>
            </div>
            <pre class="jql-json-content" id="jql-json-content">${escapeHtml(jsonString)}</pre>
        </div>
    `;
}

/**
 * JQL 에러 표시
 */
function displayJQLError(result) {
    const resultsContainer = document.getElementById('jql-test-results');

    const suggestionHTML = result.suggestion
        ? `
            <div class="jql-error-suggestion">
                <strong>💡 제안</strong>
                ${escapeHtml(result.suggestion)}
            </div>
        `
        : '';

    resultsContainer.innerHTML = `
        <div class="jql-error">
            <div class="jql-error-title">
                <span>⚠️</span>
                <span>JQL 쿼리 오류</span>
            </div>
            <div class="jql-error-message">
                ${escapeHtml(result.error)}
            </div>
            ${suggestionHTML}
        </div>
    `;
}

/**
 * JSON을 클립보드에 복사
 */
function copyJSONToClipboard() {
    const jsonContent = document.getElementById('jql-json-content');
    if (jsonContent) {
        navigator.clipboard.writeText(jsonContent.textContent)
            .then(() => {
                showToast('✅ JSON이 클립보드에 복사되었습니다', 'success');
            })
            .catch(err => {
                console.error('복사 실패:', err);
                showToast('❌ 복사 실패', 'error');
            });
    }
}

/**
 * 상대 시간 변환 (예: "2시간 전")
 */
function getRelativeTime(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffSec < 60) return '방금 전';
    if (diffMin < 60) return `${diffMin}분 전`;
    if (diffHour < 24) return `${diffHour}시간 전`;
    if (diffDay < 30) return `${diffDay}일 전`;
    if (diffDay < 365) return `${Math.floor(diffDay / 30)}달 전`;
    return `${Math.floor(diffDay / 365)}년 전`;
}

/**
 * HTML 이스케이프
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * 토스트 메시지 표시 (dashboard.js의 showToast 재사용)
 */
function showToast(message, type = 'info') {
    // dashboard.js의 showToast를 사용할 수 있으면 사용
    if (typeof window.showToast === 'function') {
        window.showToast(message, type);
    } else {
        console.log(`[${type}] ${message}`);
    }
}

// 페이지 로드 시 초기화
if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        initJQLTest();
    });

    // export for HTML onclick handlers
    window.copyJSONToClipboard = copyJSONToClipboard;
}
