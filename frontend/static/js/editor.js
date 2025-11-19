// Monaco Editor 설정
require.config({
    paths: {
        'vs': 'https://cdn.jsdelivr.net/npm/monaco-editor@latest/min/vs'
    }
});

// 전역 변수
let editor;
let availablePrompts = [];
let currentTemplateId = null;
const API_BASE_URL = '/api/v2';

// 인증 토큰 관리
function getAuthToken() {
    return localStorage.getItem('auth_token');
}

function setAuthToken(token) {
    localStorage.setItem('auth_token', token);
}

function clearAuthToken() {
    localStorage.removeItem('auth_token');
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

        // 401 에러면 로그인 필요
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
    try {
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

        return data;
    } catch (error) {
        throw error;
    }
}

// 로그인 모달 표시
function showLoginModal() {
    const modal = document.getElementById('login-modal');
    modal.classList.add('active');
    document.getElementById('login-username').focus();
}

// 로그인 모달 닫기
function closeLoginModal() {
    const modal = document.getElementById('login-modal');
    modal.classList.remove('active');
    document.getElementById('login-error').style.display = 'none';
}

// Monaco Editor 로드 및 초기화
require(['vs/editor/editor.main'], function() {
    initializeApp();
});

// 앱 초기화
async function initializeApp() {
    // 토큰 확인
    const token = getAuthToken();

    if (!token) {
        // 토큰 없으면 로그인 모달 표시
        showLoginModal();
        // 에디터는 초기화 (편집은 가능하지만 저장은 불가)
        initializeEditor();
        updatePromptList([]);
        return;
    }

    // 프롬프트 목록 가져오기
    try {
        const prompts = await fetchPrompts();
        availablePrompts = prompts;
        updatePromptList(prompts);
        initializeEditor();

        if (prompts.length === 0) {
            showToast('사용 가능한 프롬프트가 없습니다', 'warning');
        }
    } catch (error) {
        console.error('프롬프트 로드 실패:', error);

        // 인증 에러가 아니면 토스트 표시
        if (!error.message.includes('로그인')) {
            showToast('프롬프트를 불러오는데 실패했습니다: ' + error.message, 'error');
        }

        // 에디터는 초기화
        initializeEditor();
        updatePromptList([]);
    }
}

// 프롬프트 목록 가져오기
async function fetchPrompts() {
    try {
        const data = await apiCall('/prompts?include_public=true');

        // my_prompts와 public_prompts를 합침
        const allPrompts = [
            ...(data.my_prompts || []).map(p => ({ ...p, is_mine: true })),
            ...(data.public_prompts || []).map(p => ({ ...p, is_mine: false }))
        ];

        return allPrompts;
    } catch (error) {
        console.error('프롬프트 로드 에러:', error);
        return [];
    }
}

// 프롬프트 리스트 UI 업데이트
function updatePromptList(prompts) {
    const listElement = document.getElementById('prompt-list');

    if (prompts.length === 0) {
        const token = getAuthToken();
        if (!token) {
            listElement.innerHTML = `
                <div class="loading">
                    <p style="color: #7f8c8d; text-align: center; padding: 1rem;">
                        로그인 후 프롬프트를 사용할 수 있습니다
                    </p>
                </div>
            `;
        } else {
            listElement.innerHTML = `
                <div class="loading">
                    <p style="color: #7f8c8d; text-align: center; padding: 1rem;">
                        사용 가능한 프롬프트가 없습니다
                    </p>
                </div>
            `;
        }
        return;
    }

    listElement.innerHTML = prompts.map(p => `
        <div class="prompt-item" data-id="${p.id}" data-title="${(p.title || '').toLowerCase()}">
            <span class="prompt-category">${p.category || '기타'}</span>
            <strong>${p.title}</strong>
            <span class="prompt-id">{{prompt:${p.id}}}</span>
            ${p.description ? `<p>${p.description}</p>` : ''}
            ${!p.is_mine ? '<p style="color: #3498db; font-size: 0.75rem;">🌐 공개 프롬프트</p>' : ''}
        </div>
    `).join('');

    // 클릭 시 에디터에 삽입
    document.querySelectorAll('.prompt-item').forEach(item => {
        item.addEventListener('click', () => {
            const promptId = item.dataset.id;
            insertPromptPlaceholder(promptId);
        });
    });
}

// 프롬프트 placeholder 삽입
function insertPromptPlaceholder(promptId) {
    if (!editor) return;

    const position = editor.getPosition();
    const range = new monaco.Range(
        position.lineNumber,
        position.column,
        position.lineNumber,
        position.column
    );

    editor.executeEdits('', [{
        range: range,
        text: `{{prompt:${promptId}}}`
    }]);

    editor.focus();
}

