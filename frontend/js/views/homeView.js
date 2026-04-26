const HomeView = {
    currentPage: 1,
    pageSize: 12,
    filter: {},

    async render() {
        const content = document.getElementById('content');
        content.innerHTML = `
            <div class="search-bar">
                <input type="text" id="search-title" placeholder="Поиск по названию...">
                <select id="search-admission">
                    <option value="">Все типы входа</option>
                    <option value="FREE">Бесплатный</option>
                    <option value="PAID">Платный</option>
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
                    <span>📍 ${App.escapeHtml(event.venuePlace || '-')}</span>
                    <span>📅 ${App.formatDate(event.startsAt)}</span>
                </div>
                <div class="event-meta">
                    <span class="badge ${event.admissionMode === 'FREE' ? 'badge-customer' : 'badge-manager'}">
                        ${event.admissionMode === 'FREE' ? 'Бесплатный' : 'Платный'}
                    </span>
                </div>
            </div>
        `).join('');

        grid.querySelectorAll('.event-card').forEach(card => {
            card.addEventListener('click', () => {
                App.navigate(`/event/${card.dataset.id}`);
            });
        });
    }
};