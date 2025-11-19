// ============================================
// 월간 보고서 자동화 시스템 - 통합 대시보드
// ============================================

// 전역 변수
let editor;
let availablePrompts = [];
let currentTemplateId = null;
let currentPromptId = null;
let executionResults = {};
const API_BASE_URL = '/api/v2';

// ============================================
// 인증 관리
// ============================================

function getAuthToken() {
    return localStorage.getItem('auth_token');
}

function setAuthToken(token) {
    localStorage.setItem('auth_token', token);
}

function clearAuthToken() {
    localStorage.removeItem('auth_token');
}

function getUsername() {
    return localStorage.getItem('username');
}

function setUsername(username) {
    localStorage.setItem('username', username);
}

// API 호출 헬퍼
async function apiCall(endpoint, options = {}, requireAuth = true) {
    const token = getAuthToken();

    if (requireAuth && !token) {
        throw new Error('인증이 필요합니다');
    }

    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json'
        }
    };

    if (token) {
        defaultOptions.headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...(options.headers || {})
        }
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));

        if (response.status === 401) {
            clearAuthToken();
            showLoginModal();
            throw new Error('로그인이 필요합니다');
        }

        throw new Error(error.detail || `API Error: ${response.status}`);
    }

    return await response.json();
}

// 로그인
async function login(username, password) {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ username, password })
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || '로그인 실패');
    }

    const data = await response.json();
    setAuthToken(data.token);
    setUsername(data.username);

    return data;
}

// 로그아웃
function logout() {
    clearAuthToken();
    localStorage.removeItem('username');
    showLoginModal();
    showToast('로그아웃되었습니다', 'info');
}

// 로그인 모달
function showLoginModal() {
    document.getElementById('login-modal').classList.add('active');
    document.getElementById('login-username').focus();
}

function closeLoginModal() {
    document.getElementById('login-modal').classList.remove('active');
    document.getElementById('login-error').textContent = '';
}

// ============================================
// 네비게이션
// ============================================

function switchSection(sectionName) {
    // 모든 섹션 숨기기
    document.querySelectorAll('.content-section').forEach(section => {
        section.classList.remove('active');
    });

    // 선택한 섹션 표시
    document.getElementById(`section-${sectionName}`).classList.add('active');

    // 네비게이션 활성 상태 업데이트
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`[data-section="${sectionName}"]`).classList.add('active');

    // 섹션별 로직 실행
    if (sectionName === 'prompts') {
        loadPrompts();
    } else if (sectionName === 'templates') {
        loadPromptsForTemplate();
    } else if (sectionName === 'generate') {
        loadTemplatesForGenerate();
    } else if (sectionName === 'reports') {
        loadReports();
    }
}

// ============================================
// 프롬프트 관리
// ============================================

async function loadPrompts() {
    const includePublic = document.getElementById('show-public-prompts').checked;
    const category = document.getElementById('prompt-category-filter').value;

    try {
        let url = `/prompts?include_public=${includePublic}`;
        if (category) {
            url += `&category=${encodeURIComponent(category)}`;
        }

        const data = await apiCall(url);

        availablePrompts = [
            ...(data.my_prompts || []).map(p => ({ ...p, is_mine: true })),
            ...(data.public_prompts || []).map(p => ({ ...p, is_mine: false }))
        ];

        renderPrompts(availablePrompts);
        updateCategoryFilter(data.categories || []);
    } catch (error) {
        console.error('프롬프트 로드 실패:', error);
        showToast('프롬프트를 불러오는데 실패했습니다: ' + error.message, 'error');
    }
}

function renderPrompts(prompts) {
    const listElement = document.getElementById('prompts-list');

    if (prompts.length === 0) {
        listElement.innerHTML = '<div class="loading-message">프롬프트가 없습니다</div>';
        return;
    }

    listElement.innerHTML = prompts.map(p => `
        <div class="prompt-card">
            <div class="prompt-card-header">
                <div>
                    <span class="prompt-card-category">${p.category || '기타'}</span>
                    <div class="prompt-card-title">${p.title}</div>
                </div>
            </div>
            ${p.description ? `<p class="prompt-card-description">${p.description}</p>` : ''}
            ${!p.is_mine ? '<p class="text-muted" style="font-size:0.8rem;">🌐 공개 프롬프트</p>' : ''}
            <div class="prompt-card-actions">
                <button class="btn-primary btn-small" onclick="executePrompt(${p.id})">실행</button>
                ${p.is_mine ? `
                    <button class="btn-secondary btn-small" onclick="editPrompt(${p.id})">수정</button>
                    <button class="btn-danger btn-small" onclick="deletePrompt(${p.id})">삭제</button>
                ` : ''}
            </div>
        </div>
    `).join('');
}

