/**
 * JQL Editor - Monaco Editor 기반 JQL 쿼리 에디터
 *
 * 기능:
 * - Monaco Editor 초기화
 * - JQL 언어 모드 등록 및 문법 하이라이팅
 * - 자동완성 (필드명, 연산자, 값)
 */

// 전역 변수
let jqlMonacoEditor = null;
let jqlMetadataCache = {
    projects: [],
    statuses: [],
    priorities: [],
    issueTypes: [],
    users: []
};

// JQL 필드 정의
const JQL_FIELDS = [
    { label: 'project', detail: '프로젝트', documentation: '프로젝트 키 또는 이름' },
    { label: 'status', detail: '상태', documentation: '이슈 상태 (예: Done, In Progress)' },
    { label: 'assignee', detail: '담당자', documentation: '이슈 담당자' },
    { label: 'reporter', detail: '보고자', documentation: '이슈 보고자' },
    { label: 'priority', detail: '우선순위', documentation: '이슈 우선순위' },
    { label: 'type', detail: '이슈 타입', documentation: '이슈 타입 (예: Bug, Task)' },
    { label: 'created', detail: '생성일', documentation: '이슈 생성 날짜' },
    { label: 'updated', detail: '수정일', documentation: '이슈 수정 날짜' },
    { label: 'resolved', detail: '해결일', documentation: '이슈 해결 날짜' },
    { label: 'summary', detail: '제목', documentation: '이슈 제목' },
    { label: 'description', detail: '설명', documentation: '이슈 설명' },
    { label: 'labels', detail: '라벨', documentation: '이슈 라벨' },
    { label: 'component', detail: '컴포넌트', documentation: '이슈 컴포넌트' },
    { label: 'sprint', detail: '스프린트', documentation: '스프린트' },
    { label: 'fixVersion', detail: '수정 버전', documentation: '수정 버전' },
];

// JQL 연산자
const JQL_OPERATORS = ['=', '!=', '~', '!~', '>', '>=', '<', '<=', 'IN', 'NOT IN', 'IS', 'IS NOT', 'WAS', 'WAS IN', 'WAS NOT', 'CHANGED'];

// JQL 키워드
const JQL_KEYWORDS = ['AND', 'OR', 'NOT', 'ORDER BY', 'ASC', 'DESC'];

// 날짜 함수 및 표현
const JQL_DATE_FUNCTIONS = [
    { label: 'startOfDay()', detail: '오늘 00:00' },
    { label: 'endOfDay()', detail: '오늘 23:59' },
    { label: 'startOfWeek()', detail: '이번 주 시작' },
    { label: 'endOfWeek()', detail: '이번 주 끝' },
    { label: 'startOfMonth()', detail: '이번 달 시작' },
    { label: 'endOfMonth()', detail: '이번 달 끝' },
    { label: 'now()', detail: '현재 시각' },
    { label: '-1d', detail: '1일 전' },
    { label: '-7d', detail: '7일 전' },
    { label: '-1w', detail: '1주 전' },
    { label: '-1M', detail: '1달 전' },
    { label: '-3M', detail: '3달 전' },
    { label: '-6M', detail: '6달 전' },
    { label: '-1y', detail: '1년 전' },
];

/**
 * JQL Monaco Editor 초기화
 */
