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
                <select id="search-venue">
                    <option value="">Все площадки</option>
                </select>
                <input type="date" id="search-starts-from" placeholder="Начало с...">
                <input type="date" id="search-starts-to" placeholder="Начало по...">
                <button class="btn btn-primary" id="search-btn">Найти</button>
                <button class="btn btn-secondary" id="reset-btn">Сбросить</button>
            </div>
            <div id="events-container"></div>
        `;

        await this.loadVenuesForFilter();

        document.getElementById('create-event-btn').addEventListener('click', () => {
            App.navigate('/manager/event/new');
        });

        document.getElementById('search-btn').addEventListener('click', () => {
            ManagerView.loadEvents();
        });

        document.getElementById('reset-btn').addEventListener('click', () => {
            document.getElementById('search-title').value = '';
            document.getElementById('search-admission').value = '';
            document.getElementById('search-venue').value = '';
            document.getElementById('search-starts-from').value = '';
            document.getElementById('search-starts-to').value = '';
            ManagerView.loadEvents();
        });

        await ManagerView.loadEvents();
    },

    async loadVenuesForFilter() {
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

    async loadEvents() {
        const container = document.getElementById('events-container');
        container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        try {
            const filter = {
                title: document.getElementById('search-title')?.value || '',
                admissionMode: document.getElementById('search-admission')?.value || '',
                venueId: document.getElementById('search-venue')?.value || null,
                startsFrom: document.getElementById('search-starts-from')?.value || null,
                startsTo: document.getElementById('search-starts-to')?.value || null
            };
            const events = await API.searchEvents(filter, 1, 100);
            ManagerView.renderEventsTable(events);
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
                ManagerView.renderEventForm(id);
                return;
            }
            const deleteButton = e.target.closest('.delete-event');
            if (deleteButton) {
                const id = parseInt(deleteButton.dataset.id);
                ManagerView.deleteEvent(id);
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
                            <input type="datetime-local" id="startsAt" required value="${ManagerView.formatDateTimeLocal(event?.startsAt)}">
                        </div>
                        <div class="form-group">
                            <label for="endsAt">Окончание *</label>
                            <input type="datetime-local" id="endsAt" required value="${ManagerView.formatDateTimeLocal(event?.endsAt)}">
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
                        <button type="submit" class="btn btn-success" id="save-event-btn">Сохранить</button>
                        <button type="button" class="btn btn-secondary" id="cancel-event-btn">Отмена</button>
                    </div>
                </form>
            </div>
        `;

        // Cancel button - directly render events list
        document.getElementById('cancel-event-btn').addEventListener('click', () => {
            ManagerView.renderEvents();
        });

        // Form submission - save and navigate back
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
                // Directly render events list
                await ManagerView.renderEvents();
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
            await ManagerView.loadEvents();
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
            <div class="search-bar">
                <input type="text" id="search-place" placeholder="Поиск по названию...">
                <select id="search-town">
                    <option value="">Все города</option>
                </select>
                <input type="number" id="search-min-capacity" placeholder="Вместимость от..." min="0">
                <input type="number" id="search-max-capacity" placeholder="Вместимость до..." min="0">
                <button class="btn btn-primary" id="search-btn">Найти</button>
                <button class="btn btn-secondary" id="reset-btn">Сбросить</button>
            </div>
            <div id="venues-container"></div>
        `;

        await this.loadTownsForFilter();

        document.getElementById('create-venue-btn').addEventListener('click', () => {
            App.navigate('/manager/venue/new');
        });

        document.getElementById('search-btn').addEventListener('click', () => {
            ManagerView.loadVenues();
        });

        document.getElementById('reset-btn').addEventListener('click', () => {
            document.getElementById('search-place').value = '';
            document.getElementById('search-town').value = '';
            document.getElementById('search-min-capacity').value = '';
            document.getElementById('search-max-capacity').value = '';
            ManagerView.loadVenues();
        });

        await ManagerView.loadVenues();
    },

    async loadTownsForFilter() {
        try {
            const towns = await API.getTowns();
            const select = document.getElementById('search-town');
            towns.forEach(town => {
                const opt = document.createElement('option');
                opt.value = town.id;
                opt.textContent = town.name;
                select.appendChild(opt);
            });
        } catch (e) {
            console.error('Failed to load towns:', e);
        }
    },

    async loadVenues() {
        const container = document.getElementById('venues-container');
        container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        try {
            const filter = {
                place: document.getElementById('search-place')?.value || '',
                townId: document.getElementById('search-town')?.value || null,
                minCapacity: document.getElementById('search-min-capacity')?.value || null,
                maxCapacity: document.getElementById('search-max-capacity')?.value || null
            };
            const venues = await API.searchVenues(filter, 1, 100);
            ManagerView.renderVenuesTable(venues);
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
                        <th>Название</th>
                        <th>Город</th>
                        <th>Вместимость</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
                    ${venues.map(v => `
                        <tr>
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
                ManagerView.renderVenueForm(id);
            });
        });

        container.querySelectorAll('.delete-venue').forEach(button => {
            button.addEventListener('click', () => {
                const id = parseInt(button.dataset.id);
                ManagerView.deleteVenue(id);
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
                        <button type="button" class="btn btn-secondary" id="cancel-venue-btn">Отмена</button>
                    </div>
                </form>
            </div>
        `;

        // Add event listener for cancel button
        document.getElementById('cancel-venue-btn').addEventListener('click', () => {
            window.location.hash = '/manager/venues';
        });

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
                // Directly render venues list
                await ManagerView.renderVenues();
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
            await ManagerView.loadVenues();
        } catch (error) {
            App.showAlert('Ошибка: ' + error.message);
        }
    }
};

