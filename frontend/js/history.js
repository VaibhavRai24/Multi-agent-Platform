/* history.js
   Manages the "last 5 sessions" sidebar panel.
   Depends on: api.js (api object), chat.js (chatApp object), app.js (app object)
   Must be loaded AFTER api.js and app.js but BEFORE chat.js in index.html.
*/

const historyApp = {
    MAX_SESSIONS: 5,
    _listEl: null,

    init() {
        this._listEl = document.getElementById('chat-history-list');
        if (!this._listEl) return;
        this.refresh(null);
    },

    /* ── Fetch sessions from backend and re-render the list ── */
    async refresh(activeId = null) {
        if (!this._listEl) return;
        try {
            const sessions = await api.getChatSessions();
            this._render(sessions, activeId ?? (chatApp && chatApp.activeChatId));
        } catch (e) {
            console.warn('history: could not load sessions', e);
        }
    },

    /* ── Build DOM ─────────────────────────────────────────── */
    _render(sessions, activeId) {
        this._listEl.innerHTML = '';

        if (!sessions || sessions.length === 0) {
            const empty = document.createElement('li');
            empty.className = 'history-empty';
            empty.textContent = 'No recent chats yet.';
            this._listEl.appendChild(empty);
            return;
        }

        sessions.slice(0, this.MAX_SESSIONS).forEach(session => {
            const li = document.createElement('li');
            li.className = 'history-item';
            if (session.id === activeId) li.classList.add('active-session');

            li.innerHTML = `
                <i class="fa-regular fa-message"></i>
                <div class="history-item-text">
                    <span class="history-item-title" title="${this._esc(session.title)}">${this._esc(session.title)}</span>
                    <span class="history-item-date">${this._esc(session.date || '')}</span>
                </div>
                <button class="history-delete-btn" title="Delete this chat" data-id="${session.id}">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            `;

            /* Click on the row (not the delete btn) → load session */
            li.addEventListener('click', (e) => {
                if (e.target.closest('.history-delete-btn')) return;
                this._openSession(session.id, li);
            });

            /* Click on delete btn */
            li.querySelector('.history-delete-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                this._deleteSession(session.id);
            });

            this._listEl.appendChild(li);
        });
    },

    /* ── Load a session's messages into the chat pane ─────── */
    async _openSession(chatId, rowEl) {
        try {
            app.navigate('chat-page');

            /* Highlight the row immediately for snappy UX */
            this._listEl.querySelectorAll('.history-item').forEach(li =>
                li.classList.remove('active-session')
            );
            rowEl.classList.add('active-session');

            const session = await api.getChatSession(chatId);
            if (chatApp && typeof chatApp.loadSessionMessages === 'function') {
                chatApp.loadSessionMessages(session.id, session.messages);
            }
        } catch (e) {
            console.error('history: failed to open session', e);
            if (window.app) app.showToast('Could not load that chat.', 'error');
        }
    },

    /* ── Delete a session, then refresh ───────────────────── */
    async _deleteSession(chatId) {
        try {
            await api.deleteChatSession(chatId);

            /* If the deleted session was the active one, clear the chat pane */
            if (chatApp && chatApp.activeChatId === chatId) {
                chatApp.clearChat();
            }

            await this.refresh(chatApp ? chatApp.activeChatId : null);
            if (window.app) app.showToast('Chat deleted.', 'success');
        } catch (e) {
            console.error('history: delete failed', e);
            if (window.app) app.showToast('Could not delete chat.', 'error');
        }
    },

    /* ── Small HTML-escape util ───────────────────────────── */
    _esc(str) {
        return String(str).replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }
};

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('chat-history-list')) {
        historyApp.init();
    }
});
