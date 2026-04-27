const App = window.App;

export const EventView = {
    event: null,
    tickets: [],
    seatableTickets: [],

    async render(eventId) {
        const content = document.getElementById('content');
        content.innerHTML = '<div class="loading"><div class="spinner"></div><p>Загрузка события...</p></div>';

        try {
            this.event = await API.getEventById(eventId);
            await this.loadTickets();
            this.renderContent();
        } catch (error) {
            content.innerHTML = `<div class="alert alert-error">Ошибка загрузки: ${error.message}</div>`;
        }
    },

    async loadTickets() {
        try {
            this.tickets = await API.getTickets(this.event.id);
        } catch (e) {
            this.tickets = [];
        }
        try {
            this.seatableTickets = await API.getSeatableTickets(this.event.id);
        } catch (e) {
            this.seatableTickets = [];
        }
    },

    renderContent() {
        const content = document.getElementById('content');
        const event = this.event;

        content.innerHTML = `
            <div class="card">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 1rem;">
                    <div>
                        <h2>${App.escapeHtml(event.title)}</h2>
                        <div class="event-meta" style="margin-top: 0.5rem;">
                            <span>📍 ${App.escapeHtml(event.venuePlace || '-')}</span>
                            <span>📅 ${App.formatDate(event.startsAt)} - ${App.formatDate(event.endsAt)}</span>
                        </div>
                    </div>
                    <span class="badge ${event.admissionMode === 'FREE' ? 'badge-customer' : 'badge-manager'}">
                        ${event.admissionMode === 'FREE' ? 'Бесплатный' : 'Платный'}
                    </span>
                </div>
                ${event.description ? `<p style="color: var(--text-secondary); margin-bottom: 1rem;">${App.escapeHtml(event.description)}</p>` : ''}
            </div>

            <div class="card">
                <h3 class="card-title">Доступные билеты</h3>
                <div id="tickets-container">
                    ${this.renderTickets()}
                </div>
            </div>

            <div style="margin-top: 1rem;">
                <button class="btn btn-secondary" onclick="App.navigate('/')">← Назад к событиям</button>
            </div>
        `;

        this.setupBooking();
    },

    renderTickets() {
        const allTickets = [...this.tickets, ...this.seatableTickets];

        if (allTickets.length === 0) {
            return '<p style="text-align: center; color: var(--text-secondary);">Билеты не найдены</p>';
        }

        return `
            <div class="tickets-list">
                ${allTickets.map(ticket => this.renderTicketItem(ticket)).join('')}
            </div>
        `;
    },

    renderTicketItem(ticket) {
        const isSeatable = !!ticket.seatRow;
        const isBooked = !!ticket.userId;

        return `
            <div class="ticket-card ${isBooked ? 'ticket-booked' : 'ticket-available'}" data-id="${ticket.id}" data-type="${isSeatable ? 'seatable' : 'regular'}">
                <div class="ticket-info">
                    <strong>${isSeatable ? `Место: ${ticket.seatRow}-${ticket.seatNumber}` : 'Свободный вход'}</strong>
                    ${ticket.price ? `<br><small>Цена: ${ticket.price}₽</small>` : ''}
                    ${isBooked ? '<br><small style="color: var(--danger);">Уже забронирован</small>' : ''}
                </div>
                ${!isBooked && Auth.isLoggedIn() ? `
                    <button class="btn btn-success btn-sm book-btn" data-id="${ticket.id}" data-type="${isSeatable ? 'seatable' : 'regular'}">
                        Забронировать
                    </button>
                ` : ''}
            </div>
        `;
    },

    setupBooking() {
        document.querySelectorAll('.book-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const ticketId = btn.dataset.id;
                const ticketType = btn.dataset.type;

                if (!Auth.isLoggedIn()) {
                    App.showAlert('Войдите, чтобы забронировать билет', 'error');
                    App.navigate('/login');
                    return;
                }

                try {
                    if (ticketType === 'seatable') {
                        await API.updateSeatableTicket({
                            id: parseInt(ticketId),
                            userId: parseInt(Auth.getUserId())
                        });
                    } else {
                        await API.updateTicket({
                            id: parseInt(ticketId),
                            userId: parseInt(Auth.getUserId())
                        });
                    }
                    App.showAlert('Билет успешно забронирован!', 'success');
                    await this.loadTickets();
                    this.renderContent();
                } catch (error) {
                    App.showAlert('Ошибка бронирования: ' + error.message, 'error');
                }
            });
        });
    }
};
