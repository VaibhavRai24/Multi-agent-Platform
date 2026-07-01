const API_BASE = '/api/v1';

const api = {
    async request(endpoint, options = {}) {
        const token = localStorage.getItem('access_token');
        const headers = {
            ...options.headers
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers
        });

        if (response.status === 401 && window.location.pathname !== '/login.html') {
            window.location.href = 'login.html';
            return;
        }

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'API Error');
        }
        return data;
    },

    async login(username, password) {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);
        return this.request('/auth/login', {
            method: 'POST',
            body: formData
        });
    },

    async register(email, password, fullName) {
        return this.request('/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password, full_name: fullName })
        });
    },

    async getProfile() {
        return this.request('/users/me');
    },

    async uploadDocument(file) {
        const formData = new FormData();
        formData.append('file', file);
        return this.request('/documents/upload', {
            method: 'POST',
            body: formData
        });
    },

    async getDocuments() {
        return this.request('/documents/');
    },

    async deleteDocument(docId) {
        return this.request(`/documents/${docId}`, { method: 'DELETE' });
    },

    async askQuestion(query, payloadOverrides) {
        return this.request('/chat/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, ...payloadOverrides })
        });
    },

    async getChatHistory() {
        return this.request('/chat/history');
    },

    // ── Chat Sessions (last 5) ──────────────────────────────────────────
    async getChatSessions() {
        return this.request('/chat/sessions');
    },

    async getChatSession(chatId) {
        return this.request(`/chat/sessions/${chatId}`);
    },

    async deleteChatSession(chatId) {
        return this.request(`/chat/sessions/${chatId}`, { method: 'DELETE' });
    },

    // ── Reports ──────────────────────────────────────────────────────────
    async getReports() {
        return this.request('/reports/');
    },

    async saveReport(payload) {
        // payload: { title, content, format }  (format: 'markdown' | 'docx')
        return this.request('/reports/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
    },

    async viewReport(reportId) {
        return this.request(`/reports/view/${reportId}`);
    },

    async deleteReport(reportId) {
        return this.request(`/reports/${reportId}`, { method: 'DELETE' });
    },

    // Triggers a browser file download for the given report.
    // fmt: 'markdown' (default) | 'docx'
    downloadReport(reportId, fmt = 'markdown') {
        const token = localStorage.getItem('access_token');
        const url = `${API_BASE}/reports/download/${reportId}?fmt=${fmt}`;
        // Use a temporary anchor to carry the auth token via a one-shot fetch+blob
        fetch(url, { headers: token ? { 'Authorization': `Bearer ${token}` } : {} })
            .then(res => {
                if (!res.ok) throw new Error('Download failed');
                return res.blob();
            })
            .then(blob => {
                const ext = fmt === 'docx' ? 'docx' : 'md';
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = `report_${reportId}.${ext}`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                URL.revokeObjectURL(a.href);
            })
            .catch(err => {
                console.error('Report download error:', err);
                app.showToast('Download failed — please try again.', 'error');
            });
    }
};

const auth = {
    logout() {
        localStorage.removeItem('access_token');
        window.location.href = 'login.html';
    },
    check() {
        if (!localStorage.getItem('access_token') && !window.location.pathname.endsWith('login.html')) {
            window.location.href = 'login.html';
        }
    }
};
