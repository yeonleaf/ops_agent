/**
 * Report Editor - 보고서 편집 클라이언트 로직
 */

let editor = null;
let currentFile = null;
let isModified = false;

// API 엔드포인트
const API_BASE = '/api/editor';

/**
 * 페이지 로드 시 초기화
 */
document.addEventListener('DOMContentLoaded', () => {
    initializeTinyMCE();
    loadReportsList();
    setupEventListeners();

    // URL 파라미터에서 파일명 확인 및 자동 로드
    checkAndLoadFromURL();
});

/**
 * TinyMCE 에디터 초기화
 */
function initializeTinyMCE() {
    tinymce.init({
        selector: '#tinymce-editor',
        language: 'ko_KR',
        height: '80vh',
        plugins: [
            'advlist', 'autolink', 'lists', 'link', 'image', 'charmap', 'preview',
            'anchor', 'searchreplace', 'visualblocks', 'code', 'fullscreen',
            'insertdatetime', 'media', 'table', 'help', 'wordcount', 'save'
        ],
        toolbar: 'undo redo | blocks | ' +
            'bold italic forecolor backcolor | alignleft aligncenter ' +
            'alignright alignjustify | bullist numlist outdent indent | ' +
            'table tabledelete | tableprops tablerowprops tablecellprops | ' +
            'tableinsertrowbefore tableinsertrowafter tabledeleterow | ' +
            'tableinsertcolbefore tableinsertcolafter tabledeletecol | ' +
            'removeformat | code fullscreen preview | help',
        menubar: 'file edit view insert format tools table help',
        content_style: `
            body {
                font-family: 'Segoe UI', 'Malgun Gothic', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                padding: 20px;
            }
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 1rem 0;
            }
            table th,
            table td {
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
            }
            table th {
                background-color: #f2f2f2;
                font-weight: 600;
            }
            table tr:nth-child(even) {
                background-color: #f9f9f9;
            }
            table tr:hover {
                background-color: #f5f5f5;
            }
            h1, h2, h3, h4, h5, h6 {
                margin-top: 1.5rem;
                margin-bottom: 0.5rem;
            }
            .report-table {
                font-size: 0.9rem;
            }
        `,
        setup: (ed) => {
            editor = ed;
            ed.on('change', () => {
                isModified = true;
            });
        },
        save_onsavecallback: () => {
            saveReport();
        }
    });
}

/**
 * 이벤트 리스너 설정
 */
function setupEventListeners() {
    const fileSelector = document.getElementById('file-selector');
    const loadBtn = document.getElementById('load-btn');
    const saveBtn = document.getElementById('save-btn');
    const saveAsBtn = document.getElementById('save-as-btn');
    const previewBtn = document.getElementById('preview-btn');

    // 파일 선택 시 불러오기 버튼 활성화
    fileSelector.addEventListener('change', () => {
        const hasSelection = fileSelector.value !== '';
        loadBtn.disabled = !hasSelection;
    });

    // 불러오기 버튼
    loadBtn.addEventListener('click', () => {
        const filename = fileSelector.value;
        if (filename) {
            if (isModified && !confirm('저장하지 않은 변경사항이 있습니다. 계속하시겠습니까?')) {
                return;
            }
            loadReport(filename);
        }
    });

    // 저장 버튼
    saveBtn.addEventListener('click', saveReport);

    // 다른 이름으로 저장 버튼
    saveAsBtn.addEventListener('click', saveReportAs);

    // 미리보기 버튼
    previewBtn.addEventListener('click', previewReport);

    // 페이지 이탈 시 경고
    window.addEventListener('beforeunload', (e) => {
        if (isModified) {
            e.preventDefault();
            e.returnValue = '';
        }
    });
}

/**
 * 보고서 목록 로드
 */
async function loadReportsList() {
    try {
        showLoading('보고서 목록 로드 중...');

        const response = await fetch(`${API_BASE}/reports`);
        if (!response.ok) {
            throw new Error('보고서 목록을 가져오는데 실패했습니다.');
        }

        const files = await response.json();
        const fileSelector = document.getElementById('file-selector');

        // 기존 옵션 제거 (첫 번째 제외)
        fileSelector.innerHTML = '<option value="">보고서 선택...</option>';

        // 파일 목록 추가
        files.forEach(file => {
            const option = document.createElement('option');
            option.value = file;
            option.textContent = file;
            fileSelector.appendChild(option);
        });

        hideLoading();
        showToast(`${files.length}개의 보고서를 찾았습니다.`, 'info');

    } catch (error) {
        hideLoading();
        console.error('❌ 보고서 목록 로드 실패:', error);
        showToast(error.message, 'error');
    }
}

/**
 * 보고서 파일 로드
 */
async function loadReport(filename) {
    try {
        showLoading('파일 로드 중...');

        const response = await fetch(`${API_BASE}/reports/${filename}`);
        if (!response.ok) {
            throw new Error('파일을 불러오는데 실패했습니다.');
        }

        const data = await response.json();

        // 에디터에 내용 설정
        if (editor) {
            editor.setContent(data.content);
        }

        // 상태 업데이트
        currentFile = data.filename;
        isModified = false;
        updateStatusBar(currentFile, null);

        // 버튼 활성화
        document.getElementById('save-btn').disabled = false;
        document.getElementById('save-as-btn').disabled = false;
        document.getElementById('preview-btn').disabled = false;

        hideLoading();
        showToast(`'${filename}' 파일을 불러왔습니다.`, 'success');

    } catch (error) {
        hideLoading();
        console.error('❌ 파일 로드 실패:', error);
        showToast(error.message, 'error');
    }
}

