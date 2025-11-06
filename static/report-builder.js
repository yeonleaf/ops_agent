// Report Builder JavaScript

// ========================================
// Global State
// ========================================
const state = {
    token: localStorage.getItem('token'),
    user: null,
    availablePrompts: [],
    selectedPromptIds: new Set(),
    sections: [],  // 실행된 결과들
    previewHtml: null
};

// ========================================
// API Configuration
// ========================================
const API_BASE = '/api/v2';

function getHeaders() {
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${state.token}`
    };
}

// ========================================
// Utility Functions
// ========================================
function showToast(title, message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = {
        success: '✅',
        error: '❌',
        info: 'ℹ️'
    };

    toast.innerHTML = `
        <div class="toast-icon">${icons[type]}</div>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <div class="toast-message">${message}</div>
        </div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 5000);
}

function showLoading(show = true) {
    document.getElementById('loading').style.display = show ? 'flex' : 'none';
}

function updateEmptyState() {
    const emptyState = document.getElementById('empty-state');
    const sectionsList = document.getElementById('sections-list');
    const reportActions = document.getElementById('report-actions');

    if (state.sections.length === 0) {
        emptyState.style.display = 'block';
        sectionsList.style.display = 'none';
        reportActions.style.display = 'none';
    } else {
        emptyState.style.display = 'none';
        sectionsList.style.display = 'block';
        reportActions.style.display = 'block';
    }
}

function updateExecuteButton() {
    const btn = document.getElementById('execute-btn');
    btn.disabled = state.selectedPromptIds.size === 0;
}

// ========================================
// Authentication
// ========================================
function checkAuth() {
    if (!state.token) {
        window.location.href = '/static/login.html';
        return false;
    }
    return true;
}

function logout() {
    localStorage.removeItem('token');
    window.location.href = '/static/login.html';
}

// ========================================
// Load Prompts
// ========================================
async function loadPrompts() {
    try {
        const response = await fetch(`${API_BASE}/prompts?include_public=true`, {
            headers: getHeaders()
        });

        if (!response.ok) {
            if (response.status === 401) {
                logout();
                return;
            }
            throw new Error('프롬프트 로드 실패');
        }

        const data = await response.json();
        state.availablePrompts = [
            ...data.my_prompts || [],
            ...(data.public_prompts || []).map(p => ({ ...p, isPublic: true }))
        ];

        renderPromptSelector();

    } catch (error) {
        console.error('Error loading prompts:', error);
        showToast('오류', '프롬프트를 불러오는데 실패했습니다', 'error');
    }
}

// ========================================
// Render Prompt Selector
// ========================================
function renderPromptSelector() {
    const container = document.getElementById('available-prompts');

    if (state.availablePrompts.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>저장된 프롬프트가 없습니다</p></div>';
        return;
    }

    // 카테고리별 그룹핑
    const grouped = {};
    state.availablePrompts.forEach(prompt => {
        const category = prompt.category || '기타';
        if (!grouped[category]) {
            grouped[category] = [];
        }
        grouped[category].push(prompt);
    });

    container.innerHTML = '';

    for (const [category, prompts] of Object.entries(grouped)) {
        const section = document.createElement('div');
        section.className = 'category-group';

        const header = document.createElement('h3');
        header.textContent = category;
        section.appendChild(header);

        prompts.forEach(prompt => {
            const label = document.createElement('label');
            label.className = 'prompt-item';
            if (state.selectedPromptIds.has(prompt.id)) {
                label.classList.add('selected');
            }

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = prompt.id;
            checkbox.checked = state.selectedPromptIds.has(prompt.id);
            checkbox.addEventListener('change', (e) => {
                if (e.target.checked) {
                    state.selectedPromptIds.add(prompt.id);
                } else {
                    state.selectedPromptIds.delete(prompt.id);
                }
                label.classList.toggle('selected', e.target.checked);
                updateExecuteButton();
            });

            const span = document.createElement('span');
            span.textContent = prompt.title;
            if (prompt.isPublic) {
                span.textContent += ' 🌐';
            }

            label.appendChild(checkbox);
            label.appendChild(span);
            section.appendChild(label);
        });

        container.appendChild(section);
    }
}

