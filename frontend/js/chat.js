const chatApp = {
    messagesContainer: document.getElementById('chat-messages'),
    inputField: document.getElementById('chat-input'),
    agentStatus: document.getElementById('agent-status'),
    lastQuery: '',
    pendingReport: null, // { content, suggestedTitle, format } awaiting modal decision

    bind() {
        this.inputField.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
    },

    onAgentModeChange(mode) {
        const banner = document.getElementById('rag-context-banner');
        if (banner) {
            if (mode === 'rag' || mode === 'summary') {
                banner.classList.remove('hidden');
            } else {
                banner.classList.add('hidden');
            }
        }
    },

    clearChat() {
        this.messagesContainer.innerHTML = `
            <div class="message assistant-msg welcome-msg">
                <div class="avatar"><i class="fa-solid fa-robot"></i></div>
                <div class="content">
                    <p>Hello! I am your Enterprise AI Assistant. How can I help you today?</p>
                </div>
            </div>`;
    },

    async sendMessage() {
        const text = this.inputField.value.trim();
        if (!text) return;

        // Append user message
        this.appendMessage('user', text);
        this.inputField.value = '';
        this.inputField.style.height = 'auto'; // Reset size
        this.lastQuery = text;

        const agentMode = document.getElementById('agent-mode').value;
        this.agentStatus.textContent = 'Agent is processing...';
        this.agentStatus.style.color = 'var(--text-primary)';

        // Append loading assistant
        const loadingId = 'loading-' + Date.now();
        this.appendMessage('assistant', '<i class="fa-solid fa-circle-notch fa-spin"></i> Generating response...', loadingId);

        try {
            const response = await api.askQuestion(text, { agent: agentMode });
            this.updateMessage(loadingId, response.response || "No response provided", response.sources);
            this.agentStatus.textContent = 'Standing by...';
            this.agentStatus.style.color = 'var(--text-secondary)';

            // Report pipeline: backend decides (via LLM) whether this answer is
            // worth keeping as a report. If so it is auto-saved in the background,
            // and the user is also offered a popup to name/confirm/reformat it.
            if (response.report_suggested && response.response) {
                this.handleReportSuggestion(text, response.response, response.suggested_title);
            }

        } catch (error) {
            this.updateMessage(loadingId, `**Error:** Failed to reach backend. ${error.message}`);
            this.agentStatus.textContent = 'Error processing request.';
            this.agentStatus.style.color = 'var(--error)';
        }
    },

    appendMessage(role, content, id = null) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}-msg`;
        if (id) msgDiv.id = id;

        const avatarIcon = role === 'user' ? 'fa-user' : 'fa-robot';
        
        let parsedContent = content;
        if(role !== 'user' && !content.includes('fa-spin')) {
             parsedContent = marked.parse(content);
        }

        msgDiv.innerHTML = `
            <div class="avatar"><i class="fa-solid ${avatarIcon}"></i></div>
            <div class="content">${role === 'user' ? `<p>${this.escapeHTML(content)}</p>` : parsedContent}</div>
        `;

        this.messagesContainer.appendChild(msgDiv);
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    },

    updateMessage(id, markdownContent, sources) {
        const msgDiv = document.getElementById(id);
        if (msgDiv) {
            let finalHTML = marked.parse(markdownContent);
            if (sources && sources.length > 0) {
                // Extract unique source filenames from the context strings like "[filename] (score=0.82) text..."
                const sourceNames = [...new Set(
                    sources.map(s => {
                        const m = s.match(/^\[([^\]]+)\]/);
                        return m ? m[1] : null;
                    }).filter(Boolean)
                )];
                if (sourceNames.length > 0) {
                    const pills = sourceNames.map(name => {
                        const ext = name.split('.').pop().toLowerCase();
                        let icon = 'fa-file';
                        if (ext === 'pdf')  icon = 'fa-file-pdf';
                        else if (ext === 'docx') icon = 'fa-file-word';
                        else if (['csv','xlsx','xls'].includes(ext)) icon = 'fa-file-excel';
                        else if (['png','jpg','jpeg','webp','gif'].includes(ext)) icon = 'fa-file-image';
                        else if (['txt','md'].includes(ext)) icon = 'fa-file-lines';
                        return `<span class="source-pill"><i class="fa-regular ${icon}"></i> ${name}</span>`;
                    }).join('');
                    finalHTML += `<div class="source-citations"><span class="source-label"><i class="fa-solid fa-book-open"></i> From your documents:</span>${pills}</div>`;
                }
            }
            msgDiv.querySelector('.content').innerHTML = finalHTML;
        }
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    },

    // ── Report suggestion pipeline ──────────────────────────────────────────
    async handleReportSuggestion(query, answerContent, suggestedTitle) {
        const title = suggestedTitle || this.deriveTitleFromQuery(query);

        // 1) Silent auto-save as markdown in the background, regardless of
        //    whether the user engages with the popup at all.
        try {
            await api.saveReport({ title, content: answerContent, format: 'markdown' });
            if (window.reportApp) reportApp.refreshCountSilently();
        } catch (e) {
            console.error('Auto-save report failed:', e);
        }

        // 2) Also surface the popup so the user can name it and choose to keep
        //    a nicely formatted copy (docx or markdown) on top of the auto-save.
        if (window.reportApp) {
            reportApp.openSuggestModal(title, answerContent);
        }
    },

    deriveTitleFromQuery(query) {
        const words = query.replace(/[?!.]+$/, '').split(/\s+/).slice(0, 10).join(' ');
        return words.charAt(0).toUpperCase() + words.slice(1);
    },

    escapeHTML(str) {
        return str.replace(/[&<>'"]/g, 
            tag => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                "'": '&#39;',
                '"': '&quot;'
            }[tag] || tag)
        );
    }
};

document.addEventListener('DOMContentLoaded', () => {
    if(document.getElementById('chat-input')) {
        chatApp.bind();
    }
});
