const app = {
    init() {
        auth.check();
        this.loadProfile();
        this.bindEvents();
    },

    bindEvents() {
        // If the window is resized from mobile back to desktop width,
        // clear the mobile slide-out state (don't touch desktop collapse state).
        window.addEventListener('resize', () => {
            if (window.innerWidth > 768) {
                const sidebar = document.getElementById('sidebar');
                const overlay = document.getElementById('sidebar-overlay');
                if (sidebar) sidebar.classList.remove('open');
                if (overlay) overlay.classList.remove('open');
            }
        });
    },

    openSidebar() {
        if (window.innerWidth <= 768) {
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('sidebar-overlay');
            if (sidebar) sidebar.classList.add('open');
            if (overlay) overlay.classList.add('open');
        } else {
            const layout = document.getElementById('app-layout');
            if (layout) layout.classList.remove('sidebar-collapsed');
        }
    },

    closeSidebar() {
        if (window.innerWidth <= 768) {
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('sidebar-overlay');
            if (sidebar) sidebar.classList.remove('open');
            if (overlay) overlay.classList.remove('open');
        } else {
            const layout = document.getElementById('app-layout');
            if (layout) layout.classList.add('sidebar-collapsed');
        }
    },

    toggleSidebar() {
        if (window.innerWidth <= 768) {
            const sidebar = document.getElementById('sidebar');
            if (sidebar && sidebar.classList.contains('open')) {
                this.closeSidebar();
            } else {
                this.openSidebar();
            }
        } else {
            const layout = document.getElementById('app-layout');
            if (layout && layout.classList.contains('sidebar-collapsed')) {
                this.openSidebar();
            } else {
                this.closeSidebar();
            }
        }
    },

    navigate(pageId) {
        // Hide all pages
        document.querySelectorAll('.page-section').forEach(section => {
            section.classList.add('hidden');
            section.classList.remove('active');
        });
        
        // Remove active class from nav
        document.querySelectorAll('.nav-links li').forEach(li => {
            li.classList.remove('active');
        });
        
        // Show selected page
        const targetPage = document.getElementById(pageId);
        if (targetPage) {
            targetPage.classList.remove('hidden');
            targetPage.classList.add('active');
        }
        
        // Highlight nav item
        const navItem = document.querySelector(`.nav-links li[data-page="${pageId}"]`);
        if (navItem) navItem.classList.add('active');

        // On mobile, close the slide-out sidebar after picking a page
        if (window.innerWidth <= 768) this.closeSidebar();

        // Trigger specific page logic
        if (pageId === 'documents-page') docApp.loadDocuments();
        if (pageId === 'reports-page') reportApp.loadReports();
    },

    toggleTheme() {
        const html = document.documentElement;
        if (html.getAttribute('data-theme') === 'dark') {
            html.setAttribute('data-theme', 'light');
        } else {
            html.setAttribute('data-theme', 'dark');
        }
    },

    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        let icon = 'fa-circle-info';
        if(type === 'success') icon = 'fa-circle-check';
        if(type === 'error') icon = 'fa-triangle-exclamation';
        
        toast.innerHTML = `<i class="fa-solid ${icon}"></i>  ${message}`;
        container.appendChild(toast);
        
        setTimeout(() => toast.remove(), 4000);
    },

    startNewChat() {
        chatApp.clearChat();
        this.navigate('chat-page');
    },

    async loadProfile() {
        try {
            const user = await api.getProfile();
            document.getElementById('profile-name').textContent = "Administrator";
            document.getElementById('profile-email').textContent = user.email;
        } catch (e) {
            console.error("Profile load err", e);
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    if(!window.location.pathname.endsWith('login.html')){
        app.init();
    }
});