function initJQLMonacoEditor() {
    // Monaco Editor 로드 대기
    require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@latest/min/vs' } });

    require(['vs/editor/editor.main'], function () {
        // JQL 언어 등록
        monaco.languages.register({ id: 'jql' });

        // JQL 문법 하이라이팅 정의
        monaco.languages.setMonarchTokensProvider('jql', {
            keywords: JQL_KEYWORDS,
            operators: JQL_OPERATORS,

            tokenizer: {
                root: [
                    // 키워드
                    [/\b(AND|OR|NOT|ORDER BY|ASC|DESC)\b/i, 'keyword'],

                    // 필드명
                    [/\b(project|status|assignee|reporter|priority|type|created|updated|resolved|summary|description|labels|component|sprint|fixVersion)\b/i, 'type'],

                    // 연산자
                    [/[=!<>~]+|IN|NOT IN|IS|IS NOT|WAS|WAS IN|WAS NOT|CHANGED/i, 'operator'],

                    // 문자열 (큰따옴표)
                    [/"([^"\\]|\\.)*"/, 'string'],

                    // 문자열 (작은따옴표)
                    [/'([^'\\]|\\.)*'/, 'string'],

                    // 숫자
                    [/\d+/, 'number'],

                    // 함수
                    [/\b\w+\(/, 'function'],
                ]
            }
        });

        // 자동완성 프로바이더 등록
        monaco.languages.registerCompletionItemProvider('jql', {
            provideCompletionItems: provideJQLCompletionItems
        });

        // Monaco Editor 생성
        jqlMonacoEditor = monaco.editor.create(document.getElementById('jql-monaco-editor'), {
            value: '',
            language: 'jql',
            theme: 'vs',
            minimap: { enabled: false },
            lineNumbers: 'off',
            glyphMargin: false,
            folding: false,
            lineDecorationsWidth: 0,
            lineNumbersMinChars: 0,
            scrollBeyondLastLine: false,
            automaticLayout: true,
            wordWrap: 'on',
            fontSize: 13,
            fontFamily: 'Monaco, Menlo, Consolas, monospace'
        });

        console.log('✅ JQL Monaco Editor 초기화 완료');
    });
}

/**
 * JQL 자동완성 아이템 제공
 */
async function provideJQLCompletionItems(model, position) {
    const textUntilPosition = model.getValueInRange({
        startLineNumber: position.lineNumber,
        startColumn: 1,
        endLineNumber: position.lineNumber,
        endColumn: position.column,
    });

    const word = model.getWordUntilPosition(position);
    const range = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: word.startColumn,
        endColumn: word.endColumn,
    };

    // 컨텍스트 분석
    const suggestions = [];

    // 1. 필드명 자동완성 (텍스트 시작 또는 논리 연산자 다음)
    if (/(?:^|\s+(?:AND|OR|NOT)\s+)[\w]*$/i.test(textUntilPosition)) {
        JQL_FIELDS.forEach(field => {
            suggestions.push({
                label: field.label,
                kind: monaco.languages.CompletionItemKind.Field,
                detail: field.detail,
                documentation: field.documentation,
                insertText: field.label,
                range: range
            });
        });
    }

    // 2. 연산자 자동완성 (필드명 다음)
    if (/\b\w+\s*$/i.test(textUntilPosition)) {
        JQL_OPERATORS.forEach(op => {
            suggestions.push({
                label: op,
                kind: monaco.languages.CompletionItemKind.Operator,
                insertText: op + ' ',
                range: range
            });
        });
    }

    // 3. 필드 값 자동완성
    const fieldMatch = textUntilPosition.match(/\b(\w+)\s*([=~]|IN|WAS)\s*["']?(\w*)$/i);
    if (fieldMatch) {
        const fieldName = fieldMatch[1].toLowerCase();
        const operator = fieldMatch[2];

        // 필드별 값 제안
        const valueSuggestions = await getFieldValueSuggestions(fieldName);
        suggestions.push(...valueSuggestions.map(item => ({
            ...item,
            range: range
        })));
    }

    // 4. 논리 연산자 (조건 완성 후)
    if (/\b\w+\s*[=!<>~]+\s*(?:"[^"]*"|'[^']*'|\w+)\s*$/i.test(textUntilPosition)) {
        JQL_KEYWORDS.forEach(keyword => {
            suggestions.push({
                label: keyword,
                kind: monaco.languages.CompletionItemKind.Keyword,
                insertText: keyword + ' ',
                range: range
            });
        });
    }

    return { suggestions };
}

/**
 * 필드 값 자동완성 제안 가져오기
 */
async function getFieldValueSuggestions(fieldName) {
    const suggestions = [];

    switch (fieldName) {
        case 'project':
            // 프로젝트 목록 로드
            if (jqlMetadataCache.projects.length === 0) {
                await loadJiraProjects();
            }
            return jqlMetadataCache.projects.map(p => ({
                label: p.key,
                kind: monaco.languages.CompletionItemKind.Value,
                detail: p.name,
                insertText: `"${p.key}"`
            }));

        case 'status':
            // 상태 목록 로드
            if (jqlMetadataCache.statuses.length === 0) {
                await loadJiraStatuses();
            }
            return jqlMetadataCache.statuses.map(status => ({
                label: status,
                kind: monaco.languages.CompletionItemKind.Value,
                insertText: status.includes(' ') ? `"${status}"` : status
            }));

        case 'priority':
            // 우선순위 목록 로드
            if (jqlMetadataCache.priorities.length === 0) {
                await loadJiraPriorities();
            }
            return jqlMetadataCache.priorities.map(priority => ({
                label: priority,
                kind: monaco.languages.CompletionItemKind.Value,
                insertText: priority
            }));

        case 'type':
        case 'issuetype':
            // 이슈 타입 목록 로드
            if (jqlMetadataCache.issueTypes.length === 0) {
                await loadJiraIssueTypes();
            }
            return jqlMetadataCache.issueTypes.map(type => ({
                label: type,
                kind: monaco.languages.CompletionItemKind.Value,
                insertText: type
            }));

        case 'assignee':
        case 'reporter':
            // currentUser() 함수 제안
            suggestions.push({
                label: 'currentUser()',
                kind: monaco.languages.CompletionItemKind.Function,
                detail: '현재 사용자',
                insertText: 'currentUser()'
            });
            return suggestions;

        case 'created':
        case 'updated':
        case 'resolved':
            // 날짜 함수 제안
            return JQL_DATE_FUNCTIONS.map(func => ({
                label: func.label,
                kind: monaco.languages.CompletionItemKind.Function,
                detail: func.detail,
                insertText: func.label
            }));

        default:
            return [];
    }
}

/**
 * Jira 메타데이터 로드 함수들
 */
async function loadJiraProjects() {
    try {
        const response = await fetch('/api/v2/jira/projects', {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
            }
        });
        if (response.ok) {
            jqlMetadataCache.projects = await response.json();
        }
    } catch (error) {
        console.error('프로젝트 목록 로드 실패:', error);
    }
}

