/**
 * JQL Manager - JQL 쿼리 관리 기능
 *
 * 기능:
 * - JQL CRUD 작업
 * - JQL 테스트
 * - 필터링 및 검색
 */

let jqlEditor = null;
let currentJQLs = [];
let editingJQLId = null;

// API 엔드포인트
const JQL_API_BASE = '/api/v2/jql';

/**
 * JQL 목록 로드
 */
async function loadJQLs() {
    try {
        const token = localStorage.getItem('auth_token');
        if (!token) {
            showToast('로그인이 필요합니다.', 'error');
            return;
        }

        const includePublic = document.getElementById('show-public-jqls')?.checked || false;
        const system = document.getElementById('jql-system-filter')?.value || '';
        const category = document.getElementById('jql-category-filter')?.value || '';
        const search = document.getElementById('jql-search')?.value || '';

        const params = new URLSearchParams();
        if (includePublic) params.append('include_public', 'true');
        if (system) params.append('system', system);
        if (category) params.append('category', category);
        if (search) params.append('search', search);

        const response = await fetch(`${JQL_API_BASE}?${params.toString()}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error('JQL 목록 로드 실패');
        }

        const data = await response.json();
        currentJQLs = data.my_jqls || [];

        if (includePublic && data.public_jqls) {
            currentJQLs = currentJQLs.concat(data.public_jqls);
        }

        // 필터 옵션 업데이트
        updateFilterOptions(data.systems, data.categories);

        // JQL 목록 렌더링
        renderJQLs(currentJQLs);

        console.log(`✅ JQL ${data.total}개 로드 완료`);

    } catch (error) {
        console.error('❌ JQL 로드 실패:', error);
        showToast('JQL 목록을 불러오는데 실패했습니다.', 'error');
        document.getElementById('jqls-list').innerHTML = '<div class="error-message">JQL 목록을 불러오는데 실패했습니다.</div>';
    }
}

/**
 * 필터 옵션 업데이트
 */
function updateFilterOptions(systems, categories) {
    const systemFilter = document.getElementById('jql-system-filter');
    const categoryFilter = document.getElementById('jql-category-filter');

    if (systemFilter) {
        const currentSystem = systemFilter.value;
        systemFilter.innerHTML = '<option value="">모든 시스템</option>';
        systems.forEach(sys => {
            const option = document.createElement('option');
            option.value = sys;
            option.textContent = sys;
            systemFilter.appendChild(option);
        });
        systemFilter.value = currentSystem;
    }

    if (categoryFilter) {
        const currentCategory = categoryFilter.value;
        categoryFilter.innerHTML = '<option value="">모든 카테고리</option>';
        categories.forEach(cat => {
            const option = document.createElement('option');
            option.value = cat;
            option.textContent = cat;
            categoryFilter.appendChild(option);
        });
        categoryFilter.value = currentCategory;
    }
}

/**
 * JQL 목록 렌더링
 */
function renderJQLs(jqls) {
    const container = document.getElementById('jqls-list');

    if (!jqls || jqls.length === 0) {
        container.innerHTML = '<div class="empty-message">JQL이 없습니다. 새 JQL을 생성해보세요!</div>';
        return;
    }

    container.innerHTML = jqls.map(jql => `
        <div class="prompt-card jql-card" data-jql-id="${jql.id}">
            <div class="prompt-card-header">
                <div>
                    <div class="prompt-card-title">${escapeHtml(jql.name)}</div>
                    ${jql.system ? `<span class="prompt-card-category" style="background: var(--info, #17a2b8);">${escapeHtml(jql.system)}</span>` : ''}
                    ${jql.category ? `<span class="prompt-card-category" style="background: var(--warning, #ffc107);">${escapeHtml(jql.category)}</span>` : ''}
                    ${jql.is_public ? '<span class="prompt-card-category" style="background: var(--success, #28a745);">공개</span>' : ''}
                </div>
            </div>
            ${jql.description ? `<div class="prompt-card-description">${escapeHtml(jql.description)}</div>` : ''}
            <div class="jql-preview">
                <code>${escapeHtml(jql.jql ? jql.jql.substring(0, 150) : '')}${jql.jql && jql.jql.length > 150 ? '...' : ''}</code>
            </div>
            <div class="jql-card-metadata">
                ${jql.owner ? `<span>작성자: ${escapeHtml(jql.owner)}</span>` : '<span></span>'}
                <span>${formatDate(jql.updated_at)}</span>
            </div>
            <div class="prompt-card-actions">
                <button class="btn-secondary" onclick="testJQLById(${jql.id})" title="테스트">🧪 테스트</button>
                <button class="btn-primary" onclick="editJQL(${jql.id})" title="수정">✏️ 수정</button>
                <button class="btn-danger" onclick="deleteJQL(${jql.id})" title="삭제">🗑️ 삭제</button>
            </div>
        </div>
    `).join('');
}

/**
 * JQL 생성 모달 열기
 */
function openCreateJQLModal() {
    editingJQLId = null;
    document.getElementById('jql-modal-title').textContent = '새 JQL 생성';
    document.getElementById('jql-form').reset();
    document.getElementById('jql-id').value = '';

    // JQL 에디터 초기화
    if (jqlEditor) {
        jqlEditor.setValue('');
    } else {
        initializeJQLEditor();
    }

    document.getElementById('jql-test-output').style.display = 'none';
    document.getElementById('jql-modal').style.display = 'flex';
}

/**
 * JQL 수정 모달 열기
 */
async function editJQL(jqlId) {
    try {
        const token = localStorage.getItem('auth_token');
        const response = await fetch(`${JQL_API_BASE}/${jqlId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error('JQL 로드 실패');
        }

        const jql = await response.json();

        editingJQLId = jqlId;
        document.getElementById('jql-modal-title').textContent = 'JQL 수정';
        document.getElementById('jql-id').value = jql.id;
        document.getElementById('jql-name').value = jql.name || '';
        document.getElementById('jql-description').value = jql.description || '';
        document.getElementById('jql-system').value = jql.system || '';
        document.getElementById('jql-category').value = jql.category || '';
        document.getElementById('jql-is-public').checked = jql.is_public || false;

        // JQL 에디터 초기화
        if (jqlEditor) {
            jqlEditor.setValue(jql.jql || '');
        } else {
            initializeJQLEditor();
            setTimeout(() => {
                if (jqlEditor) {
                    jqlEditor.setValue(jql.jql || '');
                }
            }, 500);
        }

        document.getElementById('jql-test-output').style.display = 'none';
        document.getElementById('jql-modal').style.display = 'flex';

    } catch (error) {
        console.error('❌ JQL 로드 실패:', error);
        showToast('JQL을 불러오는데 실패했습니다.', 'error');
    }
}

/**
 * JQL 모달 닫기
 */
function closeJQLModal() {
    document.getElementById('jql-modal').style.display = 'none';
    editingJQLId = null;
}

/**
 * JQL 에디터 초기화
 */
function initializeJQLEditor() {
    require(['vs/editor/editor.main'], function() {
        const container = document.getElementById('jql-editor-container');
        if (!container) return;

        jqlEditor = monaco.editor.create(container, {
            value: '',
            language: 'plaintext',
            theme: 'vs',
            minimap: { enabled: false },
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            automaticLayout: true,
            wordWrap: 'on'
        });
    });
}

/**
 * JQL 폼 제출
 */
async function handleJQLFormSubmit(event) {
    event.preventDefault();

    const jqlId = document.getElementById('jql-id').value;
    const name = document.getElementById('jql-name').value;
    const description = document.getElementById('jql-description').value;
    const jql = jqlEditor ? jqlEditor.getValue() : '';
    const system = document.getElementById('jql-system').value;
    const category = document.getElementById('jql-category').value;
    const isPublic = document.getElementById('jql-is-public').checked;

    if (!name || !jql) {
        showToast('JQL 이름과 쿼리를 입력해주세요.', 'error');
        return;
    }

    const payload = {
        name,
        jql,
        description: description || null,
        system: system || null,
        category: category || null,
        is_public: isPublic
    };

    try {
        const token = localStorage.getItem('auth_token');
        const url = jqlId ? `${JQL_API_BASE}/${jqlId}` : JQL_API_BASE;
        const method = jqlId ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'JQL 저장 실패');
        }

        const result = await response.json();
        console.log('✅ JQL 저장 완료:', result);
        showToast('JQL이 저장되었습니다.', 'success');
        closeJQLModal();
        loadJQLs();

    } catch (error) {
        console.error('❌ JQL 저장 실패:', error);
        showToast(error.message, 'error');
    }
}

