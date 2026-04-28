const App = window.App;

export const ManagerView = {
    async renderEvents() {
        const content = document.getElementById('content');
        content.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h2>Управление событиями</h2>
                <button class="btn btn-success" id="create-event-btn">+ Создать событие</button>
            </div>
            <div class="search-bar">
                <input type="text" id="search-title" placeholder="Поиск по названию...">
                <select id="search-admission">
                    <option value="">Все типы</option>
                    <option value="SEATABLE">Размещенные места</option>
                    <option value="GENERAL">Общий вход</option>
                </select>
                <button class="btn btn-primary" id="search-btn">Найти</button>
            </div>
            <div id="events-container"></div>
        `;

        document.getElementById('create-event-btn').addEventListener('click', () => {
            App.navigate('/manager/event/new');
        });

        document.getElementById('search-btn').addEventListener('click', () => {
            this.loadEvents();
        });

        await this.loadEvents();
    },

    async loadEvents() {
        const container = document.getElementById('events-container');
        container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        try {
            const filter = {
                title: document.getElementById('search-title')?.value || '',
                admissionMode: document.getElementById('search-admission')?.value || ''
            };
            const events = await API.searchEvents(filter, 1, 100);
            this.renderEventsTable(events);
        } catch (error) {
            container.innerHTML = `<div class="alert alert-error">Ошибка: ${error.message}</div>`;
        }
    },

    renderEventsTable(events) {
        const container = document.getElementById('events-container');

        if (!events || events.length === 0) {
            container.innerHTML = '<div class="card"><p>События не найдены</p></div>';
            return;
        }

        container.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Название</th>
                        <th>Площадка</th>
                        <th>Начало</th>
                        <th>Тип входа</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
                    ${events.map(e => `
                        <tr>
                            <td>${e.id}</td>
                            <td>${App.escapeHtml(e.title)}</td>
                            <td>${App.escapeHtml(e.venuePlace || '-')}</td>
                            <td>${App.formatDate(e.startsAt)}</td>
                            <td><span class="badge ${e.admissionMode === 'GENERAL' ? 'badge-customer' : 'badge-manager'}">${e.admissionMode === 'SEATABLE' ? 'Размещенные места' : 'Общий вход'}</span></td>
                            <td class="actions">
                                <button class="btn btn-secondary btn-sm edit-event" data-id="${e.id}">Ред.</button>
                                <button class="btn btn-danger btn-sm delete-event" data-id="${e.id}">Удалить</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        // Use event delegation for edit and delete buttons
        container.onclick = (e) => {
            const editButton = e.target.closest('.edit-event');
            if (editButton) {
                const id = parseInt(editButton.dataset.id);
                this.renderEventForm(id);
                return;
            }
            const deleteButton = e.target.closest('.delete-event');
            if (deleteButton) {
                const id = parseInt(deleteButton.dataset.id);
                this.deleteEvent(id);
            }
        };
    },

    formatDateTimeLocal(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        return date.toISOString().slice(0, 16);
    },

    async renderEventForm(eventId = null) {
        const content = document.getElementById('content');
        content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        let event = null;
        let venues = [];

        try {
            venues = await API.getVenues();
            if (eventId) {
                event = await API.getEventById(eventId);
            }
        } catch (e) {
            content.innerHTML = `<div class="alert alert-error">Ошибка загрузки: ${e.message}</div>`;
            return;
        }

        content.innerHTML = `
            <div class="card" style="max-width: 600px; margin: 0 auto;">
                <h2 class="card-title">${event ? 'Редактирование события' : 'Создание события'}</h2>
                <form id="event-form">
                    <div class="form-group">
                        <label for="title">Название *</label>
                        <input type="text" id="title" required value="${event?.title || ''}">
                    </div>
                    <div class="form-group">
                        <label for="venueId">Площадка *</label>
                        <select id="venueId" required>
                            <option value="">Выберите площадку</option>
                            ${venues.map(v => `<option value="${v.id}" ${event?.venueId === v.id ? 'selected' : ''}>${App.escapeHtml(v.place)}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="startsAt">Начало *</label>
                            <input type="datetime-local" id="startsAt" required value="${this.formatDateTimeLocal(event?.startsAt)}">
                        </div>
                        <div class="form-group">
                            <label for="endsAt">Окончание *</label>
                            <input type="datetime-local" id="endsAt" required value="${this.formatDateTimeLocal(event?.endsAt)}">
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="admissionMode">Тип входа *</label>
                        <select id="admissionMode" required>
                            <option value="SEATABLE" ${event?.admissionMode === 'SEATABLE' ? 'selected' : ''}>Размещенные места</option>
                            <option value="GENERAL" ${event?.admissionMode === 'GENERAL' ? 'selected' : ''}>Общий вход</option>
                        </select>
                    </div>
                    <div id="form-error" class="alert alert-error hidden"></div>
                    <div style="display: flex; gap: 1rem;">
                        <button type="submit" class="btn btn-success">Сохранить</button>
                        <button type="button" class="btn btn-secondary" onclick="App.navigate('/manager/events')">Отмена</button>
                    </div>
                </form>
            </div>
        `;

        document.getElementById('event-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const data = {
                title: document.getElementById('title').value,
                venueId: parseInt(document.getElementById('venueId').value),
                startsAt: document.getElementById('startsAt').value,
                endsAt: document.getElementById('endsAt').value,
                admissionMode: document.getElementById('admissionMode').value
            };

            if (!data.title || !data.venueId || !data.startsAt || !data.endsAt) {
                const errorDiv = document.getElementById('form-error');
                errorDiv.textContent = 'Заполните все обязательные поля';
                errorDiv.classList.remove('hidden');
                return;
            }

            try {
                if (eventId) {
                    data.id = eventId;
                    await API.updateEvent(data);
                    App.showAlert('Событие обновлено!', 'success');
                } else {
                    await API.createEvent(data);
                    App.showAlert('Событие создано!', 'success');
                }
                App.navigate('/manager/events');
            } catch (error) {
                const errorDiv = document.getElementById('form-error');
                errorDiv.textContent = error.message;
                errorDiv.classList.remove('hidden');
            }
        });
    },

    async deleteEvent(id) {
        if (!confirm('Удалить событие?')) return;
        try {
            await API.deleteEvent(id);
            App.showAlert('Событие удалено', 'success');
            await this.loadEvents();
        } catch (error) {
            App.showAlert('Ошибка: ' + error.message);
        }
    },

    async renderVenues() {
        const content = document.getElementById('content');
        content.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h2>Управление площадками</h2>
                <button class="btn btn-success" id="create-venue-btn">+ Создать площадку</button>
            </div>
            <div id="venues-container"></div>
        `;

        document.getElementById('create-venue-btn').addEventListener('click', () => {
            App.navigate('/manager/venue/new');
        });

        await this.loadVenues();
    },

    async loadVenues() {
        const container = document.getElementById('venues-container');
        container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        try {
            const venues = await API.getVenues();
            this.renderVenuesTable(venues);
        } catch (error) {
            container.innerHTML = `<div class="alert alert-error">Ошибка: ${error.message}</div>`;
        }
    },

    renderVenuesTable(venues) {
        const container = document.getElementById('venues-container');

        if (!venues || venues.length === 0) {
            container.innerHTML = '<div class="card"><p>Площадки не найдены</p></div>';
            return;
        }

        container.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Название</th>
                        <th>Город</th>
                        <th>Вместимость</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
                    ${venues.map(v => `
                        <tr>
                            <td>${v.id}</td>
                            <td>${App.escapeHtml(v.place)}</td>
                            <td>${App.escapeHtml(v.townName || '-')}</td>
                            <td>${v.capacity || '-'}</td>
                            <td class="actions">
                                <button class="btn btn-secondary btn-sm edit-venue" data-id="${v.id}">Ред.</button>
                                <button class="btn btn-danger btn-sm delete-venue" data-id="${v.id}">Удалить</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        // Attach event listeners for edit and delete buttons
        container.querySelectorAll('.edit-venue').forEach(button => {
            button.addEventListener('click', () => {
                const id = parseInt(button.dataset.id);
                this.renderVenueForm(id);
            });
        });

        container.querySelectorAll('.delete-venue').forEach(button => {
            button.addEventListener('click', () => {
                const id = parseInt(button.dataset.id);
                this.deleteVenue(id);
            });
        });
    },

    async renderVenueForm(venueId = null) {
        const content = document.getElementById('content');
        content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        let venue = null;
        let towns = [];

        try {
            towns = await API.getTowns();
            if (venueId) {
                venue = await API.getVenueById(venueId);
            }
        } catch (e) {
            content.innerHTML = `<div class="alert alert-error">Ошибка загрузки: ${e.message}</div>`;
            return;
        }

        content.innerHTML = `
            <div class="card" style="max-width: 600px; margin: 0 auto;">
                <h2 class="card-title">${venue ? 'Редактирование площадки' : 'Создание площадки'}</h2>
                <form id="venue-form">
                    <div class="form-group">
                        <label for="place">Название *</label>
                        <input type="text" id="place" required value="${venue?.place || ''}">
                    </div>
                    <div class="form-group">
                        <label for="townId">Город *</label>
                        <select id="townId" required>
                            <option value="">Выберите город</option>
                            ${towns.map(t => `<option value="${t.id}" ${venue?.townId === t.id ? 'selected' : ''}>${App.escapeHtml(t.name)}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="capacity">Вместимость</label>
                        <input type="number" id="capacity" min="1" value="${venue?.capacity || ''}">
                    </div>
                    <div id="form-error" class="alert alert-error hidden"></div>
                    <div style="display: flex; gap: 1rem;">
                        <button type="submit" class="btn btn-success">Сохранить</button>
                        <button type="button" class="btn btn-secondary" onclick="App.navigate('/manager/venues')">Отмена</button>
                    </div>
                </form>
            </div>
        `;

        document.getElementById('venue-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const data = {
                place: document.getElementById('place').value,
                townId: parseInt(document.getElementById('townId').value),
                capacity: parseInt(document.getElementById('capacity').value) || null
            };

            if (!data.place || !data.townId) {
                const errorDiv = document.getElementById('form-error');
                errorDiv.textContent = 'Заполните все обязательные поля';
                errorDiv.classList.remove('hidden');
                return;
            }

            try {
                if (venueId) {
                    data.id = venueId;
                    await API.updateVenue(data);
                    App.showAlert('Площадка обновлена!', 'success');
                } else {
                    await API.createVenue(data);
                    App.showAlert('Площадка создана!', 'success');
                }
                App.navigate('/manager/venues');
            } catch (error) {
                const errorDiv = document.getElementById('form-error');
                errorDiv.textContent = error.message;
                errorDiv.classList.remove('hidden');
            }
        });
    },

    async deleteVenue(id) {
        if (!confirm('Удалить площадку?')) return;
        try {
            await API.deleteVenue(id);
            App.showAlert('Площадка удалена', 'success');
            await this.loadVenues();
        } catch (error) {
            App.showAlert('Ошибка: ' + error.message);
        }
    }
};