function updateCategoryFilter(categories) {
    const filterElement = document.getElementById('prompt-category-filter');
    const currentValue = filterElement.value; // 현재 선택된 값 저장

    filterElement.innerHTML = '<option value="">모든 카테고리</option>' +
        categories.map(cat => `<option value="${cat}">${cat}</option>`).join('');

    // 이전 선택 값이 여전히 목록에 있으면 복원
    if (currentValue && categories.includes(currentValue)) {
        filterElement.value = currentValue;
    }
}

function filterPrompts() {
    const searchTerm = document.getElementById('prompt-search').value.toLowerCase();
    const category = document.getElementById('prompt-category-filter').value;

    const filtered = availablePrompts.filter(p => {
        const matchesSearch = !searchTerm ||
            p.title.toLowerCase().includes(searchTerm) ||
            (p.description || '').toLowerCase().includes(searchTerm);
        const matchesCategory = !category || p.category === category;

        return matchesSearch && matchesCategory;
    });

    renderPrompts(filtered);
}

function showPromptModal(promptId = null) {
    currentPromptId = promptId;

    if (promptId) {
        // 수정 모드
        const prompt = availablePrompts.find(p => p.id === promptId);
        if (!prompt) return;

        document.getElementById('prompt-modal-title').textContent = '프롬프트 수정';
        document.getElementById('prompt-title').value = prompt.title;
        document.getElementById('prompt-category').value = prompt.category || '기타';
        document.getElementById('prompt-description').value = prompt.description || '';
        document.getElementById('prompt-content').value = prompt.prompt_content;
        document.getElementById('prompt-is-public').checked = prompt.is_public;
        document.getElementById('prompt-order').value = prompt.order_index || 999;

        // JQL 필드를 Monaco 에디터에 로드 (별도 관리)
        if (window.jqlMonacoEditor && prompt.jql) {
            window.jqlMonacoEditor.setValue(prompt.jql);
        } else if (window.jqlMonacoEditor) {
            window.jqlMonacoEditor.setValue('');
        }
    } else {
        // 생성 모드
        document.getElementById('prompt-modal-title').textContent = '새 프롬프트';
        document.getElementById('prompt-form').reset();
        document.getElementById('prompt-order').value = 999;

        // JQL 에디터 초기화
        if (window.jqlMonacoEditor) {
            window.jqlMonacoEditor.setValue('');
        }
    }

    // JQL 목록 로드
    loadJQLsForPrompt();

    document.getElementById('prompt-modal').classList.add('active');
}

function closePromptModal() {
    document.getElementById('prompt-modal').classList.remove('active');
    currentPromptId = null;
}

async function savePrompt(event) {
    event.preventDefault();

    const promptData = {
        title: document.getElementById('prompt-title').value,
        category: document.getElementById('prompt-category').value,
        description: document.getElementById('prompt-description').value,
        prompt_content: document.getElementById('prompt-content').value,
        is_public: document.getElementById('prompt-is-public').checked,
        order_index: parseInt(document.getElementById('prompt-order').value)
    };

    // JQL 필드를 Monaco 에디터에서 가져오기 (별도 관리)
    if (window.jqlMonacoEditor) {
        const jqlValue = window.jqlMonacoEditor.getValue().trim();
        promptData.jql = jqlValue || null;
    }

    try {
        if (currentPromptId) {
            // 수정
            await apiCall(`/prompts/${currentPromptId}`, {
                method: 'PUT',
                body: JSON.stringify(promptData)
            });
            showToast('프롬프트가 수정되었습니다', 'success');
        } else {
            // 생성
            await apiCall('/prompts', {
                method: 'POST',
                body: JSON.stringify(promptData)
            });
            showToast('프롬프트가 생성되었습니다', 'success');
        }

        closePromptModal();
        loadPrompts();
    } catch (error) {
        showToast('저장 실패: ' + error.message, 'error');
    }
}

