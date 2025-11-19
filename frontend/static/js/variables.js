/**
 * Variables Management
 * 전역 변수 관리 기능
 */

let currentVariables = [];
let editingVariable = null;

// 초기화
document.addEventListener('DOMContentLoaded', () => {
    // 변수 관리 섹션이 활성화되면 변수 목록 로드
    const originalSwitchSection = window.switchSection;
    window.switchSection = function(sectionName) {
        originalSwitchSection(sectionName);
        if (sectionName === 'variables') {
            loadVariables();
        }
    };

    // 이벤트 리스너 등록
    setupVariableEventListeners();
});

// 이벤트 리스너 설정
function setupVariableEventListeners() {
    // 새 변수 버튼
    const createBtn = document.getElementById('create-variable-btn');
    if (createBtn) {
        createBtn.addEventListener('click', openVariableModal);
    }

    // 변수 폼 제출
    const variableForm = document.getElementById('variable-form');
    if (variableForm) {
        variableForm.addEventListener('submit', handleVariableSubmit);
    }

    // 변수명 입력 시 실시간 검증
    const variableNameInput = document.getElementById('variable-name');
    if (variableNameInput) {
        variableNameInput.addEventListener('input', validateVariableName);
    }
}

// 변수 목록 로드
async function loadVariables() {
    const tbody = document.getElementById('variables-tbody');

    try {
        const response = await fetch('/api/v2/variables', {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });

        if (!response.ok) {
            throw new Error('변수 목록을 불러올 수 없습니다');
        }

        currentVariables = await response.json();
        renderVariablesTable(currentVariables);

    } catch (error) {
        console.error('변수 로드 실패:', error);
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="error-message">변수 목록을 불러오는데 실패했습니다</td>
            </tr>
        `;
    }
}

// 변수 테이블 렌더링
function renderVariablesTable(variables) {
    const tbody = document.getElementById('variables-tbody');

    if (!variables || variables.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="text-muted" style="text-align: center; padding: 40px;">
                    등록된 변수가 없습니다. '+ 새 변수' 버튼을 눌러 추가하세요.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = variables.map(variable => `
        <tr>
            <td><code>{{${variable.name}}}</code></td>
            <td>${escapeHtml(variable.value)}</td>
            <td>${variable.description || '<span class="text-muted">-</span>'}</td>
            <td>${formatDate(variable.updated_at)}</td>
            <td class="table-actions">
                <button class="btn-small btn-icon" onclick="editVariable('${variable.name}')" title="수정">
                    ✏️
                </button>
                <button class="btn-small btn-icon btn-danger" onclick="deleteVariable('${variable.name}')" title="삭제">
                    🗑️
                </button>
            </td>
        </tr>
    `).join('');
}

// 변수 모달 열기 (생성)
function openVariableModal() {
    editingVariable = null;
    document.getElementById('variable-modal-title').textContent = '변수 추가';
    document.getElementById('variable-form').reset();
    document.getElementById('variable-error').textContent = '';
    document.getElementById('variable-name').disabled = false;
    document.getElementById('variable-modal').classList.add('active');
}

// 변수 모달 닫기
function closeVariableModal() {
    document.getElementById('variable-modal').classList.remove('active');
    editingVariable = null;
}

// 변수 수정 모달 열기
function editVariable(variableName) {
    const variable = currentVariables.find(v => v.name === variableName);
    if (!variable) return;

    editingVariable = variableName;
    document.getElementById('variable-modal-title').textContent = '변수 수정';
    document.getElementById('variable-name').value = variable.name;
    document.getElementById('variable-name').disabled = true; // 변수명 수정 불가
    document.getElementById('variable-value').value = variable.value;
    document.getElementById('variable-description').value = variable.description || '';
    document.getElementById('variable-error').textContent = '';
    document.getElementById('variable-modal').classList.add('active');
}

// 변수명 실시간 검증
function validateVariableName(event) {
    const input = event.target;
    const value = input.value;
    const errorDiv = document.getElementById('variable-error');

    if (!value) {
        errorDiv.textContent = '';
        return;
    }

    // 패턴 검증
    const pattern = /^[a-zA-Z][a-zA-Z0-9_]*$/;
    if (!pattern.test(value)) {
        errorDiv.textContent = '변수명은 영문자로 시작해야 하며, 영문자/숫자/언더스코어만 사용할 수 있습니다';
        return;
    }

    // 길이 검증
    if (value.length > 100) {
        errorDiv.textContent = '변수명은 100자를 초과할 수 없습니다';
        return;
    }

    // 중복 검증 (편집 모드가 아닐 때만)
    if (!editingVariable && currentVariables.some(v => v.name === value)) {
        errorDiv.textContent = '이미 존재하는 변수명입니다';
        return;
    }

    errorDiv.textContent = '';
}

// 변수 폼 제출
async function handleVariableSubmit(event) {
    event.preventDefault();

    const name = document.getElementById('variable-name').value.trim();
    const value = document.getElementById('variable-value').value.trim();
    const description = document.getElementById('variable-description').value.trim();
    const errorDiv = document.getElementById('variable-error');

    errorDiv.textContent = '';

    const variableData = {
        name: name,
        value: value,
        description: description || null
    };

    try {
        let response;

        if (editingVariable) {
            // 수정
            response = await fetch(`/api/v2/variables/${editingVariable}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                },
                body: JSON.stringify({
                    value: value,
                    description: description || null
                })
            });
        } else {
            // 생성
            response = await fetch('/api/v2/variables', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                },
                body: JSON.stringify(variableData)
            });
        }

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '변수 저장에 실패했습니다');
        }

        // 성공
        showToast(editingVariable ? '변수가 수정되었습니다' : '변수가 추가되었습니다', 'success');
        closeVariableModal();
        loadVariables();

    } catch (error) {
        console.error('변수 저장 실패:', error);
        errorDiv.textContent = error.message;
    }
}