/**
 * 보고서 저장
 */
async function saveReport() {
    if (!currentFile) {
        showToast('저장할 파일을 먼저 선택해주세요.', 'warning');
        return;
    }

    try {
        showLoading('저장 중...');

        const content = editor.getContent();

        const response = await fetch(`${API_BASE}/reports/${currentFile}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ content })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '저장에 실패했습니다.');
        }

        const result = await response.json();

        // 상태 업데이트
        isModified = false;
        const now = new Date().toLocaleString('ko-KR');
        updateStatusBar(currentFile, now);

        hideLoading();
        showToast(result.message || '파일이 저장되었습니다.', 'success');

    } catch (error) {
        hideLoading();
        console.error('❌ 저장 실패:', error);
        showToast(error.message, 'error');
    }
}

/**
 * 다른 이름으로 저장
 */
async function saveReportAs() {
    const filename = prompt('저장할 파일명을 입력하세요:', currentFile || 'new_report.html');
    if (!filename) return;

    try {
        showLoading('저장 중...');

        const content = editor.getContent();

        const response = await fetch(`${API_BASE}/reports/save-as`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ filename, content })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '저장에 실패했습니다.');
        }

        const result = await response.json();

        // 상태 업데이트
        currentFile = result.filename;
        isModified = false;
        const now = new Date().toLocaleString('ko-KR');
        updateStatusBar(currentFile, now);

        // 파일 목록 새로고침
        await loadReportsList();

        // 새로 저장한 파일 선택
        document.getElementById('file-selector').value = result.filename;

        hideLoading();
        showToast(result.message || '파일이 저장되었습니다.', 'success');

    } catch (error) {
        hideLoading();
        console.error('❌ 저장 실패:', error);
        showToast(error.message, 'error');
    }
}

/**
 * 미리보기
 */
function previewReport() {
    if (!editor) {
        showToast('에디터가 초기화되지 않았습니다.', 'error');
        return;
    }

    const content = editor.getContent();
    const previewWindow = window.open('', '_blank');

    const html = `
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>미리보기 - ${currentFile || '새 문서'}</title>
            <style>
                body {
                    font-family: 'Segoe UI', 'Malgun Gothic', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 20px;
                }
                .preview-container {
                    max-width: 1200px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 40px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                table {
                    border-collapse: collapse;
                    width: 100%;
                    margin: 1rem 0;
                }
                table th,
                table td {
                    border: 1px solid #ddd;
                    padding: 12px;
                    text-align: left;
                }
                table th {
                    background-color: #f2f2f2;
                    font-weight: 600;
                }
                table tr:nth-child(even) {
                    background-color: #f9f9f9;
                }
                table tr:hover {
                    background-color: #f5f5f5;
                }
            </style>
        </head>
        <body>
            <div class="preview-container">
                ${content}
            </div>
        </body>
        </html>
    `;

    previewWindow.document.write(html);
    previewWindow.document.close();
}

/**
 * URL 파라미터에서 파일명 확인 및 자동 로드
 */
async function checkAndLoadFromURL() {
    const urlParams = new URLSearchParams(window.location.search);
    const filename = urlParams.get('file');

    if (filename) {
        // URL 파라미터 제거 (히스토리에 깨끗한 URL 유지)
        window.history.replaceState({}, document.title, window.location.pathname);

        // 파일 목록이 로드될 때까지 대기
        await waitForReportsList();

        // 파일 선택 및 로드
        const fileSelector = document.getElementById('file-selector');
        fileSelector.value = filename;

        // 불러오기 버튼 활성화 및 자동 로드
        document.getElementById('load-btn').disabled = false;
        await loadReport(filename);
    }
}

/**
 * 보고서 목록이 로드될 때까지 대기
 */
function waitForReportsList() {
    return new Promise((resolve) => {
        const checkInterval = setInterval(() => {
            const fileSelector = document.getElementById('file-selector');
            if (fileSelector.options.length > 1) { // "보고서 선택..." 외에 옵션이 있는지 확인
                clearInterval(checkInterval);
                resolve();
            }
        }, 100);

        // 최대 5초 대기
        setTimeout(() => {
            clearInterval(checkInterval);
            resolve();
        }, 5000);
    });
}

/**
 * 상태 바 업데이트
 */
function updateStatusBar(filename, savedTime) {
    document.getElementById('current-file').textContent = filename ? `📄 ${filename}` : '파일 없음';
    document.getElementById('last-saved').textContent = savedTime ? `💾 ${savedTime}` : '저장 안 됨';
}

/**
 * 토스트 메시지 표시
 */
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast toast-${type} show`;

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

/**
 * 로딩 표시
 */
function showLoading(message = '처리 중...') {
    showToast(message, 'info');
}

/**
 * 로딩 숨김
 */
function hideLoading() {
    // 토스트가 자동으로 사라지므로 별도 처리 불필요
}
