const app = {
    init() {
        auth.check();
        this.loadProfile();
        this.bindEvents();
    },

    bindEvents() {
        // Just general events can go here
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