// ========================================
// Execute Prompts (Batch)
// ========================================
async function executePrompts() {
    if (state.selectedPromptIds.size === 0) {
        showToast('알림', '최소 1개 이상의 프롬프트를 선택해주세요', 'info');
        return;
    }

    const promptIds = Array.from(state.selectedPromptIds);

    showLoading(true);

    try {
        const response = await fetch(`${API_BASE}/reports/execute-batch`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({
                prompt_ids: promptIds,
                variables: {}  // 필요시 사용자 입력 추가
            })
        });

        if (!response.ok) {
            throw new Error('실행 실패');
        }

        const data = await response.json();

        // 성공한 결과만 sections에 추가
        const successResults = data.results.filter(r => r.status === 'success');

        successResults.forEach((result, index) => {
            state.sections.push({
                prompt_id: result.prompt_id,
                title: result.title,
                category: result.category,
                html_content: result.html_result,
                order: state.sections.length + index
            });
        });

        renderSections();
        updateEmptyState();

        showToast(
            '실행 완료',
            `${data.success}개 성공, ${data.failed}개 실패`,
            data.failed > 0 ? 'info' : 'success'
        );

        // 선택 해제
        state.selectedPromptIds.clear();
        renderPromptSelector();
        updateExecuteButton();

    } catch (error) {
        console.error('Error executing prompts:', error);
        showToast('오류', '프롬프트 실행에 실패했습니다', 'error');
    } finally {
        showLoading(false);
    }
}

// ========================================
// Render Sections (Drag & Drop)
// ========================================
function renderSections() {
    const container = document.getElementById('sections-list');
    container.innerHTML = '';

    // order 순으로 정렬
    state.sections.sort((a, b) => a.order - b.order);

    state.sections.forEach((section, index) => {
        const div = document.createElement('div');
        div.className = 'section-item';
        div.dataset.id = section.prompt_id;
        div.dataset.order = section.order;

        // Preview content (처음 200자)
        const preview = section.html_content.replace(/<[^>]*>/g, '').substring(0, 200);

        div.innerHTML = `
            <div class="drag-handle">☰</div>
            <div class="section-info">
                <h4>${index + 1}. ${section.title}</h4>
                <span class="category-badge">${section.category}</span>
                <div class="section-preview">${preview}...</div>
            </div>
            <button class="remove-btn" data-prompt-id="${section.prompt_id}">
                ✕
            </button>
        `;

        // Remove button event
        const removeBtn = div.querySelector('.remove-btn');
        removeBtn.addEventListener('click', () => removeSection(section.prompt_id));

        container.appendChild(div);
    });

    // SortableJS 초기화
    initDragDrop();
}

// ========================================
// Drag & Drop
// ========================================
function initDragDrop() {
    const container = document.getElementById('sections-list');

    if (window.sortableInstance) {
        window.sortableInstance.destroy();
    }

    window.sortableInstance = Sortable.create(container, {
        animation: 150,
        handle: '.drag-handle',
        ghostClass: 'sortable-ghost',
        onEnd: function(evt) {
            // 순서 업데이트
            const items = Array.from(container.children);
            items.forEach((item, index) => {
                const promptId = parseInt(item.dataset.id);
                const section = state.sections.find(s => s.prompt_id === promptId);
                if (section) {
                    section.order = index;
                }
            });

            console.log('순서 변경됨:', state.sections.map(s => s.title));
            renderSections();  // 번호 업데이트
        }
    });
}

// ========================================
// Remove Section
// ========================================
function removeSection(promptId) {
    state.sections = state.sections.filter(s => s.prompt_id !== promptId);
    renderSections();
    updateEmptyState();
}

