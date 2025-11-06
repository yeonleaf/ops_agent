// 멀티유저 동적 보고서 시스템 - 메인 앱 로직

// 인증 체크
const token = localStorage.getItem('token');
if (!token) {
    window.location.href = '/login.html';
}

// API 설정
const API_BASE = '/api/v2';
const authHeaders = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
};

// 전역 변수
let currentPrompts = [];
let currentEditingPromptId = null;
let generatedHtml = '';

// 초기화
document.addEventListener('DOMContentLoaded', function() {
    // 사용자 정보 표시
    document.getElementById('username').textContent = localStorage.getItem('username');

    // 탭 전환
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', function() {
            switchTab(this.dataset.tab);
        });
    });

    // 초기 데이터 로드
    loadPrompts();
});

// 탭 전환
function switchTab(tabName) {
    // 탭 버튼 활성화
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.tab[data-tab="${tabName}"]`).classList.add('active');

    // 탭 컨텐츠 전환
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById(`tab-${tabName}`).classList.add('active');

    // 탭별 로드
    if (tabName === 'prompts') {
        loadMyPrompts();
    } else if (tabName === 'history') {
        loadHistory();
    }
}

// ============================================
// 프롬프트 로딩 및 렌더링
// ============================================

async function loadPrompts() {
    const includePublic = document.getElementById('include-public').checked;

    try {
        const response = await fetch(`${API_BASE}/prompts?include_public=${includePublic}`, {
            headers: authHeaders
        });

        if (!response.ok) throw new Error('프롬프트 로딩 실패');

        const data = await response.json();
        currentPrompts = data;

        renderPromptSelector(data);
    } catch (error) {
        showMessage('message-generate', error.message, 'error');
    }
}

function renderPromptSelector(data) {
    const container = document.getElementById('prompt-selector');
    container.innerHTML = '';

    // 모든 프롬프트 합치기
    const allPrompts = [
        ...(data.my_prompts || []).map(p => ({...p, isMine: true})),
        ...(data.public_prompts || []).map(p => ({...p, isMine: false}))
    ];

    if (allPrompts.length === 0) {
        container.innerHTML = '<p style="text-align:center; color:#7f8c8d; padding:40px;">프롬프트가 없습니다. "프롬프트 관리" 탭에서 생성하세요.</p>';
        return;
    }

    // 카테고리별 그룹핑
    const grouped = {};
    allPrompts.forEach(p => {
        if (!grouped[p.category]) grouped[p.category] = [];
        grouped[p.category].push(p);
    });

    // 렌더링
    for (const [category, prompts] of Object.entries(grouped)) {
        const section = document.createElement('div');
        section.className = 'category-group';
        section.innerHTML = `<h3>${category}</h3>`;

        prompts.forEach(prompt => {
            const item = document.createElement('label');
            item.className = 'prompt-item';
            item.innerHTML = `
                <input type="checkbox" value="${prompt.id}" class="prompt-checkbox">
                <div class="prompt-info">
                    <div class="prompt-title">${prompt.title}</div>
                    ${prompt.description ? `<div class="prompt-desc">${prompt.description}</div>` : ''}
                </div>
                ${!prompt.isMine ? '<span class="badge">공개</span>' : ''}
            `;
            section.appendChild(item);
        });

        container.appendChild(section);
    }
}

function selectAll() {
    document.querySelectorAll('.prompt-checkbox').forEach(cb => cb.checked = true);
}

function deselectAll() {
    document.querySelectorAll('.prompt-checkbox').forEach(cb => cb.checked = false);
}

// ============================================
// 보고서 생성
// ============================================

async function generateReport() {
    const selected = Array.from(document.querySelectorAll('.prompt-checkbox:checked'))
        .map(cb => parseInt(cb.value));

    if (selected.length === 0) {
        showMessage('message-generate', '최소 1개 이상의 프롬프트를 선택해주세요', 'error');
        return;
    }

    const title = document.getElementById('report-title').value || '월간보고';
    const includeToc = document.getElementById('include-toc').checked;
    const save = document.getElementById('save-report').checked;

    // UI 상태
    hideMessage('message-generate');
    hidePreview('preview-generate');
    showLoading('loading-generate');

    try {
        const response = await fetch(`${API_BASE}/reports/generate`, {
            method: 'POST',
            headers: authHeaders,
            body: JSON.stringify({
                title,
                prompt_ids: selected,
                include_toc: includeToc,
                save
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '보고서 생성 실패');
        }

        const data = await response.json();

        if (data.success) {
            generatedHtml = data.html;
            document.getElementById('preview-content').innerHTML = data.html;
            showPreview('preview-generate');
            showMessage('message-generate', `보고서가 생성되었습니다! (${selected.length}개 프롬프트)`, 'success');

            if (save) {
                showMessage('message-generate', `보고서가 저장되었습니다 (ID: ${data.report_id})`, 'success');
            }
        } else {
            throw new Error('보고서 생성 실패');
        }
    } catch (error) {
        showMessage('message-generate', `오류: ${error.message}`, 'error');
    } finally {
        hideLoading('loading-generate');
    }
}

function downloadReport() {
    if (!generatedHtml) return;

    const blob = new Blob([generatedHtml], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `월간보고_${new Date().toISOString().slice(0, 10)}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// ============================================
// 프롬프트 관리
// ============================================

async function loadMyPrompts() {
    showLoading('loading-prompts');
    hideMessage('message-prompts');

    try {
        const response = await fetch(`${API_BASE}/prompts?include_public=false`, {
            headers: authHeaders
        });

        if (!response.ok) throw new Error('프롬프트 로딩 실패');

        const data = await response.json();
        renderPromptList(data.my_prompts || []);
    } catch (error) {
        showMessage('message-prompts', error.message, 'error');
    } finally {
        hideLoading('loading-prompts');
    }
}

function renderPromptList(prompts) {
    const container = document.getElementById('prompt-list');

    if (prompts.length === 0) {
        container.innerHTML = '<p style="text-align:center; color:#7f8c8d; padding:40px;">프롬프트가 없습니다. "+ 새 프롬프트" 버튼을 클릭하여 생성하세요.</p>';
        return;
    }

    container.innerHTML = prompts.map(prompt => `
        <div class="prompt-card">
            <div class="prompt-card-header">
                <div class="prompt-card-title">
                    ${prompt.title}
                    ${prompt.is_public ? '<span class="badge">공개</span>' : ''}
                </div>
                <div class="prompt-card-actions">
                    <button class="btn btn-icon btn-secondary" onclick="editPrompt(${prompt.id})">✏️ 수정</button>
                    <button class="btn btn-icon btn-danger" onclick="deletePrompt(${prompt.id})">🗑️ 삭제</button>
                </div>
            </div>
            <div class="prompt-card-body">
                ${prompt.description ? `<p><strong>설명:</strong> ${prompt.description}</p>` : ''}
                <p><strong>카테고리:</strong> ${prompt.category}</p>
                <details>
                    <summary style="cursor:pointer; color:#4CAF50; margin-top:10px;">프롬프트 내용 보기</summary>
                    <pre style="background:#f5f5f5; padding:15px; margin-top:10px; border-radius:4px; overflow-x:auto;">${prompt.prompt_content}</pre>
                </details>
            </div>
            <div class="prompt-meta">
                <span>순서: ${prompt.order_index}</span>
                <span>생성일: ${new Date(prompt.created_at).toLocaleDateString('ko-KR')}</span>
            </div>
        </div>
    `).join('');
}

async function showPromptModal(promptId = null) {
    document.getElementById('prompt-modal').classList.add('show');

    // 그룹 목록 로드
    await loadGroupsForPrompt();

    if (promptId) {
        // 수정 모드
        currentEditingPromptId = promptId;
        document.getElementById('modal-title').textContent = '프롬프트 수정';

        // 데이터 로드
        loadPromptForEdit(promptId);
    } else {
        // 생성 모드
        currentEditingPromptId = null;
        document.getElementById('modal-title').textContent = '새 프롬프트';
        document.getElementById('prompt-form').reset();

        // URL에서 group_id 파라미터 확인
        const params = new URLSearchParams(window.location.search);
        const groupId = params.get('group_id');
        if (groupId) {
            document.getElementById('prompt-group').value = groupId;
        }
    }
}

async function loadGroupsForPrompt() {
    try {
        const response = await fetch(`${API_BASE}/groups`, {
            headers: authHeaders
        });

        if (response.ok) {
            const data = await response.json();
            const groups = data.groups || [];

            const select = document.getElementById('prompt-group');
            // 기존 옵션 유지 (개인 프롬프트)
            select.innerHTML = '<option value="">개인 프롬프트</option>';

            groups.forEach(group => {
                const option = document.createElement('option');
                option.value = group.id;
                option.textContent = group.name;
                select.appendChild(option);
            });

            // 그룹이 있으면 선택 영역 표시
            if (groups.length > 0) {
                document.getElementById('group-select-group').style.display = 'block';
            }
        }
    } catch (error) {
        console.error('그룹 목록 로드 실패:', error);
    }
}

function closePromptModal() {
    document.getElementById('prompt-modal').classList.remove('show');
    document.getElementById('prompt-form').reset();
    currentEditingPromptId = null;
}

async function loadPromptForEdit(promptId) {
    try {
        const response = await fetch(`${API_BASE}/prompts?include_public=false`, {
            headers: authHeaders
        });

        const data = await response.json();
        const prompt = data.my_prompts.find(p => p.id === promptId);

        if (prompt) {
            document.getElementById('prompt-id').value = prompt.id;
            document.getElementById('prompt-title-input').value = prompt.title;
            document.getElementById('prompt-category').value = prompt.category;
            document.getElementById('prompt-description').value = prompt.description || '';
            document.getElementById('prompt-content').value = prompt.prompt_content;
            document.getElementById('prompt-order').value = prompt.order_index;
            document.getElementById('prompt-public').checked = prompt.is_public;
            document.getElementById('prompt-system').value = prompt.system || '';
            document.getElementById('prompt-group').value = prompt.group_id || '';
        }
    } catch (error) {
        alert('프롬프트 로딩 실패: ' + error.message);
        closePromptModal();
    }
}

async function savePrompt(event) {
    event.preventDefault();

    const promptData = {
        title: document.getElementById('prompt-title-input').value,
        category: document.getElementById('prompt-category').value,
        description: document.getElementById('prompt-description').value,
        prompt_content: document.getElementById('prompt-content').value,
        order_index: parseInt(document.getElementById('prompt-order').value),
        is_public: document.getElementById('prompt-public').checked,
        system: document.getElementById('prompt-system').value || null,
        group_id: document.getElementById('prompt-group').value ? parseInt(document.getElementById('prompt-group').value) : null
    };

    try {
        let response;

        if (currentEditingPromptId) {
            // 수정
            response = await fetch(`${API_BASE}/prompts/${currentEditingPromptId}`, {
                method: 'PUT',
                headers: authHeaders,
                body: JSON.stringify(promptData)
            });
        } else {
            // 생성
            response = await fetch(`${API_BASE}/prompts`, {
                method: 'POST',
                headers: authHeaders,
                body: JSON.stringify(promptData)
            });
        }

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '저장 실패');
        }

        closePromptModal();
        loadMyPrompts();
        showMessage('message-prompts', '프롬프트가 저장되었습니다', 'success');

        // 보고서 생성 탭의 프롬프트도 새로고침
        loadPrompts();
    } catch (error) {
        alert('저장 실패: ' + error.message);
    }
}