function editPrompt(promptId) {
    showPromptModal(promptId);
}

async function deletePrompt(promptId) {
    if (!confirm('정말로 이 프롬프트를 삭제하시겠습니까?')) {
        return;
    }

    try {
        await apiCall(`/prompts/${promptId}`, { method: 'DELETE' });
        showToast('프롬프트가 삭제되었습니다', 'success');
        loadPrompts();
    } catch (error) {
        showToast('삭제 실패: ' + error.message, 'error');
    }
}

async function executePrompt(promptId) {
    showToast('프롬프트 실행 중...', 'info');

    try {
        const result = await apiCall(`/prompts/${promptId}/execute`, {
            method: 'POST',
            body: JSON.stringify({ variables: {} })
        });

        // 결과를 새 창에서 표시
        const newWindow = window.open('', '_blank');
        newWindow.document.write(result.html_result);
        newWindow.document.close();

        showToast('프롬프트가 실행되었습니다', 'success');
    } catch (error) {
        showToast('실행 실패: ' + error.message, 'error');
    }
}

// ============================================
// JQL 선택 및 불러오기
// ============================================

/**
 * 저장된 JQL 목록 로드 (프롬프트 모달용)
 */
async function loadJQLsForPrompt() {
    try {
        const token = localStorage.getItem('auth_token');
        if (!token) return;

        const response = await fetch('/api/v2/jql?include_public=true', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            console.error('JQL 목록 로드 실패');
            return;
        }

        const data = await response.json();
        const select = document.getElementById('saved-jql-select');

        if (!select) return;

        // 기존 옵션 제거 (첫 번째 제외)
        while (select.options.length > 1) {
            select.remove(1);
        }

        // 내 JQL 추가
        if (data.my_jqls && data.my_jqls.length > 0) {
            const myGroup = document.createElement('optgroup');
            myGroup.label = '내 JQL';
            data.my_jqls.forEach(jql => {
                const option = document.createElement('option');
                option.value = jql.id;
                option.textContent = `${jql.name}${jql.system ? ` (${jql.system})` : ''}`;
                option.dataset.jqlContent = jql.jql || '';
                myGroup.appendChild(option);
            });
            select.appendChild(myGroup);
        }

        // 공개 JQL 추가
        if (data.public_jqls && data.public_jqls.length > 0) {
            const publicGroup = document.createElement('optgroup');
            publicGroup.label = '공개 JQL';
            data.public_jqls.forEach(jql => {
                const option = document.createElement('option');
                option.value = jql.id;
                option.textContent = `${jql.name}${jql.system ? ` (${jql.system})` : ''} - ${jql.owner || ''}`;
                option.dataset.jqlContent = jql.jql || '';
                publicGroup.appendChild(option);
            });
            select.appendChild(publicGroup);
        }

        console.log(`✅ JQL 목록 로드 완료: ${data.total}개`);

    } catch (error) {
        console.error('❌ JQL 목록 로드 실패:', error);
    }
}

/**
 * 선택된 JQL을 {{jql:id}} 형식으로 프롬프트에 삽입
 */