// ========================================
// Preview Report
// ========================================
async function previewReport() {
    if (state.sections.length === 0) {
        showToast('알림', '실행된 프롬프트가 없습니다', 'info');
        return;
    }

    try {
        const title = document.getElementById('report-title').value || '월간보고';
        const includeToc = document.getElementById('include-toc').checked;

        const response = await fetch(`${API_BASE}/reports/generate-from-results`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({
                title: title,
                sections: state.sections,
                include_toc: includeToc,
                save: false  // 미리보기는 저장 안 함
            })
        });

        if (!response.ok) {
            throw new Error('미리보기 생성 실패');
        }

        const data = await response.json();
        state.previewHtml = data.html;

        // 모달에 표시
        const modal = document.getElementById('preview-modal');
        const iframe = document.getElementById('preview-iframe');
        iframe.srcdoc = data.html;
        modal.style.display = 'flex';

    } catch (error) {
        console.error('Error previewing report:', error);
        showToast('오류', '미리보기 생성에 실패했습니다', 'error');
    }
}

// ========================================
// Generate Final Report
// ========================================
async function generateReport() {
    if (state.sections.length === 0) {
        showToast('알림', '실행된 프롬프트가 없습니다', 'info');
        return;
    }

    if (!confirm('보고서를 생성하고 저장하시겠습니까?')) {
        return;
    }

    showLoading(true);

    try {
        const title = document.getElementById('report-title').value || '월간보고';
        const includeToc = document.getElementById('include-toc').checked;

        const response = await fetch(`${API_BASE}/reports/generate-from-results`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({
                title: title,
                sections: state.sections,
                include_toc: includeToc,
                save: true  // 저장
            })
        });

        if (!response.ok) {
            throw new Error('보고서 생성 실패');
        }

        const data = await response.json();

        showToast(
            '생성 완료',
            `보고서가 생성되었습니다 (ID: ${data.report_id})`,
            'success'
        );

        // 다운로드
        downloadReport(data.html, data.title);

    } catch (error) {
        console.error('Error generating report:', error);
        showToast('오류', '보고서 생성에 실패했습니다', 'error');
    } finally {
        showLoading(false);
    }
}

// ========================================
// Download Report
// ========================================
function downloadReport(html, title) {
    const blob = new Blob([html], { type: 'text/html; charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${title}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// ========================================
// Search Prompts
// ========================================
function setupSearch() {
    const searchInput = document.getElementById('prompt-search');
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        const items = document.querySelectorAll('.prompt-item');

        items.forEach(item => {
            const text = item.textContent.toLowerCase();
            if (text.includes(query)) {
                item.style.display = 'flex';
            } else {
                item.style.display = 'none';
            }
        });
    });
}

// ========================================
// Event Listeners
// ========================================
function setupEventListeners() {
    // Logout
    document.getElementById('logout-btn').addEventListener('click', logout);

    // Refresh prompts
    document.getElementById('refresh-prompts-btn').addEventListener('click', loadPrompts);

    // Execute prompts
    document.getElementById('execute-btn').addEventListener('click', executePrompts);

    // Preview
    document.getElementById('preview-btn').addEventListener('click', previewReport);

    // Generate
    document.getElementById('generate-btn').addEventListener('click', generateReport);

    // Download from preview
    document.getElementById('download-btn').addEventListener('click', () => {
        if (state.previewHtml) {
            const title = document.getElementById('report-title').value || '월간보고';
            downloadReport(state.previewHtml, title);
        }
    });

    // Modal close
    const modal = document.getElementById('preview-modal');
    const closeButtons = modal.querySelectorAll('.modal-close');
    closeButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            modal.style.display = 'none';
        });
    });

    // Modal backdrop click
    modal.querySelector('.modal-backdrop').addEventListener('click', () => {
        modal.style.display = 'none';
    });
}

// ========================================
// Initialization
// ========================================
async function init() {
    // Check authentication
    if (!checkAuth()) {
        return;
    }

    // Setup event listeners
    setupEventListeners();

    // Setup search
    setupSearch();

    // Load prompts
    await loadPrompts();

    // Update initial state
    updateEmptyState();
    updateExecuteButton();
}

// Start the app
document.addEventListener('DOMContentLoaded', init);