async function editPrompt(promptId) {
    showPromptModal(promptId);
}

async function deletePrompt(promptId) {
    if (!confirm('정말 이 프롬프트를 삭제하시겠습니까?')) return;

    try {
        const response = await fetch(`${API_BASE}/prompts/${promptId}`, {
            method: 'DELETE',
            headers: authHeaders
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '삭제 실패');
        }

        loadMyPrompts();
        showMessage('message-prompts', '프롬프트가 삭제되었습니다', 'success');

        // 보고서 생성 탭의 프롬프트도 새로고침
        loadPrompts();
    } catch (error) {
        showMessage('message-prompts', `삭제 실패: ${error.message}`, 'error');
    }
}

// ============================================
// 히스토리
// ============================================

async function loadHistory() {
    showLoading('loading-history');
    hideMessage('message-history');

    try {
        const response = await fetch(`${API_BASE}/reports`, {
            headers: authHeaders
        });

        if (!response.ok) throw new Error('히스토리 로딩 실패');

        const data = await response.json();
        renderHistoryList(data.reports || []);
    } catch (error) {
        showMessage('message-history', error.message, 'error');
    } finally {
        hideLoading('loading-history');
    }
}

function renderHistoryList(reports) {
    const container = document.getElementById('history-list');

    if (reports.length === 0) {
        container.innerHTML = '<p style="text-align:center; color:#7f8c8d; padding:40px;">저장된 보고서가 없습니다.</p>';
        return;
    }

    container.innerHTML = reports.map(report => `
        <div class="history-card" onclick="viewReport(${report.id})">
            <div class="history-card-header">
                <div class="history-card-title">${report.title}</div>
                <button class="btn btn-icon btn-danger" onclick="event.stopPropagation(); deleteReport(${report.id})">🗑️</button>
            </div>
            <div class="history-meta">
                <span>📦 ${report.prompt_count}개 프롬프트</span>
                <span>📅 ${new Date(report.created_at).toLocaleString('ko-KR')}</span>
            </div>
        </div>
    `).join('');
}

