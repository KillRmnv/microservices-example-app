const EventView = {
    event: null,
    tickets: [],
    seatableTickets: [],

    async render(eventId) {
        const content = document.getElementById('content');
        content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

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
                    <h2>${App.escapeHtml(event.title)}</h2>
                    <span class="badge ${event.admissionMode === 'FREE' ? 'badge-customer' : 'badge-manager'}">
                        ${event.admissionMode === 'FREE' ? 'Бесплатный' : 'Платный'}
                    </span>
                </div>
                
                <div class="event-meta" style="font-size: 1rem;">
                    <span>📍 ${App.escapeHtml(event.venuePlace || '-')}</span>
                    <span>📅 ${App.formatDate(event.startsAt)} - ${App.formatDate(event.endsAt)}</span>
                </div>
            </div>

            <div class="card">
                <h3 class="card-title">Доступные билеты</h3>
                <div id="tickets-container">
                    ${this.renderTickets()}
                </div>
            </div>
        `;

        this.setupBooking();
    },

    renderTickets() {
        const allTickets = [...this.tickets, ...this.seatableTickets];
        
        if (allTickets.length === 0) {
            return '<p>Билеты не найдены</p>';
        }

        return allTickets.map(ticket => `
            <div class="ticket-item available" data-id="${ticket.id}" data-type="${ticket.price ? 'seatable' : 'regular'}">
                <div>
                    <strong>${ticket.price ? `Место: ${ticket.seatRow}-${ticket.seatNumber}` : 'Свободный вход'}</strong>
                    ${ticket.price ? `<br><small>Цена: ${ticket.price}₽ | Ряд: ${ticket.seatRow} | Место: ${ticket.seatNumber}</small>` : ''}
                </div>
                <button class="btn btn-success btn-sm book-btn" data-id="${ticket.id}">Забронировать</button>
            </div>
        `).join('');
    },

    setupBooking() {
        document.querySelectorAll('.book-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const ticketId = btn.dataset.id;
                const ticketType = btn.closest('.ticket-item').dataset.type;
                
                try {
                    if (ticketType === 'seatable') {
                        await API.deleteSeatableTicket(ticketId);
                    } else {
                        await API.deleteTicket(ticketId);
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