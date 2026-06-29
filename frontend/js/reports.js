const reportApp = {
    // Tracks content pending confirmation in the suggestion modal
    _pendingContent: null,
    _pendingTitle: null,
    _pendingFormat: 'docx',   // default format for the suggest modal

    // ── Public: called from app.navigate ────────────────────────────────
    async loadReports() {
        const grid = document.getElementById('reports-grid');
        grid.innerHTML = `<p class="loading-msg"><i class="fa-solid fa-circle-notch fa-spin"></i> Loading reports…</p>`;
        try {
            const reports = await api.getReports();
            this._renderGrid(reports);
        } catch (e) {
            grid.innerHTML = `<p class="empty-state">Failed to load reports. ${e.message}</p>`;
        }
    },

    _renderGrid(reports) {
        const grid = document.getElementById('reports-grid');
        if (!reports || reports.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <i class="fa-regular fa-file-lines" style="font-size:2.5rem;color:var(--text-secondary);margin-bottom:12px"></i>
                    <p>No reports yet. Ask the assistant something substantial and it will offer to save it here.</p>
                </div>`;
            return;
        }

        grid.innerHTML = reports.map(r => `
            <div class="report-card glass-panel" id="report-card-${r.id}">
                <div class="report-card-header">
                    <i class="fa-regular ${r.format === 'docx' ? 'fa-file-word' : 'fa-file-lines'} report-icon"></i>
                    <div class="report-meta">
                        <h4 class="report-title">${this._esc(r.title)}</h4>
                        <span class="report-date">${r.date}</span>
                    </div>
                </div>
                <p class="report-preview">${this._esc(r.preview)}</p>
                <div class="report-actions">
                    <button class="report-btn report-btn-view" onclick="reportApp.viewReport(${r.id})">
                        <i class="fa-regular fa-eye"></i> View
                    </button>
                    <button class="report-btn report-btn-dl" onclick="api.downloadReport(${r.id}, 'docx')" title="Download as Word (.docx)">
                        <i class="fa-regular fa-file-word"></i> .docx
                    </button>
                    <button class="report-btn report-btn-dl" onclick="api.downloadReport(${r.id}, 'markdown')" title="Download as Markdown">
                        <i class="fa-regular fa-file-lines"></i> .md
                    </button>
                    <button class="report-btn report-btn-del" onclick="reportApp.deleteReport(${r.id})" title="Delete">
                        <i class="fa-regular fa-trash-can"></i>
                    </button>
                </div>
            </div>`).join('');
    },

    // ── Silently refresh the report count badge without a full reload ────
    async refreshCountSilently() {
        try {
            const reports = await api.getReports();
            const countEl = document.getElementById('profile-report-count');
            if (countEl) countEl.textContent = reports.length;
        } catch (_) {}
    },

    // ── View modal ───────────────────────────────────────────────────────
    async viewReport(reportId) {
        try {
            const report = await api.viewReport(reportId);
            document.getElementById('report-view-title').textContent = report.title;
            document.getElementById('report-view-body').innerHTML = marked.parse(report.content || '');
            document.getElementById('report-view-modal').classList.remove('hidden');
        } catch (e) {
            app.showToast('Could not load report: ' + e.message, 'error');
        }
    },

    closeViewModal() {
        document.getElementById('report-view-modal').classList.add('hidden');
    },

    // ── Delete ───────────────────────────────────────────────────────────
    async deleteReport(reportId) {
        if (!confirm('Delete this report? This cannot be undone.')) return;
        try {
            await api.deleteReport(reportId);
            document.getElementById(`report-card-${reportId}`)?.remove();
            const grid = document.getElementById('reports-grid');
            if (!grid.querySelector('.report-card')) {
                this._renderGrid([]);
            }
            app.showToast('Report deleted.', 'success');
        } catch (e) {
            app.showToast('Delete failed: ' + e.message, 'error');
        }
    },

    // ── Suggestion modal (called from chat.js) ───────────────────────────
    openSuggestModal(title, content) {
        this._pendingContent = content;
        this._pendingTitle = title;
        this._pendingFormat = 'docx';

        const titleInput = document.getElementById('report-title-input');
        if (titleInput) titleInput.value = title;

        // Reset format buttons
        document.querySelectorAll('.format-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.format === 'docx');
        });

        document.getElementById('report-suggest-modal').classList.remove('hidden');
    },

    selectModalFormat(fmt) {
        this._pendingFormat = fmt;
        document.querySelectorAll('.format-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.format === fmt);
        });
    },

    async confirmSuggestModal() {
        const title = (document.getElementById('report-title-input')?.value || this._pendingTitle || 'Untitled Report').trim();
        const content = this._pendingContent || '';
        const fmt = this._pendingFormat || 'docx';

        this.dismissSuggestModal();

        try {
            const saved = await api.saveReport({ title, content, format: fmt });
            app.showToast(`Report "${title}" saved!`, 'success');

            // If the user is on the reports page, refresh it
            const reportsPage = document.getElementById('reports-page');
            if (reportsPage && !reportsPage.classList.contains('hidden')) {
                this.loadReports();
            }
            this.refreshCountSilently();

            // If docx format, also trigger download immediately
            if (fmt === 'docx' && saved.id) {
                api.downloadReport(saved.id, 'docx');
            }
        } catch (e) {
            app.showToast('Failed to save report: ' + e.message, 'error');
        }
    },

    dismissSuggestModal() {
        document.getElementById('report-suggest-modal').classList.add('hidden');
        this._pendingContent = null;
        this._pendingTitle = null;
    },

    // ── Utility ──────────────────────────────────────────────────────────
    _esc(str) {
        return (str || '').replace(/[&<>'"]/g,
            tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
        );
    }
};