async function loadSelectedJQL() {
    const select = document.getElementById('saved-jql-select');
    const jqlId = select.value;

    if (!jqlId) {
        showToast('JQL을 선택해주세요.', 'warning');
        return;
    }

    try {
        const token = localStorage.getItem('auth_token');
        const response = await fetch(`/api/v2/jql/${jqlId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error('JQL 로드 실패');
        }

        const jql = await response.json();

        // 프롬프트 내용 텍스트에어리어에 {{jql:id}} 형식으로 삽입
        const promptContent = document.getElementById('prompt-content');
        if (promptContent) {
            const currentValue = promptContent.value;
            const placeholder = `{{jql:${jqlId}}}`;

            // 커서 위치에 삽입
            const cursorPos = promptContent.selectionStart;
            const newValue = currentValue.slice(0, cursorPos) + placeholder + currentValue.slice(cursorPos);
            promptContent.value = newValue;

            // 커서를 삽입된 텍스트 뒤로 이동
            promptContent.selectionStart = promptContent.selectionEnd = cursorPos + placeholder.length;
            promptContent.focus();
        }

        showToast(`JQL "${jql.name}" (ID: ${jqlId})을 삽입했습니다.`, 'success');

    } catch (error) {
        console.error('❌ JQL 불러오기 실패:', error);
        showToast('JQL을 불러오는데 실패했습니다.', 'error');
    }
}

// ============================================
// 템플릿 에디터
// ============================================

// Monaco Editor 초기화는 페이지 로드 시 한 번만
function initializeMonacoEditor() {
    require(['vs/editor/editor.main'], function() {
        editor = monaco.editor.create(document.getElementById('monaco-editor'), {
            value: '# 월간 보고서\n\n## 섹션 1\n{{prompt:',
            language: 'markdown',
            theme: 'vs-light',
            automaticLayout: true,
            minimap: { enabled: false },
            fontSize: 14,
            lineNumbers: 'on',
            wordWrap: 'on'
        });

        // 자동완성 등록
        registerAutocompletion();

        // 단축키
        editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, function() {
            saveTemplate();
        });
    });
}

function registerAutocompletion() {
    monaco.languages.registerCompletionItemProvider('markdown', {
        triggerCharacters: [':'],

        provideCompletionItems: function(model, position) {
            const textUntilPosition = model.getValueInRange({
                startLineNumber: position.lineNumber,
                startColumn: 1,
                endLineNumber: position.lineNumber,
                endColumn: position.column
            });

            const match = textUntilPosition.match(/\{\{prompt:(\w*)$/);

            if (!match) {
                return { suggestions: [] };
            }

            const typedText = match[1].toLowerCase();

            const suggestions = availablePrompts
                .filter(p => {
                    const promptIdStr = String(p.id);
                    const title = (p.title || '').toLowerCase();
                    return promptIdStr.includes(typedText) || title.includes(typedText);
                })
                .map(prompt => ({
                    label: String(prompt.id),
                    kind: monaco.languages.CompletionItemKind.Variable,
                    documentation: {
                        value: `**${prompt.title}**\n\n${prompt.description || '설명 없음'}`,
                        isTrusted: true
                    },
                    insertText: prompt.id + '}}',
                    detail: prompt.title,
                    sortText: String(prompt.id).padStart(10, '0'),
                    range: {
                        startLineNumber: position.lineNumber,
                        startColumn: position.column - typedText.length,
                        endLineNumber: position.lineNumber,
                        endColumn: position.column
                    }
                }));

            return { suggestions };
        }
    });
}

async function loadPromptsForTemplate() {
    if (availablePrompts.length === 0) {
        try {
            const data = await apiCall('/prompts?include_public=true');
            availablePrompts = [
                ...(data.my_prompts || []).map(p => ({ ...p, is_mine: true })),
                ...(data.public_prompts || []).map(p => ({ ...p, is_mine: false }))
            ];

            // 카테고리 필터 업데이트
            updateTemplateCategoryFilter(data.categories || []);
        } catch (error) {
            console.error('프롬프트 로드 실패:', error);
        }
    }

    renderPromptsForTemplate(availablePrompts);
}

function updateTemplateCategoryFilter(categories) {
    const filterElement = document.getElementById('template-category-filter');
    const currentValue = filterElement.value;

    filterElement.innerHTML = '<option value="">모든 카테고리</option>' +
        categories.map(cat => `<option value="${cat}">${cat}</option>`).join('');

    // 이전 선택 값이 여전히 목록에 있으면 복원
    if (currentValue && categories.includes(currentValue)) {
        filterElement.value = currentValue;
    }
}

function renderPromptsForTemplate(prompts) {
    const listElement = document.getElementById('template-prompts-list');

    if (prompts.length === 0) {
        listElement.innerHTML = '<div style="padding: 10px; text-align: center; color: #999;">검색 결과가 없습니다</div>';
        return;
    }

    listElement.innerHTML = prompts.map(p => `
        <div class="prompt-item-small" onclick="insertPromptToEditor(${p.id})">
            <span class="prompt-category-badge" style="font-size: 0.7em; padding: 2px 6px; background: #e3f2fd; border-radius: 3px; color: #1976d2;">${p.category || '기타'}</span>
            <strong style="display: block; margin-top: 4px;">${p.title}</strong>
            <small style="color: #999;">ID: ${p.id} | {{prompt:${p.id}}}</small>
        </div>
    `).join('');
}

function filterPromptsForTemplate() {
    const searchTerm = document.getElementById('template-prompt-search').value.toLowerCase();
    const category = document.getElementById('template-category-filter').value;

    const filtered = availablePrompts.filter(p => {
        // 카테고리 필터
        const matchesCategory = !category || p.category === category;

        // 검색어 필터
        let matchesSearch = true;
        if (searchTerm) {
            // 제목으로 검색
            const matchesTitle = p.title.toLowerCase().includes(searchTerm);

            // 카테고리로 검색
            const matchesCategorySearch = (p.category || '기타').toLowerCase().includes(searchTerm);

            // ID로 검색 (숫자 입력 시)
            const matchesId = p.id.toString().includes(searchTerm);

            // 설명으로 검색
            const matchesDescription = (p.description || '').toLowerCase().includes(searchTerm);

            matchesSearch = matchesTitle || matchesCategorySearch || matchesId || matchesDescription;
        }

        return matchesCategory && matchesSearch;
    });

    renderPromptsForTemplate(filtered);
}

function insertPromptToEditor(promptId) {
    if (!editor) return;

    const position = editor.getPosition();
    editor.executeEdits('', [{
        range: new monaco.Range(
            position.lineNumber,
            position.column,
            position.lineNumber,
            position.column
        ),
        text: `{{prompt:${promptId}}}`
    }]);

    editor.focus();
}

async function saveTemplate() {
    const title = document.getElementById('template-title').value.trim();
    const description = document.getElementById('template-description').value.trim();
    const content = editor.getValue();

    if (!title) {
        showToast('템플릿 이름을 입력해주세요', 'warning');
        return;
    }

    try {
        if (currentTemplateId) {
            await apiCall(`/templates/${currentTemplateId}`, {
                method: 'PUT',
                body: JSON.stringify({ title, description, template_content: content })
            });
            showToast('템플릿이 수정되었습니다', 'success');
        } else {
            const result = await apiCall('/templates', {
                method: 'POST',
                body: JSON.stringify({ title, description, template_content: content })
            });
            currentTemplateId = result.id;
            showToast('템플릿이 저장되었습니다', 'success');
        }
    } catch (error) {
        showToast('저장 실패: ' + error.message, 'error');
    }
}

async function loadTemplatesModal() {
    try {
        const data = await apiCall('/templates');
        const templates = data.templates || [];

        const listElement = document.getElementById('templates-list-modal');

        if (templates.length === 0) {
            listElement.innerHTML = '<p class="text-muted">저장된 템플릿이 없습니다</p>';
        } else {
            listElement.innerHTML = templates.map(t => `
                <div class="prompt-card" onclick="loadTemplate(${t.id})">
                    <div class="prompt-card-title">${t.title}</div>
                    ${t.description ? `<p class="prompt-card-description">${t.description}</p>` : ''}
                    <small class="text-muted">수정일: ${new Date(t.updated_at).toLocaleDateString('ko-KR')}</small>
                </div>
            `).join('');
        }

        document.getElementById('templates-modal').classList.add('active');
    } catch (error) {
        showToast('템플릿 목록 로드 실패: ' + error.message, 'error');
    }
}

async function loadTemplate(templateId) {
    try {
        const data = await apiCall(`/templates/${templateId}`);
        const template = data.template;

        document.getElementById('template-title').value = template.title;
        document.getElementById('template-description').value = template.description || '';
        editor.setValue(template.template_content);
        currentTemplateId = template.id;

        closeTemplatesModal();
        showToast('템플릿을 불러왔습니다', 'success');
    } catch (error) {
        showToast('템플릿 로드 실패: ' + error.message, 'error');
    }
}

function closeTemplatesModal() {
    document.getElementById('templates-modal').classList.remove('active');
}

// ============================================
// 보고서 생성
// ============================================

async function loadTemplatesForGenerate() {
    try {
        const data = await apiCall('/templates');
        const templates = data.templates || [];

        const selectElement = document.getElementById('select-template');
        selectElement.innerHTML = '<option value="">템플릿 선택...</option>' +
            templates.map(t => `<option value="${t.id}">${t.title}</option>`).join('');
    } catch (error) {
        console.error('템플릿 로드 실패:', error);
    }
}

async function onTemplateSelected(templateId) {
    if (!templateId) {
        document.getElementById('template-preview').innerHTML = '';
        document.getElementById('prompts-to-execute').innerHTML = '<p class="text-muted">템플릿을 선택하세요</p>';
        document.getElementById('generate-report-btn').disabled = true;
        return;
    }

    try {
        const data = await apiCall(`/templates/${templateId}`);
        const template = data.template;

        // 미리보기
        document.getElementById('template-preview').textContent = template.template_content;

        // 프롬프트 ID 추출
        const promptIds = extractPromptIds(template.template_content);

        if (promptIds.length === 0) {
            document.getElementById('prompts-to-execute').innerHTML = '<p class="text-muted">이 템플릿에는 프롬프트가 없습니다</p>';
            document.getElementById('generate-report-btn').disabled = true;
            return;
        }

        // 프롬프트 정보 표시
        await renderPromptsInfoOnly(promptIds);
        // 템플릿 선택 시 바로 보고서 생성 버튼 활성화
        document.getElementById('generate-report-btn').disabled = false;
    } catch (error) {
        showToast('템플릿 로드 실패: ' + error.message, 'error');
    }
}

function extractPromptIds(templateContent) {
    const regex = /\{\{prompt:(\d+)\}\}/g;
    const matches = [...templateContent.matchAll(regex)];
    return [...new Set(matches.map(m => parseInt(m[1])))];
}

async function renderPromptsInfoOnly(promptIds) {
    const listElement = document.getElementById('prompts-to-execute');

    // 프롬프트 정보 가져오기
    const prompts = availablePrompts.filter(p => promptIds.includes(p.id));

    if (prompts.length === 0) {
        listElement.innerHTML = '<p class="text-muted">프롬프트 정보를 불러올 수 없습니다</p>';
        return;
    }

    listElement.innerHTML = `
        <div class="prompts-info-list">
            <p><strong>실행될 프롬프트 (${prompts.length}개):</strong></p>
            <ul style="margin: 0.5rem 0; padding-left: 1.5rem;">
                ${prompts.map(p => `<li>${p.title}${p.description ? ` - ${p.description}` : ''}</li>`).join('')}
            </ul>
        </div>
    `;
}

// 실행 로그 관련 함수
function showExecutionLog() {
    const logArea = document.getElementById('execution-log');
    logArea.style.display = 'block';
    const logContent = document.getElementById('log-content');
    logContent.innerHTML = '';
}

function addLogMessage(message, type = 'info') {
    const logContent = document.getElementById('log-content');
    const timestamp = new Date().toLocaleTimeString('ko-KR');
    const icon = {
        'info': '📋',
        'success': '✅',
        'error': '❌',
        'warning': '⚠️'
    }[type] || '📋';

    const logEntry = document.createElement('div');
    logEntry.className = `log-entry log-${type}`;
    logEntry.innerHTML = `<span class="log-time">${timestamp}</span> ${icon} ${message}`;
    logContent.appendChild(logEntry);

    // 자동 스크롤
    logContent.scrollTop = logContent.scrollHeight;
}

function clearExecutionLog() {
    const logContent = document.getElementById('log-content');
    logContent.innerHTML = '';
    document.getElementById('execution-log').style.display = 'none';
}

async function generateFinalReport() {
    const templateId = document.getElementById('select-template').value;
    const reportTitle = document.getElementById('report-title').value.trim();

    if (!templateId) {
        showToast('템플릿을 선택해주세요', 'warning');
        return;
    }

    if (!reportTitle) {
        showToast('보고서 제목을 입력해주세요', 'warning');
        return;
    }

    // 실행 로그 표시
    showExecutionLog();
    addLogMessage('보고서 생성 시작', 'info');
    addLogMessage(`템플릿 ID: ${templateId}, 제목: ${reportTitle}`, 'info');

    // 버튼 비활성화
    const generateBtn = document.getElementById('generate-report-btn');
    generateBtn.disabled = true;
    const originalText = generateBtn.innerHTML;
    generateBtn.innerHTML = '<span class="btn-icon">⏳</span> 생성 중...';

    try {
        addLogMessage('템플릿 정보 로드 중...', 'info');

        // 템플릿 정보 가져오기
        const templateData = await apiCall(`/templates/${templateId}`);
        const promptIds = extractPromptIds(templateData.template.template_content);
        addLogMessage(`${promptIds.length}개의 프롬프트를 실행합니다`, 'info');

        addLogMessage('프롬프트 자동 실행 중... (백엔드에서 처리)', 'info');

        // 템플릿 기반 보고서 생성 API 호출 (백엔드에서 프롬프트 자동 실행)
        const result = await apiCall('/reports/generate-from-template', {
            method: 'POST',
            body: JSON.stringify({
                template_id: parseInt(templateId),
                title: reportTitle,
                save: true
            })
        });

        addLogMessage('모든 프롬프트 실행 완료', 'success');

        // 경고 메시지 표시 (있는 경우)
        if (result.warnings && result.warnings.length > 0) {
            console.warn('보고서 생성 경고:', result.warnings);
            result.warnings.forEach(warning => {
                addLogMessage(warning, 'warning');
                showToast('⚠️ ' + warning, 'warning');
            });
        }

        addLogMessage('보고서 생성 완료!', 'success');
        showToast('보고서가 생성되었습니다!', 'success');

        // 미리보기 표시
        showReportPreview(result.html, reportTitle);

        // 결과 초기화
        document.getElementById('report-title').value = '';
        generateBtn.disabled = false;
        generateBtn.innerHTML = originalText;

        // 보고서 목록 새로고침
        if (window.currentSection === 'reports') {
            loadReports();
        }
    } catch (error) {
        console.error('보고서 생성 실패:', error);
        addLogMessage(`오류 발생: ${error.message}`, 'error');
        showToast('보고서 생성 실패: ' + error.message, 'error');

        // 버튼 복원
        generateBtn.disabled = false;
        generateBtn.innerHTML = originalText;
    }
}

function showReportPreview(html, title) {
    document.getElementById('report-preview-title').textContent = title;
    const iframe = document.getElementById('report-preview-iframe');
    iframe.srcdoc = html;

    document.getElementById('report-preview-modal').classList.add('active');
}

function closeReportPreview() {
    document.getElementById('report-preview-modal').classList.remove('active');
}

function exportHTML() {
    const iframe = document.getElementById('report-preview-iframe');
    const html = iframe.srcdoc;
    const title = document.getElementById('report-preview-title').textContent;

    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${title}.html`;
    a.click();
    URL.revokeObjectURL(url);

    showToast('HTML 파일이 다운로드되었습니다', 'success');
}

// ============================================
// 보고서 목록
// ============================================

async function loadReports() {
    try {
        const data = await apiCall('/reports');
        const reports = data.reports || [];

        const listElement = document.getElementById('reports-list');

        if (reports.length === 0) {
            listElement.innerHTML = '<div class="loading-message">저장된 보고서가 없습니다</div>';
        } else {
            listElement.innerHTML = reports.map(r => `
                <div class="report-item">
                    <div class="report-item-header">
                        <div class="report-item-title">${r.title}</div>
                        <div class="report-item-actions">
                            <button class="btn-primary btn-small" onclick="viewReport(${r.id})">보기</button>
                            <button class="btn-secondary btn-small" onclick="editReport(${r.id}, '${r.title}')">수정</button>
                            <button class="btn-danger btn-small" onclick="deleteReport(${r.id})">삭제</button>
                        </div>
                    </div>
                    <div class="report-item-meta">
                        생성일: ${new Date(r.created_at).toLocaleString('ko-KR')} |
                        프롬프트: ${r.prompt_count}개
                    </div>
                </div>
            `).join('');
        }
    } catch (error) {
        showToast('보고서 목록 로드 실패: ' + error.message, 'error');
    }
}

async function viewReport(reportId) {
    try {
        const data = await apiCall(`/reports/${reportId}`);
        showReportPreview(data.html_content, data.title);
    } catch (error) {
        showToast('보고서 로드 실패: ' + error.message, 'error');
    }
}

async function deleteReport(reportId) {
    if (!confirm('정말로 이 보고서를 삭제하시겠습니까?')) {
        return;
    }

    try {
        await apiCall(`/reports/${reportId}`, { method: 'DELETE' });
        showToast('보고서가 삭제되었습니다', 'success');
        loadReports();
    } catch (error) {
        showToast('삭제 실패: ' + error.message, 'error');
    }
}

async function editReport(reportId, reportTitle) {
    try {
        showToast('보고서를 에디터로 불러오는 중...', 'info');

        // 1. 보고서 내용 가져오기
        const data = await apiCall(`/reports/${reportId}`);
        const htmlContent = data.html_content;

        // 2. 파일명 생성 (안전한 파일명으로 변환)
        const safeTitle = reportTitle.replace(/[^a-zA-Z0-9가-힣_-]/g, '_');
        const timestamp = new Date().toISOString().slice(0, 10).replace(/-/g, '');
        const filename = `${safeTitle}_${timestamp}_${reportId}`;

        // 3. HTML 파일로 저장
        let savedFilename = filename + '.html';
        const saveResponse = await fetch('/api/editor/reports/save-as', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: filename,
                content: htmlContent
            })
        });

        if (saveResponse.ok) {
            const result = await saveResponse.json();
            savedFilename = result.filename;
        } else if (saveResponse.status === 409) {
            // 이미 존재하는 파일이면 덮어쓰기
            const updateResponse = await fetch(`/api/editor/reports/${savedFilename}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: htmlContent })
            });

            if (!updateResponse.ok) {
                throw new Error('파일 업데이트 실패');
            }
        } else {
            throw new Error('파일 저장 실패');
        }

        // 4. 에디터 페이지로 이동 (파일명을 URL 파라미터로 전달)
        window.location.href = `/report-editor?file=${encodeURIComponent(savedFilename)}`;

    } catch (error) {
        console.error('보고서 편집 실패:', error);
        showToast('보고서를 에디터로 불러오는데 실패했습니다: ' + error.message, 'error');
    }
}

// ============================================
// 유틸리티
// ============================================

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// ============================================
// 초기화 및 이벤트 리스너
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    // 인증 확인
    const token = getAuthToken();
    const username = getUsername();

    if (!token) {
        showLoginModal();
    } else {
        document.getElementById('username-display').textContent = username || '사용자';
        // Monaco Editor 초기화
        require.config({
            paths: {
                'vs': 'https://cdn.jsdelivr.net/npm/monaco-editor@latest/min/vs'
            }
        });
        initializeMonacoEditor();

        // 첫 섹션 로드
        loadPrompts();
    }

    // 로그인 폼
    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();

        const username = document.getElementById('login-username').value;
        const password = document.getElementById('login-password').value;
        const errorDiv = document.getElementById('login-error');

        try {
            errorDiv.textContent = '';
            const data = await login(username, password);

            showToast('로그인 성공!', 'success');
            closeLoginModal();

            document.getElementById('username-display').textContent = data.username;

            // Monaco Editor 초기화
            require.config({
                paths: {
                    'vs': 'https://cdn.jsdelivr.net/npm/monaco-editor@latest/min/vs'
                }
            });
            initializeMonacoEditor();

            // 데이터 로드
            loadPrompts();
        } catch (error) {
            errorDiv.textContent = error.message;
        }
    });

    // 로그아웃
    document.getElementById('logout-btn').addEventListener('click', logout);

    // 네비게이션
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const section = item.dataset.section;
            switchSection(section);
        });
    });

    // 프롬프트 관리
    document.getElementById('create-prompt-btn').addEventListener('click', () => showPromptModal());
    document.getElementById('prompt-form').addEventListener('submit', savePrompt);
    document.getElementById('prompt-search').addEventListener('input', filterPrompts);
    document.getElementById('prompt-category-filter').addEventListener('change', loadPrompts);
    document.getElementById('show-public-prompts').addEventListener('change', loadPrompts);

    // 템플릿 에디터
    document.getElementById('save-template-btn').addEventListener('click', saveTemplate);
    document.getElementById('load-template-btn').addEventListener('click', loadTemplatesModal);
    document.getElementById('template-prompt-search').addEventListener('input', filterPromptsForTemplate);
    document.getElementById('template-category-filter').addEventListener('change', filterPromptsForTemplate);

    // 보고서 생성
    document.getElementById('select-template').addEventListener('change', (e) => onTemplateSelected(e.target.value));
    document.getElementById('generate-report-btn').addEventListener('click', generateFinalReport);

    // 보고서 목록
    document.getElementById('refresh-reports-btn').addEventListener('click', loadReports);

    // 모달 외부 클릭 시 닫기
    document.getElementById('prompt-modal').addEventListener('click', (e) => {
        if (e.target.id === 'prompt-modal') closePromptModal();
    });

    // Export
    document.getElementById('export-html-btn').addEventListener('click', exportHTML);
});