// 에디터 초기화
function initializeEditor() {
    // 2. Monaco Editor 생성
    editor = monaco.editor.create(document.getElementById('editor'), {
        value: '# 월간 보고서\n\n## 개요\n여기에 보고서 내용을 작성하세요.\n\n## 주요 내용\n{{prompt:',
        language: 'markdown',
        theme: 'vs-light',
        automaticLayout: true,
        minimap: { enabled: false },
        fontSize: 14,
        lineNumbers: 'on',
        wordWrap: 'on',
        suggestOnTriggerCharacters: true,
        quickSuggestions: {
            other: true,
            comments: false,
            strings: true
        }
    });

    // 3. 자동완성 프로바이더 등록
    monaco.languages.registerCompletionItemProvider('markdown', {
        triggerCharacters: [':'],

        provideCompletionItems: function(model, position) {
            const textUntilPosition = model.getValueInRange({
                startLineNumber: position.lineNumber,
                startColumn: 1,
                endLineNumber: position.lineNumber,
                endColumn: position.column
            });

            // {{prompt: 패턴 체크
            const match = textUntilPosition.match(/\{\{prompt:(\w*)$/);

            if (!match) {
                return { suggestions: [] };
            }

            const typedText = match[1].toLowerCase(); // 이미 입력된 텍스트

            // 4. 필터링된 제안 생성
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
                        value: `**${prompt.title}**\n\n${prompt.description || '설명 없음'}\n\n카테고리: ${prompt.category || '기타'}`,
                        isTrusted: true
                    },
                    insertText: prompt.id + '}}',
                    detail: prompt.title,
                    sortText: String(prompt.id).padStart(10, '0'), // 정렬 순서
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

    // 5. 단축키 등록
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, function() {
        saveTemplate();
    });

    // 에디터 내용 변경 시 유효성 상태 초기화
    editor.onDidChangeModelContent(() => {
        const statusBadge = document.getElementById('validation-status');
        statusBadge.textContent = '';
        statusBadge.className = 'status-badge';
    });
}

// 프롬프트 검색
document.getElementById('prompt-search')?.addEventListener('input', (e) => {
    const searchTerm = e.target.value.toLowerCase();
    const promptItems = document.querySelectorAll('.prompt-item');

    promptItems.forEach(item => {
        const title = item.dataset.title || '';
        const text = item.textContent.toLowerCase();

        if (title.includes(searchTerm) || text.includes(searchTerm)) {
            item.classList.remove('hidden');
        } else {
            item.classList.add('hidden');
        }
    });
});

// 템플릿 저장
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
            // 업데이트
            await apiCall(`/templates/${currentTemplateId}`, {
                method: 'PUT',
                body: JSON.stringify({
                    title,
                    description: description || null,
                    template_content: content
                })
            });
            showToast('템플릿이 수정되었습니다!', 'success');
        } else {
            // 새로 생성
            const result = await apiCall('/templates', {
                method: 'POST',
                body: JSON.stringify({
                    title,
                    description: description || null,
                    template_content: content
                })
            });
            currentTemplateId = result.id;
            showToast('템플릿이 저장되었습니다!', 'success');

            // 유효성 검사 결과 표시
            if (result.validation) {
                displayValidation(result.validation);
            }
        }
    } catch (error) {
        showToast('저장 실패: ' + error.message, 'error');
    }
}

// 템플릿 불러오기 (목록 표시)
async function loadTemplates() {
    try {
        const data = await apiCall('/templates');
        const templates = data.templates || [];

        const modal = document.getElementById('templates-modal');
        const listElement = document.getElementById('templates-list');

        if (templates.length === 0) {
            listElement.innerHTML = '<p style="text-align: center; color: #7f8c8d;">저장된 템플릿이 없습니다</p>';
        } else {
            listElement.innerHTML = templates.map(t => `
                <div class="template-item" data-id="${t.id}">
                    <div class="template-item-header">
                        <h3>${t.title}</h3>
                        <div class="template-item-actions">
                            <button class="btn-primary btn-load" data-id="${t.id}">불러오기</button>
                            <button class="btn-danger btn-delete" data-id="${t.id}">삭제</button>
                        </div>
                    </div>
                    ${t.description ? `<p>${t.description}</p>` : ''}
                    <div class="template-item-meta">
                        수정일: ${new Date(t.updated_at).toLocaleDateString('ko-KR')}
                    </div>
                </div>
            `).join('');

            // 이벤트 리스너 추가
            listElement.querySelectorAll('.btn-load').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    loadTemplate(parseInt(btn.dataset.id));
                });
            });

            listElement.querySelectorAll('.btn-delete').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    deleteTemplate(parseInt(btn.dataset.id));
                });
            });
        }

        modal.classList.add('active');
    } catch (error) {
        showToast('템플릿 목록 로드 실패: ' + error.message, 'error');
    }
}