async function viewReport(reportId) {
    try {
        const response = await fetch(`${API_BASE}/reports/${reportId}`, {
            headers: authHeaders
        });

        if (!response.ok) throw new Error('보고서 로딩 실패');

        const report = await response.json();

        document.getElementById('report-modal-title').textContent = report.title;
        document.getElementById('report-modal-content').innerHTML = report.html_content;
        document.getElementById('report-modal').classList.add('show');
    } catch (error) {
        showMessage('message-history', error.message, 'error');
    }
}

function closeReportModal() {
    document.getElementById('report-modal').classList.remove('show');
}

async function deleteReport(reportId) {
    if (!confirm('정말 이 보고서를 삭제하시겠습니까?')) return;

    try {
        const response = await fetch(`${API_BASE}/reports/${reportId}`, {
            method: 'DELETE',
            headers: authHeaders
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '삭제 실패');
        }

        loadHistory();
        showMessage('message-history', '보고서가 삭제되었습니다', 'success');
    } catch (error) {
        showMessage('message-history', `삭제 실패: ${error.message}`, 'error');
    }
}

// ============================================
// UI 헬퍼 함수
// ============================================

function showLoading(id) {
    document.getElementById(id).classList.add('show');
}

function hideLoading(id) {
    document.getElementById(id).classList.remove('show');
}

function showMessage(id, text, type) {
    const el = document.getElementById(id);
    el.textContent = text;
    el.className = `message show ${type}`;

    // 3초 후 자동 숨김
    setTimeout(() => hideMessage(id), 5000);
}

function hideMessage(id) {
    document.getElementById(id).className = 'message';
}

function showPreview(id) {
    document.getElementById(id).classList.add('show');
}

function hidePreview(id) {
    document.getElementById(id).classList.remove('show');
}

function logout() {
    if (confirm('로그아웃 하시겠습니까?')) {
        localStorage.clear();
        window.location.href = '/login.html';
    }
}
