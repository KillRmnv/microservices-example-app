const App = {
    routes: {},
    currentView: null,

    init() {
        this.setupRoutes();
        this.setupAuth();
        window.addEventListener('hashchange', () => this.handleRoute());
        document.getElementById('modal-close').addEventListener('click', () => this.closeModal());
        document.getElementById('modal-overlay').addEventListener('click', (e) => {
            if (e.target.id === 'modal-overlay') this.closeModal();
        });
        this.handleRoute();
    },

    setupRoutes() {
        this.routes = {
            '': () => import('./views/homeView.js').then(m => m.render()),
            '/': () => import('./views/homeView.js').then(m => m.render()),
            '/login': () => import('./views/authView.js').then(m => m.renderLogin()),
            '/register': () => import('./views/authView.js').then(m => m.renderRegister()),
            '/event/:id': (params) => import('./views/eventView.js').then(m => m.render(params.id)),
            '/my-tickets': () => import('./views/myTicketsView.js').then(m => m.render()),
            '/manager/events': () => import('./views/managerView.js').then(m => m.renderEvents()),
            '/manager/event/new': () => import('./views/managerView.js').then(m => m.renderEventForm()),
            '/manager/event/:id/edit': (params) => import('./views/managerView.js').then(m => m.renderEventForm(params.id)),
            '/manager/venues': () => import('./views/managerView.js').then(m => m.renderVenues()),
            '/manager/venue/new': () => import('./views/managerView.js').then(m => m.renderVenueForm()),
            '/manager/venue/:id/edit': (params) => import('./views/managerView.js').then(m => m.renderVenueForm(params.id)),
            '/admin/users': () => import('./views/adminView.js').then(m => m.renderUsers()),
            '/admin/towns': () => import('./views/adminView.js').then(m => m.renderTowns()),
        };
    },

    setupAuth() {
        const body = document.body;
        const authSection = document.getElementById('auth-section');

        if (Auth.isLoggedIn()) {
            body.classList.add('logged-in');
            const role = Auth.getUserRole();
            body.classList.add(`role-${role.toLowerCase()}`);
            
            authSection.innerHTML = `
                <span style="margin-right: 1rem;">${Auth.getUserEmail()}</span>
                <span class="badge badge-${role.toLowerCase()}">${role}</span>
                <button id="logout-btn" class="btn btn-secondary">Выйти</button>
            `;
            document.getElementById('logout-btn').addEventListener('click', () => Auth.logout());
        }
    },

    async handleRoute() {
        const hash = window.location.hash.slice(1) || '/';
        const content = document.getElementById('content');
        const loading = document.getElementById('loading');
        
        content.innerHTML = '';
        loading.classList.remove('hidden');

        try {
            const matched = this.matchRoute(hash);
            if (matched) {
                if (matched.route.startsWith('/admin') && !Auth.canManageUsers()) {
                    content.innerHTML = this.noAccessView();
                } else if (matched.route.startsWith('/manager') && !Auth.canManageEvents()) {
                    content.innerHTML = this.noAccessView();
                } else {
                    await matched.handler(matched.params);
                }
            } else {
                content.innerHTML = '<div class="card"><h2>Страница не найдена</h2></div>';
            }
        } catch (error) {
            console.error('Route error:', error);
            content.innerHTML = `<div class="alert alert-error">Ошибка загрузки: ${error.message}</div>`;
        } finally {
            loading.classList.add('hidden');
        }
    },

    matchRoute(path) {
        for (const [pattern, handler] of Object.entries(this.routes)) {
            if (pattern === path) {
                return { route: pattern, handler, params: {} };
            }

            const paramNames = [];
            const regexPattern = pattern.replace(/:([^/]+)/g, (_, name) => {
                paramNames.push(name);
                return '([^/]+)';
            });

            const regex = new RegExp(`^${regexPattern}$`);
            const match = path.match(regex);

            if (match) {
                const params = {};
                paramNames.forEach((name, i) => {
                    params[name] = match[i + 1];
                });
                return { route: pattern, handler, params };
            }
        }
        return null;
    },

    noAccessView() {
        return `
            <div class="no-access">
                <h2>Доступ запрещен</h2>
                <p>У вас недостаточно прав для просмотра этой страницы.</p>
                <button class="btn btn-primary" onclick="App.navigate('/')">На главную</button>
            </div>
        `;
    },

    navigate(path) {
        window.location.hash = path;
    },

    showModal(content) {
        const overlay = document.getElementById('modal-overlay');
        const modalContent = document.getElementById('modal-content');
        modalContent.innerHTML = content;
        overlay.classList.remove('hidden');
    },

    closeModal() {
        document.getElementById('modal-overlay').classList.add('hidden');
    },

    showAlert(message, type = 'error') {
        const content = document.getElementById('content');
        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.textContent = message;
        content.prepend(alert);
        setTimeout(() => alert.remove(), 5000);
    },

    formatDate(dateStr) {
        if (!dateStr) return '-';
        return new Date(dateStr).toLocaleString('ru-RU');
    },

    escapeHtml(str) {
        if (!str) return '';
        return str.replace(/[&<>"']/g, (m) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[m]));
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());