// 특정 템플릿 불러오기
async function loadTemplate(templateId) {
    try {
        const data = await apiCall(`/templates/${templateId}`);
        const template = data.template;

        document.getElementById('template-title').value = template.title;
        document.getElementById('template-description').value = template.description || '';
        editor.setValue(template.template_content);
        currentTemplateId = template.id;

        closeModal();
        showToast('템플릿을 불러왔습니다', 'success');
    } catch (error) {
        showToast('템플릿 로드 실패: ' + error.message, 'error');
    }
}

// 템플릿 삭제
async function deleteTemplate(templateId) {
    if (!confirm('정말로 이 템플릿을 삭제하시겠습니까?')) {
        return;
    }

    try {
        await apiCall(`/templates/${templateId}`, {
            method: 'DELETE'
        });
        showToast('템플릿이 삭제되었습니다', 'success');

        // 현재 편집 중인 템플릿이면 초기화
        if (currentTemplateId === templateId) {
            newTemplate();
        }

        // 목록 새로고침
        loadTemplates();
    } catch (error) {
        showToast('삭제 실패: ' + error.message, 'error');
    }
}

// 새 템플릿
function newTemplate() {
    document.getElementById('template-title').value = '새 템플릿';
    document.getElementById('template-description').value = '';
    editor.setValue('# 보고서 제목\n\n## 섹션 1\n{{prompt:');
    currentTemplateId = null;

    const statusBadge = document.getElementById('validation-status');
    statusBadge.textContent = '';
    statusBadge.className = 'status-badge';
}

// 유효성 검사
async function validateTemplate() {
    const content = editor.getValue();

    try {
        const data = await apiCall('/templates', {
            method: 'POST',
            body: JSON.stringify({
                title: 'validation-temp',
                template_content: content
            })
        });

        if (data.validation) {
            displayValidation(data.validation);
        }

        // 임시로 생성된 템플릿 삭제
        if (data.id && !currentTemplateId) {
            await apiCall(`/templates/${data.id}`, { method: 'DELETE' });
        }
    } catch (error) {
        showToast('유효성 검사 실패: ' + error.message, 'error');
    }
}

// 유효성 검사 결과 표시
function displayValidation(validation) {
    const statusBadge = document.getElementById('validation-status');

    if (validation.valid) {
        statusBadge.textContent = '✓ 유효함';
        statusBadge.className = 'status-badge valid';
        if (validation.warnings.length > 0) {
            showToast('경고: ' + validation.warnings.join(', '), 'warning');
        }
    } else {
        statusBadge.textContent = '✗ 오류 있음';
        statusBadge.className = 'status-badge invalid';
        showToast('오류: ' + validation.errors.join(', '), 'error');
    }
}

// 모달 닫기
function closeModal() {
    document.getElementById('templates-modal').classList.remove('active');
}

// 토스트 알림 표시
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// 이벤트 리스너
document.getElementById('save-btn')?.addEventListener('click', saveTemplate);
document.getElementById('load-btn')?.addEventListener('click', loadTemplates);
document.getElementById('new-btn')?.addEventListener('click', newTemplate);
document.getElementById('validate-btn')?.addEventListener('click', validateTemplate);

// 모달 닫기 버튼
document.querySelector('.close-btn')?.addEventListener('click', closeModal);
document.getElementById('templates-modal')?.addEventListener('click', (e) => {
    if (e.target.id === 'templates-modal') {
        closeModal();
    }
});

// 로그인 폼 이벤트
document.getElementById('login-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();

    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    const errorDiv = document.getElementById('login-error');

    try {
        errorDiv.style.display = 'none';

        // 로그인 시도
        const data = await login(username, password);

        // 성공
        showToast('로그인 성공!', 'success');
        closeLoginModal();

        // 프롬프트 다시 로드
        const prompts = await fetchPrompts();
        availablePrompts = prompts;
        updatePromptList(prompts);

        if (prompts.length === 0) {
            showToast('사용 가능한 프롬프트가 없습니다', 'warning');
        }

    } catch (error) {
        console.error('로그인 실패:', error);
        errorDiv.textContent = error.message;
        errorDiv.style.display = 'block';
    }
});