// 변수 삭제
async function deleteVariable(variableName) {
    try {
        // 먼저 사용 현황 확인
        const usageResponse = await fetch(`/api/v2/variables/${variableName}/usage`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });

        if (!usageResponse.ok) {
            throw new Error('변수 사용 현황을 확인할 수 없습니다');
        }

        const usage = await usageResponse.json();

        // 삭제 확인 모달 표시
        showDeleteConfirmation(variableName, usage);

    } catch (error) {
        console.error('변수 사용 현황 확인 실패:', error);
        showToast('변수 삭제에 실패했습니다', 'error');
    }
}

// 삭제 확인 모달 표시
function showDeleteConfirmation(variableName, usage) {
    const modal = document.getElementById('variable-delete-modal');
    const messageDiv = document.getElementById('delete-variable-message');
    const usageDiv = document.getElementById('delete-variable-usage');
    const confirmBtn = document.getElementById('confirm-delete-btn');

    messageDiv.innerHTML = `<strong>{{${variableName}}}</strong> 변수를 삭제하시겠습니까?`;

    if (usage && usage.length > 0) {
        usageDiv.innerHTML = `
            <div class="warning-box">
                <strong>⚠️ 경고:</strong> 이 변수는 ${usage.length}개 프롬프트에서 사용 중입니다.
                <ul>
                    ${usage.map(u => `<li>${escapeHtml(u.prompt_title)}</li>`).join('')}
                </ul>
                <p>삭제 후 해당 프롬프트에서 변수를 사용할 수 없게 됩니다.</p>
            </div>
        `;
    } else {
        usageDiv.innerHTML = '';
    }

    // 확인 버튼 이벤트 (기존 이벤트 제거 후 재등록)
    const newConfirmBtn = confirmBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

    newConfirmBtn.addEventListener('click', async () => {
        await executeDelete(variableName, usage.length > 0);
    });

    modal.classList.add('active');
}

// 삭제 모달 닫기
function closeDeleteModal() {
    document.getElementById('variable-delete-modal').classList.remove('active');
}

// 실제 삭제 실행
async function executeDelete(variableName, hasUsage) {
    try {
        const response = await fetch(`/api/v2/variables/${variableName}?force=${hasUsage}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '변수 삭제에 실패했습니다');
        }

        showToast('변수가 삭제되었습니다', 'success');
        closeDeleteModal();
        loadVariables();

    } catch (error) {
        console.error('변수 삭제 실패:', error);
        showToast(error.message, 'error');
    }
}

// 유틸리티 함수들

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// 전역으로 노출 (HTML onclick에서 사용)
window.editVariable = editVariable;
window.deleteVariable = deleteVariable;
window.closeVariableModal = closeVariableModal;
window.closeDeleteModal = closeDeleteModal;
