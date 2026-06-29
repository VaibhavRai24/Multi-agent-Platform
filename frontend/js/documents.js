const docApp = {
    bind() {
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-upload');
        if (!dropZone || !fileInput) return;

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(ev =>
            dropZone.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); })
        );
        ['dragenter', 'dragover'].forEach(ev =>
            dropZone.addEventListener(ev, () => dropZone.classList.add('dragover'))
        );
        ['dragleave', 'drop'].forEach(ev =>
            dropZone.addEventListener(ev, () => dropZone.classList.remove('dragover'))
        );
        dropZone.addEventListener('drop', e => this.handleFiles(e.dataTransfer.files));
        fileInput.addEventListener('change', () => this.handleFiles(fileInput.files));
    },

    handleFiles(files) {
        [...files].forEach(f => this.uploadFile(f));
    },

    async uploadFile(file) {
        const progressContainer = document.getElementById('upload-progress-container');
        const progressFill      = document.getElementById('upload-progress');
        const uploadLabel       = document.getElementById('upload-status-label');

        progressContainer.style.display = 'block';
        progressFill.style.width = '20%';
        if (uploadLabel) uploadLabel.textContent = `Processing ${file.name}…`;
        app.showToast(`Uploading ${file.name}…`);

        try {
            // Animate progress while waiting
            let pct = 20;
            const ticker = setInterval(() => {
                pct = Math.min(pct + 8, 85);
                progressFill.style.width = pct + '%';
            }, 400);

            const result = await api.uploadDocument(file);
            clearInterval(ticker);
            progressFill.style.width = '100%';

            const statusMsg = result.status === 'processed'
                ? `✓ ${file.name} indexed (${result.chunks_indexed} chunks)`
                : `⚠ ${file.name} saved but not indexed (${result.status})`;

            if (uploadLabel) uploadLabel.textContent = statusMsg;
            app.showToast(statusMsg, result.status === 'processed' ? 'success' : 'info');

            setTimeout(() => {
                progressContainer.style.display = 'none';
                progressFill.style.width = '0%';
                if (uploadLabel) uploadLabel.textContent = '';
            }, 2000);

            this.loadDocuments();
        } catch (err) {
            app.showToast(`Upload failed: ${err.message}`, 'error');
            progressContainer.style.display = 'none';
            if (uploadLabel) uploadLabel.textContent = '';
        }
    },

    async loadDocuments() {
        const tbody = document.getElementById('documents-tbody');
        const statEl = document.getElementById('stat-total-docs');
        const profileEl = document.getElementById('profile-doc-count');
        if (!tbody) return;

        tbody.innerHTML = `<tr><td colspan="6" class="placeholder-text" style="text-align:center;padding:24px">
            <i class="fa-solid fa-circle-notch fa-spin" style="margin-right:8px"></i>Loading documents…</td></tr>`;

        try {
            const docs = await api.getDocuments();
            if (statEl) statEl.textContent = docs.length;
            if (profileEl) profileEl.textContent = docs.length;
            tbody.innerHTML = '';

            if (docs.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" class="placeholder-text" style="text-align:center;padding:32px;color:var(--text-secondary)">
                    <i class="fa-solid fa-folder-open" style="font-size:2rem;display:block;margin-bottom:12px;opacity:0.4"></i>
                    No documents yet. Upload files above to add them to your knowledge base.</td></tr>`;
                return;
            }

            docs.forEach(doc => {
                const tr = document.createElement('tr');
                const ext = doc.file_type.toLowerCase();

                let icon = 'fa-file';
                let iconColor = 'var(--text-secondary)';
                if (ext === 'pdf')  { icon = 'fa-file-pdf';   iconColor = '#ef4444'; }
                if (ext === 'docx') { icon = 'fa-file-word';  iconColor = '#3b82f6'; }
                if (['csv', 'xlsx', 'xls'].includes(ext)) { icon = 'fa-file-excel'; iconColor = '#10b981'; }
                if (['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(ext)) { icon = 'fa-file-image'; iconColor = '#a855f7'; }
                if (['txt', 'md'].includes(ext)) { icon = 'fa-file-lines'; iconColor = '#f59e0b'; }

                const statusConfig = {
                    processed:  { label: 'Indexed',    cls: 'status-indexed'  },
                    failed:     { label: 'Failed',     cls: 'status-failed'   },
                    no_index:   { label: 'No Index',   cls: 'status-noindex'  },
                    pending:    { label: 'Pending…',   cls: 'status-pending'  },
                    processing: { label: 'Processing', cls: 'status-pending'  },
                };
                const s = statusConfig[doc.status] || { label: doc.status, cls: '' };

                const date = new Date(doc.created_at).toLocaleDateString('en-IN', {
                    day: '2-digit', month: 'short', year: 'numeric'
                });

                tr.innerHTML = `
                    <td>
                        <span class="doc-name-cell">
                            <i class="fa-regular ${icon}" style="color:${iconColor};font-size:1.1rem;flex-shrink:0"></i>
                            <span class="doc-filename" title="${doc.title}">${doc.title}</span>
                        </span>
                    </td>
                    <td><span class="file-type-badge">${ext.toUpperCase()}</span></td>
                    <td>${date}</td>
                    <td>${doc.chunks_indexed > 0 ? doc.chunks_indexed + ' chunks' : '—'}</td>
                    <td><span class="doc-status-badge ${s.cls}">${s.label}</span></td>
                    <td>
                        <button class="doc-delete-btn" onclick="docApp.deleteDocument(${doc.id}, '${doc.title.replace(/'/g, "\\'")}')"
                            title="Remove from knowledge base">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="6" style="padding:20px;color:var(--error);text-align:center">Failed to load documents: ${e.message}</td></tr>`;
        }
    },

    async deleteDocument(docId, title) {
        if (!confirm(`Remove "${title}" from your knowledge base? This will also delete its vectors from Pinecone.`)) return;
        try {
            await api.deleteDocument(docId);
            app.showToast(`"${title}" removed.`, 'success');
            this.loadDocuments();
        } catch (e) {
            app.showToast(`Delete failed: ${e.message}`, 'error');
        }
    }
};

const reportApp = {
    modalFormat: 'docx',     // currently selected format inside the suggest modal
    modalContent: '',        // raw answer content waiting to be saved
    modalSuggestedTitle: '',

    async loadReports() {
        const grid = document.getElementById('reports-grid');
        if (!grid) return;
        grid.innerHTML = `<p class="placeholder-text" style="grid-column:1/-1;text-align:center;padding:24px">
            <i class="fa-solid fa-circle-notch fa-spin" style="margin-right:8px"></i>Loading reports…</p>`;
        try {
            const reports = await api.getReports();
            grid.innerHTML = '';
            const profileEl = document.getElementById('profile-report-count');
            if (profileEl) profileEl.textContent = reports.length;

            if (reports.length === 0) {
                grid.innerHTML = `<p class="placeholder-text" style="grid-column:1/-1;text-align:center;padding:32px">
                    <i class="fa-solid fa-file-circle-plus" style="font-size:2rem;display:block;margin-bottom:12px;opacity:0.4"></i>
                    No reports yet. Ask something in chat &mdash; reports get suggested and saved automatically.</p>`;
                return;
            }

            reports.forEach(report => {
                const card = document.createElement('div');
                card.className = 'report-card glass-panel';
                const fmtIcon = report.format === 'docx' ? 'fa-file-word' : 'fa-file-lines';
                card.innerHTML = `
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px">
                        <h3>${this.escapeHTML(report.title)}</h3>
                        <span class="file-type-badge"><i class="fa-regular ${fmtIcon}"></i> ${report.format.toUpperCase()}</span>
                    </div>
                    <p style="color:var(--text-secondary);font-size:0.85rem">Generated on ${report.date}</p>
                    <p class="report-preview">${this.escapeHTML(report.preview || '')}</p>
                    <div class="report-actions">
                        <button onclick="reportApp.downloadReport(${report.id}, '${this.escapeForAttr(report.title)}')" title="Download">
                            <i class="fa-solid fa-download"></i> Download
                        </button>
                        <button onclick="reportApp.viewReport(${report.id})" title="View">
                            <i class="fa-solid fa-eye"></i> View
                        </button>
                        <button class="report-delete-btn" onclick="reportApp.deleteReport(${report.id}, '${this.escapeForAttr(report.title)}')" title="Delete">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </div>
                `;
                grid.appendChild(card);
            });
        } catch (e) {
            grid.innerHTML = `<p class="error-text" style="grid-column:1/-1;text-align:center">Failed to fetch reports: ${e.message}</p>`;
        }
    },

    async refreshCountSilently() {
        try {
            const reports = await api.getReports();
            const profileEl = document.getElementById('profile-report-count');
            if (profileEl) profileEl.textContent = reports.length;
            // If the user is currently looking at the reports page, refresh the grid too
            const reportsPage = document.getElementById('reports-page');
            if (reportsPage && reportsPage.classList.contains('active')) {
                this.loadReports();
            }
        } catch (e) {
            console.error('Silent report count refresh failed:', e);
        }
    },

    async downloadReport(reportId, title) {
        try {
            const token = localStorage.getItem('access_token');
            const resp = await fetch(`/api/v1/reports/download/${reportId}`, {
                headers: token ? { 'Authorization': `Bearer ${token}` } : {}
            });
            if (!resp.ok) throw new Error('Download failed');
            const blob = await resp.blob();
            const disposition = resp.headers.get('Content-Disposition') || '';
            const match = disposition.match(/filename="?([^"]+)"?/);
            const filename = match ? match[1] : `${title || 'report'}.md`;

            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
            app.showToast('Download started.', 'success');
        } catch (e) {
            app.showToast(`Download failed: ${e.message}`, 'error');
        }
    },

    async viewReport(reportId) {
        try {
            const report = await api.viewReport(reportId);
            document.getElementById('report-view-title').textContent = report.title;
            const body = document.getElementById('report-view-body');
            body.innerHTML = (report.format === 'docx')
                ? marked.parse(report.content) // server stores the source markdown even for docx exports
                : marked.parse(report.content);
            document.getElementById('report-view-modal').classList.remove('hidden');
        } catch (e) {
            app.showToast(`Could not open report: ${e.message}`, 'error');
        }
    },

    closeViewModal() {
        document.getElementById('report-view-modal').classList.add('hidden');
    },

    async deleteReport(reportId, title) {
        if (!confirm(`Delete report "${title}"? This cannot be undone.`)) return;
        try {
            await api.deleteReport(reportId);
            app.showToast(`"${title}" deleted.`, 'success');
            this.loadReports();
        } catch (e) {
            app.showToast(`Delete failed: ${e.message}`, 'error');
        }
    },

    // ── Suggestion modal (triggered from chat.js) ───────────────────────────
    openSuggestModal(suggestedTitle, content) {
        this.modalContent = content;
        this.modalSuggestedTitle = suggestedTitle;
        this.modalFormat = 'docx';

        document.getElementById('report-title-input').value = suggestedTitle;
        document.querySelectorAll('#report-suggest-modal .format-btn').forEach(b => {
            b.classList.toggle('active', b.dataset.format === 'docx');
        });
        document.getElementById('report-suggest-modal').classList.remove('hidden');
    },

    selectModalFormat(format) {
        this.modalFormat = format;
        document.querySelectorAll('#report-suggest-modal .format-btn').forEach(b => {
            b.classList.toggle('active', b.dataset.format === format);
        });
    },

    dismissSuggestModal() {
        document.getElementById('report-suggest-modal').classList.add('hidden');
        this.modalContent = '';
        this.modalSuggestedTitle = '';
    },

    async confirmSuggestModal() {
        const titleInput = document.getElementById('report-title-input');
        const title = (titleInput.value || this.modalSuggestedTitle || 'Untitled Report').trim();

        try {
            await api.saveReport({ title, content: this.modalContent, format: this.modalFormat });
            app.showToast(`Report "${title}" saved as ${this.modalFormat.toUpperCase()}.`, 'success');
            this.refreshCountSilently();
        } catch (e) {
            app.showToast(`Could not save report: ${e.message}`, 'error');
        } finally {
            document.getElementById('report-suggest-modal').classList.add('hidden');
            this.modalContent = '';
            this.modalSuggestedTitle = '';
        }
    },

    escapeHTML(str) {
        return String(str).replace(/[&<>'"]/g,
            tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
        );
    },

    escapeForAttr(str) {
        return String(str).replace(/'/g, "\\'");
    }
};

document.addEventListener('DOMContentLoaded', () => { docApp.bind(); });
