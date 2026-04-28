const App = window.App;

export const HomeView = {
    currentPage: 1,
    pageSize: 12,
    filter: {},
    totalPages: 1,

    async render() {
        const content = document.getElementById('content');
        content.innerHTML = `
            <div class="search-bar">
                <input type="text" id="search-title" placeholder="Поиск по названию...">
                <select id="search-admission">
                    <option value="">Все типы входа</option>
                    <option value="SEATABLE">Размещенные места</option>
                    <option value="GENERAL">Общий вход</option>
                </select>
                <select id="search-venue">
                    <option value="">Все площадки</option>
                </select>
                <button class="btn btn-primary" id="search-btn">Найти</button>
                <button class="btn btn-secondary" id="reset-btn">Сбросить</button>
            </div>
            <div id="events-grid" class="card-grid"></div>
            <div id="pagination" class="pagination"></div>
        `;

        await this.loadVenues();
        this.setupListeners();
        await this.loadEvents();
    },

    async loadVenues() {
        try {
            const venues = await API.getVenues();
            const select = document.getElementById('search-venue');
            venues.forEach(venue => {
                const opt = document.createElement('option');
                opt.value = venue.id;
                opt.textContent = venue.place;
                select.appendChild(opt);
            });
        } catch (e) {
            console.error('Failed to load venues:', e);
        }
    },

    setupListeners() {
        document.getElementById('search-btn').addEventListener('click', () => {
            this.filter = this.getFilter();
            this.currentPage = 1;
            this.loadEvents();
        });

        document.getElementById('reset-btn').addEventListener('click', () => {
            document.getElementById('search-title').value = '';
            document.getElementById('search-admission').value = '';
            document.getElementById('search-venue').value = '';
            this.filter = {};
            this.currentPage = 1;
            this.loadEvents();
        });
    },

    getFilter() {
        return {
            title: document.getElementById('search-title').value,
            admissionMode: document.getElementById('search-admission').value,
            venueId: document.getElementById('search-venue').value || null
        };
    },

    async loadEvents() {
        const grid = document.getElementById('events-grid');
        grid.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        try {
            const events = await API.searchEvents(this.filter, this.currentPage, this.pageSize);
            this.renderEvents(events);
            this.renderPagination();
        } catch (error) {
            grid.innerHTML = `<div class="alert alert-error">Ошибка загрузки: ${error.message}</div>`;
        }
    },

    renderEvents(events) {
        const grid = document.getElementById('events-grid');

        if (!events || events.length === 0) {
            grid.innerHTML = '<div class="card"><p style="text-align:center">События не найдены</p></div>';
            return;
        }

        grid.innerHTML = events.map(event => `
            <div class="card event-card" data-id="${event.id}">
                <h3>${App.escapeHtml(event.title)}</h3>
                <div class="event-meta">
                    <span>${event.venuePlace || '-'}</span>
                    <span>${App.formatDate(event.startsAt)}</span>
                </div>
                <div class="event-meta" style="margin-top: 0.5rem;">
                    <span class="badge ${event.admissionMode === 'GENERAL' ? 'badge-customer' : 'badge-manager'}">
                        ${event.admissionMode === 'SEATABLE' ? 'Размещенные места' : 'Общий вход'}
                    </span>
                </div>
            </div>
        `).join('');

        grid.querySelectorAll('.event-card').forEach(card => {
            card.addEventListener('click', () => {
                App.navigate(`/event/${card.dataset.id}`);
            });
        });
    },

    renderPagination() {
        const pagination = document.getElementById('pagination');
        if (this.totalPages <= 1) {
            pagination.innerHTML = '';
            return;
        }

        let buttons = '';
        const maxVisible = 5;
        let start = Math.max(1, this.currentPage - Math.floor(maxVisible / 2));
        let end = Math.min(this.totalPages, start + maxVisible - 1);

        if (this.currentPage > 1) {
            buttons += `<button class="page-btn" data-page="${this.currentPage - 1}">← Назад</button>`;
        }

        for (let i = start; i <= end; i++) {
            buttons += `<button class="${i === this.currentPage ? 'active' : ''} page-btn" data-page="${i}">${i}</button>`;
        }

        if (this.currentPage < this.totalPages) {
            buttons += `<button class="page-btn" data-page="${this.currentPage + 1}">Вперед →</button>`;
        }

        pagination.innerHTML = buttons;

        // Attach event listeners for pagination buttons
        pagination.querySelectorAll('.page-btn').forEach(button => {
            button.addEventListener('click', () => {
                const page = parseInt(button.dataset.page);
                this.goToPage(page);
            });
        });
    },

    goToPage(page) {
        this.currentPage = page;
        this.loadEvents();
    }
};
