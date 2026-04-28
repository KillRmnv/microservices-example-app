const App = window.App;

export const MyTicketsView = {
    async render() {
        const content = document.getElementById('content');

        if (!Auth.isLoggedIn()) {
            content.innerHTML = `
                <div class="card" style="max-width: 500px; margin: 2rem auto;">
                    <h2>Мои билеты</h2>
                    <p>Пожалуйста, <a href="#/login">войдите</a> для просмотра ваших билетов.</p>
                </div>
            `;
            return;
        }

        content.innerHTML = `
            <div class="card">
                <h2>Мои билеты</h2>
                <div id="tickets-loading" class="loading">
                    <div class="spinner"></div>
                    <p>Загрузка билетов...</p>
                </div>
                <div id="tickets-content" class="hidden"></div>
            </div>
        `;

        try {
            const userId = Auth.getUserId();
            if (!userId) {
                console.warn('[MyTickets] No user ID found, skipping updateUserInfo');
                // await Auth.updateUserInfo(); // Removed to prevent role overwrite
            }

            const { tickets, seatableTickets } = await API.getMyTickets(Auth.getUserId());
            this.renderTickets(tickets, seatableTickets);
        } catch (error) {
            document.getElementById('tickets-loading').innerHTML = `
                <div class="alert alert-error">Ошибка загрузки: ${error.message}</div>
            `;
        }
    },

    renderTickets(tickets, seatableTickets) {
        const loading = document.getElementById('tickets-loading');
        const content = document.getElementById('tickets-content');

        loading.classList.add('hidden');
        content.classList.remove('hidden');

        const allTickets = [
            ...tickets.map(t => ({ ...t, type: 'regular' })),
            ...seatableTickets.map(t => ({ ...t, type: 'seatable' }))
        ];

        if (allTickets.length === 0) {
            content.innerHTML = `
                <div class="empty-state">
                    <p>У вас пока нет забронированных билетов.</p>
                    <a href="#/" class="btn btn-primary">Перейти к событиям</a>
                </div>
            `;
            return;
        }

        content.innerHTML = `
            <div class="tickets-list">
                ${allTickets.map(ticket => this.renderTicketCard(ticket)).join('')}
            </div>
        `;
    },

    renderTicketCard(ticket) {
        const isSeatable = ticket.type === 'seatable';
        const title = ticket.eventTitle || 'Событие';
        const venue = ticket.venuePlace || '-';
        const eventDate = App.formatDate(ticket.eventStartsAt);

        return `
            <div class="ticket-card ${isSeatable ? 'ticket-seatable' : 'ticket-regular'}">
                <div class="ticket-header">
                    <h3>${App.escapeHtml(title)}</h3>
                    <span class="badge ${isSeatable ? 'badge-manager' : 'badge-customer'}">
                        ${isSeatable ? 'С местом' : 'Свободный вход'}
                    </span>
                </div>
                <div class="ticket-details">
                    <p>${App.escapeHtml(venue)}</p>
                    <p>${eventDate}</p>
                    ${isSeatable ? `
                        <p>🎫 Место: ${ticket.seatRow}-${ticket.seatNumber}</p>
                        ${ticket.price ? `<p>💰 Цена: ${ticket.price}₽</p>` : ''}
                    ` : ''}
                    ${!isSeatable && ticket.price ? `<p>💰 Цена: ${ticket.price}₽</p>` : ''}
                </div>
                <div class="ticket-actions">
                    <button class="btn btn-sm btn-danger refund-ticket" data-ticket-id="${ticket.id}" data-ticket-type="${ticket.type}">
                        Вернуть билет
                    </button>
                </div>
            </div>
        `;
    },

    async refundTicket(ticketId, ticketType) {
        if (!confirm('Вы уверены, что хотите вернуть билет?')) return;

        try {
            if (ticketType === 'seatable') {
                await API.deleteSeatableTicket(ticketId);
            } else {
                await API.deleteTicket(ticketId);
            }
            App.showAlert('Билет успешно возвращен', 'success');
            await this.render();
        } catch (error) {
            App.showAlert('Ошибка возврата: ' + error.message, 'error');
        }
    }
};