async function loadJiraStatuses() {
    try {
        const response = await fetch('/api/v2/jira/statuses', {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
            }
        });
        if (response.ok) {
            jqlMetadataCache.statuses = await response.json();
        }
    } catch (error) {
        console.error('상태 목록 로드 실패:', error);
    }
}

async function loadJiraPriorities() {
    try {
        const response = await fetch('/api/v2/jira/priorities', {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
            }
        });
        if (response.ok) {
            jqlMetadataCache.priorities = await response.json();
        }
    } catch (error) {
        console.error('우선순위 목록 로드 실패:', error);
    }
}

async function loadJiraIssueTypes() {
    try {
        const response = await fetch('/api/v2/jira/issue-types', {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
            }
        });
        if (response.ok) {
            jqlMetadataCache.issueTypes = await response.json();
        }
    } catch (error) {
        console.error('이슈 타입 목록 로드 실패:', error);
    }
}

/**
 * 탭 전환 처리
 */
function setupJQLTabs() {
    const tabs = document.querySelectorAll('.jql-tab');
    const textPanel = document.getElementById('jql-text-editor');
    const monacoPanel = document.getElementById('jql-monaco-editor');
    const testButton = document.getElementById('test-jql-btn');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabType = tab.dataset.tab;

            // 탭 활성화
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // 패널 전환
            if (tabType === 'text') {
                textPanel.style.display = 'block';
                monacoPanel.style.display = 'none';
                testButton.style.display = 'none';

                // 값을 복사하지 않음 - 텍스트와 JQL은 독립적으로 관리
            } else if (tabType === 'jql') {
                textPanel.style.display = 'none';
                monacoPanel.style.display = 'block';
                testButton.style.display = 'flex';

                // 값을 복사하지 않음 - 텍스트와 JQL은 독립적으로 관리

                // Monaco 에디터 레이아웃 업데이트
                setTimeout(() => {
                    if (jqlMonacoEditor) {
                        jqlMonacoEditor.layout();
                    }
                }, 10);
            }
        });
    });
}

// 페이지 로드 시 초기화
if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        initJQLMonacoEditor();
        setupJQLTabs();
    });
}

// export for other modules
if (typeof window !== 'undefined') {
    window.jqlEditor = {
        getEditor: () => jqlMonacoEditor,
        getValue: () => jqlMonacoEditor ? jqlMonacoEditor.getValue() : '',
        setValue: (value) => { if (jqlMonacoEditor) jqlMonacoEditor.setValue(value); }
    };
}