/**
 * JQL 삭제
 */
async function deleteJQL(jqlId) {
    if (!confirm('이 JQL을 삭제하시겠습니까?')) {
        return;
    }

    try {
        const token = localStorage.getItem('auth_token');
        const response = await fetch(`${JQL_API_BASE}/${jqlId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'JQL 삭제 실패');
        }

        console.log('✅ JQL 삭제 완료');
        showToast('JQL이 삭제되었습니다.', 'success');
        loadJQLs();

    } catch (error) {
        console.error('❌ JQL 삭제 실패:', error);
        showToast(error.message, 'error');
    }
}

/**
 * JQL ID로 테스트
 */
async function testJQLById(jqlId) {
    try {
        const token = localStorage.getItem('auth_token');
        const response = await fetch(`${JQL_API_BASE}/test`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                jql_id: jqlId,
                max_results: 20
            })
        });

        if (!response.ok) {
            throw new Error('JQL 테스트 실패');
        }

        const result = await response.json();
        displayJQLTestResult(result);

    } catch (error) {
        console.error('❌ JQL 테스트 실패:', error);
        showToast('JQL 테스트에 실패했습니다.', 'error');
    }
}

/**
 * 모달 내 JQL 테스트
 */
async function testJQLInModal() {
    const jql = jqlEditor ? jqlEditor.getValue() : '';

    if (!jql) {
        showToast('JQL을 입력해주세요.', 'error');
        return;
    }

    const resultSpan = document.getElementById('jql-test-result');
    resultSpan.innerHTML = '<span class="loading">테스트 중...</span>';

    try {
        const token = localStorage.getItem('auth_token');
        const response = await fetch(`${JQL_API_BASE}/test`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                jql: jql,
                max_results: 20
            })
        });

        if (!response.ok) {
            throw new Error('JQL 테스트 실패');
        }

        const result = await response.json();

        // 결과 표시
        if (result.success) {
            resultSpan.innerHTML = `<span class="success">✅ ${result.total}개 이슈 발견 (${result.execution_time_ms}ms)</span>`;

            // 상세 결과 표시
            const outputDiv = document.getElementById('jql-test-output');
            const contentDiv = document.getElementById('jql-test-content');

            let html = `<p><strong>총 ${result.total}개 이슈</strong> (실행 시간: ${result.execution_time_ms}ms)</p>`;

            if (result.substituted_jql && result.substituted_jql !== result.original_jql) {
                html += `<p><strong>변수 치환:</strong></p>`;
                html += `<pre>${escapeHtml(result.original_jql)}</pre>`;
                html += `<p>↓</p>`;
                html += `<pre>${escapeHtml(result.substituted_jql)}</pre>`;
            }

            if (result.issues && result.issues.length > 0) {
                html += '<h5>이슈 목록 (최대 20개)</h5>';
                html += '<ul>';
                result.issues.forEach(issue => {
                    html += `<li><strong>${escapeHtml(issue.key)}</strong>: ${escapeHtml(issue.summary || '')}</li>`;
                });
                html += '</ul>';
            }

            contentDiv.innerHTML = html;
            outputDiv.style.display = 'block';

        } else {
            resultSpan.innerHTML = `<span class="error">❌ ${escapeHtml(result.error)}</span>`;
            const outputDiv = document.getElementById('jql-test-output');
            outputDiv.style.display = 'none';
        }

    } catch (error) {
        console.error('❌ JQL 테스트 실패:', error);
        resultSpan.innerHTML = `<span class="error">❌ 테스트 실패</span>`;
    }
}

/**
 * JQL 테스트 결과 표시 (별도 모달)
 */
function displayJQLTestResult(result) {
    let message = '';

    if (result.success) {
        message = `JQL 테스트 성공!\n\n`;
        message += `총 ${result.total}개 이슈 발견\n`;
        message += `실행 시간: ${result.execution_time_ms}ms\n`;

        if (result.jql_name) {
            message += `JQL 이름: ${result.jql_name}\n`;
        }

        if (result.substituted_jql && result.substituted_jql !== result.original_jql) {
            message += `\n변수 치환:\n${result.original_jql}\n↓\n${result.substituted_jql}`;
        }

        if (result.issues && result.issues.length > 0) {
            message += `\n\n이슈 샘플 (최대 5개):\n`;
            result.issues.slice(0, 5).forEach(issue => {
                message += `- ${issue.key}: ${issue.summary || ''}\n`;
            });
        }

        alert(message);
    } else {
        message = `JQL 테스트 실패\n\n`;
        message += `에러: ${result.error}\n`;

        if (result.suggestion) {
            message += `제안: ${result.suggestion}`;
        }

        alert(message);
    }
}

/**
 * 유틸리티 함수
 */
function escapeHtml(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.toString().replace(/[&<>"']/g, m => map[m]);
}

function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// 이벤트 리스너 등록
document.addEventListener('DOMContentLoaded', () => {
    // JQL 생성 버튼
    const createBtn = document.getElementById('create-jql-btn');
    if (createBtn) {
        createBtn.addEventListener('click', openCreateJQLModal);
    }

    // JQL 폼 제출
    const jqlForm = document.getElementById('jql-form');
    if (jqlForm) {
        jqlForm.addEventListener('submit', handleJQLFormSubmit);
    }

    // JQL 테스트 버튼
    const testBtn = document.getElementById('test-jql-btn-modal');
    if (testBtn) {
        testBtn.addEventListener('click', testJQLInModal);
    }

    // 필터 이벤트
    const jqlSearch = document.getElementById('jql-search');
    if (jqlSearch) {
        jqlSearch.addEventListener('input', debounce(loadJQLs, 500));
    }

    const jqlSystemFilter = document.getElementById('jql-system-filter');
    if (jqlSystemFilter) {
        jqlSystemFilter.addEventListener('change', loadJQLs);
    }

    const jqlCategoryFilter = document.getElementById('jql-category-filter');
    if (jqlCategoryFilter) {
        jqlCategoryFilter.addEventListener('change', loadJQLs);
    }

    const showPublicJQLs = document.getElementById('show-public-jqls');
    if (showPublicJQLs) {
        showPublicJQLs.addEventListener('change', loadJQLs);
    }

    // 초기 로드 (JQL 섹션이 활성화되면)
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                const jqlSection = document.getElementById('section-jql');
                if (jqlSection && jqlSection.classList.contains('active') && currentJQLs.length === 0) {
                    loadJQLs();
                }
            }
        });
    });

    const jqlSection = document.getElementById('section-jql');
    if (jqlSection) {
        observer.observe(jqlSection, { attributes: true });
    }
});

// Debounce 유틸리티
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Toast 메시지 표시 함수 (dashboard.js에 있지만 여기서도 정의)
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    if (!toast) return;

    toast.textContent = message;
    toast.className = `toast ${type}`;
    toast.classList.add('show');

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}
